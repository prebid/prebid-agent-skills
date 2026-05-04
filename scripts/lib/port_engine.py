"""scripts/lib/port_engine.py — Phase D1.2 mechanical helpers for port skills.

Nine helpers wrapping deterministic mechanical operations the
``port-go2java`` / ``port-java2go`` SKILLs invoke. Prose-driven SKILL
bodies walk the 46 port-translation rules; this engine provides the
small bag of structurally-mechanical transformations that don't fit
cleanly into prose (byte-copy, name normalization, alias-graph
inversion, IAB data-table translation, alphabetical insert into
``bidders.go`` / ``adapter_builders.go``, prefix-uniqueness pre-check,
``gofmt`` post-process, R5 at port time, schema-validated port-report
emit).

Public API
----------

- ``byte_copy(source_path, dest_path) -> bool``
- ``normalize_bidder_name(go_name, *, target_lang='java', allow_list=None) -> str``
- ``alias_graph_invert(parent_spec, alias_specs, *, direction) -> Dict[str, dict]``
- ``iab_table_translate(direction, source_artifact) -> Union[str, Dict[str, Any]]``
- ``r5_check_at_port_time(source_spec, dest_spec) -> R5Result``
- ``port_report_emit(report_dict, path, *, schema_path=None) -> None``
- ``alphabetical_insert(file_path, marker_pattern, insert_line, *, language='go') -> None``
- ``prefix_uniqueness_check(target_lang, bidder_name, *, existing_names=None) -> Tuple[bool, List[str]]``
- ``gofmt_post_process(file_paths) -> Tuple[bool, str]``

Each helper has a corresponding test class in
``scripts/tests/test_port_engine.py``. Helpers that consume external
state (filesystem, subprocess, upstream APIs) accept dependency-injection
hooks so the tests stay deterministic.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

try:
    import yaml  # PyYAML
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

try:
    import jsonschema  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    jsonschema = None  # type: ignore[assignment]

from scripts.lib import r5_check as _r5_lib
from scripts.lib.r5_check import R5Result


# ---------------------------------------------------------------------------
# Repo-relative paths used by helpers that read static state.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PORT_REPORT_SCHEMA = (
    _REPO_ROOT / "prebid-server-go" / "read" / "skills" / "shared" / "port-report.schema.json"
)
_DEFAULT_BIDDER_TABLE = (
    _REPO_ROOT / "prebid-server-go" / "read" / "skills" / "shared" / "bidder-constant-table.yaml"
)


# ---------------------------------------------------------------------------
# Helper 1 — byte_copy (Rule 38)
# ---------------------------------------------------------------------------


def byte_copy(source_path: Union[str, Path], dest_path: Union[str, Path]) -> bool:
    """Copy bytes verbatim from ``source_path`` to ``dest_path``; verify SHA-256.

    Rule 38 contract: bidder-params JSON (and other byte-fidelity files)
    must be byte-identical between Go and Java. The destination's parent
    directory is created if missing.

    Returns ``True`` iff the SHA-256 of the read source equals the SHA-256
    of the written destination AND the byte counts match. Raises ``OSError``
    on I/O failure.
    """
    src = Path(source_path)
    dst = Path(dest_path)
    src_bytes = src.read_bytes()
    src_sha = hashlib.sha256(src_bytes).hexdigest()
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src_bytes)
    dst_bytes = dst.read_bytes()
    dst_sha = hashlib.sha256(dst_bytes).hexdigest()
    return src_sha == dst_sha and len(src_bytes) == len(dst_bytes)


# ---------------------------------------------------------------------------
# Helper 2 — normalize_bidder_name (Rule 46)
# ---------------------------------------------------------------------------

# Default allow-list per ADR-005 Rule 46 ("Excluded cases"). Holds Go→Java
# YAML-name overrides where the lowercase formula misfires (rebrands,
# brand-acronym preservation). Digit-leading bidders pass through the
# default formula unchanged. D1.3 will populate
# `bidder-constant-table.yaml` as the richer authoritative source; this
# small seed is what D1.2 ships so the helper is callable from D2 day one.
DEFAULT_NAME_ALLOW_LIST: Dict[str, str] = {
    # Cross-language rebrands / explicit overrides.
    "cadent_aperture_mx": "emxdigital",
}


def normalize_bidder_name(
    go_name: str,
    *,
    target_lang: str = "java",
    allow_list: Optional[Dict[str, str]] = None,
) -> str:
    """Rule 46 mechanical formula: Go name → Java YAML name.

    Default formula (per ADR-005): ``re.sub(r"[^a-z0-9]", "", go_name.lower())``
    — lowercase + drop non-``[a-z0-9]``. The ``allow_list`` overrides the
    formula for brand-acronym preservation, rebrands, and other cases the
    ADR documents as exceptions.

    Currently only ``target_lang='java'`` is supported. The Java→Go
    inverse is not fully mechanical (the same Java lowercase form maps
    to multiple possible Go camelCase names) and requires a per-pair
    dual-spec assertion lookup (see plan §D3.1 Rule 46 inverse).

    Raises ``ValueError`` on unsupported ``target_lang``.
    """
    if target_lang != "java":
        raise ValueError(
            f"target_lang={target_lang!r} not supported; Java→Go inverse needs "
            "per-pair dual-spec assertion lookup (plan §D3.1)."
        )
    table = allow_list if allow_list is not None else DEFAULT_NAME_ALLOW_LIST
    if go_name in table:
        return table[go_name]
    return re.sub(r"[^a-z0-9]", "", go_name.lower())


# ---------------------------------------------------------------------------
# Helper 3 — alias_graph_invert (Rule 33)
# ---------------------------------------------------------------------------


# R5-strict keys per scripts/lib/r5_check.R5_STRICT_KEYS, scoped to
# bidder_info subfields that legitimately vary per-alias. The
# schema_interpretation.* keys (params.schema_interpretation.required_fields,
# combinators_used, flexible_types) are tied to the bidder-params JSON
# schema and CANNOT vary per-alias — the alias inherits the parent's
# bidder-params identity by reference. They are intentionally excluded.
_R5_ALIASABLE_KEYS: Tuple[str, ...] = (
    "capabilities",
    "endpoint",
    "geoscope",
    "gvl_vendor_id",
    "endpoint_compression",
    "modifying_vast_xml_allowed",
    "maintainer",
)


def alias_graph_invert(
    parent_spec: Dict[str, Any],
    alias_specs: List[Dict[str, Any]],
    *,
    direction: str,
) -> Dict[str, Dict[str, Any]]:
    """Rule 33 alias-graph inversion.

    Java parent's ``aliases:`` block ↔ Go child's ``aliasOf:`` field.
    Same logical relationship, opposite encoding. ``direction`` selects
    which side is being constructed:

    - ``'go-to-java'``: input is a Go parent + N Go alias specs (each
      with own ``static/bidder-info/{alias}.yaml`` and ``aliasOf: parent``);
      output is the per-parent Java YAML's ``aliases:`` block content
      (mapping ``{alias_name: {bidder-info-overrides}}``).
    - ``'java-to-go'``: input is a Java parent spec carrying an
      ``aliases:`` block; output is per-alias Go YAMLs (mapping
      ``{alias_name: {full bidder-info yaml with aliasOf parent}}``).

    Returns a dict keyed by alias name with the inverted encoding. The
    returned values are dicts ready to be serialized as YAML by the
    caller; this helper does NOT write files.

    Raises ``ValueError`` on unsupported ``direction``.
    """
    if direction == "go-to-java":
        # Build the Java aliases block: {alias_name: per-alias overrides}.
        out: Dict[str, Dict[str, Any]] = {}
        for alias in alias_specs:
            alias_name = alias.get("meta", {}).get("bidder_name")
            if not alias_name:
                continue
            bi = alias.get("bidder_info", {}) or {}
            entry: Dict[str, Any] = {}
            # Forward keys from the alias's bidder_info that diverge from the
            # parent's. R5-strict alias-eligible subset (see _R5_ALIASABLE_KEYS).
            parent_bi = parent_spec.get("bidder_info", {}) or {}
            for k, v in bi.items():
                if k in _R5_ALIASABLE_KEYS:
                    if v != parent_bi.get(k):
                        entry[k] = v
            out[alias_name] = entry
        return out
    if direction == "java-to-go":
        # Java parent's `aliases:` block → per-alias Go yamls (alias has its
        # own static/bidder-info/{alias}.yaml with `aliasOf: parent`).
        parent_name = parent_spec.get("meta", {}).get("bidder_name")
        if not parent_name:
            raise ValueError("java-to-go inversion requires parent_spec.meta.bidder_name")
        java_aliases = parent_spec.get("aliases", {}) or {}
        out = {}
        for alias_name, overrides in java_aliases.items():
            # Each Go alias YAML carries `aliasOf: parent` plus the parent's
            # bidder-info merged with the alias's overrides.
            parent_bi = parent_spec.get("bidder_info", {}) or {}
            merged: Dict[str, Any] = {**parent_bi, **(overrides or {})}
            merged["aliasOf"] = parent_name
            out[alias_name] = merged
        return out
    raise ValueError(f"direction={direction!r} not supported; expected 'go-to-java' or 'java-to-go'")


# ---------------------------------------------------------------------------
# Helper 4 — iab_table_translate (Rule 42)
# ---------------------------------------------------------------------------


def iab_table_translate(
    direction: str,
    source_artifact: Union[str, Dict[str, Any]],
    *,
    package_name: str = "iab",
    var_name: str = "iabCategories",
) -> Union[str, Dict[str, Any]]:
    """Rule 42 IAB-cat storage translation.

    Go side stores IAB categories as a Go data file
    (``adapters/{bidder}/iab_categories.go``) with a static-init map
    plus a ``delivery_mechanism`` constant. Java side inlines the
    mapping under ``adapters.{bidder}.iab-cat-mapping`` in the YAML
    bidder-config.

    ``direction`` selects:

    - ``'go-to-java'``: input is the Go file source as a string; output
      is the Java-side dict ready for YAML emission under
      ``adapters.{bidder}.iab-cat-mapping``. ``package_name`` and
      ``var_name`` arguments are ignored (Go-only metadata; Java has no
      analog).
    - ``'java-to-go'``: input is the Java YAML mapping dict; output is
      the Go data-file source as a string. ``package_name`` and
      ``var_name`` control the Go file's ``package`` declaration and
      ``var`` name; defaults are the upstream-canonical ``iab`` and
      ``iabCategories``.

    The Go-data-file extraction parses the ``map[string]string`` literal
    after a ``var <name> = map[string]string{`` opener. The brace counter
    skips Go string literals (so ``"}"`` inside a value does not close
    the map) and the entry regex tolerates ``\\"``-escaped quotes inside
    string values. Round-trip preserves the mapping; package/var names
    are NOT preserved through go-to-java→java-to-go because the Java
    YAML has no place to record them — pass them explicitly to
    ``java-to-go`` if a non-default file shape is needed.
    """
    if direction == "go-to-java":
        if not isinstance(source_artifact, str):
            raise TypeError("go-to-java expects Go source string")
        return _parse_go_iab_table(source_artifact)
    if direction == "java-to-go":
        if not isinstance(source_artifact, dict):
            raise TypeError("java-to-go expects Java YAML dict")
        return _emit_go_iab_table(source_artifact, package_name=package_name, var_name=var_name)
    raise ValueError(f"direction={direction!r} not supported; expected 'go-to-java' or 'java-to-go'")


_IAB_GO_OPENER_RE = re.compile(
    r"var\s+(\w*[Ii]ab\w*)\s*=\s*map\[string\]string\s*\{",
    re.MULTILINE,
)


def _parse_go_iab_table(source: str) -> Dict[str, str]:
    """Extract the Go ``map[string]string`` literal as a Python dict.

    Brace counter is string-literal-aware: ``"}"`` and ``"{"`` inside Go
    double-quoted strings do not affect nesting. Backslash escapes
    (e.g., ``\\"``, ``\\\\``) are honored so that ``"a\\"b"`` parses as
    a single string literal containing ``a"b``.
    """
    m = _IAB_GO_OPENER_RE.search(source)
    if not m:
        raise ValueError("could not find Go IAB map opener (`var <name> = map[string]string{`)")
    body_start = m.end()
    depth = 1
    end = None
    in_string = False
    escaped = False
    for idx in range(body_start, len(source)):
        ch = source[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = idx
                break
    if end is None:
        raise ValueError("unterminated Go map literal")
    body = source[body_start:end]
    return _parse_go_map_entries(body)


def _parse_go_map_entries(body: str) -> Dict[str, str]:
    """Tokenize ``"key": "value",`` pairs out of a Go map body.

    Tolerates whitespace and embedded backslash-escaped quotes in either
    key or value. Ignores trailing commas and inter-entry whitespace.
    """
    out: Dict[str, str] = {}
    pos = 0
    n = len(body)
    while pos < n:
        # Skip whitespace and commas.
        while pos < n and body[pos] in " \t\r\n,":
            pos += 1
        if pos >= n:
            break
        # Expect a key-string opening quote.
        if body[pos] != '"':
            # Unexpected token — advance one char and continue (best-effort).
            pos += 1
            continue
        key, pos = _consume_go_string(body, pos)
        # Skip whitespace + ':'.
        while pos < n and body[pos] in " \t\r\n":
            pos += 1
        if pos >= n or body[pos] != ":":
            raise ValueError(f"expected ':' after key at position {pos}")
        pos += 1
        while pos < n and body[pos] in " \t\r\n":
            pos += 1
        if pos >= n or body[pos] != '"':
            raise ValueError(f"expected value-string at position {pos}")
        value, pos = _consume_go_string(body, pos)
        out[key] = value
    return out


def _consume_go_string(body: str, pos: int) -> Tuple[str, int]:
    """Consume a Go double-quoted string starting at ``body[pos] == '\"'``.

    Returns the unescaped value and the position immediately after the
    closing quote. Honors ``\\"``, ``\\\\``, ``\\n``, ``\\t`` escape
    sequences. Raises ``ValueError`` on an unterminated string.
    """
    assert body[pos] == '"'
    pos += 1
    chars: List[str] = []
    n = len(body)
    while pos < n:
        ch = body[pos]
        if ch == "\\" and pos + 1 < n:
            nxt = body[pos + 1]
            chars.append({"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}.get(nxt, nxt))
            pos += 2
            continue
        if ch == '"':
            return "".join(chars), pos + 1
        chars.append(ch)
        pos += 1
    raise ValueError("unterminated Go string literal")


def _emit_go_iab_table(
    mapping: Dict[str, Any],
    *,
    package_name: str = "iab",
    var_name: str = "iabCategories",
) -> str:
    """Emit the Go ``map[string]string`` literal source from a Python dict.

    ``package_name`` and ``var_name`` control the file's ``package``
    line and ``var`` identifier; defaults are upstream-canonical
    (``iab`` / ``iabCategories``).
    """
    lines = [f"package {package_name}", "", f"var {var_name} = map[string]string{{"]
    for k in sorted(mapping.keys()):
        v = mapping[k]
        lines.append(f'\t{json.dumps(k)}: {json.dumps(str(v))},')
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helper 5 — r5_check_at_port_time
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _DictSpecView:
    """Minimal SpecView shim for in-memory port-time specs.

    Implements the ``SpecView`` protocol over a plain dict, supporting
    dotted-path ``get(...)`` lookups the way the harness's ``Spec``
    dataclass does.
    """

    bidder: str
    raw: Dict[str, Any]

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.raw
        for part in dotted.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node


def r5_check_at_port_time(
    source_spec: Dict[str, Any],
    dest_spec: Dict[str, Any],
) -> R5Result:
    """Run R5-strict cross-language equivalence at port emit time.

    Wraps ``scripts.lib.r5_check.compare_pair`` with port-time semantics:
    no ``cross-language-pairs/{bidder}.dual-spec-assertions.yaml`` is
    consulted (the pair file may not exist for new bidders). Both inputs
    are plain dicts (typically the source spec the SKILL was handed and
    the freshly-emitted destination spec).

    The helper infers the source/destination language from each spec's
    ``source_language`` field; the bidder name comes from
    ``meta.bidder_name`` (else falls back to ``unknown``).
    """
    src_view = _DictSpecView(
        bidder=(source_spec.get("meta") or {}).get("bidder_name") or "unknown",
        raw=source_spec,
    )
    dst_view = _DictSpecView(
        bidder=(dest_spec.get("meta") or {}).get("bidder_name") or src_view.bidder,
        raw=dest_spec,
    )
    src_lang = source_spec.get("source_language")
    dst_lang = dest_spec.get("source_language")
    # compare_pair takes (go_view, java_view); route accordingly.
    if src_lang == "go" and dst_lang == "java":
        return _r5_lib.compare_pair(src_view, dst_view)
    if src_lang == "java" and dst_lang == "go":
        return _r5_lib.compare_pair(dst_view, src_view)
    raise ValueError(
        f"unsupported language pair: source_language={src_lang!r}, dest_language={dst_lang!r}"
    )


# ---------------------------------------------------------------------------
# Helper 6 — port_report_emit
# ---------------------------------------------------------------------------


def port_report_emit(
    report_dict: Dict[str, Any],
    path: Union[str, Path],
    *,
    schema_path: Optional[Union[str, Path]] = None,
) -> None:
    """Schema-validate and write a port report.

    Validates ``report_dict`` against ``port-report.schema.json``
    (default location: the repo's ``prebid-server-go/read/skills/shared/``).
    Raises ``jsonschema.ValidationError`` if invalid; the caller's
    port-report dict must be fixed before emit. Otherwise writes the
    report as JSON (sorted keys, 2-space indent, trailing newline) to
    ``path``; parent directory is created if missing.

    Raises ``RuntimeError`` if ``jsonschema`` is not installed.
    """
    if jsonschema is None:
        raise RuntimeError("jsonschema is required for port_report_emit (pip install jsonschema)")
    schema_file = Path(schema_path) if schema_path else _DEFAULT_PORT_REPORT_SCHEMA
    with open(schema_file, "r", encoding="utf-8") as fh:
        schema = json.load(fh)
    jsonschema.validate(instance=report_dict, schema=schema)
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report_dict, fh, sort_keys=True, indent=2)
        fh.write("\n")


# ---------------------------------------------------------------------------
# Helper 7 — alphabetical_insert
# ---------------------------------------------------------------------------


def alphabetical_insert(
    file_path: Union[str, Path],
    marker_pattern: str,
    insert_line: str,
    *,
    language: str = "go",
) -> None:
    """Insert ``insert_line`` into ``file_path`` at the alphabetical position.

    Used by the port skills to add entries to ``openrtb_ext/bidders.go``
    (constant declarations + ``coreBidderNames`` slice) and
    ``exchange/adapter_builders.go`` (import + map entry) without
    disturbing the rest of the file.

    ``marker_pattern`` is a regex that identifies lines that belong to
    a target block. The helper:

    1. Identifies all contiguous runs of matching lines. A run is
       broken by ANY non-matching line (closing brace, blank line, the
       opener of a sibling block). This is how openrtb_ext/bidders.go's
       two ``const ( ... )`` blocks (10 Reserved* + 261 Bidder*) are
       discriminated by the same marker pattern.
    2. Picks the longest run as the target block. Ties raise
       ``ValueError`` — the caller must use a more specific pattern.
    3. Inserts ``insert_line`` at the correct ``(s.lower(), s)``
       lexicographic position via ``bisect_left`` — the helper does NOT
       re-sort the existing block. Upstream HEAD has ~20 of 261
       entries that are locally out-of-order under
       ``(s.lower(), s)``; re-sorting would create unrelated diffs in
       the port PR. Local violations are preserved; the new entry
       lands at canonical position.

    Sort key: ``(s.lower(), s)`` — case-insensitive primary,
    case-sensitive ASCII tiebreak. Closest match to upstream order
    (verified against ``openrtb_ext/bidders.go`` HEAD; plain ASCII has
    136 mismatches versus 20 for ``(lower, s)``).

    ``language`` is recorded for error messages but does not currently
    change behavior — both Go and Java upstream sort with the same
    primary key.

    The function is idempotent: inserting a line that already exists
    in the target block is a no-op (no duplicate).

    Raises ``ValueError`` if ``marker_pattern`` matches no lines, or
    if multiple matched runs tie for longest (caller must disambiguate
    via a more specific pattern).
    """
    import bisect

    fp = Path(file_path)
    text = fp.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    pattern = re.compile(marker_pattern)

    runs: List[List[int]] = []
    current: List[int] = []
    for i, ln in enumerate(lines):
        if pattern.search(ln):
            current.append(i)
        else:
            if current:
                runs.append(current)
                current = []
    if current:
        runs.append(current)
    if not runs:
        raise ValueError(
            f"marker_pattern={marker_pattern!r} matched no lines in {fp} "
            f"(language={language})"
        )
    longest_size = max(len(r) for r in runs)
    longest_runs = [r for r in runs if len(r) == longest_size]
    if len(longest_runs) > 1:
        raise ValueError(
            f"marker_pattern={marker_pattern!r} produced {len(longest_runs)} "
            f"contiguous runs of length {longest_size} (tie). Use a more "
            f"specific pattern to disambiguate (file: {fp})."
        )
    target_run = longest_runs[0]
    block_start = target_run[0]
    block_end = target_run[-1] + 1
    block_lines = lines[block_start:block_end]

    sort_key: Callable[[str], Tuple[str, str]] = lambda s: (s.lower(), s)
    canonical_insert = insert_line if insert_line.endswith("\n") else insert_line + "\n"
    if canonical_insert in block_lines:
        return  # idempotent: already present

    keys = [sort_key(ln) for ln in block_lines]
    pos = bisect.bisect_left(keys, sort_key(canonical_insert))
    new_block = block_lines[:pos] + [canonical_insert] + block_lines[pos:]
    new_lines = lines[:block_start] + new_block + lines[block_end:]
    fp.write_text("".join(new_lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Helper 8 — prefix_uniqueness_check
# ---------------------------------------------------------------------------


def prefix_uniqueness_check(
    target_lang: str,
    bidder_name: str,
    *,
    existing_names: Optional[List[str]] = None,
    table_path: Optional[Union[str, Path]] = None,
) -> Tuple[bool, List[str]]:
    """Pre-emit guard against ``TestBidderUniquenessGatekeeping`` (Go).

    Upstream Go enforces that no two bidder names share the same first
    six lowercase letters (``coreBidderNames`` slice in
    ``openrtb_ext/bidders.go`` + a unit-test gatekeeper). The port skill
    runs this BEFORE emitting Go artifacts: if the first 6 letters of
    ``bidder_name.lower()`` collide with any existing name in the
    upstream slice, abort with operator notification.

    ``existing_names`` (list of bidder names) is the dependency-injection
    hook tests use. When omitted, the helper attempts to load the
    canonical table at
    ``prebid-server-go/read/skills/shared/bidder-constant-table.yaml``
    (D1.3 deliverable). If the table is also missing, the helper returns
    ``(True, [])`` with no collision detection — callers should treat
    this as best-effort and notify operators.

    ``target_lang='java'`` returns ``(True, [])`` immediately — Java's
    upstream has no equivalent first-6-letter gatekeeper.

    Returns ``(ok, colliding_existing)`` where ``ok`` is True when
    there is no collision, and ``colliding_existing`` lists the existing
    names whose 6-letter prefix collides.
    """
    if target_lang == "java":
        return True, []
    if target_lang != "go":
        raise ValueError(f"target_lang={target_lang!r} not supported")
    if existing_names is None:
        existing_names = _load_bidder_table(table_path)
        if existing_names is None:
            return True, []  # best-effort fallback
    prefix = (bidder_name or "").lower()[:6]
    if not prefix:
        return True, []
    colliding = [
        n for n in existing_names
        if n != bidder_name and n.lower()[:6] == prefix
    ]
    return (len(colliding) == 0), colliding


def _load_bidder_table(table_path: Optional[Union[str, Path]]) -> Optional[List[str]]:
    """Load the bidder-constant-table.yaml (D1.3 deliverable). Returns None if absent."""
    if yaml is None:
        return None
    fp = Path(table_path) if table_path else _DEFAULT_BIDDER_TABLE
    if not fp.exists():
        return None
    try:
        with open(fp, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except (OSError, yaml.YAMLError):  # type: ignore[union-attr]
        return None
    # Convention: top-level `bidders:` key is the canonical list of names.
    bidders = data.get("bidders") if isinstance(data, dict) else None
    if isinstance(bidders, list):
        return [str(b) for b in bidders]
    if isinstance(bidders, dict):
        return list(bidders.keys())
    return None


# ---------------------------------------------------------------------------
# Helper 9 — gofmt_post_process
# ---------------------------------------------------------------------------


def gofmt_post_process(
    file_paths: List[Union[str, Path]],
    *,
    runner: Optional[Callable[[List[str]], Tuple[int, str, str]]] = None,
) -> Tuple[bool, str]:
    """Run ``gofmt -s -w <file_paths>`` over emitted Go files.

    Upstream Go CI requires ``gofmt -s`` clean output. The port skill's
    Step 5 emission is best-effort idiomatic; this post-process gate
    pins the output to the canonical formatting before the operator
    inspects it.

    ``runner`` is a dependency-injection hook that takes an argv list
    and returns ``(returncode, stdout, stderr)``. When omitted, the
    helper invokes ``subprocess.run`` directly.

    Returns ``(ok, stderr_or_message)`` where ``ok`` is ``True`` iff
    ``gofmt`` exited 0 and produced no diff. On non-zero exit, ``ok`` is
    ``False`` and the second element is the stderr (or a message
    indicating ``gofmt`` is not on PATH).
    """
    if not file_paths:
        return True, ""
    argv = ["gofmt", "-s", "-w"] + [str(p) for p in file_paths]
    if runner is not None:
        rc, _, stderr = runner(argv)
        return rc == 0, stderr
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False, "gofmt not found on PATH"
    return result.returncode == 0, result.stderr
