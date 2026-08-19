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
from pathlib import Path
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


# Make the sibling `lib/` package importable when this file is run as a
# script (`python3 scripts/round-trip-ci.py`) or loaded via importlib (the
# unit-test pattern in scripts/tests/test_round_trip_ci.py). Python adds
# the script's dir to sys.path automatically only in the script case.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

# R5 logic was lifted to scripts/lib/r5_check.py in Phase D0.1 so that the
# port skills (port-go2java / port-java2go) can compute R5 from the same
# source of truth as this harness. Module-level re-exports below keep
# test_round_trip_ci.py imports unchanged. The names listed in __all__ are
# the load-bearing re-exports; they are imported here precisely so that
# `import round_trip_ci as rtci; rtci.R5_STRICT_KEYS` resolves the way
# scripts/tests/test_round_trip_ci.py expects.
from lib.r5_check import (  # noqa: E402  (after sys.path setup)
    R5_ADVISORY_DIVERGENT_KEYS,
    R5_FORM_DIVERGENT_KEYS,
    R5_STRICT_KEYS,
    R5Diagnostic,
    R5Result,
    SpecView,
    _list_set_eq,
    _maintainer_eq,
    compare_pair as _r5_compare_pair,
    deep_eq,
    normalize_endpoint_macros,
)

# Public re-export surface for downstream tests + the port skills.
# Pyright's reportUnused* respects __all__ presence here.
__all__ = (
    "R5_ADVISORY_DIVERGENT_KEYS",
    "R5_FORM_DIVERGENT_KEYS",
    "R5_STRICT_KEYS",
    "R5Diagnostic",
    "R5Result",
    "SpecView",
    "_list_set_eq",
    "_maintainer_eq",
    "deep_eq",
    "normalize_endpoint_macros",
)


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


class TaxaRegistryUnreachable(Exception):
    """Raised by `parse_taxa_registry` when the behavior-taxonomy.md file
    is missing, unreadable, or contains no parseable taxa registry. R3b
    cannot enforce the closed registry without it; main() catches at
    startup and exits 3 (mirrors the GhApiUnreachable Wave 10 recipe).

    Wave 11b post-review fix (2b): the prior behavior was to return an
    empty list and emit per-spec SEV_WARN "could not load taxa registry
    — skipped" on every golden, producing CI runs that exited 2 with
    "0 failures" while R3b was silently disabled. Reviewers reading
    those runs trusted the gate was holding when it wasn't. Fail-loud
    abort prevents that trust gap.
    """


def parse_taxa_registry(taxonomy_md_path: str) -> List[str]:
    """Extract the list of allowed `edge_case_taxon` values from the markdown.

    Raises TaxaRegistryUnreachable on any condition that would have
    silently degraded R3b in the prior implementation: missing file,
    no registry section, empty registry. Caller MUST catch (in main())
    at startup so the workflow aborts with a clear diagnostic instead
    of running per-spec checks against an empty allowlist."""
    if not os.path.isfile(taxonomy_md_path):
        raise TaxaRegistryUnreachable(
            f"taxa registry not found at {taxonomy_md_path}; "
            f"behavior-taxonomy.md was renamed/moved/deleted, or the "
            f"YAML→MD render is stale (run scripts/render-taxonomy.py)"
        )
    with open(taxonomy_md_path, "r", encoding="utf-8") as fh:
        text = fh.read()
    # Find the registry section (case- and back-tick-tolerant).
    pattern = re.compile(r"^##\s+quirks\s+`?edge_case_taxon`?[^\n]*$", re.MULTILINE | re.IGNORECASE)
    m = pattern.search(text)
    if not m:
        raise TaxaRegistryUnreachable(
            f"taxa registry section (## quirks edge_case_taxon) not found in "
            f"{taxonomy_md_path}; the markdown structure was edited or the "
            f"render is broken — run scripts/render-taxonomy.py"
        )
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
    result = list(seen.keys())
    if not result:
        raise TaxaRegistryUnreachable(
            f"taxa registry at {taxonomy_md_path} parsed to an empty list; "
            f"the table structure may have changed (column order, table "
            f"format) — re-render via scripts/render-taxonomy.py and verify"
        )
    return result


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


class GhApiUnreachable(Exception):
    """Raised by `gh_path_exists` when the gh CLI is unauthenticated,
    rate-limited, network-failed, or otherwise can't reach the API.
    DISTINCT from a genuine HTTP 404 (file doesn't exist at the ref,
    returns False) AND from `gh` not installed (returns None — the
    expected fallback when --check-network can't be honored).

    Wave 10 incident, recipe mirrored from audit-golden.py: missing
    GH_TOKEN in CI caused unauthenticated `gh api` calls to rate-limit
    or 401, and the prior gh_path_exists treated every non-zero
    returncode as 404. R1 reported "file not reachable" for every
    upstream path on every spec — a silent false-FAIL flood that masked
    real upstream-drift signals. The fix: distinguish failure modes by
    inspecting stderr; raise this typed exception on auth/network/rate-
    limit failures so main() aborts with exit 3 rather than emitting a
    flood of misleading FAILs.
    """


def gh_path_exists(
    repo: str, sha: str, path: str, cache: Dict[Tuple[str, str], bool]
) -> Optional[bool]:
    """Best-effort path existence check via `gh api`.

    Returns:
        - True on HTTP 200 (path exists at the ref).
        - False on genuine HTTP 404 (path does not exist at the ref).
        - None when `gh` CLI is not on PATH (network check unavailable;
          R1 falls back to structural-plausibility-only and emits WARN).

    Raises:
        GhApiUnreachable on any non-404 failure (auth missing, rate
        limit, timeout, network error, malformed response). main()
        catches this at the top level and exits 3 — propagating ensures
        the audit aborts rather than silently emitting false FAILs.
    """
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
    except FileNotFoundError as exc:
        raise GhApiUnreachable(f"gh CLI vanished mid-run: {exc}")
    except subprocess.TimeoutExpired:
        raise GhApiUnreachable(f"timeout fetching {repo}/{path}@{sha}")
    except Exception as exc:  # noqa: BLE001
        raise GhApiUnreachable(
            f"gh subprocess failed for {repo}/{path}@{sha}: "
            f"{type(exc).__name__}: {exc}"
        )
    if proc.returncode == 0:
        cache[key] = True
        return True
    stderr = (proc.stderr or "").strip()
    # `gh api` exits non-zero with stderr "gh: Not Found (HTTP 404)" for
    # genuine 404s. Auth failures, rate limits, and network errors
    # surface as different stderr text — propagate as GhApiUnreachable
    # so the audit aborts rather than treating "API unreachable" as
    # "every file is missing" (the Wave 10 false-FAIL flood incident).
    if "HTTP 404" in stderr or "Not Found" in stderr:
        cache[key] = False
        return False
    raise GhApiUnreachable(
        f"gh api failed for {repo}/{path}@{sha} (returncode={proc.returncode}): "
        f"{stderr or '<empty stderr>'}"
    )


# ---------------------------------------------------------------------------
# R2: bidder_params_sha256 integrity
# ---------------------------------------------------------------------------


def _blobs_dir_for(spec: Spec) -> Path:
    """Content-addressed store beside the golden that references it."""
    return Path(spec.path).resolve().parent / "blobs"


def r2_check(spec: Spec) -> List[Finding]:
    """Params integrity, split three ways.

    The old R2 hashed `bidder_params_json` -- the reader's own output -- so a
    lossy transcription produced a self-consistent hash. Two beachfront goldens
    dropped ~30 bytes from a description and passed. Self-consistency is not
    fidelity, so the check is now:

      R2a  the stored blob hashes to bidder_params_ref.sha256
      R2b  the stored blob's length equals bidder_params_ref.bytes -- an
           independent witness, because a length cannot be re-derived from
           transcribed text the way a hash can
      R2c  ref.sha256 and ref.bytes equal upstream at ref.resolved_commit, and
           the stored blob is byte-identical to it. NOT here -- it needs the
           network. `scripts/verify-params-refs.py`, run by the upstream-sync
           workflow. R2a/R2b alone cannot see a forgery that edits blob, sha and
           byte count together: they agree with each other, and only upstream
           breaks the tie.

    `bidder_params_json` is gone at 2.0.0. While it survived the migration it was
    compared against the blob as a WARN, and both beachfront goldens warned --
    the two files whose inline text was never upstream. Removing the field
    removed the category.
    """
    findings: List[Finding] = []
    ref = spec.raw.get("bidder_params_ref")
    declared = spec.raw.get("bidder_params_sha256")

    if ref is None:
        # Aliases legitimately have neither: they inherit the parent's params.
        if (spec.raw.get("meta") or {}).get("is_alias"):
            return [Finding("R2", spec.label, SEV_PASS, "alias inherits parent params")]
        return [Finding("R2", spec.label, SEV_FAIL, "bidder_params_ref missing")]

    for field in ("path", "resolved_commit", "sha256", "bytes"):
        if ref.get(field) in (None, ""):
            return [Finding("R2", spec.label, SEV_FAIL,
                            f"bidder_params_ref.{field} missing")]

    blob = _blobs_dir_for(spec) / str(ref["sha256"])
    if not blob.is_file():
        return [Finding("R2", spec.label, SEV_FAIL,
                        f"blob {ref['sha256']} absent from "
                        f"{_blobs_dir_for(spec).name}/ -- nothing to verify against")]
    data = blob.read_bytes()

    actual = hashlib.sha256(data).hexdigest()
    if actual != ref["sha256"]:
        findings.append(Finding("R2", spec.label, SEV_FAIL,
                                f"R2a blob content hashes {actual} but ref declares "
                                f"{ref['sha256']}"))
    else:
        findings.append(Finding("R2", spec.label, SEV_PASS, f"R2a blob sha={actual[:12]}"))

    if len(data) != int(ref["bytes"]):
        findings.append(Finding("R2", spec.label, SEV_FAIL,
                                f"R2b blob is {len(data)}B, ref declares {ref['bytes']}B"))
    else:
        findings.append(Finding("R2", spec.label, SEV_PASS, f"R2b bytes={len(data)}"))

    if declared != ref["sha256"]:
        findings.append(Finding("R2", spec.label, SEV_FAIL,
                                f"bidder_params_sha256 {declared} does not mirror "
                                f"bidder_params_ref.sha256 {ref['sha256']}"))

    if "bidder_params_json" in spec.raw:
        # Removed at 2.0.0. A golden that still carries it was not migrated, and
        # a stale inline copy beside a ref is exactly the ambiguity the ref
        # exists to remove -- so this is a failure, not a tolerated leftover.
        findings.append(Finding(
            "R2", spec.label, SEV_FAIL,
            "bidder_params_json was removed at adapter_spec_version 2.0.0; run "
            "scripts/migrate/1.3.0-to-2.0.0.py --drop-inline"))
    return findings


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


def _load_lossy_field_paths() -> Dict[str, Dict[str, bool]]:
    """Phase D4.1: parse `Round-Trip Safety` section of port-translation-rules.yaml.

    Returns mapping ``{field_path: {direction: True}}`` where ``direction``
    is one of ``go-to-java`` or ``java-to-go``. ``r_port_round_trip`` consults
    this map: a divergence on a field flagged as lossy in the relevant
    direction is recorded as expected (no FAIL), per
    docs/methodology/port-skills-design.md Round-Trip Safety semantics.
    """
    rules_path = os.path.join(
        REPO_ROOT, "prebid-server-go", "read", "skills", "shared",
        "port-translation-rules.yaml",
    )
    try:
        with open(rules_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except (OSError, yaml.YAMLError):
        return {}
    out: Dict[str, Dict[str, bool]] = {}
    for section in data.get("sections") or []:
        if section.get("kind") != "round_trip_safety":
            continue
        table = section.get("verdict_table") or {}
        for row in table.get("rows") or []:
            if not isinstance(row, list) or len(row) < 4:
                continue
            field_path = (row[0] or "").strip().strip("`")
            lossy_direction = (row[2] or "").strip().lower()
            verdict = (row[3] or "").strip().lower()
            if "lossy" not in verdict:
                continue
            if not field_path:
                continue
            entry = out.setdefault(field_path, {})
            # Direction column shapes: "Go→Java→Go" (Go is source-of-truth,
            # round-trip via Java loses info) or "Java→Go→Java".
            if "go→java→go" in lossy_direction or "go-to-java-to-go" in lossy_direction:
                entry["go-to-java"] = True
            if "java→go→java" in lossy_direction or "java-to-go-to-java" in lossy_direction:
                entry["java-to-go"] = True
    return out


def _round_trip_artifact_path(bidder: str, language: str) -> Optional[str]:
    """Phase D4.1: locate a round-trip artifact for a given bidder + target language.

    Looks under (in precedence order):
      1. ``.tmp/full-loop/*/round-trip/{language}/{bidder}.yaml`` (Teal flow transient)
      2. ``prebid-server-{language}/port-{source}2{target}/output/{bidder}/round-trip/{bidder}.spec.yaml``

    Returns the first matching path, or None when no artifact exists yet
    (the common case in the corpus today; round-trip CI gates surface
    findings only when operator runs persist artifacts).
    """
    other = "go" if language == "java" else "java"
    candidates = [
        os.path.join(REPO_ROOT, ".tmp", "full-loop", "*", "round-trip", language, f"{bidder}.yaml"),
        os.path.join(REPO_ROOT, f"prebid-server-{language}", f"port-{other}2{language}",
                     "output", bidder, "round-trip", f"{bidder}.spec.yaml"),
    ]
    for pattern in candidates:
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[-1]  # most-recent run-id when multiple
    return None


def r_port_round_trip(go_spec: Optional[Spec], java_spec: Optional[Spec],
                       lossy_paths: Optional[Dict[str, Dict[str, bool]]] = None) -> List[Finding]:
    """Phase D4.1: port-side round-trip determinism.

    For each paired bidder (go_spec + java_spec both present), check
    whether round-trip artifacts exist at canonical paths and validate
    them. The full round-trip path is:

      original Go spec → port-go2java → Java spec at .tmp → port-java2go →
      Go spec at .tmp/round-trip/go/{bidder}.yaml

    The harness compares the ORIGINAL Go spec to the round-tripped Go
    spec. Differences on fields flagged as lossy in
    port-translation-rules.yaml's Round-Trip Safety section are
    recorded as expected (no FAIL). Other differences emit WARN.

    When no round-trip artifact exists (the common state today —
    operator-side runs haven't landed any), emits SKIP with reason
    "no round-trip artifact". The framework is in place for when
    operator runs persist artifacts.

    Inverse direction (Java spec → port-java2go → Go intermediate →
    port-go2java → Java round-tripped) is symmetric; the helper checks
    both directions when artifacts are present.
    """
    primary = go_spec or java_spec
    if primary is None:
        return []
    bidder = primary.bidder
    if go_spec is None or java_spec is None:
        return [Finding("R11", f"pair/{bidder}", SEV_SKIP,
                        "round-trip requires paired Go + Java goldens (one side missing)")]

    if lossy_paths is None:
        lossy_paths = _load_lossy_field_paths()

    findings: List[Finding] = []
    for direction in ("go-to-java", "java-to-go"):
        # The "round-trip" artifact lives in the SAME language as the source —
        # round trip = source → other → back to source.
        rt_lang = "go" if direction == "go-to-java" else "java"
        rt_path = _round_trip_artifact_path(bidder, rt_lang)
        if not rt_path:
            findings.append(Finding(
                "R11", f"pair/{bidder}/{direction}", SEV_SKIP,
                f"no round-trip artifact (looked for {rt_lang}/{bidder}.yaml under .tmp/full-loop/ and port-*/output/)",
            ))
            continue
        try:
            with open(rt_path, "r", encoding="utf-8") as fh:
                rt_raw = yaml.safe_load(fh) or {}
        except (OSError, yaml.YAMLError) as exc:
            findings.append(Finding(
                "R11", f"pair/{bidder}/{direction}", SEV_FAIL,
                f"could not load round-trip artifact at {rt_path}: {exc}",
            ))
            continue
        original_spec = go_spec if direction == "go-to-java" else java_spec
        diffs = _round_trip_diff(original_spec.raw, rt_raw, lossy_paths, direction)
        if not diffs:
            findings.append(Finding(
                "R11", f"pair/{bidder}/{direction}", SEV_PASS,
                "round-trip lossless (modulo expected lossy-direction fields)",
            ))
        else:
            for diff in diffs:
                findings.append(Finding(
                    "R11", f"pair/{bidder}/{direction}", SEV_WARN,
                    f"unexpected round-trip divergence at {diff['path']}: "
                    f"original={diff['original']!r} round-tripped={diff['round_tripped']!r}",
                ))
    return findings


def _round_trip_diff(
    original: Dict[str, Any],
    round_tripped: Dict[str, Any],
    lossy_paths: Dict[str, Dict[str, bool]],
    direction: str,
) -> List[Dict[str, Any]]:
    """Walk original vs round-tripped spec; collect fields that diverge AND
    are NOT flagged as lossy in the relevant direction. Returns a list of
    {path, original, round_tripped} dicts for unexpected divergences.

    keys_to_check is intentionally minimal — limited to the R5-strict
    subset whose divergence is meaningful regardless of direction. The
    Round-Trip Safety table at port-translation-rules.yaml lists many
    paths flagged lossy that are NOT in this set (e.g., code.builder.*,
    spring_config.*, tests.unit_test_methods_count); the lossy_paths
    loader is forward-looking — a future expansion of keys_to_check
    can add those without re-shaping the diff loop. Today, none of the
    paths in keys_to_check appear in the Round-Trip Safety lossy list,
    so the lossy_paths intersection is empty by design (the gate is in
    place against future schema additions).

    Per Phase D4.1 follow-up: bidder_info.endpoint compares via
    normalize_endpoint_macros so macro-form equivalent endpoints
    (Go {{.X}} vs Java ${X}) don't fire false WARNs — same canonical
    form R5 uses for the form-divergent comparison.
    """
    out: List[Dict[str, Any]] = []
    keys_to_check = (
        # R5-strict subset — divergences here are unexpected even given
        # lossy-direction asymmetries elsewhere.
        "bidder_info.endpoint",
        "bidder_info.maintainer",
        "bidder_info.gvl_vendor_id",
        "bidder_info.geoscope",
        "bidder_info.modifying_vast_xml_allowed",
        "bidder_info.endpoint_compression",
        "bidder_info.capabilities",
        "bidder_params_sha256",
    )
    for path in keys_to_check:
        if _is_lossy_in_direction(path, direction, lossy_paths):
            continue
        orig_val = _walk_dotted(original, path)
        rt_val = _walk_dotted(round_tripped, path)
        # bidder_info.endpoint may use language-specific macro syntax;
        # canonicalize before comparing so {{.Host}} ≡ ${host} ≡ {{Host}}.
        if path == "bidder_info.endpoint":
            orig_val = normalize_endpoint_macros(orig_val) if isinstance(orig_val, str) else orig_val
            rt_val = normalize_endpoint_macros(rt_val) if isinstance(rt_val, str) else rt_val
        if not _values_equivalent(orig_val, rt_val):
            out.append({
                "path": path,
                "original": orig_val,
                "round_tripped": rt_val,
            })
    return out


def _is_lossy_in_direction(
    path: str,
    direction: str,
    lossy_paths: Dict[str, Dict[str, bool]],
) -> bool:
    """Check whether a field path is flagged lossy in the given direction
    in the Round-Trip Safety table."""
    entry = lossy_paths.get(path) or {}
    return bool(entry.get(direction))


def _walk_dotted(node: Any, dotted: str) -> Any:
    for part in dotted.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node


def _values_equivalent(a: Any, b: Any) -> bool:
    """JSON-stable equivalence (lists order-insensitive when set-equality
    is the natural semantic; falls back to deep equality)."""
    if isinstance(a, list) and isinstance(b, list):
        try:
            return sorted(json.dumps(x, sort_keys=True, default=str) for x in a) == \
                   sorted(json.dumps(x, sort_keys=True, default=str) for x in b)
        except TypeError:
            pass
    return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


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


def r5_check(go_spec: Optional[Spec], java_spec: Optional[Spec],
             dual_specs: Dict[str, Dict[str, Any]]) -> List[Finding]:
    """Cross-language structural parity. Thin adapter over
    ``scripts.lib.r5_check.compare_pair``.

    Runtime values are the source of truth; the dual-spec assertion is an
    EXPECTATION verified against runtime, not a free pass. Polarity contract:
    when dual-spec says severity:pass but runtime values disagree, FAIL —
    the assertion is stale.
    """
    primary = go_spec or java_spec
    if primary is None:
        return []
    bidder = primary.bidder
    dual = dual_specs.get(bidder) or {}
    raw_assertions = dual.get("assertions") if isinstance(dual.get("assertions"), dict) else {}
    assertions: Dict[str, Any] = raw_assertions if isinstance(raw_assertions, dict) else {}
    overall = dual.get("overall") or {}
    result: R5Result = _r5_compare_pair(
        go_spec, java_spec, assertions=assertions, overall=overall,
    )
    return [
        Finding("R5", f"pair/{bidder}", d.severity, d.detail)
        for d in result.diagnostics
    ]


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


# Wave 11b post-review (3d): macro registries lifted from inline Python
# literals to data at `prebid-server-go/read/skills/shared/endpoint-macros.yaml`.
# Adding a new macro is now a YAML edit, not a code change.
ENDPOINT_MACROS_PATH = os.path.join(
    REPO_ROOT, "prebid-server-go", "read", "skills", "shared", "endpoint-macros.yaml"
)


def _load_endpoint_macros() -> Dict[str, frozenset]:
    """Load the four R8 macro registries from endpoint-macros.yaml.

    Returns a dict with keys go_template_macros, java_conventional_macros,
    user_sync_macros, openrtb_macros — each mapped to a frozenset of
    macro names. Raises FileNotFoundError if the YAML is missing (a
    deeply-broken state; the script can't run R8 without the registry).
    """
    if not os.path.isfile(ENDPOINT_MACROS_PATH):
        raise FileNotFoundError(
            f"endpoint-macros.yaml not found at {ENDPOINT_MACROS_PATH}; "
            f"R8 cannot recognize macros without it"
        )
    with open(ENDPOINT_MACROS_PATH, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    out: Dict[str, frozenset] = {}
    for key in ("go_template_macros", "java_conventional_macros",
                "user_sync_macros", "openrtb_macros"):
        values = data.get(key) or []
        if not isinstance(values, list):
            raise ValueError(
                f"endpoint-macros.yaml: expected `{key}` to be a list, "
                f"got {type(values).__name__}"
            )
        out[key] = frozenset(values)
    return out


_MACRO_REGISTRIES = _load_endpoint_macros()
GO_TEMPLATE_MACROS = _MACRO_REGISTRIES["go_template_macros"]
JAVA_CONVENTIONAL_MACROS = _MACRO_REGISTRIES["java_conventional_macros"]
USER_SYNC_MACROS = _MACRO_REGISTRIES["user_sync_macros"]
OPENRTB_MACROS = _MACRO_REGISTRIES["openrtb_macros"]
del _MACRO_REGISTRIES
# Placeholder forms R8 recognises, in match order. The alternation order matters:
# `{{Host}}` must match the double-brace arm, not the single-brace one, and
# `${AUCTION_PRICE}` must match the dollar arm.
#
#   {{.Host}}          Go text/template
#   {{Host}}           Java, pre-UriTemplate
#   #{REGION}#         deploy-time token
#   ${AUCTION_PRICE}   OpenRTB
#   {Host}             Java, POST-UriTemplate -- added late, and its absence
#                      made R8 blind to every current Java endpoint. Upstream
#                      migrated to single-brace in #4444 (2026-07-20); the
#                      corpus goldens still carry the double-brace form because
#                      they were read before that, which is why the gap did not
#                      show up as a corpus failure. A freshly-read Java adapter
#                      with an unsubstituted macro would have reported "all
#                      placeholders recognised".
PLACEHOLDER_RE = re.compile(
    r"\{\{\.?([A-Za-z_][A-Za-z0-9_]*)\}\}"
    r"|#\{([A-Za-z_][A-Za-z0-9_]*)\}#"
    r"|\$\{([A-Za-z_][A-Za-z0-9_]*)\}"
    r"|\{([A-Za-z_][A-Za-z0-9_]*)\}"
)


def _collect_endpoint_strings(spec: Spec) -> List[Tuple[str, str]]:
    """Return (path, value) tuples for every endpoint-bearing string in the
    spec that should be walked for placeholder recognition.

    Wave 11b B5 #7 expansion: prior r8_check walked ONLY bidder_info.endpoint,
    missing user-sync URLs, hardcoded Java static-field macros, and
    deploy-time-token strings. Now covers:

    - bidder_info.endpoint
    - bidder_info.user_sync.{iframe,redirect}.url
    - bidder_info.user_sync.{iframe,redirect}.uid_macro (redirect.* only)
    - bidder_info.user_sync.{iframe_url,redirect_url}  (legacy flat form)
    - bidder_class.static_fields[*].value (Java hardcoded macro literals)

    SKIPS prose paths where placeholder-shaped strings are quotes of code,
    not real macros: cross_language.{go,java}_specific_concerns[],
    quirks[].summary, provenance.warnings[].summary.

    deploy_time_tokens[*].token strings ARE the placeholders being
    substituted; not walked here (they're treated as authoritative
    deploy-time tokens by the placeholder-recognition pass)."""
    out: List[Tuple[str, str]] = []
    raw = spec.raw

    bi = raw.get("bidder_info") or {}
    if isinstance(bi, dict):
        ep = bi.get("endpoint")
        if isinstance(ep, str) and ep:
            out.append(("bidder_info.endpoint", ep))

        us = bi.get("user_sync") or {}
        if isinstance(us, dict):
            for sub in ("iframe", "redirect"):
                v = us.get(sub) or {}
                if isinstance(v, dict):
                    s_url = v.get("url")
                    if isinstance(s_url, str) and s_url:
                        out.append((f"bidder_info.user_sync.{sub}.url", s_url))
                    if sub == "redirect":
                        um = v.get("uid_macro")
                        if isinstance(um, str) and um:
                            out.append(("bidder_info.user_sync.redirect.uid_macro", um))
            for fld in ("iframe_url", "redirect_url"):
                s = us.get(fld)
                if isinstance(s, str) and s:
                    out.append((f"bidder_info.user_sync.{fld}", s))

    bc = raw.get("bidder_class") or {}
    if isinstance(bc, dict):
        for sf in (bc.get("static_fields") or []):
            if isinstance(sf, dict):
                v = sf.get("value")
                if isinstance(v, str) and v:
                    name = sf.get("name") or "?"
                    out.append((f"bidder_class.static_fields[{name}].value", v))

    return out


def _substituted_java_macros(spec: Spec) -> frozenset:
    """Macro names this Java spec records the code substituting.

    Upstream substitutes an endpoint macro in three shapes, and only one of them
    is a class-level constant:

      1. a named constant in the bidder class -- `SUPPLY_ID_MACRO = "SupplyId"`
         then `replaceMacro(SUPPLY_ID_MACRO, ...)`  (thetradedesk)
      2. a named constant in the CONFIGURATION class -- AaxConfiguration's
         `EXTERNAL_URL_MACRO = "PREBID_SERVER_ENDPOINT"`
      3. an inline literal at the call site -- ElementalTVBidder's
         `endpoint.replaceMacro("AdUnit", extImp.getAdunit())`, no constant at all

    So `bidder_class.static_fields[]` answers the question for shape 1 only. The
    field that covers all three is `endpoint_resolution.macros_used`, the read's
    record of what the call sites substitute -- 7 Java goldens populate it, and
    smarthub's lists exactly the three macros its endpoint uses even though its
    static_fields records none of them.

    `macro_field_set` is accepted as the same thing under the other key: the
    corpus uses both, which is itself a defect worth fixing in the goldens.
    Brace-wrapped entries are normalised, because elementaltv records
    `['{{AdUnit}}']` where every other golden records bare names.
    """
    out = set()
    # The corpus records this at TWO paths and they are not interchangeable:
    # `bidder_info.endpoint_construction.macros_used` is populated in nearly every
    # golden, while `code.make_requests.endpoint_resolution.macros_used` is
    # populated in a minority (28 of 42 goldens have one and not the other).
    # Reading only one makes recognition depend on which reader filled which
    # field, so both are read. R8b below reports the two disagreeing.
    sources = [
        ((spec.raw.get("bidder_info") or {}).get("endpoint_construction") or {}),
        (((spec.raw.get("code") or {}).get("make_requests") or {})
         .get("endpoint_resolution") or {}),
    ]
    for er in sources:
        for key in ("macros_used", "macro_field_set"):
            for entry in (er.get(key) or []):
                if not isinstance(entry, str):
                    continue
                token = entry.strip()
                matched = False
                for m in PLACEHOLDER_RE.finditer(token):
                    name = m.group(1) or m.group(2) or m.group(3) or m.group(4)
                    if name:
                        out.add(name)
                        matched = True
                if not matched:
                    # A bare name is the form replaceMacro takes. Anything with
                    # whitespace is prose, not a macro name (emxdigital and
                    # cadent_aperture_mx record sentences here) -- admitting it
                    # would let prose silence R8.
                    bare = token.strip("{}.")
                    if bare and not any(c.isspace() for c in bare):
                        out.add(bare)

    # Shape 1 as well: a constant whose value IS the macro.
    for field in ((spec.raw.get("bidder_class") or {}).get("static_fields") or []):
        if not isinstance(field, dict):
            continue
        value = field.get("value")
        if not isinstance(value, str):
            continue
        token = value.strip()
        for m in PLACEHOLDER_RE.finditer(token):
            name = m.group(1) or m.group(2) or m.group(3) or m.group(4)
            if name:
                out.add(name)
    return frozenset(out)


def _macro_record_disagreement(spec: Spec) -> Optional[str]:
    """The two macros_used copies, when both populated, must name the same set.

    `bidder_info.endpoint_construction.macros_used` and
    `code.make_requests.endpoint_resolution.macros_used` are the same claim
    recorded twice. Nothing compared them, and they diverge: limelightDigital
    lists the same two names in a different order (harmless), while
    cadent_aperture_mx and emxdigital hold bare names at one path and prose
    sentences at the other -- "ts (Instant.now().getEpochSecond() -- NO
    testing-mode override...)" is not a macro name, and R8 must not be able to
    admit a placeholder because prose happened to contain the right substring.

    One path being absent is NOT a disagreement: 28 of 42 goldens populate one
    and leave the other null, which is a read-completeness question for the
    golden refresh rather than a contradiction. Only two populated lists that
    name different things are reported here.
    """
    a = ((spec.raw.get("bidder_info") or {}).get("endpoint_construction") or {}).get("macros_used")
    b = (((spec.raw.get("code") or {}).get("make_requests") or {})
         .get("endpoint_resolution") or {}).get("macros_used")
    if not isinstance(a, list) or not isinstance(b, list) or not a or not b:
        return None

    def norm(items):
        out = set()
        for it in items:
            if not isinstance(it, str):
                continue
            token = it.strip()
            hit = False
            for m in PLACEHOLDER_RE.finditer(token):
                name = m.group(1) or m.group(2) or m.group(3) or m.group(4)
                if name:
                    out.add(name)
                    hit = True
            if not hit:
                bare = token.strip("{}.")
                # Keep only the leading identifier, so "t (TMax milliseconds...)"
                # compares as "t" -- otherwise every prose entry reads as a
                # different macro and the check says nothing useful.
                head = bare.split()[0].strip("{}.,") if bare.split() else ""
                if head:
                    out.add(head)
        return out

    sa, sb = norm(a), norm(b)
    if sa == sb:
        return None
    return (f"macros_used disagrees between paths: "
            f"bidder_info.endpoint_construction={sorted(sa)} vs "
            f"code.make_requests.endpoint_resolution={sorted(sb)}")


def r8_check(spec: Spec) -> List[Finding]:
    """Wave 11b B5 #7: expanded from single-field walk (bidder_info.endpoint)
    to recursive collection across user-sync URLs, hardcoded static-field
    macros, and the original endpoint. Each placeholder is recognized
    against per-language macro registries plus deploy-time-token names."""
    leaves = _collect_endpoint_strings(spec)
    if not leaves:
        return [Finding("R8", spec.label, SEV_PASS, "no endpoint-bearing strings to check")]
    if spec.language == "go":
        # Closed by construction: macros.EndpointTemplateParams is a struct, and
        # text/template resolves against its fields, so a name outside the set
        # cannot resolve.
        macros = GO_TEMPLATE_MACROS
    else:
        # Open by construction: each Java bidder declares its own macro name as a
        # constant and calls Uri.replaceMacro(NAME, value); Uri.java holds no name
        # registry. So "not on a list" is not a finding -- what is checkable is
        # whether this spec shows the bidder declaring the macro it uses.
        #
        # JAVA_CONVENTIONAL_MACROS deliberately does NOT admit. Letting it would
        # make the hint list the authority its own comment says it is not, and it
        # would hide the real gap: smarthub's endpoint uses Host/AccountID/SourceId,
        # SmarthubBidder declares a constant for each, and the golden records none
        # of them. It is used below to tell a reviewer the name is a known spelling.
        macros = _substituted_java_macros(spec)
    warnings = spec.get("provenance.warnings") or []
    has_warning = any(
        (w.get("type") or "") == "endpoint-placeholder-unresolved"
        for w in warnings
        if isinstance(w, dict)
    )
    # Build the deploy-time-token NAME set (extract name from token strings
    # like `#{REGION}#`, not the full token string). Pre-Wave-11b code had
    # a latent bug here: it stored the full token string then compared
    # against extracted placeholder names — never matched. B5 #7 fixes
    # this incidentally by extracting names from the token strings.
    deploy_token_names: set = set()
    for t in (spec.get("deploy_time_tokens") or []):
        if isinstance(t, dict):
            tok = t.get("token")
            if isinstance(tok, str):
                for m in PLACEHOLDER_RE.finditer(tok):
                    n = m.group(1) or m.group(2) or m.group(3) or m.group(4)
                    if n:
                        deploy_token_names.add(n)

    findings: List[Finding] = []
    seen_unrecognised = 0
    for path, value in leaves:
        # User-sync URL macros are recognized in addition to the per-language
        # endpoint macro set. Wave 11b B5 #7 introduces USER_SYNC_MACROS to
        # admit GDPR/GDPRConsent/USPrivacy/GPP/etc. when walking user-sync
        # path leaves. OPENRTB_MACROS apply everywhere (AUCTION_PRICE etc.
        # may appear in any endpoint-bearing string per OpenRTB 2.5 §4.1).
        path_macros = macros | OPENRTB_MACROS
        if "user_sync" in path:
            path_macros |= USER_SYNC_MACROS
        for m in PLACEHOLDER_RE.finditer(value):
            name = m.group(1) or m.group(2) or m.group(3) or m.group(4)
            if not name:
                continue
            if name in path_macros or name in deploy_token_names:
                continue
            seen_unrecognised += 1
            if has_warning:
                findings.append(Finding(
                    "R8", spec.label, SEV_PASS,
                    f"placeholder {{{{.{name}}}}} at {path} unrecognised but warning emitted",
                ))
            else:
                if spec.language == "go":
                    detail = (f"placeholder {{{{.{name}}}}} at {path} is not a field of "
                              f"macros.EndpointTemplateParams, so text/template cannot "
                              f"resolve it, and no provenance warning documents the deviation")
                else:
                    hint = (" It is a conventional Java macro spelling, so the likely cause "
                            "is an incomplete read rather than a missing substitution."
                            if name in JAVA_CONVENTIONAL_MACROS else "")
                    detail = (f"placeholder {{{name}}} at {path} is not recorded as substituted: "
                              f"absent from endpoint_resolution.macros_used and from any "
                              f"bidder_class.static_fields[] value, so on this spec nothing "
                              f"calls replaceMacro for it and it would reach the exchange "
                              f"literally.{hint}")
                findings.append(Finding("R8", spec.label, SEV_WARN, detail))
    disagreement = _macro_record_disagreement(spec)
    if disagreement:
        findings.append(Finding("R8", spec.label, SEV_WARN, disagreement))
    if not findings:
        findings.append(Finding(
            "R8", spec.label, SEV_PASS,
            f"{len(leaves)} endpoint-bearing string(s) checked; all placeholders recognised",
        ))
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
        # Wave 11b post-review fix (2b): this branch is now defensive only —
        # parse_taxa_registry raises TaxaRegistryUnreachable on missing/empty
        # registry, which main() catches at startup with exit 3. If we somehow
        # reach this with an empty list, the upstream guard failed and we
        # should fail loudly per spec rather than silently SEV_WARN.
        return [Finding("R3b", spec.label, SEV_FAIL,
            "internal: r_taxa_check called with empty registered list "
            "(should have been caught by main()'s TaxaRegistryUnreachable "
            "abort; this Finding indicates a control-flow regression)")]
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


RULE_ORDER = ["R1", "R2", "R3", "R3b", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11"]


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
    # below.  Wave 11b tightened all three previously-advisory rules; the
    # caveats here describe what now lands:
    #
    # R3 — keyword pairing strict by default post-Wave-11b B5 #3
    #      (--strict-r3 default-on; round-2 audit confirmed 40/0/0 on
    #      corpus). --lenient-r3 opts back to the advisory mode.
    # R5 — Wave 11b B5 #2 refactored R5_STRICT_KEYS to per-key
    #      comparators: list-set-equality for capabilities/geoscope/
    #      schema_interpretation list keys; email-only equality for
    #      maintainer; deep_eq for pure-data scalars. Wave 11b B4 C1
    #      split the divergent-keys bucket into FORM_DIVERGENT (endpoint
    #      with normalize_endpoint_macros) + ADVISORY_DIVERGENT.
    # R8 — Wave 11b B5 #7 expanded the walker from single-field
    #      (bidder_info.endpoint) to multi-path collector covering
    #      user-sync URLs (iframe/redirect.url + uid_macro + flat forms),
    #      bidder_class.static_fields[*].value, plus the original
    #      endpoint. USER_SYNC_MACROS + OPENRTB_MACROS registries admit
    #      well-known macros without noise.
    rule_descriptions = {
        "R1": "file-reachability",
        "R2": "sha integrity",
        "R3": "custom-quirk pairing (strict by default; --lenient-r3 to relax)",
        "R3b": "quirk taxa registered",
        "R4": "round-trip determinism",
        "R5": "cross-language structural parity (per-key comparators)",
        "R6": "bidder_name / package / constant",
        "R7": "bidder-constant-mismatch surfaces",
        "R8": "endpoint placeholder (recursive walker — endpoint + user_sync + static_fields)",
        "R9": "legacy encoding/json direct usage",
        "R10": "canonical-harness flag",
        "R11": "port-side round-trip determinism (Phase D4.1)",
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
        default=True,
        help="(Wave 11b default-on) Require quirk id/summary keyword pairing for every `custom` enum value. Round-2 audit confirmed 40 pass / 0 fail across corpus; safe to default-on.",
    )
    parser.add_argument(
        "--lenient-r3",
        action="store_false",
        dest="strict_r3",
        help="(Wave 11b opt-out) Disable strict R3 keyword-pairing; falls back to advisory mode (any non-empty quirks list satisfies). Use only when quirks are deliberately under-documented.",
    )
    parser.add_argument(
        "--lenient-r3b",
        action="store_true",
        dest="lenient_r3b",
        help="Downgrade unregistered taxa from FAIL to WARN (use while taxonomy lags goldens). R3b is the quirks-taxa-registry rule.",
    )
    # Wave 11b post-review fix (2a): --lenient-r9 was a misnamed alias —
    # the flag controls R3b (taxa registry), but R9 is "legacy encoding/json
    # direct usage" with no lenient mode. Anyone reading --help and passing
    # --lenient-r9 hoping to relax R9 silently relaxed R3b instead. Renamed
    # to --lenient-r3b; --lenient-r9 kept as a deprecated alias that emits
    # a stderr warning, with intent to remove in a future wave.
    parser.add_argument(
        "--lenient-r9",
        action="store_true",
        dest="lenient_r3b",
        help=argparse.SUPPRESS,  # hide deprecated alias from --help
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

    # Wave 11b post-review fix (2b): fail loudly when the taxa registry can't
    # load. Mirrors the GhApiUnreachable Wave 10 recipe. Prior behavior was
    # to return [] and let r_taxa_check emit SEV_WARN per-spec ("skipped"),
    # producing CI runs with "0 failures" while R3b was silently disabled.
    try:
        registered_taxa = parse_taxa_registry(TAXONOMY_PATH)
    except TaxaRegistryUnreachable as exc:
        print(f"ERROR: R3b taxa registry unreachable: {exc}", file=sys.stderr)
        print("R3b cannot enforce the closed taxa registry without it.",
              file=sys.stderr)
        print("Aborting to prevent silent gate degradation.", file=sys.stderr)
        return 3

    # Wave 11b post-review fix (2a): emit deprecation warning when the old
    # --lenient-r9 flag was passed (still wired via dest=lenient_r3b).
    if "--lenient-r9" in sys.argv:
        print("DEPRECATED: --lenient-r9 is renamed to --lenient-r3b; "
              "the old name will be removed in a future wave",
              file=sys.stderr)

    dual_specs = load_dual_specs()

    findings: List[Finding] = []
    gh_cache: Dict[Tuple[str, str], bool] = {}

    # Per-spec rules — wrap each call in try/except so a crash on one rule
    # doesn't void the others, and a crash on one spec doesn't void the run.
    per_spec_rules = [
        ("R1",  lambda s: r1_check(s, args.check_network, gh_cache)),
        ("R2",  r2_check),
        ("R3",  lambda s: r3_check(s, strict=args.strict_r3)),
        ("R3b", lambda s: r_taxa_check(s, registered_taxa, lenient=args.lenient_r3b)),
        ("R4",  r4_check),
        ("R6",  r6_check),
        ("R7",  r7_check),
        ("R8",  r8_check),
        ("R9",  r9_check),
        ("R10", r10_check),
    ]
    # R5: per port pair OR per dual-spec entry (run even when one side is missing).
    all_r5_bidders = sorted(set(pair_bidders) | set(dual_specs.keys()))
    try:
        for spec in specs:
            for rule_name, fn in per_spec_rules:
                try:
                    findings.extend(fn(spec))
                except GhApiUnreachable:
                    raise  # propagate to top-level handler below
                except Exception as exc:  # noqa: BLE001
                    findings.append(Finding(
                        rule_name, spec.label, SEV_FAIL,
                        f"rule crashed: {type(exc).__name__}: {exc}",
                    ))

        # Load R-T safety table once for the full per-pair sweep.
        lossy_paths = _load_lossy_field_paths()
        for bidder in all_r5_bidders:
            go_spec = by_lang_bidder.get(("go", bidder))
            java_spec = by_lang_bidder.get(("java", bidder))
            try:
                findings.extend(r5_check(go_spec, java_spec, dual_specs))
            except GhApiUnreachable:
                raise  # propagate to top-level handler
            except Exception as exc:  # noqa: BLE001
                findings.append(Finding(
                    "R5", f"pair/{bidder}", SEV_FAIL,
                    f"rule crashed: {type(exc).__name__}: {exc}",
                ))
            # R11: port-side round-trip determinism (Phase D4.1).
            try:
                findings.extend(r_port_round_trip(go_spec, java_spec, lossy_paths))
            except Exception as exc:  # noqa: BLE001
                findings.append(Finding(
                    "R11", f"pair/{bidder}", SEV_FAIL,
                    f"rule crashed: {type(exc).__name__}: {exc}",
                ))
    except GhApiUnreachable as exc:
        # Wave 10 recipe: distinguish "API unreachable" from "file doesn't
        # exist". Aborting with exit 3 prevents the silent false-FAIL flood
        # the prior swallowed-non-zero behavior produced.
        print(f"ERROR: GitHub API unreachable during R1 network check: {exc}",
              file=sys.stderr)
        print("Common causes:", file=sys.stderr)
        print("  - GH_TOKEN missing or insufficient scope", file=sys.stderr)
        print("  - rate limit exceeded", file=sys.stderr)
        print("  - network unavailable", file=sys.stderr)
        print("Aborting to avoid emitting misleading FAILs against reachable files.",
              file=sys.stderr)
        return 3
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
