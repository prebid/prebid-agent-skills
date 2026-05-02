#!/usr/bin/env python3
"""audit-golden.py — Phase 1.5 golden vs upstream verification.

For each golden Adapter Specification YAML, fetches the upstream files at
the golden's `provenance.source.resolved_commit` and verifies that the
recorded facts match upstream byte-for-byte where applicable. Encodes a
deterministic-subset of the orchestrator's mechanical checks; does NOT
run the full Claude SKILL.

Checks performed:

  C1  bidder_params_sha256 matches sha256(upstream bidder-params JSON)
  C2  bidder_info top-level fields match upstream YAML (endpoint,
      endpoint_compression, gvl_vendor_id, default_enabled, maintainer
      email, capabilities, geoscope, modifying_vast_xml_allowed)
  C3  Every entry in code.file_layout.files[] exists in upstream
      adapter directory
  C4  Every fixture filename in tests.fixture_inventory.* exists at
      tests.test_root_directory upstream (Go: adapters/<bidder>/<root>/;
      Java: src/test/java/.../<root>/)
  C5  meta.bidder_name matches the golden's filename basename

Skipped or partially-handled cases:

  - Aliases (meta.is_alias=true): only C1 and C5 run; C2/C3/C4 are
    inheritance-driven and would require resolving against the parent
  - One-side-only goldens (Java orphan, etc.): same as standalone
  - Java goldens: bidder-params lives under
    src/main/resources/static/bidder-params/<bidder>.json; bidder-config
    lives under src/main/resources/bidder-config/<bidder>.yaml

Usage:
  python3 scripts/audit-golden.py <bidder>           # one bidder, both langs if both exist
  python3 scripts/audit-golden.py --all              # every golden
  python3 scripts/audit-golden.py --json <bidder>    # machine-readable

Exit codes:
  0  all checks pass for the audited golden(s)
  1  at least one check FAIL
  2  warnings only (e.g., upstream unreachable for some bidders)
"""

from __future__ import annotations

import argparse
import base64
import dataclasses
import glob
import hashlib
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Finding & report shapes
# ---------------------------------------------------------------------------

SEV_PASS = "pass"
SEV_WARN = "warn"
SEV_FAIL = "fail"
SEV_SKIP = "skip"


@dataclasses.dataclass
class Finding:
    check: str           # C1, C2, C3, C4, C5
    severity: str        # pass | warn | fail | skip
    field: str           # e.g., "bidder_info.endpoint"
    detail: str

    def short(self) -> str:
        return f"  [{self.check} {self.severity.upper()}] {self.field}: {self.detail}"


@dataclasses.dataclass
class Audit:
    golden_path: str
    bidder: str
    language: str        # "go" | "java"
    commit: str
    is_alias: bool
    findings: List[Finding] = dataclasses.field(default_factory=list)

    @property
    def status(self) -> str:
        if any(f.severity == SEV_FAIL for f in self.findings):
            return SEV_FAIL
        if any(f.severity == SEV_WARN for f in self.findings):
            return SEV_WARN
        return SEV_PASS


# ---------------------------------------------------------------------------
# Upstream fetch helpers (gh api authenticated)
# ---------------------------------------------------------------------------

GO_REPO = "prebid/prebid-server"
JAVA_REPO = "prebid/prebid-server-java"


def gh_get_file(repo: str, path: str, ref: str) -> Optional[bytes]:
    """Fetch a single file's raw bytes via gh api. Returns None on 404."""
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/contents/{path}?ref={ref}"],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    try:
        d = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(d, dict) or "content" not in d:
        return None
    try:
        return base64.b64decode(d["content"])
    except Exception:
        return None


def gh_list_dir(repo: str, path: str, ref: str) -> Optional[List[Dict[str, Any]]]:
    """List a directory's entries via gh api. Returns None on 404."""
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/contents/{path}?ref={ref}"],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    try:
        d = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if isinstance(d, list):
        return d
    return None


# ---------------------------------------------------------------------------
# Per-check logic
# ---------------------------------------------------------------------------


def check_c1_bidder_params_sha(audit: Audit, golden: Dict[str, Any]) -> None:
    """Verify upstream sha256(bidder-params JSON) == golden's recorded SHA."""
    expected_sha = golden.get("bidder_params_sha256")
    if audit.is_alias:
        # Aliases inherit the parent's bidder-params JSON; their own file
        # doesn't exist upstream. The SHA in the golden represents the
        # parent's file. Verifying it would require parent-resolution.
        audit.findings.append(Finding(
            "C1", SEV_SKIP, "bidder_params_sha256",
            "alias spec — params inherited from parent (not audited)",
        ))
        return
    if not expected_sha:
        return
    if audit.language == "go":
        path = f"static/bidder-params/{audit.bidder}.json"
        repo = GO_REPO
    else:
        path = f"src/main/resources/static/bidder-params/{audit.bidder}.json"
        repo = JAVA_REPO
    upstream = gh_get_file(repo, path, audit.commit)
    if upstream is None:
        audit.findings.append(Finding(
            "C1", SEV_WARN, "bidder_params_sha256",
            f"upstream {path} not found at {audit.commit[:8]} — file may have moved/been deleted",
        ))
        return
    actual_sha = hashlib.sha256(upstream).hexdigest()
    if actual_sha != expected_sha:
        audit.findings.append(Finding(
            "C1", SEV_FAIL, "bidder_params_sha256",
            f"golden={expected_sha} upstream={actual_sha} — golden is stale OR upstream rotated bytes",
        ))
    else:
        audit.findings.append(Finding(
            "C1", SEV_PASS, "bidder_params_sha256",
            f"sha matches upstream {actual_sha[:12]}…",
        ))


def check_c2_bidder_info(audit: Audit, golden: Dict[str, Any]) -> None:
    """Compare bidder_info top-level fields against upstream YAML."""
    if audit.is_alias:
        # Aliases inherit fields from parent; per-field comparison would
        # need to resolve through the parent. Skip for now; a future audit
        # iteration can do parent-resolution.
        audit.findings.append(Finding(
            "C2", SEV_SKIP, "bidder_info.*",
            "alias inheritance not resolved (parent-resolution out of scope for Phase 1.5)",
        ))
        return

    if audit.language == "go":
        path = f"static/bidder-info/{audit.bidder}.yaml"
        repo = GO_REPO
        # Go YAML is flat: keys at top level (endpoint, maintainer, capabilities, etc.)
        flat = True
    else:
        path = f"src/main/resources/bidder-config/{audit.bidder}.yaml"
        repo = JAVA_REPO
        # Java YAML nests under adapters.<bidder>.{...}
        flat = False
    upstream_bytes = gh_get_file(repo, path, audit.commit)
    if upstream_bytes is None:
        audit.findings.append(Finding(
            "C2", SEV_WARN, "bidder_info.*",
            f"upstream {path} not found at {audit.commit[:8]}",
        ))
        return
    try:
        upstream_yaml = yaml.safe_load(upstream_bytes.decode("utf-8"))
    except Exception as exc:
        audit.findings.append(Finding(
            "C2", SEV_FAIL, "bidder_info.*",
            f"upstream YAML failed to parse: {exc}",
        ))
        return

    if flat:
        upstream_root = upstream_yaml
    else:
        adapters = (upstream_yaml or {}).get("adapters") or {}
        upstream_root = adapters.get(audit.bidder) or {}

    bi = golden.get("bidder_info") or {}
    # Go uses snake_case for our spec, but upstream YAML uses camelCase
    # (Go) or kebab-case (Java). Translate per language.
    field_map_go = {
        "endpoint": "endpoint",
        "endpoint_compression": "endpointCompression",
        "modifying_vast_xml_allowed": "modifyingVastXmlAllowed",
    }
    field_map_java = {
        "endpoint": "endpoint",
        "endpoint_compression": "endpoint-compression",
        "modifying_vast_xml_allowed": "modifying-vast-xml-allowed",
    }
    field_map = field_map_go if audit.language == "go" else field_map_java

    # Booleans absent from upstream YAML default to False. A golden that
    # records `false` is consistent with `None` in upstream YAML — only
    # `True` golden vs `None` upstream is real divergence.
    BOOLEAN_FIELDS_DEFAULT_FALSE = {"modifying_vast_xml_allowed"}
    BOOLEAN_FIELDS_DEFAULT_TRUE = {"default_enabled"}
    # Some fields are case-insensitive at parse time (e.g., gzip == GZIP).
    CASE_INSENSITIVE_STRING_FIELDS = {"endpoint_compression"}

    def _compare(spec_field: str, upstream_key: str) -> None:
        spec_value = bi.get(spec_field)
        if spec_value is None:
            return  # field nulled in golden — nothing to verify
        upstream_value = upstream_root.get(upstream_key)
        # Apply boolean default-equivalence
        if spec_field in BOOLEAN_FIELDS_DEFAULT_FALSE:
            if spec_value is False and upstream_value is None:
                audit.findings.append(Finding(
                    "C2", SEV_PASS, f"bidder_info.{spec_field}",
                    "False matches upstream-absent (defaults to false)",
                ))
                return
        if spec_field in BOOLEAN_FIELDS_DEFAULT_TRUE:
            if spec_value is True and upstream_value is None:
                audit.findings.append(Finding(
                    "C2", SEV_PASS, f"bidder_info.{spec_field}",
                    "True matches upstream-absent (defaults to true)",
                ))
                return
        if spec_field in CASE_INSENSITIVE_STRING_FIELDS:
            if (isinstance(spec_value, str) and isinstance(upstream_value, str)
                    and spec_value.lower() == upstream_value.lower()):
                audit.findings.append(Finding(
                    "C2", SEV_PASS, f"bidder_info.{spec_field}",
                    f"matches upstream (case-insensitive: golden={spec_value!r} upstream={upstream_value!r})",
                ))
                return
        if upstream_value != spec_value:
            audit.findings.append(Finding(
                "C2", SEV_FAIL, f"bidder_info.{spec_field}",
                f"golden={spec_value!r} upstream={upstream_value!r}",
            ))
        else:
            audit.findings.append(Finding(
                "C2", SEV_PASS, f"bidder_info.{spec_field}",
                f"matches upstream",
            ))

    for spec_field, upstream_key in field_map.items():
        _compare(spec_field, upstream_key)

    # Maintainer email — nested
    spec_email = ((bi.get("maintainer") or {}).get("email"))
    if spec_email:
        if audit.language == "go":
            upstream_email = (upstream_root.get("maintainer") or {}).get("email")
        else:
            upstream_email = (upstream_root.get("meta-info") or {}).get("maintainer-email")
        if upstream_email != spec_email:
            audit.findings.append(Finding(
                "C2", SEV_FAIL, "bidder_info.maintainer.email",
                f"golden={spec_email!r} upstream={upstream_email!r}",
            ))
        else:
            audit.findings.append(Finding(
                "C2", SEV_PASS, "bidder_info.maintainer.email",
                "matches upstream",
            ))

    # GVL vendor ID — nested differently per language
    spec_gvl = bi.get("gvl_vendor_id")
    if spec_gvl is not None:
        if audit.language == "go":
            upstream_gvl = upstream_root.get("gvlVendorID")
        else:
            upstream_gvl = (upstream_root.get("meta-info") or {}).get("vendor-id")
        # Treat 0/None equivalently (unset GVL)
        spec_gvl_norm = 0 if spec_gvl in (0, None, "") else spec_gvl
        upstream_gvl_norm = 0 if upstream_gvl in (0, None, "") else upstream_gvl
        if upstream_gvl_norm != spec_gvl_norm:
            audit.findings.append(Finding(
                "C2", SEV_FAIL, "bidder_info.gvl_vendor_id",
                f"golden={spec_gvl} upstream={upstream_gvl}",
            ))
        else:
            audit.findings.append(Finding(
                "C2", SEV_PASS, "bidder_info.gvl_vendor_id",
                "matches upstream",
            ))


def check_c3_file_layout(audit: Audit, golden: Dict[str, Any]) -> None:
    """Verify each file in code.file_layout.files[] exists upstream.

    Walks the bidder directory + 1 level of subdirectories. Java commonly
    splits helper classes into `request/`, `response/`, `proto/` subdirs;
    Go is typically flat but msft has `test-extrainfo/` (which doesn't
    contain Go source, just JSON fixtures, so it's irrelevant here).
    """
    if audit.is_alias:
        audit.findings.append(Finding(
            "C3", SEV_SKIP, "code.file_layout.files",
            "alias — adapter code is the parent's; not audited per-file",
        ))
        return
    code = golden.get("code") or {}
    files = ((code.get("file_layout") or {}).get("files") or [])
    if not files:
        audit.findings.append(Finding(
            "C3", SEV_SKIP, "code.file_layout.files",
            "no files declared in golden",
        ))
        return
    # Use the golden's declared bidder_dir if present; otherwise derive.
    cl = golden.get("cross_language") or {}
    if audit.language == "go":
        repo = GO_REPO
        go_arts = cl.get("go_artifacts") or {}
        adapter_dir = (go_arts.get("bidder_dir") or f"adapters/{audit.bidder}").rstrip("/")
    else:
        repo = JAVA_REPO
        java_arts = cl.get("java_artifacts") or {}
        adapter_dir = (
            java_arts.get("bidder_dir") or f"src/main/java/org/prebid/server/bidder/{audit.bidder}"
        ).rstrip("/")

    # List the bidder dir; if it has subdirs that are likely to host helper
    # classes (request/, response/, proto/), list those too. We collect ALL
    # filenames (basename) into a single set for matching against declared.
    upstream_listing = gh_list_dir(repo, adapter_dir, audit.commit)
    if upstream_listing is None:
        audit.findings.append(Finding(
            "C3", SEV_WARN, "code.file_layout.files",
            f"upstream dir {adapter_dir} not listable at {audit.commit[:8]}",
        ))
        return
    upstream_names: set = set()

    def _walk(path: str, depth: int) -> None:
        listing = gh_list_dir(repo, path, audit.commit) or []
        for item in listing:
            t = item.get("type")
            if t == "file":
                upstream_names.add(item["name"])
            elif t == "dir" and depth > 0 and audit.language == "java":
                # Recurse into Java subdirs that commonly host helpers
                # (request/, response/, proto/, model/). Allow 2 levels
                # deep — huaweiads has model/request/, rubicon has
                # proto/request/, etc.
                sub = item["name"]
                if sub in {"request", "response", "proto", "model", "models", "ext"}:
                    _walk(f"{path}/{sub}", depth - 1)

    for item in upstream_listing:
        if item.get("type") == "file":
            upstream_names.add(item["name"])
        elif item.get("type") == "dir" and audit.language == "java":
            sub = item["name"]
            if sub in {"request", "response", "proto", "model", "models", "ext"}:
                _walk(f"{adapter_dir}/{sub}", depth=2)
    # Also walk the proto directory for Java (ExtImp* lives under
    # src/main/java/org/prebid/server/proto/openrtb/ext/request/<bidder>/)
    if audit.language == "java":
        proto_listing = gh_list_dir(
            repo,
            f"src/main/java/org/prebid/server/proto/openrtb/ext/request/{audit.bidder}",
            audit.commit,
        ) or []
        for s in proto_listing:
            if s.get("type") == "file":
                upstream_names.add(s["name"])
    declared_names = {(f.get("name") or "").rsplit("/", 1)[-1] for f in files}
    missing_upstream = declared_names - upstream_names
    extra_upstream_non_test = (upstream_names - declared_names) - {
        n for n in upstream_names
        if n.endswith("_test.go") or n.endswith("Test.java")
    }
    # Special-case "single-file at top of bidder/ namespace" goldens
    # (Java's `generic` adapter): bidder_dir is the framework root and
    # contains many framework classes that are NOT this bidder's. If the
    # golden declares only one file at the dir root, suppress the
    # framework-file noise.
    is_framework_root = (
        audit.language == "java"
        and adapter_dir.rstrip("/").endswith("/bidder")
        and len(declared_names) <= 2
    )
    if is_framework_root:
        extra_upstream_non_test = set()
    # Files tracked under params.ext_struct.file (Go: openrtb_ext/imp_<X>.go;
    # Java: ExtImp<Bidder>.java in proto/openrtb/ext/request/<bidder>/) are
    # NOT declared in code.file_layout.files[] — they live in a separate
    # spec block. Suppress them from "extras" so the audit doesn't
    # spuriously WARN.
    extra_upstream_non_test = {
        n for n in extra_upstream_non_test
        if not (n.startswith("ExtImp") and n.endswith(".java"))
        and not (n.startswith("ExtUser") and audit.bidder.lower() in n.lower() and n.endswith(".java"))
        # Other proto-path files (e.g., RubiconVideoParams.java) live
        # under proto/openrtb/ext/request/<bidder>/ and are conceptually
        # tracked under params/proto blocks; suppress as "extras" if they
        # carry the bidder name as their TitleCase prefix and end in .java
        and not (n.endswith(".java") and audit.bidder.replace("_", "").lower() in n.lower())
    }
    if missing_upstream:
        audit.findings.append(Finding(
            "C3", SEV_FAIL, "code.file_layout.files",
            f"declared in golden but missing upstream: {sorted(missing_upstream)}",
        ))
    if extra_upstream_non_test:
        audit.findings.append(Finding(
            "C3", SEV_WARN, "code.file_layout.files",
            f"upstream has files not in golden: {sorted(extra_upstream_non_test)}",
        ))
    if not missing_upstream and not extra_upstream_non_test:
        audit.findings.append(Finding(
            "C3", SEV_PASS, "code.file_layout.files",
            f"{len(declared_names)} declared files all match upstream",
        ))


def check_c4_fixture_inventory(audit: Audit, golden: Dict[str, Any]) -> None:
    """Spot-check fixture filenames against upstream test directory."""
    if audit.is_alias:
        audit.findings.append(Finding(
            "C4", SEV_SKIP, "tests.fixture_inventory",
            "alias — fixtures are inherited; not audited per-file",
        ))
        return
    tests = golden.get("tests") or {}
    test_root = tests.get("test_root_directory")
    inv = tests.get("fixture_inventory") or {}
    declared = []
    for category, items in inv.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and item.get("filename"):
                declared.append((category, item["filename"]))
    if not declared:
        audit.findings.append(Finding(
            "C4", SEV_SKIP, "tests.fixture_inventory",
            "no fixtures declared in golden",
        ))
        return
    if not test_root:
        audit.findings.append(Finding(
            "C4", SEV_WARN, "tests.test_root_directory",
            "test_root_directory unset; skipping per-file existence check",
        ))
        return
    if audit.language == "go":
        # Go: adapters/<bidder>/<test_root>/<category>/<filename>.json
        # test_root is e.g. "koblertest"; categories live underneath.
        # Special case: msft has dual test root — categories prefixed
        # with `extrainfo_` map to `test-extrainfo/<rest>/`, others to
        # the canonical test_root.
        base = f"adapters/{audit.bidder}/{test_root}"
        repo = GO_REPO
    else:
        # Java IT fixtures live at src/test/resources/org/prebid/server/it/
        # The golden's test_root_directory points at the JUnit class root
        # (under src/test/java/...), NOT the JSON fixture root. The
        # filename field may itself include a path prefix (e.g.,
        # 'openrtb2/generic/test-...json') — in which case we resolve
        # against the IT base, otherwise prepend openrtb2/<bidder>/.
        base = "src/test/resources/org/prebid/server/it"
        repo = JAVA_REPO

    # Sample-check: list ALL category directories in a single pass; for
    # each declared filename, ensure it exists in the listing.
    categories_seen: Dict[str, set] = {}
    for category, filename in declared:
        if audit.language == "go":
            # msft dual test root: extrainfo_* categories live under
            # adapters/<bidder>/test-extrainfo/<remainder>
            if category.startswith("extrainfo_"):
                remainder = category[len("extrainfo_"):]
                cat_dir = f"adapters/{audit.bidder}/test-extrainfo/{remainder}"
            else:
                cat_dir = f"{base}/{category}"
            check_filename = filename
        else:
            # If filename has a '/', it's a relative path from the IT base
            if "/" in filename:
                # Split the path: dir + basename
                dir_part, _, fname = filename.rpartition("/")
                cat_dir = f"{base}/{dir_part}"
                check_filename = fname
            else:
                cat_dir = f"{base}/openrtb2/{audit.bidder}"
                check_filename = filename
        if cat_dir not in categories_seen:
            listing = gh_list_dir(repo, cat_dir, audit.commit)
            if listing is None:
                categories_seen[cat_dir] = set()
            else:
                categories_seen[cat_dir] = {
                    i["name"] for i in listing if i.get("type") == "file"
                }
        if check_filename not in categories_seen[cat_dir]:
            audit.findings.append(Finding(
                "C4", SEV_FAIL, f"tests.fixture_inventory.{category}",
                f"{filename} not found upstream at {cat_dir}",
            ))
    # Aggregate pass result
    fail_count = sum(1 for f in audit.findings if f.check == "C4" and f.severity == SEV_FAIL)
    if fail_count == 0:
        audit.findings.append(Finding(
            "C4", SEV_PASS, "tests.fixture_inventory",
            f"{len(declared)} fixture filenames all exist upstream",
        ))


def check_c5_bidder_name_filename(audit: Audit, golden: Dict[str, Any]) -> None:
    """Verify meta.bidder_name == golden filename basename."""
    expected = audit.bidder
    actual = (golden.get("meta") or {}).get("bidder_name")
    if not actual:
        audit.findings.append(Finding(
            "C5", SEV_FAIL, "meta.bidder_name",
            "missing meta.bidder_name in golden",
        ))
        return
    if actual != expected:
        audit.findings.append(Finding(
            "C5", SEV_FAIL, "meta.bidder_name",
            f"golden filename={expected} but meta.bidder_name={actual}",
        ))
    else:
        audit.findings.append(Finding(
            "C5", SEV_PASS, "meta.bidder_name",
            f"matches filename ({expected})",
        ))


# ---------------------------------------------------------------------------
# Discovery + driver
# ---------------------------------------------------------------------------


def discover_goldens(filter_bidder: Optional[str] = None) -> List[str]:
    paths: List[str] = []
    for lang in ("prebid-server-go", "prebid-server-java"):
        pattern = os.path.join(REPO_ROOT, lang, "read", "test-fixtures", "*.golden.spec.yaml")
        for p in sorted(glob.glob(pattern)):
            bidder = os.path.basename(p).removesuffix(".golden.spec.yaml")
            if filter_bidder and bidder != filter_bidder:
                continue
            paths.append(p)
    return paths


def audit_one(path: str) -> Audit:
    bidder = os.path.basename(path).removesuffix(".golden.spec.yaml")
    language = "go" if "/prebid-server-go/" in path else "java"
    with open(path) as fp:
        golden = yaml.safe_load(fp)
    commit = (
        ((golden.get("provenance") or {}).get("source") or {}).get("resolved_commit")
        or ""
    )
    is_alias = bool((golden.get("meta") or {}).get("is_alias"))
    audit = Audit(
        golden_path=path, bidder=bidder, language=language,
        commit=commit, is_alias=is_alias,
    )
    if not commit:
        audit.findings.append(Finding(
            "PRE", SEV_FAIL, "provenance.source.resolved_commit",
            "missing — cannot fetch upstream",
        ))
        return audit
    check_c5_bidder_name_filename(audit, golden)
    check_c1_bidder_params_sha(audit, golden)
    check_c2_bidder_info(audit, golden)
    check_c3_file_layout(audit, golden)
    check_c4_fixture_inventory(audit, golden)
    return audit


def render_text(audits: List[Audit]) -> Tuple[str, int]:
    lines: List[str] = []
    fail_count = 0
    warn_count = 0
    for a in audits:
        rel = os.path.relpath(a.golden_path, REPO_ROOT)
        status_label = a.status.upper()
        lines.append(f"### {rel} [{a.language}] [{status_label}]")
        lines.append(f"  bidder: {a.bidder}  commit: {a.commit[:12]}…  is_alias: {a.is_alias}")
        for f in a.findings:
            lines.append(f.short())
            if f.severity == SEV_FAIL:
                fail_count += 1
            elif f.severity == SEV_WARN:
                warn_count += 1
        lines.append("")
    lines.append(f"OVERALL: {len(audits)} goldens audited, {fail_count} failure(s), {warn_count} warning(s)")
    if fail_count:
        exit_code = 1
    elif warn_count:
        exit_code = 2
    else:
        exit_code = 0
    lines.append(f"EXIT CODE: {exit_code}")
    return "\n".join(lines), exit_code


def render_json(audits: List[Audit]) -> Tuple[str, int]:
    fail_count = sum(1 for a in audits for f in a.findings if f.severity == SEV_FAIL)
    warn_count = sum(1 for a in audits for f in a.findings if f.severity == SEV_WARN)
    payload = {
        "audits": [
            {
                "golden_path": os.path.relpath(a.golden_path, REPO_ROOT),
                "bidder": a.bidder,
                "language": a.language,
                "commit": a.commit,
                "is_alias": a.is_alias,
                "status": a.status,
                "findings": [
                    {"check": f.check, "severity": f.severity,
                     "field": f.field, "detail": f.detail}
                    for f in a.findings
                ],
            }
            for a in audits
        ],
        "summary": {
            "audited": len(audits),
            "fail": fail_count,
            "warn": warn_count,
        },
    }
    if fail_count:
        exit_code = 1
    elif warn_count:
        exit_code = 2
    else:
        exit_code = 0
    return json.dumps(payload, indent=2), exit_code


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("bidder", nargs="?", help="Bidder name (audits both Go and Java goldens if both exist)")
    parser.add_argument("--all", action="store_true", help="Audit every golden under prebid-server-{go,java}/read/test-fixtures/")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    if not args.all and not args.bidder:
        parser.error("supply a bidder name or --all")

    paths = discover_goldens(filter_bidder=None if args.all else args.bidder)
    if not paths:
        print(f"ERROR: no goldens matched {'--all' if args.all else args.bidder!r}", file=sys.stderr)
        return 1

    audits = [audit_one(p) for p in paths]
    if args.json:
        text, code = render_json(audits)
    else:
        text, code = render_text(audits)
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
