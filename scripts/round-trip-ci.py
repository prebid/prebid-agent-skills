#!/usr/bin/env python3
"""
Round-trip CI harness for the read-skill suite (R1-R10).

Validates the correctness invariants documented in
prebid-server-go/read/skills/shared/adapter-spec.md against every golden
spec under prebid-server-{go,java}/read/test-fixtures/.

Usage (from repo root):
    python3 scripts/round-trip-ci.py
    python3 scripts/round-trip-ci.py --json
    python3 scripts/round-trip-ci.py --check-network        # opt-in R1 GitHub fetch
    python3 scripts/round-trip-ci.py --strict-r3            # tighten R3 keyword pairing

Exit codes:
    0  every rule passed (warnings allowed)
    1  one or more rules emitted at least one FAIL
    2  no FAIL but at least one WARN
"""

from __future__ import annotations

import argparse
import dataclasses
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import OrderedDict
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import yaml  # PyYAML
except ImportError:  # pragma: no cover
    sys.stderr.write("ERROR: PyYAML is required (pip install pyyaml)\n")
    sys.exit(3)


# ---------------------------------------------------------------------------
# Repo layout (paths are absolute and stable; the repo lives under prebid-agent-skills)
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
GO_FIXTURES = os.path.join(REPO_ROOT, "prebid-server-go", "read", "test-fixtures")
JAVA_FIXTURES = os.path.join(REPO_ROOT, "prebid-server-java", "read", "test-fixtures")
DUAL_SPECS_DIR = os.path.join(REPO_ROOT, "cross-language-pairs")
TAXONOMY_PATH = os.path.join(
    REPO_ROOT, "prebid-server-go", "read", "skills", "shared", "behavior-taxonomy.md"
)


# ---------------------------------------------------------------------------
# Severity model
# ---------------------------------------------------------------------------

SEV_PASS = "pass"
SEV_WARN = "warn"
SEV_FAIL = "fail"
SEV_SKIP = "skip"


@dataclasses.dataclass
class Finding:
    rule: str
    spec: str
    severity: str
    detail: str

    def short(self) -> str:
        return f"  [{self.rule}] {self.severity.upper():4s} {self.spec}: {self.detail}"


# ---------------------------------------------------------------------------
# Spec loading
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Spec:
    path: str
    bidder: str
    language: str  # "go" or "java"
    raw: Dict[str, Any]
    raw_text: str

    @property
    def label(self) -> str:
        return f"{self.language}/{self.bidder}"

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.raw
        for part in dotted.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node


def load_spec(path: str, language: str) -> Optional[Spec]:
    bidder = os.path.basename(path).replace(".golden.spec.yaml", "")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw_text = fh.read()
        raw = yaml.safe_load(raw_text)
    except (OSError, yaml.YAMLError) as exc:
        print(
            f"ERROR: cannot load spec {path}: {exc}",
            file=sys.stderr,
        )
        return None
    if not isinstance(raw, dict):
        print(
            f"ERROR: spec {path} did not parse as a YAML mapping",
            file=sys.stderr,
        )
        return None
    return Spec(path=path, bidder=bidder, language=language, raw=raw, raw_text=raw_text)


def discover_specs() -> List[Spec]:
    specs: List[Spec] = []
    for path in sorted(glob.glob(os.path.join(GO_FIXTURES, "*.golden.spec.yaml"))):
        s = load_spec(path, "go")
        if s is not None:
            specs.append(s)
    for path in sorted(glob.glob(os.path.join(JAVA_FIXTURES, "*.golden.spec.yaml"))):
        s = load_spec(path, "java")
        if s is not None:
            specs.append(s)
    return specs


# ---------------------------------------------------------------------------
# Quirk taxa registry (R9 source-of-truth, parsed from behavior-taxonomy.md)
# ---------------------------------------------------------------------------


def parse_taxa_registry(taxonomy_md_path: str) -> List[str]:
    """Extract the list of allowed `edge_case_taxon` values from the markdown."""
    if not os.path.isfile(taxonomy_md_path):
        return []
    with open(taxonomy_md_path, "r", encoding="utf-8") as fh:
        text = fh.read()
    # Find the registry section (case- and back-tick-tolerant).
    pattern = re.compile(r"^##\s+quirks\s+`?edge_case_taxon`?[^\n]*$", re.MULTILINE | re.IGNORECASE)
    m = pattern.search(text)
    if not m:
        return []
    section = text[m.end():]
    # Stop at the next H2.
    next_h2 = re.search(r"^##\s", section, re.MULTILINE)
    if next_h2:
        section = section[: next_h2.start()]
    taxa: List[str] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        # Skip header and divider rows.
        if line.startswith("| Taxon") or set(line.replace("|", "").strip()) <= set("-: "):
            continue
        cells = [c.strip().strip("`") for c in line.strip("|").split("|")]
        if not cells:
            continue
        candidate = cells[0]
        # Filter out empty / non-identifier rows. Allow dots (e.g. `pre-1.22`).
        if candidate and re.match(r"^[a-z0-9][a-z0-9\-_.]+$", candidate):
            taxa.append(candidate)
    # De-duplicate while preserving order.
    seen: Dict[str, None] = OrderedDict()
    for t in taxa:
        seen.setdefault(t, None)
    return list(seen.keys())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def walk_paths(node: Any, prefix: str = "") -> Iterable[Tuple[str, Any]]:
    """Yield (dotted_path, leaf_value) for every leaf in `node`."""
    if isinstance(node, dict):
        for k, v in node.items():
            sub = f"{prefix}.{k}" if prefix else str(k)
            yield from walk_paths(v, sub)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            sub = f"{prefix}[{i}]"
            yield from walk_paths(v, sub)
    else:
        yield prefix, node


# Fields where `custom` is an enum value (per behavior-taxonomy.md). Each entry is
# the dotted path of the field carrying the enum; for list-elements we use the
# trailing `[].kind` / `[].method` / `[]` marker to indicate per-item leaves.
CUSTOM_ENABLED_FIELDS = (
    # Rules-list fields
    "code.make_requests.batching.rules[].kind",
    "code.make_bids.bid_type_resolution.method_chain[].method",
    # Scalar enum fields
    "code.make_requests.request_body.kind",
    "code.make_requests.imp_ext_unmarshal.kind",
    "code.make_requests.endpoint_resolution.kind",
    "code.make_bids.response_type",
    "code.make_bids.http_status_handling.kind",
    "code.make_bids.application_status_handling.kind",
    "bidder_info.endpoint_construction.kind",
    "headers_constructed.authentication_kind",
    "tests.go_directory_naming",
    "tests.java_it_folder_naming",
    "ext_pojo_construction.custom_unmarshal.kind",
    # List-of-enum fields
    "params.schema_interpretation.combinators_used[]",
)


def find_custom_values(spec: Spec) -> List[str]:
    """Return dotted paths where the enum value is `custom`."""
    findings: List[str] = []
    for dotted, value in walk_paths(spec.raw):
        if value != "custom":
            continue
        # Filter to only paths that match a known enum field pattern.
        normalized = re.sub(r"\[\d+\]", "[]", dotted)
        for field_pattern in CUSTOM_ENABLED_FIELDS:
            if normalized == field_pattern:
                findings.append(dotted)
                break
        else:
            # Unknown path emitted `custom` — still surface it; it's a fishy state.
            findings.append(dotted)
    return findings


# ---------------------------------------------------------------------------
# R1: file-reachability
# ---------------------------------------------------------------------------


# Plausible path prefixes per language (purely structural validation).
GO_PATH_PREFIXES = (
    "adapters/",
    "openrtb_ext/",
    "config/",
    "static/",
    "macros/",
    "endpoints/",
    "exchange/",
    "errortypes/",
    "metrics/",
    "yaml/",
    "test/",
)
JAVA_PATH_PREFIXES = (
    "src/main/",
    "src/test/",
)
# Special filenames seen in goldens (bare basenames without a directory).
PLAUSIBLE_BARE_BASENAMES = re.compile(r"^[A-Za-z0-9_./\-]+\.(go|java|json|yaml|md|properties)$")


def collect_file_refs(spec: Spec) -> List[Tuple[str, str]]:
    """Return [(yaml_dotted_path, file_path)] for every spec field named `file`."""
    refs: List[Tuple[str, str]] = []
    for dotted, value in walk_paths(spec.raw):
        if not isinstance(value, str):
            continue
        # Match leaves whose key is `file` (possibly inside indexed lists).
        if dotted.endswith(".file") or dotted == "file":
            refs.append((dotted, value))
    return refs


def r1_check(spec: Spec, network_check: bool, gh_cache: Dict[Tuple[str, str], bool]) -> List[Finding]:
    """Validate file-reachability of every `file:` field reference."""
    findings: List[Finding] = []
    refs = collect_file_refs(spec)
    if not refs:
        return [Finding("R1", spec.label, SEV_PASS, "no file refs to check")]
    repo = (spec.get("provenance.source.repo") or "").strip()
    sha = (spec.get("provenance.source.resolved_commit") or "").strip()
    if not repo or not sha:
        return [
            Finding("R1", spec.label, SEV_FAIL, "missing provenance.source.repo or resolved_commit")
        ]
    plausible_prefixes: Tuple[str, ...]
    if spec.language == "go":
        plausible_prefixes = GO_PATH_PREFIXES
    else:
        plausible_prefixes = JAVA_PATH_PREFIXES
    for dotted, path in refs:
        if not path.strip():
            findings.append(Finding("R1", spec.label, SEV_FAIL, f"empty file path at {dotted}"))
            continue
        # Reject paths that contain placeholder syntax that should never reach R1.
        if "{{" in path or "<" in path or "$" in path:
            findings.append(
                Finding(
                    "R1",
                    spec.label,
                    SEV_FAIL,
                    f"unresolved placeholder in file path at {dotted}: {path}",
                )
            )
            continue
        # Reject path traversal — `..` as any segment AND absolute paths are hard fails.
        path_parts = path.split("/")
        if any(p == ".." for p in path_parts) or path.startswith("/"):
            findings.append(
                Finding(
                    "R1",
                    spec.label,
                    SEV_FAIL,
                    f"path traversal/absolute path forbidden at {dotted}: {path}",
                )
            )
            continue
        # Structural plausibility: the path either starts with one of the per-language
        # prefixes, OR is a bare basename inside the adapter directory (e.g., `kobler.go`),
        # OR is a relative path with one of the file extensions we recognise.
        is_plausible = (
            path.startswith(plausible_prefixes)
            or PLAUSIBLE_BARE_BASENAMES.match(path) is not None
        )
        if not is_plausible:
            findings.append(
                Finding(
                    "R1",
                    spec.label,
                    SEV_FAIL,
                    f"implausible file path at {dotted}: {path}",
                )
            )
            continue
        if network_check:
            ok = gh_path_exists(repo, sha, path, gh_cache)
            if ok is None:
                findings.append(
                    Finding(
                        "R1",
                        spec.label,
                        SEV_WARN,
                        f"network check unavailable for {path}",
                    )
                )
            elif ok is False:
                findings.append(
                    Finding(
                        "R1",
                        spec.label,
                        SEV_FAIL,
                        f"file not reachable at {sha[:8]}: {path}",
                    )
                )
    if not findings:
        findings.append(
            Finding(
                "R1",
                spec.label,
                SEV_PASS,
                f"{len(refs)} file refs structurally plausible",
            )
        )
    return findings


def gh_path_exists(
    repo: str, sha: str, path: str, cache: Dict[Tuple[str, str], bool]
) -> Optional[bool]:
    """Best-effort check via `gh api` if `gh` is on PATH; returns None if no network/gh."""
    key = (repo, sha + ":" + path)
    if key in cache:
        return cache[key]
    if shutil.which("gh") is None:
        cache[key] = None  # type: ignore[assignment]
        return None
    try:
        proc = subprocess.run(
            ["gh", "api", f"repos/{repo}/contents/{path}?ref={sha}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, OSError):
        cache[key] = None  # type: ignore[assignment]
        return None
    ok = proc.returncode == 0
    cache[key] = ok
    return ok


# ---------------------------------------------------------------------------
# R2: bidder_params_sha256 integrity
# ---------------------------------------------------------------------------


def r2_check(spec: Spec) -> List[Finding]:
    text = spec.raw.get("bidder_params_json")
    declared = spec.raw.get("bidder_params_sha256")
    if not isinstance(text, str) or not isinstance(declared, str):
        return [
            Finding(
                "R2",
                spec.label,
                SEV_FAIL,
                "bidder_params_json or bidder_params_sha256 missing or non-string",
            )
        ]
    actual = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if actual != declared:
        return [
            Finding(
                "R2",
                spec.label,
                SEV_FAIL,
                f"sha mismatch: computed={actual} declared={declared}",
            )
        ]
    return [Finding("R2", spec.label, SEV_PASS, f"sha={actual[:12]}")]


# ---------------------------------------------------------------------------
# R3: `custom` enum value requires paired quirk
# ---------------------------------------------------------------------------


# Shorthand keywords that should appear in a quirk id/summary if it is the
# corresponding witness for a `custom` enum value at a given path. The lookup
# is best-effort; a custom value with NO quirks at all is always FAIL.
R3_PAIRING_HINTS = {
    "code.make_requests.request_body.kind": (
        "request_body",
        "request-body",
        "request body",
        "custom-request",
        "custom request",
        "non-openrtb",
    ),
    "code.make_bids.response_type": (
        "response",
        "custom-response",
        "custom response",
        "response_type",
        "custom-payload",
    ),
    "code.make_requests.batching.rules": (
        "batching",
        "batched",
        "imp-flatten",
        "flatten",
        "split",
    ),
    "code.make_bids.bid_type_resolution.method_chain": (
        "bid_type",
        "bid-type",
        "method_chain",
        "method-chain",
        "mtype",
        "mediatype",
    ),
    "code.make_requests.imp_ext_unmarshal.kind": (
        "imp_ext",
        "imp-ext",
        "impext",
        "unmarshal",
    ),
    "code.make_requests.endpoint_resolution.kind": (
        "endpoint",
        "url",
        "uri",
    ),
    "code.make_bids.http_status_handling.kind": (
        "status",
        "http",
    ),
    "code.make_bids.application_status_handling.kind": (
        "retcode",
        "status",
        "application",
    ),
    "bidder_info.endpoint_construction.kind": (
        "endpoint",
        "url",
    ),
    "headers_constructed.authentication_kind": (
        "auth",
        "header",
    ),
    "tests.go_directory_naming": (
        "test",
        "directory",
    ),
    "tests.java_it_folder_naming": (
        "test",
        "folder",
        "directory",
    ),
    "ext_pojo_construction.custom_unmarshal.kind": (
        "unmarshal",
        "deserialize",
        "deserializer",
    ),
    "params.schema_interpretation.combinators_used": (
        "combinator",
        "oneof",
        "anyof",
    ),
}


def r3_check(spec: Spec, strict: bool = False) -> List[Finding]:
    customs = find_custom_values(spec)
    quirks = spec.raw.get("quirks") or []
    findings: List[Finding] = []
    if not customs:
        findings.append(Finding("R3", spec.label, SEV_PASS, "no `custom` values"))
        return findings
    if not isinstance(quirks, list) or len(quirks) == 0:
        for path in customs:
            findings.append(
                Finding(
                    "R3",
                    spec.label,
                    SEV_FAIL,
                    f"`custom` at {path} has no paired quirks[] entry",
                )
            )
        return findings
    # In non-strict mode: any non-empty quirks list satisfies pairing for every custom.
    # In strict mode: require at least one quirk whose id/summary contains a hint keyword.
    unpaired: List[str] = []
    for path in customs:
        normalized = re.sub(r"\[\d+\]", "", path)
        # Trim trailing field marker for hint lookup.
        for field, hints in R3_PAIRING_HINTS.items():
            if normalized.startswith(field):
                hint_set = hints
                break
        else:
            hint_set = ()
        if strict and hint_set:
            paired = False
            for q in quirks:
                blob = " ".join(
                    str(q.get(k, "")) for k in ("id", "summary", "edge_case_taxon")
                ).lower()
                if any(h in blob for h in hint_set):
                    paired = True
                    break
            if not paired:
                unpaired.append(path)
        # Non-strict: pairing satisfied by quirks list being non-empty.
    if unpaired:
        for path in unpaired:
            findings.append(
                Finding(
                    "R3",
                    spec.label,
                    SEV_FAIL,
                    f"`custom` at {path}: no quirk summary mentions field; strict pairing failed",
                )
            )
        return findings
    findings.append(
        Finding(
            "R3",
            spec.label,
            SEV_PASS,
            f"{len(customs)} `custom` values, {len(quirks)} quirks (paired)",
        )
    )
    return findings


# ---------------------------------------------------------------------------
# R4: round-trip determinism
# ---------------------------------------------------------------------------


# Fields excluded from the determinism diff per the spec.
DETERMINISM_IGNORED_KEYS = (
    "provenance.read.timestamp_utc",
    "provenance.read.operator",
)


def normalize_for_determinism(spec_raw: Dict[str, Any]) -> Dict[str, Any]:
    """Return a deep copy with the ignored keys deleted."""
    copy = json.loads(json.dumps(spec_raw, sort_keys=True, default=str))

    def delete(obj: Any, dotted: str) -> None:
        parts = dotted.split(".")
        for p in parts[:-1]:
            if not isinstance(obj, dict) or p not in obj:
                return
            obj = obj[p]
        if isinstance(obj, dict):
            obj.pop(parts[-1], None)

    for path in DETERMINISM_IGNORED_KEYS:
        delete(copy, path)
    return copy


def r4_check(spec: Spec) -> List[Finding]:
    """Round-trip determinism: load → normalize → dump three times; assert
    dump2 == dump3 (idempotent under round-trip).

    This catches goldens whose structure shifts under re-serialization
    (sets-as-lists, datetime objects, anchor reuse, non-stable map orderings).
    Compare passes 2 and 3 (not 1 and 2) — pass 1 may differ from passes 2+
    because the original raw spec carries comments / formatting that the YAML
    dumper drops.
    """
    try:
        # Pass 1: spec.raw → normalize → dump.
        norm1 = normalize_for_determinism(spec.raw)
        dump1 = yaml.safe_dump(norm1, sort_keys=True, default_flow_style=False)
        # Pass 2: load dump1 → normalize → dump.
        loaded2 = yaml.safe_load(dump1)
        norm2 = normalize_for_determinism(loaded2)
        dump2 = yaml.safe_dump(norm2, sort_keys=True, default_flow_style=False)
        # Pass 3: load dump2 → normalize → dump.
        loaded3 = yaml.safe_load(dump2)
        norm3 = normalize_for_determinism(loaded3)
        dump3 = yaml.safe_dump(norm3, sort_keys=True, default_flow_style=False)
    except (TypeError, ValueError, yaml.YAMLError) as exc:
        return [Finding("R4", spec.label, SEV_FAIL, f"non-deterministic serialization: {exc}")]
    if dump2 != dump3:
        return [Finding("R4", spec.label, SEV_FAIL,
            "round-trip not idempotent (dump2 != dump3)")]
    return [Finding("R4", spec.label, SEV_PASS, "round-trip idempotent")]


# ---------------------------------------------------------------------------
# R5: cross-language structural parity for port pairs
# ---------------------------------------------------------------------------


def deep_eq(a: Any, b: Any) -> bool:
    """Order-insensitive equality for lists where order is unstable (e.g. combinators_used)."""
    return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


# R5-strict keys: runtime divergence is FAIL (semantic equivalence required across
# languages). When the dual-spec assertion says severity:warn, downgrade to WARN.
# When dual-spec says severity:pass but runtime disagrees → FAIL (stale-pass).
R5_STRICT_KEYS = (
    ("bidder_info.capabilities",                "bidder_info_capabilities"),
    # params.schema_interpretation is decomposed into runtime-invariant
    # subfields only. The whole block contains prose-bearing fields
    # (properties[].description, properties[].notes) that legitimately
    # differ across languages — Java may reference Pattern.matches semantics,
    # Go may reference regexp substring semantics, etc. Comparing the whole
    # block via deep_eq fired stale-pass FAILs on dual-spec assertions that
    # were correctly capturing semantic equivalence (e.g., thetradedesk).
    ("params.schema_interpretation.required_fields",  "params_schema_interpretation"),
    ("params.schema_interpretation.combinators_used", "params_schema_interpretation"),
    ("params.schema_interpretation.flexible_types",   "params_schema_interpretation"),
    ("bidder_info.gvl_vendor_id",               "bidder_info_gvl_vendor_id"),
    ("bidder_info.endpoint_compression",        "bidder_info_endpoint_compression"),
    ("bidder_info.geoscope",                    "bidder_info_geoscope"),
    ("bidder_info.maintainer",                  "bidder_info_maintainer"),
    ("bidder_info.modifying_vast_xml_allowed",  "bidder_info_modifying_vast_xml_allowed"),
)
# R5-divergent keys: legitimate language-idiom divergence. Honor only the
# assertion's severity (no runtime FAIL on divergence).
# - bidder_info.endpoint: macro form differs by language (Go's `{{.X}}` template
#   vs Java's `${X}` / `%s` printf form) — same observable URL post-substitution.
# - bidder_info.endpoint_construction: kind+macros struct mirrors per-language
#   mechanism; Go-template vs String.replace is per-language idiom.
# - bidder_info.default_enabled: Java's edge-case #30 enabled:false opt-in pattern
#   is legitimate (e.g., optidigital).
R5_DIVERGENT_KEYS = (
    ("bidder_info.endpoint",                    "bidder_info_endpoint"),
    ("bidder_info.endpoint_construction",       "bidder_info_endpoint_construction"),
    ("bidder_info.default_enabled",             "bidder_info_default_enabled"),
    ("meta.alias_metadata",                     "alias_metadata"),
    (None,                                      "lifecycle_rename"),
    (None,                                      "port_lineage"),
    (None,                                      "reviewer_cohort"),
    (None,                                      "test_fixture_cost"),
)


def r5_check(go_spec: Optional[Spec], java_spec: Optional[Spec],
             dual_specs: Dict[str, Dict[str, Any]]) -> List[Finding]:
    """Cross-language structural parity. Runtime values are the source of truth;
    the dual-spec assertion is an EXPECTATION verified against runtime, not a
    free pass.

    Polarity contract: runtime takes precedence. When dual-spec says severity:pass
    but runtime values disagree, FAIL — the assertion is stale. Always run
    deep_eq; never short-circuit on the assertion's own claim.
    """
    # Determine bidder name from whichever side has a spec.
    primary = go_spec or java_spec
    if primary is None:
        return []
    bidder = primary.bidder
    findings: List[Finding] = []

    dual = dual_specs.get(bidder) or {}
    raw_assertions = dual.get("assertions") if isinstance(dual.get("assertions"), dict) else {}
    assertions: Dict[str, Any] = raw_assertions if isinstance(raw_assertions, dict) else {}
    overall = dual.get("overall") or {}

    # Honor overall.cross_language_state + blocker_count.
    cls_state = (overall.get("cross_language_state") or "").lower()
    blocker_count = overall.get("blocker_count") or 0
    if cls_state == "divergent-semantic" and isinstance(blocker_count, int) and blocker_count > 0:
        findings.append(Finding(
            "R5", f"pair/{bidder}", SEV_FAIL,
            f"overall.cross_language_state=divergent-semantic with {blocker_count} blocker(s)",
        ))
    elif cls_state.startswith("divergent") and isinstance(blocker_count, int) and blocker_count > 0:
        findings.append(Finding(
            "R5", f"pair/{bidder}", SEV_WARN,
            f"overall.cross_language_state={cls_state} with {blocker_count} blocker(s)",
        ))

    # bidder_params_sha256 — load-bearing R5 contract.
    go_sha = go_spec.raw.get("bidder_params_sha256") if go_spec else None
    java_sha = java_spec.raw.get("bidder_params_sha256") if java_spec else None
    sha_assert = assertions.get("bidder_params_sha256") if isinstance(assertions, dict) else None

    if go_spec is not None and java_spec is not None:
        if go_sha == java_sha and go_sha is not None:
            findings.append(Finding("R5", f"pair/{bidder}", SEV_PASS,
                f"bidder_params_sha256 equal ({go_sha[:12]})"))
        else:
            # Runtime SHAs disagree. Determine severity from the dual-spec
            # assertion if present.
            severity = SEV_WARN
            explanation = "differs"
            if isinstance(sha_assert, dict):
                sev = (sha_assert.get("severity") or "").lower()
                if sev in ("fail", "error"):
                    severity = SEV_FAIL
                elif sev == "pass":
                    # POLARITY INVERSION: runtime says different but dual-spec
                    # claims byte_equal — the assertion is stale. FAIL.
                    severity = SEV_FAIL
                    explanation = "stale-pass-assertion (dual-spec claims byte_equal but runtime SHAs differ)"
                elif sev in ("warn", "warning"):
                    severity = SEV_WARN
                if explanation == "differs":
                    kind = sha_assert.get("divergence_kind") or ""
                    if sha_assert.get("semantically_equal") is True:
                        explanation = f"byte-only divergence ({kind})" if kind else "byte-only divergence"
                    elif sha_assert.get("semantically_equal") is False:
                        explanation = f"semantic divergence ({kind})" if kind else "semantic divergence"
                    else:
                        explanation = kind or explanation
            else:
                # Heuristic fallback: scan quirks for byte-vs-semantic signals.
                blobs = [
                    " ".join(str(q.get(k, "")) for k in ("id", "summary", "edge_case_taxon")).lower()
                    for q in (go_spec.raw.get("quirks") or []) + (java_spec.raw.get("quirks") or [])
                    if isinstance(q, dict)
                ]
                byte_divergence = any("byte" in b and "divergen" in b for b in blobs)
                semantic_divergence = any(
                    "semantic" in b and "divergen" in b
                    and "semantically identical" not in b
                    and "semantic match" not in b
                    for b in blobs
                )
                if semantic_divergence:
                    severity = SEV_FAIL
                    explanation = "semantic divergence (per quirk)"
                elif byte_divergence:
                    severity = SEV_WARN
                    explanation = "whitespace/byte divergence (per quirk)"
            findings.append(Finding("R5", f"pair/{bidder}", severity,
                f"bidder_params_sha256 {explanation}: go={go_sha or 'none'} java={java_sha or 'none'}"))
    elif sha_assert is not None:
        # One side missing a fixture; surface the asymmetry (PASS — informational).
        findings.append(Finding("R5", f"pair/{bidder}", SEV_PASS,
            f"only-one-side fixture; dual-spec sha-assertion noted (severity={sha_assert.get('severity', '?') if isinstance(sha_assert, dict) else '?'})"))

    # R5-strict keys: runtime divergence FAILs unless dual-spec downgrades to WARN.
    for spec_field, dual_key in R5_STRICT_KEYS:
        if go_spec is None or java_spec is None:
            continue
        a = go_spec.get(spec_field)
        b = java_spec.get(spec_field)
        if a is None and b is None:
            continue
        dual_assert = assertions.get(dual_key) if isinstance(assertions, dict) else None
        if not deep_eq(a, b):
            severity = SEV_FAIL
            stale = False
            if isinstance(dual_assert, dict):
                sev = (dual_assert.get("severity") or "").lower()
                if sev in ("warn", "warning"):
                    severity = SEV_WARN
                elif sev == "pass":
                    stale = True
            if stale:
                findings.append(Finding(
                    "R5", f"pair/{bidder}", SEV_FAIL,
                    f"{spec_field} runtime divergence but dual-spec claims pass — stale",
                ))
            else:
                findings.append(Finding("R5", f"pair/{bidder}", severity,
                    f"{spec_field} differs across languages"))

    # R5-divergent keys: honor only the assertion severity. No runtime FAIL.
    for spec_field, dual_key in R5_DIVERGENT_KEYS:
        dual_assert = assertions.get(dual_key) if isinstance(assertions, dict) else None
        if not isinstance(dual_assert, dict):
            continue
        sev = (dual_assert.get("severity") or "").lower()
        summary = dual_assert.get("divergence_summary") or "divergent per dual-spec"
        if sev in ("fail", "error"):
            findings.append(Finding("R5", f"pair/{bidder}", SEV_FAIL, f"{dual_key}: {summary}"))
        elif sev in ("warn", "warning"):
            findings.append(Finding("R5", f"pair/{bidder}", SEV_WARN, f"{dual_key}: {summary}"))

    return findings


# ---------------------------------------------------------------------------
# R6: bidder_name == package_name
# ---------------------------------------------------------------------------


def r6_check(spec: Spec) -> List[Finding]:
    bidder_name = (spec.get("meta.bidder_name") or "").strip()
    if not bidder_name:
        return [Finding("R6", spec.label, SEV_FAIL, "missing meta.bidder_name")]
    cl = spec.raw.get("cross_language") or {}
    go_arts = cl.get("go_artifacts") or {}
    java_arts = cl.get("java_artifacts") or {}
    pkg = go_arts.get("package_name")
    java_dir = java_arts.get("bidder_dir") or ""
    java_dir_basename = java_dir.rstrip("/").rsplit("/", 1)[-1]
    findings: List[Finding] = []
    # Detect rebrand acknowledgment once — used by both package_name and
    # bidder_constant checks to suppress false-positive findings.
    warnings = spec.get("provenance.warnings") or []
    rebrand = any(
        (w.get("type") or "").startswith("bidder-name-rebrand")
        for w in warnings if isinstance(w, dict)
    )
    # Alias suppression: when meta.is_alias=true, cross_language artifacts
    # route through the parent's package/dir (Go aliases live under the
    # parent's adapters/<parent>/ package; Java alias-only YAMLs register
    # under the parent's bidder dir). Compare package_name and bidder_dir
    # against meta.alias_of (the parent), not the alias's own bidder_name.
    is_alias = bool(spec.get("meta.is_alias"))
    alias_of = (spec.get("meta.alias_of") or "").strip()
    expected_pkg_name = alias_of if (is_alias and alias_of) else bidder_name
    alias_note = f" (parent={alias_of})" if is_alias and alias_of else ""
    if pkg and pkg != expected_pkg_name:
        # Real-world divergence: msft uses BidderMicrosoft constant but bidder dir is msft.
        # The test is package_name == bidder_name (or alias's parent); package_name
        # should match the directory the adapter code lives in.
        findings.append(
            Finding(
                "R6",
                spec.label,
                SEV_WARN,
                f"meta.bidder_name={bidder_name} != go_artifacts.package_name={pkg}{alias_note}",
            )
        )
    if java_dir_basename and java_dir_basename.lower() != expected_pkg_name.lower():
        findings.append(
            Finding(
                "R6",
                spec.label,
                SEV_WARN,
                f"meta.bidder_name={bidder_name} != java_artifacts.bidder_dir basename={java_dir_basename}{alias_note}",
            )
        )
    # Validate cross_language.go_artifacts.bidder_constant on Go-source specs.
    # For aliases, inherit the parent's expected constant.
    bidder_constant = go_arts.get("bidder_constant") or ""
    expected_constant = f"openrtb_ext.Bidder{expected_pkg_name.capitalize()}"
    if bidder_constant and bidder_constant.lower() != expected_constant.lower() and not rebrand:
        findings.append(
            Finding(
                "R6", spec.label, SEV_WARN,
                f"go_artifacts.bidder_constant={bidder_constant} != expected {expected_constant}",
            )
        )
    if not findings:
        findings.append(Finding("R6", spec.label, SEV_PASS, f"bidder_name={bidder_name}"))
    return findings


# ---------------------------------------------------------------------------
# R7: bidder-constant-mismatch detection (warn, not fail)
# ---------------------------------------------------------------------------


def r7_check(spec: Spec) -> List[Finding]:
    """Surface bidder-constant-mismatch on three surfaces:
    (1) params.params_test.bidder_constant_referenced ≠ canonical (Go-only);
    (2) provenance.warnings[].type == bidder-constant-mismatch;
    (3) quirks[].edge_case_taxon == bidder-constant-mismatch.

    Each occurrence becomes a separate WARN finding. Kobler's two copy-paste
    bugs (kobler_test.go:12 BidderKargo + params_test.go:47 BidderKrushmedia)
    surface as two findings — surfaces 2 and 1 respectively.
    """
    findings: List[Finding] = []
    warnings = spec.get("provenance.warnings") or []
    rebrand = any(
        (w.get("type") or "").startswith("bidder-name-rebrand")
        for w in warnings if isinstance(w, dict)
    )

    # Surfaces 2 & 3 apply regardless of language — Java specs can carry
    # bidder-constant-mismatch quirks (kobler-java has 2 such quirks
    # documenting the Go-side bugs).
    for w in warnings:
        if isinstance(w, dict) and (w.get("type") or "") == "bidder-constant-mismatch":
            location = f"{w.get('file', '?')}:{w.get('line', '?')}"
            findings.append(Finding(
                "R7", spec.label, SEV_WARN,
                f"bidder-constant-mismatch warning at {location}: {w.get('summary', '')}",
            ))
    for q in (spec.raw.get("quirks") or []):
        if isinstance(q, dict) and q.get("edge_case_taxon") == "bidder-constant-mismatch":
            findings.append(Finding(
                "R7", spec.label, SEV_WARN,
                f"bidder-constant-mismatch quirk: {q.get('id', '?')} — {q.get('summary', '')}",
            ))

    # Surface 1: params_test.bidder_constant_referenced (Go-only — Java has no constant).
    if spec.language == "go":
        bidder = (spec.get("meta.bidder_name") or "").strip()
        referenced = spec.get("params.params_test.bidder_constant_referenced")
        if bidder and referenced:
            expected_a = f"openrtb_ext.Bidder{bidder.capitalize()}"
            if not referenced.startswith("openrtb_ext.Bidder"):
                findings.append(Finding("R7", spec.label, SEV_WARN,
                    f"unexpected constant: {referenced}"))
            elif referenced.lower() != expected_a.lower() and not rebrand:
                findings.append(Finding(
                    "R7", spec.label, SEV_WARN,
                    f"bidder-constant-mismatch (params_test): referenced={referenced} expected≈{expected_a}",
                ))

    if not findings:
        findings.append(Finding("R7", spec.label, SEV_PASS, "no bidder-constant-mismatch surfaces"))
    return findings


# ---------------------------------------------------------------------------
# R8: endpoint placeholder unresolved warnings
# ---------------------------------------------------------------------------


# Macros known to the prebid-server-go macros.EndpointTemplateParams (subset; canonical).
GO_TEMPLATE_MACROS = {
    "AccountID",
    "AdUnit",
    "BidderCode",
    "GvlID",
    "Host",
    "MediaType",
    "PageID",
    "PartnerID",
    "PlacementID",
    "PublisherID",
    "RegionID",
    "SiteID",
    "SourceID",
    "TagID",
    "Username",
    "ZoneID",
}
# Java template macros (used in URL replacement). These are not Go-template-formatted.
JAVA_TEMPLATE_MACROS = {
    "PREBID_SERVER_ENDPOINT",
    "AdUnit",
    "Host",
    "PartnerId",
    "PageID",
    "PartnerCode",
    "PublisherId",
    "RegionId",
    "ZoneId",
    "AccountId",
    "Source",
    "GvlId",
}
PLACEHOLDER_RE = re.compile(r"\{\{\.?([A-Za-z_][A-Za-z0-9_]*)\}\}|#\{([A-Za-z_][A-Za-z0-9_]*)\}#|\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def r8_check(spec: Spec) -> List[Finding]:
    endpoint = spec.get("bidder_info.endpoint") or ""
    if not isinstance(endpoint, str) or not endpoint:
        return [Finding("R8", spec.label, SEV_PASS, "no endpoint")]
    matches = list(PLACEHOLDER_RE.finditer(endpoint))
    if not matches:
        return [Finding("R8", spec.label, SEV_PASS, "no placeholder")]
    macros = GO_TEMPLATE_MACROS if spec.language == "go" else JAVA_TEMPLATE_MACROS
    warnings = spec.get("provenance.warnings") or []
    has_warning = any(
        (w.get("type") or "") == "endpoint-placeholder-unresolved"
        for w in warnings
        if isinstance(w, dict)
    )
    deploy_tokens = {
        (t.get("token") or "")
        for t in (spec.get("deploy_time_tokens") or [])
        if isinstance(t, dict)
    }
    findings: List[Finding] = []
    for m in matches:
        name = m.group(1) or m.group(2) or m.group(3)
        if not name:
            continue
        if name in macros or name in deploy_tokens:
            continue
        if has_warning:
            findings.append(
                Finding(
                    "R8",
                    spec.label,
                    SEV_PASS,
                    f"placeholder {{{{.{name}}}}} unrecognised but warning emitted",
                )
            )
        else:
            findings.append(
                Finding(
                    "R8",
                    spec.label,
                    SEV_WARN,
                    f"placeholder {{{{.{name}}}}} not in macro registry and no provenance warning",
                )
            )
    if not findings:
        findings.append(Finding("R8", spec.label, SEV_PASS, "all placeholders recognised"))
    return findings


# ---------------------------------------------------------------------------
# R3b: quirk taxa registry (renamed from R9 — see CHANGELOG of Wave 4)
# ---------------------------------------------------------------------------


def r_taxa_check(spec: Spec, registered: List[str], lenient: bool = False) -> List[Finding]:
    """R3b: every quirks[].edge_case_taxon must be in the closed registry.

    Each violation becomes a separate Finding (split per-spec — was previously
    joined into a single ;-delimited detail string >1000 chars). Empty quirks
    list → PASS.
    """
    quirks = spec.raw.get("quirks") or []
    if not isinstance(quirks, list):
        return [Finding("R3b", spec.label, SEV_FAIL, "quirks is not a list")]
    if not quirks:
        return [Finding("R3b", spec.label, SEV_PASS, "no quirks")]
    if not registered:
        return [Finding("R3b", spec.label, SEV_WARN,
            "could not load taxa registry from behavior-taxonomy.md — skipped")]
    findings: List[Finding] = []
    bad_severity = SEV_WARN if lenient else SEV_FAIL
    for i, q in enumerate(quirks):
        if not isinstance(q, dict):
            findings.append(Finding("R3b", spec.label, bad_severity,
                f"quirk #{i}: not a mapping"))
            continue
        taxon = q.get("edge_case_taxon")
        qid = q.get("id", "?")
        if taxon is None or taxon == "":
            findings.append(Finding("R3b", spec.label, bad_severity,
                f"quirk #{i} ({qid}): missing edge_case_taxon"))
            continue
        if taxon not in registered:
            findings.append(Finding("R3b", spec.label, bad_severity,
                f"quirk #{i} ({qid}): unregistered taxon `{taxon}`"))
    if not findings:
        findings.append(Finding("R3b", spec.label, SEV_PASS,
            f"{len(quirks)} quirks, all taxa registered"))
    return findings


# ---------------------------------------------------------------------------
# R9: legacy encoding/json direct-usage detection
# ---------------------------------------------------------------------------


def r9_check(spec: Spec) -> List[Finding]:
    """R9: detect Go specs that use encoding/json directly (no jsonutil) without
    a paired quirk/warning surfacing the legacy pattern.

    Walks code.imports.has_jsonutil + code.file_layout.files[].uses_marshal.
    When direct json.Marshal usage is detected without a paired
    legacy-encoding-json-direct-usage quirk OR warning, surface a finding so
    reviewers know to flag.
    """
    if spec.language != "go":
        return [Finding("R9", spec.label, SEV_PASS, "skip — Java spec")]
    findings: List[Finding] = []
    has_jsonutil = spec.get("code.imports.has_jsonutil")
    files = spec.get("code.file_layout.files") or []
    uses_marshal = [
        f.get("name") or f.get("path", "?") for f in files
        if isinstance(f, dict) and f.get("uses_marshal") is True
    ]
    has_quirk = any(
        (q.get("edge_case_taxon") or "") == "legacy-encoding-json-direct-usage"
        for q in (spec.raw.get("quirks") or []) if isinstance(q, dict)
    )
    has_warning = any(
        (w.get("type") or "") == "legacy-encoding-json-direct-usage"
        for w in (spec.get("provenance.warnings") or []) if isinstance(w, dict)
    )
    if has_jsonutil is False and uses_marshal and not (has_quirk or has_warning):
        for path in uses_marshal:
            findings.append(Finding(
                "R9", spec.label, SEV_WARN,
                f"legacy encoding/json usage at {path} but no quirk/warning surfaced",
            ))
    if not findings:
        findings.append(Finding("R9", spec.label, SEV_PASS, "no legacy encoding/json drift"))
    return findings


# ---------------------------------------------------------------------------
# R10: tests.uses_canonical_harness == false triggers warning
# ---------------------------------------------------------------------------


def r10_check(spec: Spec) -> List[Finding]:
    is_alias = bool(spec.get("meta.is_alias"))
    tests = spec.raw.get("tests")
    if is_alias and tests is None:
        # Aliases inherit the parent's tests block; harness flag is N/A.
        return [Finding("R10", spec.label, SEV_PASS, "alias spec; tests inherited from parent")]
    uses = spec.get("tests.uses_canonical_harness")
    warnings = spec.get("provenance.warnings") or []
    has_warning = any(
        (w.get("type") or "") == "legacy-test-helpers-imported"
        for w in warnings
        if isinstance(w, dict)
    )
    has_quirk = any(
        (q.get("edge_case_taxon") or "") == "legacy-test-helpers-imported"
        for q in (spec.raw.get("quirks") or [])
        if isinstance(q, dict)
    )
    if uses is None:
        return [Finding("R10", spec.label, SEV_FAIL, "tests.uses_canonical_harness missing")]
    if uses is True:
        return [Finding("R10", spec.label, SEV_PASS, "uses_canonical_harness=true")]
    # uses_canonical_harness == False: must surface as warning OR quirk.
    if has_warning or has_quirk:
        return [
            Finding(
                "R10",
                spec.label,
                SEV_PASS,
                "uses_canonical_harness=false; warning/quirk present",
            )
        ]
    return [
        Finding(
            "R10",
            spec.label,
            SEV_FAIL,
            "uses_canonical_harness=false but no legacy-test-helpers-imported warning/quirk",
        )
    ]


# ---------------------------------------------------------------------------
# Dual-spec assertions loader
# ---------------------------------------------------------------------------


def load_dual_specs() -> Dict[str, Dict[str, Any]]:
    """Load every dual-spec assertion file. Returns {bidder: yaml_doc}."""
    out: Dict[str, Dict[str, Any]] = {}
    if not os.path.isdir(DUAL_SPECS_DIR):
        return out
    for path in sorted(glob.glob(os.path.join(DUAL_SPECS_DIR, "*.dual-spec-assertions.yaml"))):
        bidder = os.path.basename(path).replace(".dual-spec-assertions.yaml", "")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                doc = yaml.safe_load(fh)
            if isinstance(doc, dict):
                out[bidder] = doc
        except (OSError, yaml.YAMLError) as exc:
            print(f"WARN: cannot load dual-spec {path}: {exc}", file=sys.stderr)
    return out


# ---------------------------------------------------------------------------
# Aggregation + reporting
# ---------------------------------------------------------------------------


RULE_ORDER = ["R1", "R2", "R3", "R3b", "R4", "R5", "R6", "R7", "R8", "R9", "R10"]


def aggregate(findings: List[Finding]) -> Dict[str, Dict[str, int]]:
    """Return {rule: {pass: N, warn: N, fail: N}}."""
    counts: Dict[str, Dict[str, int]] = {}
    for f in findings:
        bucket = counts.setdefault(f.rule, {SEV_PASS: 0, SEV_WARN: 0, SEV_FAIL: 0, SEV_SKIP: 0})
        bucket[f.severity] += 1
    return counts


def render_text(
    findings: List[Finding],
    spec_count: int,
    pair_count: int,
    dual_count: int,
    counts: Dict[str, Dict[str, int]],
    show_all: bool,
) -> Tuple[str, int]:
    lines: List[str] = []
    lines.append("=== Round-trip CI: read-skill suite ===")
    lines.append(
        f"Goldens checked: {spec_count} ({pair_count} port pairs, {dual_count} dual-spec assertions)"
    )
    lines.append("")
    # Rule labels are short for table-formatting; documented enforcement
    # caveats below. Wave 11b will tighten the actual checks; until then,
    # readers should treat the labels as advisory:
    #
    # R3 — labeled "custom-quirk pairing" but in DEFAULT mode (no
    #      --strict-r3) treats ANY non-empty quirks[] list as paired for
    #      every `custom` enum value. Pass --strict-r3 for keyword-pairing
    #      enforcement (CI does NOT pass --strict-r3 by default).
    # R5 — labeled "cross-language structural parity" but Wave 1's
    #      prose-key decomposition only covers `params.schema_interpretation`.
    #      Other R5_STRICT_KEYS entries (geoscope list-order,
    #      maintainer alt-fields, capabilities set-equality) may emit
    #      stale-FAIL on legitimate divergence. See Wave 11b plan B5.
    # R8 — labeled "endpoint placeholder unresolved" but checks ONLY
    #      `bidder_info.endpoint`. ADR-007 F1 multi-endpoints
    #      (`code.make_requests.endpoint_resolution.endpoints[*]`) and
    #      dynamic-template URLs in headers are NOT walked. See Wave 11b
    #      plan B5 finding-7.
    rule_descriptions = {
        "R1": "file-reachability",
        "R2": "sha integrity",
        "R3": "custom-quirk pairing (advisory; --strict-r3 to enforce)",
        "R3b": "quirk taxa registered",
        "R4": "round-trip determinism",
        "R5": "cross-language structural parity (subset; see Wave 11b)",
        "R6": "bidder_name / package / constant",
        "R7": "bidder-constant-mismatch surfaces",
        "R8": "endpoint placeholder (bidder_info.endpoint only)",
        "R9": "legacy encoding/json direct usage",
        "R10": "canonical-harness flag",
    }
    for rule in RULE_ORDER:
        bucket = counts.get(rule, {})
        p = bucket.get(SEV_PASS, 0)
        w = bucket.get(SEV_WARN, 0)
        f_ = bucket.get(SEV_FAIL, 0)
        s = bucket.get(SEV_SKIP, 0)
        total = p + w + f_ + s
        line = f"{rule} {rule_descriptions[rule]:<35s} pass={p} warn={w} fail={f_}"
        if s:
            line += f" skip={s}"
        line += f" (n={total})"
        lines.append(line)
    lines.append("")
    # Detail block: surface every WARN/FAIL (and PASS too if --verbose).
    detail_lines: List[str] = []
    for f in findings:
        if f.severity in (SEV_WARN, SEV_FAIL) or show_all:
            detail_lines.append(f.short())
    if detail_lines:
        lines.append("--- findings ---")
        lines.extend(detail_lines)
        lines.append("")
    total_fail = sum(c.get(SEV_FAIL, 0) for c in counts.values())
    total_warn = sum(c.get(SEV_WARN, 0) for c in counts.values())
    if total_fail:
        lines.append(f"OVERALL: {total_fail} failure(s), {total_warn} warning(s)")
    elif total_warn:
        lines.append(f"OVERALL: 0 failures, {total_warn} warning(s)")
    else:
        lines.append("OVERALL: all checks pass")
    if total_fail:
        exit_code = 1
    elif total_warn:
        exit_code = 2
    else:
        exit_code = 0
    lines.append(f"EXIT CODE: {exit_code}")
    return "\n".join(lines), exit_code


def render_json(
    findings: List[Finding],
    spec_count: int,
    pair_count: int,
    dual_count: int,
    counts: Dict[str, Dict[str, int]],
) -> Tuple[str, int]:
    total_fail = sum(c.get(SEV_FAIL, 0) for c in counts.values())
    total_warn = sum(c.get(SEV_WARN, 0) for c in counts.values())
    if total_fail:
        exit_code = 1
    elif total_warn:
        exit_code = 2
    else:
        exit_code = 0
    payload = {
        "goldens_checked": spec_count,
        "port_pairs": pair_count,
        "dual_specs": dual_count,
        "rules": {
            rule: {
                "pass": counts.get(rule, {}).get(SEV_PASS, 0),
                "warn": counts.get(rule, {}).get(SEV_WARN, 0),
                "fail": counts.get(rule, {}).get(SEV_FAIL, 0),
                "skip": counts.get(rule, {}).get(SEV_SKIP, 0),
            }
            for rule in RULE_ORDER
        },
        "findings": [
            {"rule": f.rule, "spec": f.spec, "severity": f.severity, "detail": f.detail}
            for f in findings
        ],
        "summary": {
            "fail": total_fail,
            "warn": total_warn,
            "exit_code": exit_code,
        },
    }
    return json.dumps(payload, indent=2, sort_keys=False), exit_code


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-parseable JSON instead of human-readable text",
    )
    parser.add_argument(
        "--check-network",
        action="store_true",
        help="Run R1 against GitHub via `gh api` (requires authenticated gh)",
    )
    parser.add_argument(
        "--strict-r3",
        action="store_true",
        help="Require quirk id/summary keyword pairing for every `custom` enum value",
    )
    parser.add_argument(
        "--lenient-r9",
        action="store_true",
        help="Downgrade unregistered taxa from FAIL to WARN (use while taxonomy lags goldens)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print every finding (including PASS) in text mode",
    )
    parser.add_argument(
        "--allow-known-broken-pairs",
        default="",
        metavar="LIST",
        help=(
            "Comma-separated list of cross-language-pair bidder names "
            "whose dual-spec FAILs are downgraded to informational (do not "
            "set exit code 1). Used in CI to admit intentional severity:fail "
            "assertions while still gating on unexpected regressions."
        ),
    )
    args = parser.parse_args(argv)
    known_broken = {
        b.strip() for b in (args.allow_known_broken_pairs or "").split(",")
        if b.strip()
    }

    specs = discover_specs()
    if not specs:
        print(
            "ERROR: no goldens found under prebid-server-{go,java}/read/test-fixtures/",
            file=sys.stderr,
        )
        return 1

    # Index by bidder per-language for R5 pairing.
    by_lang_bidder: Dict[Tuple[str, str], Spec] = {(s.language, s.bidder): s for s in specs}
    go_bidders = {s.bidder for s in specs if s.language == "go"}
    java_bidders = {s.bidder for s in specs if s.language == "java"}
    pair_bidders = sorted(go_bidders & java_bidders)

    registered_taxa = parse_taxa_registry(TAXONOMY_PATH)
    dual_specs = load_dual_specs()

    findings: List[Finding] = []
    gh_cache: Dict[Tuple[str, str], bool] = {}

    # Per-spec rules — wrap each call in try/except so a crash on one rule
    # doesn't void the others, and a crash on one spec doesn't void the run.
    per_spec_rules = [
        ("R1",  lambda s: r1_check(s, args.check_network, gh_cache)),
        ("R2",  r2_check),
        ("R3",  lambda s: r3_check(s, strict=args.strict_r3)),
        ("R3b", lambda s: r_taxa_check(s, registered_taxa, lenient=args.lenient_r9)),
        ("R4",  r4_check),
        ("R6",  r6_check),
        ("R7",  r7_check),
        ("R8",  r8_check),
        ("R9",  r9_check),
        ("R10", r10_check),
    ]
    for spec in specs:
        for rule_name, fn in per_spec_rules:
            try:
                findings.extend(fn(spec))
            except Exception as exc:  # noqa: BLE001
                findings.append(Finding(
                    rule_name, spec.label, SEV_FAIL,
                    f"rule crashed: {type(exc).__name__}: {exc}",
                ))

    # R5: per port pair OR per dual-spec entry (run even when one side is missing).
    all_r5_bidders = sorted(set(pair_bidders) | set(dual_specs.keys()))
    for bidder in all_r5_bidders:
        go_spec = by_lang_bidder.get(("go", bidder))
        java_spec = by_lang_bidder.get(("java", bidder))
        try:
            findings.extend(r5_check(go_spec, java_spec, dual_specs))
        except Exception as exc:  # noqa: BLE001
            findings.append(Finding(
                "R5", f"pair/{bidder}", SEV_FAIL,
                f"rule crashed: {type(exc).__name__}: {exc}",
            ))
    if not all_r5_bidders:
        findings.append(Finding("R5", "n/a", SEV_PASS, "no port pairs to compare"))

    # Apply --allow-known-broken-pairs: downgrade FAIL→WARN for findings whose
    # spec label is `pair/<bidder>` or `<lang>/<bidder>` for any bidder in the
    # known-broken list. The pair file's intentional severity:fail still
    # surfaces in output (now as WARN) but doesn't drive the exit code to 1.
    if known_broken:
        downgraded = []
        for f in findings:
            spec_bidder = f.spec.split("/", 1)[-1] if "/" in f.spec else f.spec
            if f.severity == SEV_FAIL and spec_bidder in known_broken:
                downgraded.append(Finding(
                    f.rule, f.spec, SEV_WARN,
                    f.detail + " [downgraded by --allow-known-broken-pairs]",
                ))
            else:
                downgraded.append(f)
        findings = downgraded

    counts = aggregate(findings)

    if args.json:
        text, code = render_json(findings, len(specs), len(pair_bidders), len(dual_specs), counts)
    else:
        text, code = render_text(
            findings,
            len(specs),
            len(pair_bidders),
            len(dual_specs),
            counts,
            show_all=args.verbose,
        )
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
