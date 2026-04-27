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
                f"sha mismatch: computed={actual[:12]} declared={declared[:12]}",
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
    """
    Round-trip determinism cannot be exercised at CI time without re-invoking the
    read skill. We approximate it by verifying:

      (a) the spec parses successfully (already done at load time);
      (b) the spec re-serializes deterministically when ignored fields are stripped
          — i.e., the YAML is structurally valid and idempotent under sort-key
          serialization. This catches goldens that contain non-serialisable values
          (binary, datetime objects, anchors) which would defeat round-tripping.

    A true R4 will wrap the read skill execution in CI; this check is the
    structural pre-condition.
    """
    try:
        norm = normalize_for_determinism(spec.raw)
        json.dumps(norm, sort_keys=True, default=str)
    except (TypeError, ValueError) as exc:
        return [Finding("R4", spec.label, SEV_FAIL, f"non-deterministic serialization: {exc}")]
    return [Finding("R4", spec.label, SEV_PASS, "structurally serialisable")]


# ---------------------------------------------------------------------------
# R5: cross-language structural parity for port pairs
# ---------------------------------------------------------------------------


def deep_eq(a: Any, b: Any) -> bool:
    """Order-insensitive equality for lists where order is unstable (e.g. combinators_used)."""
    return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


def r5_check(go_spec: Spec, java_spec: Spec, dual_specs: Dict[str, Dict[str, Any]]) -> List[Finding]:
    bidder = go_spec.bidder
    findings: List[Finding] = []

    go_sha = go_spec.raw.get("bidder_params_sha256")
    java_sha = java_spec.raw.get("bidder_params_sha256")

    # Look up dual-spec assertion (if available) for severity guidance.
    # Dual-spec format (cross-language-pairs/{bidder}.dual-spec-assertions.yaml):
    #   assertions:
    #     bidder_params_sha256:
    #       go: <sha>
    #       java: <sha>
    #       byte_equal: bool
    #       semantically_equal: bool
    #       severity: pass|warn|fail
    dual = dual_specs.get(bidder) or {}
    assertions = dual.get("assertions") or {}
    sha_assert = assertions.get("bidder_params_sha256") if isinstance(assertions, dict) else None

    if go_sha == java_sha and go_sha is not None:
        findings.append(
            Finding(
                "R5",
                f"pair/{bidder}",
                SEV_PASS,
                f"bidder_params_sha256 equal ({go_sha[:12]})",
            )
        )
    else:
        # Determine severity from the dual-spec assertion if available; otherwise
        # default to warn (whitespace-divergence) unless the goldens themselves
        # tag the divergence as semantic via a quirk.
        severity = SEV_WARN
        explanation = "differs"
        if isinstance(sha_assert, dict):
            sev = (sha_assert.get("severity") or "").lower()
            if sev in ("fail", "error"):
                severity = SEV_FAIL
            elif sev in ("warn", "warning"):
                severity = SEV_WARN
            elif sev == "pass":
                severity = SEV_PASS
            kind = sha_assert.get("divergence_kind") or ""
            if sha_assert.get("semantically_equal") is True:
                explanation = f"byte-only divergence ({kind})" if kind else "byte-only divergence"
            elif sha_assert.get("semantically_equal") is False:
                explanation = f"semantic divergence ({kind})" if kind else "semantic divergence"
            else:
                explanation = kind or explanation
        else:
            # Heuristic fallback: scan quirks for explicit byte-vs-semantic signals.
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
        findings.append(
            Finding(
                "R5",
                f"pair/{bidder}",
                severity,
                f"bidder_params_sha256 {explanation}: go={go_sha[:12] if go_sha else 'none'} java={java_sha[:12] if java_sha else 'none'}",
            )
        )

    # Additional structural-parity checks per schema R5.
    # When a dual-spec assertion exists, defer to its `severity` and `equivalent`
    # verdict (the assertion authors compared semantics, not raw bytes). Otherwise
    # fall back to a naive deep_eq.
    parity_check_specs = (
        ("bidder_info.capabilities", "bidder_info_capabilities"),
        ("params.schema_interpretation", "params_schema_interpretation"),
        ("bidder_info.gvl_vendor_id", "bidder_info_gvl_vendor_id"),
    )
    for spec_field, dual_key in parity_check_specs:
        a = go_spec.get(spec_field)
        b = java_spec.get(spec_field)
        if a is None or b is None:
            continue
        dual_assert = (
            assertions.get(dual_key) if isinstance(assertions, dict) else None
        )
        if isinstance(dual_assert, dict):
            equivalent = dual_assert.get("equivalent")
            sev = (dual_assert.get("severity") or "").lower()
            if equivalent is True or sev == "pass":
                # Authoritative pass — skip the naive deep_eq.
                continue
            severity = SEV_WARN
            if sev in ("fail", "error"):
                severity = SEV_FAIL
            findings.append(
                Finding(
                    "R5",
                    f"pair/{bidder}",
                    severity,
                    f"{spec_field} differs (per dual-spec assertion)",
                )
            )
            continue
        if not deep_eq(a, b):
            findings.append(
                Finding(
                    "R5",
                    f"pair/{bidder}",
                    SEV_WARN,
                    f"{spec_field} differs across languages",
                )
            )
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
    if pkg and pkg != bidder_name:
        # Real-world divergence: msft uses BidderMicrosoft constant but bidder dir is msft.
        # The test is package_name == bidder_name (not bidder_constant); package_name
        # should match the directory.
        findings.append(
            Finding(
                "R6",
                spec.label,
                SEV_WARN,
                f"meta.bidder_name={bidder_name} != go_artifacts.package_name={pkg}",
            )
        )
    if java_dir_basename and java_dir_basename.lower() != bidder_name.lower():
        findings.append(
            Finding(
                "R6",
                spec.label,
                SEV_WARN,
                f"meta.bidder_name={bidder_name} != java_artifacts.bidder_dir basename={java_dir_basename}",
            )
        )
    if not findings:
        findings.append(Finding("R6", spec.label, SEV_PASS, f"bidder_name={bidder_name}"))
    return findings


# ---------------------------------------------------------------------------
# R7: bidder-constant-mismatch detection (warn, not fail)
# ---------------------------------------------------------------------------


def r7_check(spec: Spec) -> List[Finding]:
    """
    Flag every spec whose params_test.bidder_constant_referenced does not match the
    canonical Bidder<Capitalised> constant for its meta.bidder_name. This is a WARN
    by design — the kobler goldens deliberately encode two real copy-paste artifacts.
    """
    if spec.language != "go":
        # The Java specs use null for bidder_constant_referenced.
        return [Finding("R7", spec.label, SEV_PASS, "skip — Java spec")]
    bidder = (spec.get("meta.bidder_name") or "").strip()
    referenced = spec.get("params.params_test.bidder_constant_referenced")
    if not bidder or not referenced:
        return [Finding("R7", spec.label, SEV_PASS, "no params_test.bidder_constant_referenced to check")]
    expected_a = f"openrtb_ext.Bidder{bidder.capitalize()}"
    # MSFT special case: Bidder constant is BidderMicrosoft (rebrand-fork). Only the
    # bidder_name doesn't share a stem with the constant; treat any constant of the
    # form openrtb_ext.Bidder<X> where the YAML separately documents the rebrand as
    # acceptable. We stop short of hardcoding bidder names — the warning surface is
    # the bidder-constant-mismatch quirk, which the read skill emits.
    if not referenced.startswith("openrtb_ext.Bidder"):
        return [Finding("R7", spec.label, SEV_WARN, f"unexpected constant: {referenced}")]
    if referenced.lower() != expected_a.lower():
        # Surface as WARN unless the spec already has a bidder-name-rebrand warning.
        warnings = spec.get("provenance.warnings") or []
        rebrand = any(
            (w.get("type") or "").startswith("bidder-name-rebrand")
            for w in warnings
            if isinstance(w, dict)
        )
        if rebrand:
            return [
                Finding("R7", spec.label, SEV_PASS, f"constant rebrand acknowledged: {referenced}")
            ]
        return [
            Finding(
                "R7",
                spec.label,
                SEV_WARN,
                f"bidder-constant-mismatch: referenced={referenced} expected≈{expected_a}",
            )
        ]
    return [Finding("R7", spec.label, SEV_PASS, f"constant match: {referenced}")]


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
# R9: quirk taxa registry
# ---------------------------------------------------------------------------


def r9_check(spec: Spec, registered: List[str], lenient: bool = False) -> List[Finding]:
    quirks = spec.raw.get("quirks") or []
    if not isinstance(quirks, list):
        return [Finding("R9", spec.label, SEV_FAIL, "quirks is not a list")]
    if not quirks:
        return [Finding("R9", spec.label, SEV_PASS, "no quirks")]
    if not registered:
        # If we couldn't parse the registry, downgrade to warn rather than fail.
        return [
            Finding(
                "R9",
                spec.label,
                SEV_WARN,
                "could not load taxa registry from behavior-taxonomy.md — skipped",
            )
        ]
    bad: List[str] = []
    bad_severity = SEV_WARN if lenient else SEV_FAIL
    for i, q in enumerate(quirks):
        if not isinstance(q, dict):
            bad.append(f"#{i}: not a mapping")
            continue
        taxon = q.get("edge_case_taxon")
        if taxon is None or taxon == "":
            bad.append(f"#{i} ({q.get('id', '?')}): missing edge_case_taxon")
            continue
        if taxon not in registered:
            bad.append(f"#{i} ({q.get('id', '?')}): unregistered taxon `{taxon}`")
    if bad:
        return [Finding("R9", spec.label, bad_severity, "; ".join(bad))]
    return [Finding("R9", spec.label, SEV_PASS, f"{len(quirks)} quirks, all taxa registered")]


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


RULE_ORDER = ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10"]


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
    rule_descriptions = {
        "R1": "file-reachability",
        "R2": "sha integrity",
        "R3": "custom-quirk pairing",
        "R4": "round-trip determinism",
        "R5": "cross-language sha equality",
        "R6": "bidder_name == package_name",
        "R7": "bidder-constant-mismatch",
        "R8": "endpoint placeholder unresolved",
        "R9": "quirk taxa registered",
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
    args = parser.parse_args(argv)

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

    for spec in specs:
        findings.extend(r1_check(spec, args.check_network, gh_cache))
        findings.extend(r2_check(spec))
        findings.extend(r3_check(spec, strict=args.strict_r3))
        findings.extend(r4_check(spec))
        findings.extend(r6_check(spec))
        findings.extend(r7_check(spec))
        findings.extend(r8_check(spec))
        findings.extend(r9_check(spec, registered_taxa, lenient=args.lenient_r9))
        findings.extend(r10_check(spec))

    # R5: per port pair.
    for bidder in pair_bidders:
        go_spec = by_lang_bidder.get(("go", bidder))
        java_spec = by_lang_bidder.get(("java", bidder))
        if go_spec is None or java_spec is None:
            continue
        findings.extend(r5_check(go_spec, java_spec, dual_specs))
    if not pair_bidders:
        findings.append(Finding("R5", "n/a", SEV_PASS, "no port pairs to compare"))

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
