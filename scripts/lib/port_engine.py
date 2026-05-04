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
            # Java-side per-alias overrides typically: endpoint, geoscope,
            # capabilities differences. Include keys from the alias's
            # bidder_info that diverge from the parent's.
            parent_bi = parent_spec.get("bidder_info", {}) or {}
            for k, v in bi.items():
                if k in {"capabilities", "endpoint", "geoscope", "gvl_vendor_id",
                         "endpoint_compression", "modifying_vast_xml_allowed"}:
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
      ``adapters.{bidder}.iab-cat-mapping``.
    - ``'java-to-go'``: input is the Java YAML mapping dict; output is
      the Go data-file source as a string.

    The Go-data-file extraction parses the ``map[string]string`` literal
    after a ``var iabCategories = map[string]string{`` opener; the helper
    is robust to whitespace but requires the upstream-conventional layout.
    """
    if direction == "go-to-java":
        if not isinstance(source_artifact, str):
            raise TypeError("go-to-java expects Go source string")
        return _parse_go_iab_table(source_artifact)
    if direction == "java-to-go":
        if not isinstance(source_artifact, dict):
            raise TypeError("java-to-go expects Java YAML dict")
        return _emit_go_iab_table(source_artifact)
    raise ValueError(f"direction={direction!r} not supported; expected 'go-to-java' or 'java-to-go'")


_IAB_GO_OPENER_RE = re.compile(
    r"var\s+\w*[Ii]ab\w*\s*=\s*map\[string\]string\s*\{",
    re.MULTILINE,
)
_IAB_GO_ENTRY_RE = re.compile(
    r'"([^"]*)"\s*:\s*"([^"]*)"\s*,?',
)


def _parse_go_iab_table(source: str) -> Dict[str, str]:
    """Extract the Go ``map[string]string`` literal as a Python dict."""
    m = _IAB_GO_OPENER_RE.search(source)
    if not m:
        raise ValueError("could not find Go IAB map opener (`var <name> = map[string]string{`)")
    body_start = m.end()
    # Find matching closing brace at same nesting level.
    depth = 1
    end = None
    for idx in range(body_start, len(source)):
        ch = source[idx]
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
    out: Dict[str, str] = {}
    for em in _IAB_GO_ENTRY_RE.finditer(body):
        out[em.group(1)] = em.group(2)
    return out


def _emit_go_iab_table(mapping: Dict[str, Any]) -> str:
    """Emit the Go ``map[string]string`` literal source from a Python dict."""
    lines = ["package iab", "", "var iabCategories = map[string]string{"]
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

    ``marker_pattern`` is a regex that identifies a line WITHIN the
    block where insertion should happen. The helper finds the contiguous
    run of matching lines, sorts the run + ``insert_line`` together
    case-insensitively (ties broken by case-sensitive ASCII so
    ``BidderAaA`` < ``BidderAaa``), and rewrites the file with the new
    line at the correct position.

    ``language`` is recorded for error messages but does not currently
    change behavior — both Go and Java upstream sort alphabetically with
    the same case-insensitive primary key.

    The function is idempotent: inserting a line that already exists in
    the block is a no-op (no duplicate).

    Raises ``ValueError`` if ``marker_pattern`` matches no lines.
    """
    fp = Path(file_path)
    text = fp.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    pattern = re.compile(marker_pattern)
    matched_idxs = [i for i, ln in enumerate(lines) if pattern.search(ln)]
    if not matched_idxs:
        raise ValueError(
            f"marker_pattern={marker_pattern!r} matched no lines in {fp} "
            f"(language={language})"
        )
    # The block is the contiguous range covering all matches (including
    # any non-matching lines between matches — typical when the block
    # has a few annotated entries).
    block_start = matched_idxs[0]
    block_end = matched_idxs[-1] + 1
    block_lines = lines[block_start:block_end]
    # Sort key: case-insensitive primary, case-sensitive secondary.
    sort_key: Callable[[str], Tuple[str, str]] = lambda s: (s.lower(), s)
    canonical_insert = insert_line if insert_line.endswith("\n") else insert_line + "\n"
    if canonical_insert in block_lines:
        return  # idempotent: already present
    new_block = sorted(block_lines + [canonical_insert], key=sort_key)
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
