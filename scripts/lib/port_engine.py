"""scripts/lib/port_engine.py — Phase D1.2 + D4.3 mechanical helpers for port skills.

Mechanical helpers wrapping deterministic operations the
``port-go2java`` / ``port-java2go`` SKILLs invoke. Prose-driven SKILL
bodies walk the 46 port-translation rules; this engine provides the
small bag of structurally-mechanical transformations that don't fit
cleanly into prose (byte-copy, name normalization, alias-graph
inversion, IAB data-table translation, alphabetical insert into
``bidders.go`` / ``adapter_builders.go``, prefix-uniqueness pre-check,
``gofmt`` post-process, R5 at port time, schema-validated port-report
emit, pre-submit checkstyle dry-run, Java→Go ``imp.ext`` shape
transform for Rule 36 inverse fixture authoring, and Go-adapter
MakeRequests mutation simulation for D3.8 F-new-16 fixture body
authoring).

Public API
----------

- ``byte_copy(source_path, dest_path) -> bool``
- ``materialize_params(ref, blobs_dir=None, checkout=None) -> bytes``
- ``normalize_bidder_name(go_name, *, target_lang='java', allow_list=None) -> str``
- ``alias_graph_invert(parent_spec, alias_specs, *, direction) -> Dict[str, dict]``
- ``iab_table_translate(direction, source_artifact) -> Union[str, Dict[str, Any]]``
- ``r5_check_at_port_time(source_spec, dest_spec) -> R5Result``
- ``port_report_emit(report_dict, path, *, schema_path=None) -> None``
- ``alphabetical_insert(file_path, marker_pattern, insert_line, *, language='go') -> None``
- ``prefix_uniqueness_check(target_lang, bidder_name, *, existing_names=None) -> Tuple[bool, List[str]]``
- ``lookup_forms(yaml_name, *, table_path=None, table_data=None) -> Dict[str, str]``
- ``gofmt_post_process(file_paths) -> Tuple[bool, str]``
- ``mvn_checkstyle_dry_run(target_clone, *, pom_file='extra/pom.xml', runner=None) -> Tuple[bool, List[Dict]]``
- ``imp_ext_shape_transform_java_to_go(fixture_dict, java_bidder_name) -> Dict[str, Any]``
- ``exemplary_fixture_assemble_java_to_go(*, java_auction_request, java_auction_response, java_bid_request, java_bid_response, java_bidder_name, expected_request_body_simulator=None, default_bid_type='banner', test_endpoint=TEST_ENDPOINT, inject_empty_user_if_missing=False) -> Dict[str, Any]``
- ``simulate_makerequests_mutations(bid_request, mutations) -> Dict[str, Any]``

Each helper has a corresponding test class in
``scripts/tests/test_port_engine.py``. Helpers that consume external
state (filesystem, subprocess, upstream APIs) accept dependency-injection
hooks so the tests stay deterministic.
"""

from __future__ import annotations

import copy
import dataclasses
import functools
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
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
# Helper 1b — materialize_params (Rule 38, ref-based)
# ---------------------------------------------------------------------------

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


def materialize_params(
    ref: Dict[str, Any],
    blobs_dir: Optional[Union[str, Path]] = None,
    checkout: Optional[Union[str, Path]] = None,
    *,
    runner: Optional[Callable[[List[str], Path], Tuple[int, bytes]]] = None,
) -> bytes:
    """Return the exact bidder-params bytes a ``bidder_params_ref`` names.

    Rule 38 in its ref-based form. The Adapter Specification no longer
    inlines the params text; it carries a content-addressed reference::

        bidder_params_ref:
          path: static/bidder-params/kobler.json   # upstream-relative
          resolved_commit: d7f8515b86258688304b0d9b6668c6a0e258bc9e
          sha256: 125fef34c3c83c63342e94c74b7ac9f98d026ada4e6a0112157387d787c7b685
          bytes: 431

    The port carries that block forward unchanged and calls this helper to
    obtain the bytes it must write at the destination path.

    Why this is verifiable where the inline copy was not: ``sha256`` and
    ``bytes`` describe bytes the reader did *not* author. The superseded
    contract hashed ``bidder_params_json`` — the reader's own output — so a
    lossy transcription produced a self-consistent hash and cleared every
    check. ``bytes`` is a second, independent witness: a byte count cannot
    be back-derived from text the reader wrote.

    Resolution order
    ----------------
    1. ``blobs_dir/<ref.sha256>`` — the content-addressed blob store at
       ``prebid-server-{go,java}/read/test-fixtures/blobs/``. Offline and
       self-naming: a blob is filed under the digest of its own content.
    2. ``checkout`` — a local upstream clone. Read is pinned to
       ``ref.resolved_commit`` via ``git cat-file blob <commit>:<path>``
       so a clone fetched past the spec's commit still yields the bytes
       the ref attests to. If the pinned read fails (not a git work tree,
       shallow clone missing the commit), the helper falls back to
       ``checkout/<ref.path>`` on disk — verification below still governs,
       so a drifted working tree raises rather than returning wrong bytes.

    Parameters
    ----------
    ref : dict
        The spec's ``bidder_params_ref`` block. ``path``, ``sha256`` and
        ``bytes`` are always required; ``resolved_commit`` is required only
        when resolution reaches the ``checkout`` branch.
    blobs_dir : str | Path | None
        Blob-store directory. A directory that exists but holds no blob for
        this digest is not an error on its own — resolution falls through.
    checkout : str | Path | None
        Local upstream clone root.
    runner : callable | None
        Dependency-injection hook for the pinned git read; receives
        ``(argv, cwd)`` and returns ``(returncode, stdout_bytes)``. Must
        return raw bytes — decoding to ``str`` would defeat the contract.

    Returns
    -------
    bytes
        The verified params bytes. Never a partial or unverified read: the
        return value hashes to ``ref.sha256`` and is ``ref.bytes`` long.
        An empty return is possible only when the ref itself attests to
        zero bytes.

    Raises
    ------
    ValueError
        If ``ref`` is malformed; if no source resolves (a missing blob and
        no usable checkout is an error, never an empty return); or if the
        resolved bytes fail either witness. The message names the source
        that produced the bytes so blob-store corruption is distinguishable
        from checkout drift.
    """
    path, sha256_expected, bytes_expected = _validate_params_ref(ref)

    data: Optional[bytes] = None
    source = ""
    attempts: List[str] = []

    if blobs_dir is not None:
        blob = Path(blobs_dir) / sha256_expected
        if blob.is_file():
            data = blob.read_bytes()
            source = f"blob store {blob}"
        else:
            attempts.append(f"blob store miss at {blob}")

    if data is None and checkout is not None:
        data, source, checkout_attempts = _read_params_from_checkout(
            Path(checkout), path, ref, runner
        )
        attempts.extend(checkout_attempts)

    if data is None:
        if blobs_dir is None and checkout is None:
            attempts.append("no blobs_dir and no checkout supplied")
        raise ValueError(
            f"materialize_params: cannot resolve bidder_params_ref for {path!r} "
            f"(sha256={sha256_expected}) — " + "; ".join(attempts)
        )

    sha256_actual = hashlib.sha256(data).hexdigest()
    problems: List[str] = []
    if sha256_actual != sha256_expected:
        problems.append(
            f"sha256 mismatch: ref says {sha256_expected}, bytes hash to {sha256_actual}"
        )
    if len(data) != bytes_expected:
        problems.append(
            f"byte-count mismatch: ref says {bytes_expected}, got {len(data)}"
        )
    if problems:
        raise ValueError(
            f"materialize_params: {path!r} read from {source} failed verification — "
            + "; ".join(problems)
        )
    return data


def _validate_params_ref(ref: Any) -> Tuple[str, str, int]:
    """Check the always-required keys on a ``bidder_params_ref``.

    Returns ``(path, sha256, bytes)``. Raises ``ValueError`` naming the
    offending key. ``resolved_commit`` is validated lazily by the checkout
    branch — a blob-store hit does not need it.
    """
    if not isinstance(ref, dict):
        raise ValueError(
            f"materialize_params: ref must be a bidder_params_ref mapping; got {type(ref).__name__}"
        )
    path = ref.get("path")
    if not path or not isinstance(path, str):
        raise ValueError(
            f"materialize_params: bidder_params_ref.path must be a non-empty "
            f"upstream-relative string; got {path!r}"
        )
    # The path is joined onto a checkout root, so an absolute path or a `..`
    # component would read outside the clone. Verification would still refuse
    # to return foreign bytes, but the read itself should not happen.
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(
            f"materialize_params: bidder_params_ref.path must be relative to the "
            f"upstream root with no '..' components; got {path!r}"
        )
    sha256_expected = ref.get("sha256")
    if not isinstance(sha256_expected, str) or not _SHA256_HEX_RE.match(sha256_expected):
        raise ValueError(
            f"materialize_params: bidder_params_ref.sha256 must be 64 lowercase hex "
            f"chars; got {sha256_expected!r}"
        )
    bytes_expected = ref.get("bytes")
    # bool is an int subclass; reject it so `bytes: true` cannot pass as 1.
    if isinstance(bytes_expected, bool) or not isinstance(bytes_expected, int) or bytes_expected < 0:
        raise ValueError(
            f"materialize_params: bidder_params_ref.bytes must be a non-negative "
            f"integer (the second witness; without it a sha-only check is a "
            f"single-witness check); got {bytes_expected!r}"
        )
    return path, sha256_expected, bytes_expected


def _read_params_from_checkout(
    checkout: Path,
    path: str,
    ref: Dict[str, Any],
    runner: Optional[Callable[[List[str], Path], Tuple[int, bytes]]],
) -> Tuple[Optional[bytes], str, List[str]]:
    """Read ``path`` out of ``checkout``, pinned to ``ref.resolved_commit``.

    Returns ``(data_or_None, source_label, attempt_notes)``.
    """
    commit = ref.get("resolved_commit")
    if not commit or not isinstance(commit, str):
        raise ValueError(
            f"materialize_params: resolving {path!r} from a checkout requires "
            f"bidder_params_ref.resolved_commit; got {commit!r}"
        )
    attempts: List[str] = []
    argv = ["git", "-C", str(checkout), "cat-file", "blob", f"{commit}:{path}"]
    rc, stdout = -1, b""
    if runner is not None:
        rc, stdout = runner(argv, checkout)
    else:
        try:
            result = subprocess.run(argv, capture_output=True, check=False, timeout=60)
            rc, stdout = result.returncode, result.stdout
        except FileNotFoundError:
            attempts.append("git not found on PATH")
        except subprocess.TimeoutExpired:
            attempts.append(f"git cat-file {commit}:{path} exceeded 60s")
    if rc == 0:
        return stdout, f"checkout {checkout} pinned at {commit}", attempts
    if rc != -1:
        attempts.append(f"git cat-file blob {commit}:{path} in {checkout} exited {rc}")

    # Unpinned fallback. Verification is what makes this safe: a working
    # tree that has moved past `resolved_commit` fails the sha256/bytes
    # witnesses instead of yielding the wrong bytes.
    on_disk = checkout / path
    if on_disk.is_file():
        return on_disk.read_bytes(), f"checkout working tree {on_disk} (unpinned)", attempts
    attempts.append(f"no file at {on_disk}")
    return None, "", attempts


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
    raw = _load_bidder_table_raw(table_path)
    if raw is None:
        return None
    bidders = raw.get("bidders")
    if isinstance(bidders, list):
        return [str(b) for b in bidders]
    if isinstance(bidders, dict):
        return list(bidders.keys())
    return None


def _load_bidder_table_raw(
    table_path: Optional[Union[str, Path]],
) -> Optional[Dict[str, Any]]:
    """Load the full bidder-constant-table.yaml dict (with `bidders:` mapping).

    Returns the parsed top-level dict on success, or ``None`` when the
    file is absent, PyYAML is not installed, or the file fails to parse.
    The richer return value (vs ``_load_bidder_table``) is used by the
    F-new-34 ``lookup_forms`` helper which needs to inspect each bidder
    entry's value (simple string OR mapping with ``forms:`` sub-map).

    Cached by resolved-path key (``maxsize=4``) so repeat lookups across
    a single ``port_engine`` invocation don't re-parse the 271-entry YAML.
    Call ``_load_bidder_table_raw.cache_clear()`` if the table is edited
    mid-process (test suites already isolate via fresh ``table_data=``).
    ``cache_clear`` is exposed as a passthrough to the inner cached loader.
    """
    if yaml is None:
        return None
    fp = Path(table_path) if table_path else _DEFAULT_BIDDER_TABLE
    return _load_bidder_table_raw_cached(fp.resolve())


@functools.lru_cache(maxsize=4)
def _load_bidder_table_raw_cached(
    resolved_path: Path,
) -> Optional[Dict[str, Any]]:
    """Inner cached loader keyed by ``resolved_path`` (hashable, comparable)."""
    if not resolved_path.exists():
        return None
    try:
        with open(resolved_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}  # type: ignore[union-attr]
    except (OSError, yaml.YAMLError):  # type: ignore[union-attr]
        return None
    return data if isinstance(data, dict) else None


# Expose ``cache_clear`` on the public passthrough so the docstring's
# advice ``_load_bidder_table_raw.cache_clear()`` actually works (without
# this assignment the LRU lives only on the inner ``_load_bidder_table_raw_cached``
# function and the public-name call would raise AttributeError).
_load_bidder_table_raw.cache_clear = _load_bidder_table_raw_cached.cache_clear  # type: ignore[attr-defined]
_load_bidder_table_raw.cache_info = _load_bidder_table_raw_cached.cache_info  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Helper 8b — lookup_forms (Rule 46 / F-new-34)
# ---------------------------------------------------------------------------


# Form-keys carried by `ctx.naming_form_resolution` (passed to bidder.go.j2
# and consumed by the multi-form-aware naming sites). Ordering matters
# only for diagnostic / canonical-dict-equality purposes; the renderer
# reads by key.
NAMING_FORM_KEYS: Tuple[str, ...] = (
    "go_yaml_name",
    "go_package_name",
    "go_constant_root",
    "java_yaml_name",
    "java_class_root",
    "java_package",
)


def _mechanical_forms(yaml_name: str, go_constant_root: str) -> Dict[str, str]:
    """Default mechanical-derivation formula for the six naming forms.

    Used when a bidder's `bidder-constant-table.yaml` entry is the
    simple-string form (no explicit `forms:` sub-map). The Rule 46
    formula (`lowercase + drop non-[a-z0-9]`) supplies the Java-side
    lowercase yaml/package; Go-side defaults pass `yaml_name` through;
    the Java class root defaults to the Go constant root (mechanical
    PascalCase pairs).
    """
    java_form = re.sub(r"[^a-z0-9]", "", (yaml_name or "").lower())
    return {
        "go_yaml_name": yaml_name,
        "go_package_name": yaml_name,
        "go_constant_root": go_constant_root,
        "java_yaml_name": java_form,
        "java_class_root": go_constant_root,
        "java_package": java_form,
    }


def lookup_forms(
    yaml_name: str,
    *,
    table_path: Optional[Union[str, Path]] = None,
    table_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Resolve the per-aspect naming forms for ``yaml_name`` (F-new-34).

    Returns a dict with the six naming-form keys per :data:`NAMING_FORM_KEYS`
    suitable for assignment into ``ctx.naming_form_resolution`` consumed
    by ``bidder.go.j2``. The helper is the canonical entry point for the
    port-java2go renderer's Rule 46 multi-form-aware naming sites.

    Resolution order:

    1. If ``table_data`` is provided, inspect its ``bidders`` sub-map for
       ``yaml_name``. Otherwise load
       ``prebid-server-go/read/skills/shared/bidder-constant-table.yaml``
       (or ``table_path`` override).
    2. If the entry's value is a mapping with a ``forms:`` sub-map, the
       sub-map IS the result — missing keys default to the mechanical
       formula so partial sub-maps remain valid.
    3. If the entry's value is a simple string (mechanical case), or the
       entry is absent altogether, derive all six forms mechanically:
       ``yaml_name`` passes through for Go forms; ``go_constant_root``
       takes the simple-string value (or a PascalCase first-letter-upper
       of ``yaml_name`` if the entry is absent); Java forms apply the
       Rule 46 lowercase formula.

    The helper is dependency-injection-friendly: ``table_data`` short-circuits
    the YAML load entirely (used by tests + by callers that already hold the
    parsed dict). The return is always a fresh dict; mutations by callers
    do not affect subsequent calls.
    """
    data = table_data if table_data is not None else _load_bidder_table_raw(table_path)
    bidders = (data or {}).get("bidders") if isinstance(data, dict) else None

    entry: Any = None
    if isinstance(bidders, dict):
        entry = bidders.get(yaml_name)

    # Determine the Go constant root + any explicit forms sub-map.
    explicit_forms: Dict[str, str] = {}
    if isinstance(entry, dict):
        # Mapping-form entry: look for `go_constant_root` + `forms:`.
        go_constant_root = str(entry.get("go_constant_root") or "")
        raw_forms = entry.get("forms")
        if isinstance(raw_forms, dict):
            for k in NAMING_FORM_KEYS:
                v = raw_forms.get(k)
                if isinstance(v, str) and v:
                    explicit_forms[k] = v
        # If go_constant_root only lives in `forms:` sub-map, recover it.
        if not go_constant_root:
            go_constant_root = explicit_forms.get("go_constant_root", "")
    elif isinstance(entry, str) and entry:
        go_constant_root = entry
    else:
        # Entry absent (or non-string / non-dict): derive PascalCase from
        # yaml_name's first letter. This is the historical naive formula
        # (`Bidder` + yaml_name[0].upper() + yaml_name[1:]) per the table
        # header comment; it's good enough for unknown-bidder fallback.
        go_constant_root = (yaml_name[:1].upper() + yaml_name[1:]) if yaml_name else ""

    base = _mechanical_forms(yaml_name, go_constant_root)
    base.update(explicit_forms)
    # `go_constant_root` always reflects the authoritative value (either
    # from the explicit forms sub-map, the simple-string entry, or the
    # mechanical fallback). Same applies when the mapping-form entry
    # carries `go_constant_root` at the top level but not inside `forms:`.
    if "go_constant_root" not in explicit_forms and go_constant_root:
        base["go_constant_root"] = go_constant_root
    return base


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


# ---------------------------------------------------------------------------
# Helper 10 — mvn_checkstyle_dry_run (Phase D4.3)
# ---------------------------------------------------------------------------


def mvn_checkstyle_dry_run(
    target_clone: Union[str, Path],
    *,
    pom_file: str = "extra/pom.xml",
    runner: Optional[Callable[[List[str], Path], Tuple[int, str, str]]] = None,
) -> Tuple[bool, List[Dict[str, Any]]]:
    """Phase D4.3: invoke ``mvn -B checkstyle:check`` against the emitted Java
    tree to surface style violations BEFORE the operator opens the PR.

    The Java port-go2java SKILL Step 5 calls this helper when
    ``--target-clone=<path>`` is provided AND ``mvn`` is on PATH. Violations
    surface as ``human_todos[]`` entries with category ``style-violation``
    in the port-report (per port-report.schema.json::human_todos.category
    enum admitted in v0.2.0).

    Parameters:
      - ``target_clone``: path to the local prebid-server-java clone.
      - ``pom_file``: relative path to the pom file from the clone root.
        Defaults to ``extra/pom.xml`` per upstream's checkstyle profile.
      - ``runner``: dependency-injection hook that receives ``(argv, cwd)``
        and returns ``(returncode, stdout, stderr)``. When omitted, the
        helper invokes ``subprocess.run`` with ``cwd=target_clone``.

    Returns ``(ok, violations)`` where ``ok`` is ``True`` iff ``mvn``
    exited 0 (no checkstyle violations); ``violations`` is a list of
    ``{file, line, severity, message}`` dicts parsed from ``mvn`` stdout.
    On runtime failure (mvn missing, target_clone path absent), returns
    ``(False, [{"severity": "infrastructure", "message": ...}])``.

    Skip semantics: when the SKILL invokes this with no target_clone,
    the SKILL emits ``human_todos[]: { category: style-violation,
    summary: "checkstyle dry-run skipped — no --target-clone provided" }``
    and proceeds.
    """
    target = Path(target_clone)
    if not target.is_dir():
        return False, [{
            "severity": "infrastructure",
            "message": f"target_clone path is not a directory: {target}",
            "file": None,
            "line": None,
        }]
    argv = ["mvn", "-B", "checkstyle:check", "--file", pom_file]
    if runner is not None:
        rc, stdout, stderr = runner(argv, target)
    else:
        try:
            # Phase D4.3 follow-up: bound subprocess to 5 minutes so a hung
            # mvn (network stall pulling a checkstyle profile, deadlocked
            # surefire fork, etc.) doesn't block indefinitely. Operator can
            # rerun manually if the bidder genuinely needs > 300s.
            result = subprocess.run(
                argv,
                cwd=str(target),
                capture_output=True,
                text=True,
                check=False,
                timeout=300,
            )
        except FileNotFoundError:
            return False, [{
                "severity": "infrastructure",
                "message": "mvn not found on PATH",
                "file": None,
                "line": None,
            }]
        except subprocess.TimeoutExpired:
            return False, [{
                "severity": "infrastructure",
                "message": "mvn -B checkstyle:check exceeded 300s timeout",
                "file": None,
                "line": None,
            }]
        rc, stdout, stderr = result.returncode, result.stdout, result.stderr
    violations = _parse_checkstyle_violations(stdout, stderr)
    return rc == 0, violations


# Two checkstyle output formats are emitted across maven-checkstyle-plugin
# versions / configurations. The regex registry below handles both; the
# parser tries each in turn.
#
# Format A (legacy / some 2.x configurations + verbose output):
#   [ERROR] /path/to/File.java:42:5: Method length is 200 lines. [MethodLength]
#
# Format B (maven-checkstyle-plugin 3.x default):
#   [ERROR] /path/to/File.java:[42,5] (sizes) MethodLength: Method length is 200 lines.
#
# Both forms include severity, file path, line, optional column, message,
# and a rule name; field placement differs. The Phase D4.3 reviewer noted
# that synthetic test inputs matched format A but real upstream
# maven-checkstyle-plugin output is format B; without both regexes a
# real-world run would parse zero violations.
_CHECKSTYLE_LINE_RES = (
    # Format A: file:line:col: message [Rule]
    re.compile(
        r"^\[(?P<sev>ERROR|WARN(?:ING)?)\]\s+(?P<file>[^\s:]+):(?P<line>\d+)(?::(?P<col>\d+))?:\s+(?P<msg>.+?)(?:\s+\[(?P<rule>[^\]]+)\])?\s*$",
        re.MULTILINE,
    ),
    # Format B: file:[line,col] (group) Rule: message
    re.compile(
        r"^\[(?P<sev>ERROR|WARN(?:ING)?)\]\s+(?P<file>[^\s:]+):\[(?P<line>\d+)(?:,(?P<col>\d+))?\]\s+\((?P<group>[^)]+)\)\s+(?P<rule>\S+):\s+(?P<msg>.+?)\s*$",
        re.MULTILINE,
    ),
)


def _parse_checkstyle_violations(stdout: str, stderr: str) -> List[Dict[str, Any]]:
    """Parse ``mvn -B checkstyle:check`` output into structured violations.

    Walks both regex formats in turn. A line that matches either format
    is recorded once (the regex set is mutually exclusive on real
    checkstyle output; defensive against double-counting if a future
    plugin version emits both forms simultaneously).
    """
    text = "\n".join(filter(None, (stdout, stderr)))
    out: List[Dict[str, Any]] = []
    seen_at_offset: set[int] = set()
    for regex in _CHECKSTYLE_LINE_RES:
        for m in regex.finditer(text):
            if m.start() in seen_at_offset:
                continue
            seen_at_offset.add(m.start())
            sev = m.group("sev").lower()
            file_path = m.group("file")
            # Only file:line:col-shaped lines that mention a Java file are real
            # checkstyle violations; skip the surrounding mvn build banner.
            if not file_path.endswith(".java"):
                continue
            out.append({
                "severity": sev,
                "file": file_path,
                "line": int(m.group("line")),
                "column": int(m.group("col")) if m.group("col") else None,
                "message": m.group("msg").strip(),
                "rule": m.group("rule"),
            })
    return out


# ---------------------------------------------------------------------------
# Helper 11 — imp_ext_shape_transform_java_to_go (Rule 36 inverse, fixture side)
# ---------------------------------------------------------------------------


def imp_ext_shape_transform_java_to_go(
    fixture_dict: Dict[str, Any],
    java_bidder_name: str,
) -> Dict[str, Any]:
    """Rule 36 inverse — rewrite Java per-bidder ``imp.ext`` slot key to Go's
    canonical ``"bidder"`` key for every imp in an auction-request fixture.

    Java's pre-adapter processor leaves the auction-request's ``imp.ext`` as
    ``{<bidder_name>: {...}}`` (the per-bidder slot, e.g. ``imp.ext.kobler``).
    Go's adapter unmarshals ``imp.ext.bidder`` (post-PrebidServer-Go split).
    When ``port-java2go`` re-authors a Java IT 4-file fixture set into a Go
    flat exemplary fixture, it copies the Java auction-request verbatim into
    ``mockBidRequest`` and the Go test harness then fails to parse
    ``imp.ext.bidder``. This helper applies the rename so the emitted
    ``mockBidRequest.imp[].ext`` is in Go-canonical shape.

    Scope and contract:
      - Operates on the OUTER auction-request only (Go's ``mockBidRequest``).
        The caller is expected to pass the dict that will be assigned to
        ``mockBidRequest`` (either the full fixture root, OR a root with
        ``mockBidRequest`` already extracted — the helper looks for
        ``imp[]`` at the top level).
      - The INNER ``httpCalls[].expectedRequest.body`` (the modified
        BidRequest the adapter sends upstream) is NOT touched here; that's
        the operator's hand-fill or a separate pass.
      - Other ``imp.ext`` keys (``prebid``, ``tid``, ``gpid``, etc.) pass
        through untouched. Only the per-bidder-name slot key is renamed.
      - If an ``imp.ext`` already has a ``"bidder"`` key (defensive — should
        not happen for Java-side fixtures but guards against double-apply),
        the helper raises ``ValueError`` rather than overwriting.
      - If an ``imp.ext`` is missing the bidder slot entirely (already-Go
        shaped, or malformed), that imp is left untouched (no error).
      - Empty ``imp[]`` array, missing ``imp`` key entirely → no-op return.

    Returns a deep-copied dict; the input is NOT mutated. (Match the
    clone-and-return convention of ``alias_graph_invert``: callers can
    treat the returned dict as a fresh artifact safe to serialize.)

    Parameters
    ----------
    fixture_dict : dict
        Auction-request dict containing an ``imp[]`` array. Typically this
        is ``mockBidRequest`` from a Go exemplary fixture during emit.
    java_bidder_name : str
        The Java per-bidder slot key to rename (e.g. ``"kobler"``). Sourced
        from the spec's ``meta.bidder_name``. Must be a non-empty string.

    Raises
    ------
    ValueError
        If ``java_bidder_name`` is empty/None, or if any imp's ``ext``
        already contains a ``"bidder"`` key alongside the Java slot.
    """
    if not java_bidder_name or not isinstance(java_bidder_name, str):
        raise ValueError(
            f"java_bidder_name must be a non-empty string; got {java_bidder_name!r}"
        )
    out = copy.deepcopy(fixture_dict)
    imps = out.get("imp")
    if not isinstance(imps, list):
        return out  # no-op: missing imp key (rare malformed fixture)
    for idx, imp in enumerate(imps):
        if not isinstance(imp, dict):
            continue
        ext = imp.get("ext")
        if not isinstance(ext, dict):
            continue
        if java_bidder_name not in ext:
            # imp.ext missing the bidder slot entirely — already-Go-shaped
            # or malformed Java; leave imp untouched per contract.
            continue
        if "bidder" in ext:
            raise ValueError(
                f"imp[{idx}].ext already has a 'bidder' key alongside "
                f"{java_bidder_name!r}; refusing to overwrite. The fixture may "
                f"already be Go-shaped (double-apply) or carry a malformed mix."
            )
        # Rename the per-bidder slot key. Other keys (prebid, tid, gpid, ...)
        # pass through untouched.
        ext["bidder"] = ext.pop(java_bidder_name)
    return out


# ---------------------------------------------------------------------------
# Helper 12 — simulate_makerequests_mutations (D3.8 F-new-16 fixture-body sim)
# ---------------------------------------------------------------------------


def simulate_makerequests_mutations(
    bid_request: Dict[str, Any],
    mutations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Apply a sequence of MakeRequests mutation ops to a bid-request dict.

    D3.8 F-new-16 helper: ports of non-passthrough Go adapters need an
    accurate ``httpCalls[].expectedRequest.body`` in their flat exemplary
    fixture (Go testCommon harness). The Go adapter's MakeRequests rewrites
    the prebid-server-internal BidRequest before serializing it onto the
    wire (sanitize Device/User, rewrite Site/App, fill Banner.W/H from
    format[0], strip imp.Ext, etc.) — fixtures must reflect that mutated
    body, not the input. Helper-less, fixtures end up shaped like the
    auction request (passthrough assumption) and Go-side test runs fail
    body-shape comparison.

    The helper takes a list of mutation OPERATIONS observed across the
    corpus (D3.8 spike doc: ``docs/runs/d3.8-mvp-pairs-spike-2026-05-05.md``)
    and applies them in order to a deepcopy of the input. Each op is a
    dict with a string ``kind`` field plus op-specific params. Unknown
    kinds raise ``ValueError`` listing the offending op-kind.

    Supported op kinds (canonical via D3.8 spike F-new-16 / F-new-20):

    1. ``device-zero-fields`` (params: ``fields: list[str]``) —
       kobler/beachfront pattern. Zeros out specific Device fields
       (typically ``ip`` / ``ipv6``). No-op if Device key absent or
       a named field absent.
    2. ``user-null`` — kobler/beachfront pattern. Sets ``user=None``
       (i.e., removes the ``user`` key, equivalent to ``request.User = nil``
       in Go).
    3. ``imp-bidfloor-convert-to-usd`` — kobler/adverxo/limelightDigital/
       vungle pattern. Caller is responsible for supplying converted
       values via ``imp.bidfloor`` already; helper just normalizes
       ``imp.bidfloorcur`` to ``"USD"`` when it's set to a non-USD
       currency on imps with a positive bidfloor. The helper CANNOT
       perform the actual conversion (no FX rate data); it documents
       the contract that fixture authors must pre-convert.
    4. ``imp-ext-strip-after-extraction`` — adkernelAdn pattern (F-new-20).
       Sets ``imp.ext=None`` for every imp (equivalent to ``imp.Ext = nil``
       in Go's ``compatImpression``).
    5. ``imp-ext-rewrap-with-bidder-slot`` (params: ``slot_name: str``) —
       vungle pattern. Re-wraps ``imp.ext`` so existing bidder content
       moves under the named slot key (the inverse of F4's transform):
       ``{"bidder": {...}, "prebid": {...}}`` → ``{"vungle": {...},
       "prebid": {...}, "bidder": {...}}`` where the slot value is the
       existing ``bidder`` dict. Per the upstream ``vungleImpressionExt``
       struct, the bidder-slot is preserved AND the named slot is added
       (the Go marshaler emits both fields).
    6. ``site-null`` — vungle pattern. Sets ``site=None`` during Site→App
       synthesis.
    7. ``app-replace-with-synthesis`` (params: ``app_synthesis_payload:
       dict``) — vungle pattern. Replaces ``app`` with the operator-
       supplied synthesis payload. The actual synthesis logic is bidder-
       specific (vungle uses ``bidderImpExt.PubAppStoreID``); the helper
       cannot derive the payload, so the caller computes it from the
       bidder spec and passes it in verbatim.
    8. ``site-publisher-rewrite`` (params: ``publisher_id: str``) —
       thetradedesk pattern. Overwrites ``site.publisher.id``. No-op if
       site or site.publisher absent.
    9. ``app-publisher-rewrite`` (params: ``publisher_id: str``) —
       thetradedesk pattern. Overwrites ``app.publisher.id``. No-op if
       app or app.publisher absent.
    10. ``site-publisher-null`` — adkernelAdn pattern. Sets
        ``site.publisher=None`` (equivalent to ``Site.Publisher = nil``).
    11. ``site-domain-clear`` — adkernelAdn pattern. Sets ``site.domain=""``.
    12. ``app-publisher-null`` — adkernelAdn pattern. Sets
        ``app.publisher=None``.
    13. ``banner-format-fill-wh`` — adkernelAdn / thetradedesk pattern.
        For every imp with a ``banner`` and missing ``banner.w`` / ``banner.h``,
        copies ``w``/``h`` from the first ``banner.format[]`` entry and
        drops format[0] from the array. Matches Go's
        ``compatBannerImpression``.
    14. ``imp-tagid-from-ext`` (params: ``ext_field_name: str``,
        ``slot_name: str``) — vungle pattern. For every imp, sets
        ``imp.tagid`` to ``imp.ext[slot_name][ext_field_name]`` when both
        keys resolve to a value. ``slot_name`` is REQUIRED (raises
        ``ValueError`` if absent or empty) — vungle is the only canonical
        caller and it has a known slot ("vungle"); requiring the slot
        eliminates the cross-slot mis-route the prior heuristic was
        prone to (PR #5 reviewer F-2).
    15. ``currency-normalize-to-list`` (params: ``currency: str``) —
        kobler pattern. Appends the currency to ``cur`` if not present.
        No-op if ``cur`` already contains the currency.

    Implementation notes:
      - Always deepcopies the input. The caller's ``bid_request`` is
        never mutated.
      - When an op references a path that doesn't exist (e.g.,
        ``device-zero-fields`` on a request with no ``device``), the
        op is skipped silently. Java-IT-derived fixtures sometimes lack
        fields the Go adapter would otherwise touch.
      - For ``imp-bidfloor-convert-to-usd``: this op is a no-op when
        ``bidfloorcur=="USD"`` (the common case in passthrough fixtures);
        when ``bidfloorcur != "USD"``, the helper sets
        ``bidfloorcur="USD"`` and leaves ``bidfloor`` as-is (caller is
        responsible for passing in pre-converted values). This matches
        Go's mutation semantics where the BidFloor field is overwritten
        with a converted numeric value the helper cannot compute.
      - The op list is applied in caller-supplied order. Some op
        sequences are dependency-bound; the helper does NOT enforce
        ordering — the caller (renderer) is responsible. Known
        dependency pairs (PR #5 reviewer F-3 — non-exhaustive but
        covers every pattern observed across the 6 MVP canaries):

          (a) ``imp-ext-rewrap-with-bidder-slot`` BEFORE
              ``imp-tagid-from-ext`` when the tagid is sourced from
              the rewrapped slot (vungle).
          (b) ``site-null`` BEFORE ``app-replace-with-synthesis``
              (vungle's Site→App handoff: null the existing site, then
              install the synthesized app).
          (c) ``imp-ext-strip-after-extraction`` LAST among imp.ext
              touches (adkernelAdn) — it nulls imp.ext, so any later
              imp.ext-reading op (including ``imp-tagid-from-ext``)
              reads None and silently no-ops.

        All other op pairs commute (touch disjoint paths). When the
        renderer's call site is reviewed in a canary trace, mis-ordering
        surfaces as a fixture diff against the live Go-side test —
        not a Python error — so audit the trace whenever a new bidder
        introduces a novel mutation sequence.

    Parameters
    ----------
    bid_request : dict
        The Go-shape ``mockBidRequest`` (or the BidRequest-equivalent
        dict the operator wants to simulate the adapter's output of).
        Must be deepcopy-safe (a JSON-loaded dict satisfies this).
    mutations : list[dict]
        Ordered op list. Each op is ``{"kind": <str>, ...op-params}``.

    Returns
    -------
    dict
        Deep-copied ``bid_request`` with all mutations applied in order.

    Raises
    ------
    ValueError
        If any op's ``kind`` is not in the supported set. The error
        message includes the unrecognized kind for diagnostics.
    """
    out = copy.deepcopy(bid_request)
    for idx, op in enumerate(mutations):
        if not isinstance(op, dict):
            raise ValueError(
                f"mutations[{idx}] is not a dict: {op!r}"
            )
        kind = op.get("kind")
        applier = _MAKEREQUESTS_MUTATION_APPLIERS.get(kind)
        if applier is None:
            raise ValueError(
                f"mutations[{idx}] has unsupported kind={kind!r}; "
                f"supported kinds: {sorted(_MAKEREQUESTS_MUTATION_APPLIERS.keys())}"
            )
        applier(out, op)
    return out


# ---- Per-op appliers --------------------------------------------------------


def _apply_device_zero_fields(req: Dict[str, Any], op: Dict[str, Any]) -> None:
    # Mirror Go's `device.IP = ""` wire form: Go's openrtb2.Device fields
    # carry omitempty tags on IP, IPv6, etc., so the marshaled wire form
    # OMITS the keys after zeroing. Python's json.dumps has no omitempty
    # equivalent, so emitting `device[k] = ""` would carry `"ip": ""` on
    # the wire — divergent from upstream Go's actual marshal output. We
    # mirror Go's wire form by deleting the keys (same idiom as
    # _apply_user_null below; F-new-35 ex post facto correction).
    device = req.get("device")
    if not isinstance(device, dict):
        return  # no Device → no-op
    fields = op.get("fields") or []
    for fname in fields:
        if fname in device:
            del device[fname]


def _apply_user_null(req: Dict[str, Any], _op: Dict[str, Any]) -> None:
    # Match Go's `request.User = nil` semantics: remove the key entirely
    # so the JSON-marshaled body omits the field. (`json.dumps({...,
    # "user": None})` would emit `"user":null`, but Go's `omitempty` tag
    # on BidRequest.User would drop it. We mirror Go's wire form.)
    if "user" in req:
        del req["user"]


def _apply_imp_bidfloor_convert_to_usd(req: Dict[str, Any], _op: Dict[str, Any]) -> None:
    imps = req.get("imp")
    if not isinstance(imps, list):
        return
    for imp in imps:
        if not isinstance(imp, dict):
            continue
        bidfloor = imp.get("bidfloor")
        bidfloorcur = imp.get("bidfloorcur")
        # Helper contract: only re-tag bidfloorcur. Caller pre-converts the
        # numeric value. Skip imps where conversion is not applicable.
        if (
            isinstance(bidfloor, (int, float))
            and bidfloor > 0
            and isinstance(bidfloorcur, str)
            and bidfloorcur != ""
            and bidfloorcur.upper() != "USD"
        ):
            imp["bidfloorcur"] = "USD"


def _apply_imp_ext_strip_after_extraction(req: Dict[str, Any], _op: Dict[str, Any]) -> None:
    imps = req.get("imp")
    if not isinstance(imps, list):
        return
    for imp in imps:
        if not isinstance(imp, dict):
            continue
        # Match Go's `imp.Ext = nil`: remove the key so the JSON-marshaled
        # body has no `ext` field on this imp.
        if "ext" in imp:
            del imp["ext"]


def _apply_imp_ext_rewrap_with_bidder_slot(req: Dict[str, Any], op: Dict[str, Any]) -> None:
    slot_name = op.get("slot_name")
    if not isinstance(slot_name, str) or not slot_name:
        raise ValueError(
            f"imp-ext-rewrap-with-bidder-slot requires a non-empty 'slot_name'; got {slot_name!r}"
        )
    imps = req.get("imp")
    if not isinstance(imps, list):
        return
    for imp in imps:
        if not isinstance(imp, dict):
            continue
        ext = imp.get("ext")
        if not isinstance(ext, dict):
            continue
        # vungleImpressionExt is `{*ExtImpBidder, vungle: ImpExtVungle}` —
        # i.e., the marshaled JSON has BOTH the embedded bidder/prebid keys
        # AND a new `vungle` key carrying the bidder-slot content. We mirror
        # that shape: copy the existing `bidder` content under the new slot
        # key without removing it (the bidder slot stays for the embedded-
        # struct path).
        bidder_content = ext.get("bidder")
        if bidder_content is None:
            # No bidder slot to rewrap; skip without erroring (defensive).
            continue
        ext[slot_name] = copy.deepcopy(bidder_content)


def _apply_site_null(req: Dict[str, Any], _op: Dict[str, Any]) -> None:
    if "site" in req:
        del req["site"]


def _apply_app_replace_with_synthesis(req: Dict[str, Any], op: Dict[str, Any]) -> None:
    payload = op.get("app_synthesis_payload")
    if not isinstance(payload, dict):
        raise ValueError(
            "app-replace-with-synthesis requires 'app_synthesis_payload' (dict); "
            f"got {type(payload).__name__}"
        )
    req["app"] = copy.deepcopy(payload)


def _apply_site_publisher_rewrite(req: Dict[str, Any], op: Dict[str, Any]) -> None:
    pub_id = op.get("publisher_id")
    if not isinstance(pub_id, str):
        raise ValueError(
            f"site-publisher-rewrite requires 'publisher_id' (str); got {pub_id!r}"
        )
    site = req.get("site")
    if not isinstance(site, dict):
        return
    publisher = site.get("publisher")
    if not isinstance(publisher, dict):
        return
    publisher["id"] = pub_id


def _apply_app_publisher_rewrite(req: Dict[str, Any], op: Dict[str, Any]) -> None:
    pub_id = op.get("publisher_id")
    if not isinstance(pub_id, str):
        raise ValueError(
            f"app-publisher-rewrite requires 'publisher_id' (str); got {pub_id!r}"
        )
    app = req.get("app")
    if not isinstance(app, dict):
        return
    publisher = app.get("publisher")
    if not isinstance(publisher, dict):
        return
    publisher["id"] = pub_id


def _apply_site_publisher_null(req: Dict[str, Any], _op: Dict[str, Any]) -> None:
    site = req.get("site")
    if not isinstance(site, dict):
        return
    if "publisher" in site:
        del site["publisher"]


def _apply_site_domain_clear(req: Dict[str, Any], _op: Dict[str, Any]) -> None:
    site = req.get("site")
    if not isinstance(site, dict):
        return
    # Match Go's `Site.Domain = ""` — set to empty string (NOT delete) since
    # Go's openrtb2.Site.Domain has no omitempty tag and the marshaled body
    # carries `"domain":""` after the rewrite.
    site["domain"] = ""


def _apply_app_publisher_null(req: Dict[str, Any], _op: Dict[str, Any]) -> None:
    app = req.get("app")
    if not isinstance(app, dict):
        return
    if "publisher" in app:
        del app["publisher"]


def _apply_banner_format_fill_wh(req: Dict[str, Any], _op: Dict[str, Any]) -> None:
    imps = req.get("imp")
    if not isinstance(imps, list):
        return
    for imp in imps:
        if not isinstance(imp, dict):
            continue
        banner = imp.get("banner")
        if not isinstance(banner, dict):
            continue
        # Go's compatBannerImpression: only fills if BOTH W and H are nil.
        if banner.get("w") is not None or banner.get("h") is not None:
            continue
        formats = banner.get("format")
        if not isinstance(formats, list) or not formats:
            continue
        first = formats[0]
        if not isinstance(first, dict):
            continue
        if "w" in first:
            banner["w"] = first["w"]
        if "h" in first:
            banner["h"] = first["h"]
        # Drop format[0] from the list (mirrors `banner.Format = banner.Format[1:]`).
        banner["format"] = formats[1:]


def _apply_imp_tagid_from_ext(req: Dict[str, Any], op: Dict[str, Any]) -> None:
    field_name = op.get("ext_field_name")
    if not isinstance(field_name, str) or not field_name:
        raise ValueError(
            f"imp-tagid-from-ext requires non-empty 'ext_field_name'; got {field_name!r}"
        )
    slot_name = op.get("slot_name")
    if not isinstance(slot_name, str) or not slot_name:
        raise ValueError(
            f"imp-tagid-from-ext requires non-empty 'slot_name' (the imp.ext "
            f"key whose value-dict carries the target field); got {slot_name!r}"
        )
    imps = req.get("imp")
    if not isinstance(imps, list):
        return
    for imp in imps:
        if not isinstance(imp, dict):
            continue
        ext = imp.get("ext")
        if not isinstance(ext, dict):
            continue
        slot = ext.get(slot_name)
        if isinstance(slot, dict) and field_name in slot:
            imp["tagid"] = slot[field_name]


def _apply_currency_normalize_to_list(req: Dict[str, Any], op: Dict[str, Any]) -> None:
    currency = op.get("currency")
    if not isinstance(currency, str) or not currency:
        raise ValueError(
            f"currency-normalize-to-list requires non-empty 'currency'; got {currency!r}"
        )
    cur = req.get("cur")
    if cur is None:
        # Per Go semantics: kobler appends to `request.Cur` only if not
        # present; if Cur is nil, the append yields a one-element slice.
        req["cur"] = [currency]
        return
    if not isinstance(cur, list):
        # Defensive: malformed `cur` field (string, dict, etc.) — leave
        # untouched. Go-side would have failed unmarshal earlier.
        return
    if currency in cur:
        return
    cur.append(currency)


# Dispatch table — populated AFTER the appliers are defined so the names
# resolve. Keeping it adjacent keeps the kind-string registry obvious.
_MAKEREQUESTS_MUTATION_APPLIERS: Dict[
    str,
    Callable[[Dict[str, Any], Dict[str, Any]], None],
] = {
    "device-zero-fields": _apply_device_zero_fields,
    "user-null": _apply_user_null,
    "imp-bidfloor-convert-to-usd": _apply_imp_bidfloor_convert_to_usd,
    "imp-ext-strip-after-extraction": _apply_imp_ext_strip_after_extraction,
    "imp-ext-rewrap-with-bidder-slot": _apply_imp_ext_rewrap_with_bidder_slot,
    "site-null": _apply_site_null,
    "app-replace-with-synthesis": _apply_app_replace_with_synthesis,
    "site-publisher-rewrite": _apply_site_publisher_rewrite,
    "app-publisher-rewrite": _apply_app_publisher_rewrite,
    "site-publisher-null": _apply_site_publisher_null,
    "site-domain-clear": _apply_site_domain_clear,
    "app-publisher-null": _apply_app_publisher_null,
    "banner-format-fill-wh": _apply_banner_format_fill_wh,
    "imp-tagid-from-ext": _apply_imp_tagid_from_ext,
    "currency-normalize-to-list": _apply_currency_normalize_to_list,
}


# ---------------------------------------------------------------------------
# Helper 13 — exemplary_fixture_assemble_java_to_go (D3.8 canary v2: F-new-9/10/11/13; canary v3: F-new-22)
# ---------------------------------------------------------------------------
#
# Bundles fixture-authoring concerns the kobler canary v2 + vungle canary
# v3 surfaced (renderer-level): cur fallback, canonical TEST_ENDPOINT,
# expected_bids from bid-response, expectedRequest.body simulation, and
# opt-in empty-user injection for adapters whose Go side dereferences
# ``request.User`` without a nil-check. Promoted from canary v2/v3
# one-off renderers to a reusable helper so future Java→Go canaries
# (aax, adverxo, thetradedesk, ...) do not rediscover the same shape
# contract.
#
# - F-new-9: bid-response.cur fallback. Java's framework defaults
#   Currency to USD when bid-response lacks ``cur``; Go's adapter does
#   ``bidderResponse.Currency = bidResponse.Cur`` directly, so an empty
#   ``cur`` produces an empty Currency that fails the test expectation.
#   Helper copies cur from auction-response when bid-response omits it
#   (lenient on conflicts: bid-response wins, no error).
#
# - F-new-10: TEST_ENDPOINT canonical constant. The emitted
#   bidder_test.go calls Builder() with ``"https://test.example.com/bid"``;
#   the emitted exemplary fixture's ``expectedRequest.uri`` must match
#   that, NOT the real bidder-info endpoint. Constant lives at module
#   scope so other call sites share a single source of truth.
#
# - F-new-11: expected_bids derive from bid-response (the bare upstream
#   bids the adapter receives + the type the adapter computes), NOT from
#   auction-response (post-prebid-server enriched bids with exp,
#   ext.origbidcpm, ext.prebid.meta — none of which the adapter generates).
#
# - F-new-13: expectedRequest.body simulation. Passthrough adapters
#   (no per-bidder request mutation) get body == mockBidRequest.
#   Non-passthrough adapters supply ``expected_request_body_simulator``
#   (typically a partial of ``simulate_makerequests_mutations`` from
#   helper 12 above). When omitted, falls back to passthrough — known-
#   imperfect for non-passthrough but the closest sensible default.
#
# - F-new-22: opt-in empty-user injection. Java IT auction-requests
#   sometimes lack a ``user`` object entirely; Java's bidder code is
#   null-safe (``ObjectUtil.getIfNotNull(bidRequest.getUser(), ...)``)
#   so the IT scenario passes upstream. The Go adapter equivalent often
#   dereferences ``request.User.X`` directly (e.g. vungle.go:68
#   ``requestCopy.User.BuyerUID``) — nil-panics when User is absent.
#   Opt-in flag ``inject_empty_user_if_missing=True`` injects ``user: {}``
#   into the F4-transformed mock_bid_request when ``user`` is absent or
#   None. ``BuyerUID`` and friends are ``omitempty``-tagged so the
#   wire-format body matches the no-user case (``user: {}``). Default
#   False preserves backward-compat with kobler/aax canary v2 callers
#   whose Go adapters do not deref User unconditionally.

# F-new-10: canonical Builder() test endpoint. Matches the URL the
# emitted bidder_test.go's Builder invocation passes via
# ``config.Adapter{Endpoint: ...}``. Renderers/templates that import this
# constant share a single source of truth so a future endpoint change
# updates exactly one place.
TEST_ENDPOINT = "https://test.example.com/bid"


def _apply_cur_fallback(
    bid_response: Dict[str, Any],
    auction_response: Dict[str, Any],
) -> Dict[str, Any]:
    """F-new-9: fill bid-response.cur from auction-response when absent.

    Java IT bid-response often omits ``cur`` because the Java framework
    defaults Currency to USD before the adapter sees the response. The
    Go adapter assigns ``bidderResponse.Currency = bidResponse.Cur``
    directly — empty ``cur`` produces empty Currency that fails Go's
    test expectation of ``USD``. Bridge by copying ``cur`` from
    auction-response.

    Lenient on conflicts: when both responses carry a ``cur`` and they
    differ, the bid-response value wins (it is the upstream-true ground
    truth; auction-response is post-server). No error is raised — the
    audit doc/spike intent is best-effort fixture authoring, not
    strict validation. The reasoning, per the audit doc:

        the bid-response is closer to ground truth.

    Returns a deep-copied bid_response dict; inputs are not mutated.
    """
    out = copy.deepcopy(bid_response)
    if "cur" in out:
        # Bid-response wins on conflict (lenient mode); no override.
        return out
    if isinstance(auction_response, dict) and "cur" in auction_response:
        out["cur"] = auction_response["cur"]
    return out


def _expected_bids_from_bid_response(
    bid_response: Dict[str, Any],
    default_type: str,
) -> List[Dict[str, Any]]:
    """F-new-11: derive expected_bids from the BARE upstream bid-response.

    The Go adapter's MakeBids returns the bare bid the upstream sent,
    paired with the BidType the adapter computed. The Java auction-
    response captures POST-prebid-server-processing state (extra fields
    the framework added: ``exp``, ``ext.origbidcpm``, ``ext.prebid.meta``)
    that the adapter neither generates nor is responsible for — using
    auction-response bids causes Go's expected vs actual JSON comparison
    to diverge on every fixture.

    Returns ``[]`` when seatbid is missing or empty. Each entry is
    ``{"bid": <bare bid dict>, "type": <default_type>}``. The default
    type is a per-bidder choice (banner is the safe baseline; vungle
    forces video; native-only bidders use native).

    Bid dicts ARE deep-copied. The outer ``exemplary_fixture_assemble_
    java_to_go`` helper promises "Inputs are NOT mutated" — without the
    copy, the returned ctx's ``expected_bids[].bid`` aliases entries
    inside the caller's ``java_bid_response`` and any downstream mutator
    leaks through (reviewer F-1, PR #5).
    """
    out: List[Dict[str, Any]] = []
    if not isinstance(bid_response, dict):
        return out
    seatbid = bid_response.get("seatbid")
    if not isinstance(seatbid, list):
        return out
    for sb in seatbid:
        if not isinstance(sb, dict):
            continue
        bids = sb.get("bid")
        if not isinstance(bids, list):
            continue
        for bid in bids:
            if not isinstance(bid, dict):
                continue
            out.append({"bid": copy.deepcopy(bid), "type": default_type})
    return out


def _default_expected_request_body(mock_bid_request: Dict[str, Any]) -> Dict[str, Any]:
    """F-new-13 passthrough fallback: body == mockBidRequest.

    For passthrough adapters (no per-bidder request mutation in MakeRequests),
    the body the adapter sends upstream is byte-identical to the
    BidRequest it received. Returns a deep-copied dict so callers can
    safely mutate or serialize without affecting mock_bid_request.

    Known-imperfect for non-passthrough adapters (currency conversion,
    macro substitution, native ADM unwrap). Those callers must supply
    ``expected_request_body_simulator`` to
    ``exemplary_fixture_assemble_java_to_go``; the typical pattern is to
    bind ``simulate_makerequests_mutations`` (helper 12) with the
    bidder's mutation op-list as the simulator.
    """
    return copy.deepcopy(mock_bid_request)


def exemplary_fixture_assemble_java_to_go(
    *,
    java_auction_request: Dict[str, Any],
    java_auction_response: Dict[str, Any],
    java_bid_request: Dict[str, Any],
    java_bid_response: Dict[str, Any],
    java_bidder_name: str,
    expected_request_body_simulator: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    default_bid_type: str = "banner",
    test_endpoint: str = TEST_ENDPOINT,
    inject_empty_user_if_missing: bool = False,
) -> Dict[str, Any]:
    """Assemble the ctx dict for ``exemplary-fixture.json.j2`` from a Java
    IT 4-file fixture set, applying the Rule 36 inverse semantic-coverage
    transform plus F-new-9/10/11/13 fixture-authoring concerns and the
    F-new-22 opt-in empty-user injection.

    The returned ctx dict matches the exemplary-fixture template's input
    contract (see ``prebid-server-go/port-java2go/templates/exemplary-fixture.json.j2``)::

        {
          "mock_bid_request": <publisher-side BidRequest, F4-transformed,
                                optional user:{} inject>,    # F-new-22
          "http_calls": [
            {
              "uri": <test_endpoint>,                       # F-new-10
              "body": <expected request body>,              # F-new-13
              "status": 200,
              "response": <bid-response with cur fallback>, # F-new-9
              "imp_ids": [<imp[].id>, ...],                 # F-new-12
            },
          ],
          "expected_bids": [{"bid": ..., "type": ...}, ...],  # F-new-11
          "expected_currency": <auction-response.cur or "USD">,
        }

    Parameters
    ----------
    java_auction_request : dict
        Java IT ``test-auction-{bidder}-request.json``: the publisher-
        side BidRequest the harness feeds to MakeRequests. Imp[].ext
        carries the per-bidder slot (``imp.ext.{java_bidder_name}``);
        the F4 helper rewrites it to Go's ``imp.ext.bidder`` shape.
    java_auction_response : dict
        Java IT ``test-auction-{bidder}-response.json``: the publisher-
        visible auction response, used here for ``cur`` fallback
        (F-new-9) and ``expected_currency`` default.
    java_bid_request : dict
        Java IT ``test-{bidder}-bid-request.json``: the framework-
        enriched bid-request capture. NOT used as ``expectedRequest.body``
        directly (F-new-13: it carries Java-framework-added fields the
        Go adapter does not emit). Reserved for future simulator-input
        use; accepted now so the helper signature stays stable.
    java_bid_response : dict
        Java IT ``test-{bidder}-bid-response.json``: the bare upstream
        bid-response. The cur fallback (F-new-9) and expected_bids
        derivation (F-new-11) operate on this.
    java_bidder_name : str
        The Java per-bidder slot key (e.g. ``"kobler"``). Sourced from
        the spec's ``meta.bidder_name``. Forwarded to
        ``imp_ext_shape_transform_java_to_go``.
    expected_request_body_simulator : Callable[[dict], dict] | None
        F-new-13: optional callback that receives the F4-transformed
        ``mock_bid_request`` and returns the body the Go adapter would
        marshal upstream. Required for non-passthrough adapters
        (currency conversion, ADM unwrap, macro substitution). Typical
        pattern: ``functools.partial(simulate_makerequests_mutations,
        mutations=ops)``. When omitted, the helper falls back to the
        passthrough body (``body == mock_bid_request``). The simulator
        may return either the same dict (ok) or a fresh dict; the
        caller is responsible for not mutating its input if it cares
        about the original.
    default_bid_type : str
        F-new-11: the bid type the Go adapter computes for every
        upstream bid in the bid-response. Defaults to ``"banner"``.
        Per-bidder overrides: ``"video"`` for vungle, ``"native"`` for
        native-only bidders, etc.
    test_endpoint : str
        F-new-10: the URL the emitted ``bidder_test.go``'s Builder()
        passes via ``config.Adapter{Endpoint: ...}``. Defaults to the
        canonical ``TEST_ENDPOINT`` shared with bidder-test.go.j2.
        Override only if the rendered test uses a non-standard endpoint.
    inject_empty_user_if_missing : bool
        F-new-22: when True, after the F4 imp.ext shape transform but
        before ``expected_request_body_simulator`` is invoked, inject
        ``user: {}`` into ``mock_bid_request`` if the ``user`` key is
        absent or None. Pass True for adapters that dereference
        ``request.User`` without a nil-check (e.g. vungle vungle.go:68
        ``requestCopy.User.BuyerUID``). The empty struct's fields are
        ``omitempty``-tagged so wire-format matches the no-user case
        (the body emits ``"user": {}``). Defaults to False to preserve
        backward compatibility with kobler/aax callers whose Go
        adapters do not deref User unconditionally. The simulator (when
        supplied) sees the same post-injection mock_bid_request the
        harness will feed to MakeRequests.

    Returns
    -------
    dict
        The ctx dict ready to feed
        ``env.get_template("exemplary-fixture.json.j2").render(ctx=...)``.

    Notes on input mutation
    -----------------------
    Inputs are NOT mutated. The helper deepcopies anything it modifies
    (via ``imp_ext_shape_transform_java_to_go`` and ``_apply_cur_fallback``).
    The simulator callback is invoked with the F4-transformed
    ``mock_bid_request``; if the simulator mutates that dict, the
    returned ctx's ``mock_bid_request`` is still the (already-deepcopied)
    F4 output — the caller's original ``java_auction_request`` is safe
    regardless.

    Raises
    ------
    ValueError
        If ``java_bidder_name`` is empty/None or not a string.
    """
    if not java_bidder_name or not isinstance(java_bidder_name, str):
        raise ValueError(
            f"java_bidder_name must be a non-empty string; got {java_bidder_name!r}"
        )

    # Step 1 — F4 imp.ext shape transform on the auction-request → mock_bid_request.
    mock_bid_request = imp_ext_shape_transform_java_to_go(
        java_auction_request, java_bidder_name
    )

    # Step 1b — F-new-22 opt-in empty-user injection. Runs after F4 and
    # before the simulator (Step 4) so the simulator sees the same
    # mock_bid_request the harness will feed to MakeRequests. No-op when
    # the auction-request already carries a (non-None) ``user`` object.
    if inject_empty_user_if_missing and mock_bid_request.get("user") is None:
        mock_bid_request["user"] = {}

    # Step 2 — F-new-9 cur fallback on bid-response.
    bid_response_with_cur = _apply_cur_fallback(java_bid_response, java_auction_response)

    # Step 3 — F-new-12 imp_ids from the F4-transformed auction-request.
    imp_ids: List[str] = []
    imps = mock_bid_request.get("imp")
    if isinstance(imps, list):
        for imp in imps:
            if isinstance(imp, dict) and "id" in imp:
                imp_ids.append(imp["id"])

    # Step 4 — F-new-13 expected_request_body via simulator or passthrough.
    if expected_request_body_simulator is not None:
        expected_request_body = expected_request_body_simulator(mock_bid_request)
    else:
        expected_request_body = _default_expected_request_body(mock_bid_request)

    # Step 5 — F-new-11 expected_bids from bid-response.
    expected_bids = _expected_bids_from_bid_response(java_bid_response, default_bid_type)

    # Step 6 — expected_currency from auction-response (default "USD").
    expected_currency = "USD"
    if isinstance(java_auction_response, dict):
        cur = java_auction_response.get("cur")
        if isinstance(cur, str) and cur:
            expected_currency = cur

    # Step 7 — assemble the ctx dict.
    return {
        "mock_bid_request": mock_bid_request,
        "http_calls": [
            {
                "uri": test_endpoint,
                "body": expected_request_body,
                "status": 200,
                "response": bid_response_with_cur,
                "imp_ids": imp_ids,
            }
        ],
        "expected_bids": expected_bids,
        "expected_currency": expected_currency,
    }


def extract_entity_strategies(source_spec: Any) -> Optional[Dict[str, str]]:
    """Extract entity_strategies dict from a source spec's make_requests block.

    Returns the dict of {Entity: strategy_kind} (e.g., {"Imp": "in-place",
    "Device": "none", "Site": "replace-with-app-synthesis"}) for use as
    ctx.entity_strategies in the bidder.java.j2 template's makeHttpRequests
    scaffold (F-new-78). Returns None if make_requests or entity_strategies is
    absent.

    Entity scope:
    - BidRequest-level entities: Imp, Device, User, Site, App, Cur, Source —
      mutations applied at BidRequest.toBuilder() chain.
    - Per-imp entities: Banner, Video — mutations applied INSIDE the per-imp
      Imp.toBuilder() chain (live under imp.banner / imp.video, not
      bidRequest.banner). The template emits Banner/Video TODO comments
      within the Imp.toBuilder() block, not at the BidRequest level.

    Strategy-kind contract: the helper does NOT validate values. Expected
    kinds are {"in-place", "copy-then-mutate", "deep-copy-then-mutate",
    "append-if-missing", "replace-with-app-synthesis",
    "synthesize-app-replacement", "passthrough", "none"}, but an unexpected
    string flows through to the template unmodified — the template's
    `not in ("passthrough", "none")` guard treats anything else as
    "emit a TODO", which is conservative but may produce confusing TODOs
    for malformed input. Caller should validate value-set if strict
    enforcement is required.

    Per port-go2java/SKILL.md Step 5 + Rule 5 (Lombok immutable-rebuild pattern).
    """
    if not isinstance(source_spec, dict):
        return None
    code = source_spec.get("code")
    if not isinstance(code, dict):
        return None
    make_requests = code.get("make_requests")
    if not isinstance(make_requests, dict):
        return None
    mutation = make_requests.get("mutation")
    if not isinstance(mutation, dict):
        return None
    es = mutation.get("entity_strategies")
    if not isinstance(es, dict):
        return None
    return es
