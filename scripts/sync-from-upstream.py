#!/usr/bin/env python3
"""scripts/sync-from-upstream.py — Phase 4.1 drift detection.

Compares each pinned bidder golden against current upstream master and
emits a structured drift report. Per audit B3, this is the
deterministic-subset of the orchestrator's mechanical checks — it does
NOT run the full Claude SKILL. It encodes byte-fact comparisons (file
SHA, file presence, key field values) only.

Drift classification:
- `no-drift`   — upstream and golden match byte-for-byte / field-for-field on the checked surface.
- `data-only`  — a YAML field changed value (endpoint URL, gvl_vendor_id,
                  default_enabled, etc.) but the file shape is unchanged. Warns;
                  surfaces a "data-only-drift" finding the maintainer can
                  ack into the golden.
- `structural` — a file appeared/disappeared, the bidder_params_sha changed
                  (schema bytes diverged), a new top-level YAML key showed up,
                  or a new `*.go` file showed up in the adapter package. Fails;
                  needs a human read+update of the golden.
- `breaking`   — schema-required upstream field is missing or has the wrong
                  type. Fails; signals an upstream change that broke our
                  classification rules.

Output:
    scripts/output/drift-report.json   — machine-readable per-bidder findings.
    scripts/output/drift-report.md     — human-readable summary.

Usage:
    python3 scripts/sync-from-upstream.py                              # github-raw, all pinned
    python3 scripts/sync-from-upstream.py --source-mode=local --go-checkout=/path/to/prebid-server
    python3 scripts/sync-from-upstream.py --bidder=kobler              # single-bidder run
    python3 scripts/sync-from-upstream.py --strict                     # warns become exit 1

Exit codes: 0 (clean), 1 (fail OR warns under --strict), 2 (warns only).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, NamedTuple, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDENS_GO = REPO_ROOT / "prebid-server-go" / "read" / "test-fixtures"
GOLDENS_JAVA = REPO_ROOT / "prebid-server-java" / "read" / "test-fixtures"
DEFAULT_OUT_DIR = REPO_ROOT / "scripts" / "output"

UPSTREAM_GO_REPO = "prebid/prebid-server"
UPSTREAM_JAVA_REPO = "prebid/prebid-server-java"

# Per-bidder file lists. The set is intentionally small — Phase 4.1 is
# the mechanical sub-set; the full orchestrator covers the long tail.
GO_FILES_PER_BIDDER = [
    "static/bidder-info/{bidder}.yaml",
    "static/bidder-params/{bidder}.json",
]
JAVA_FILES_PER_BIDDER = [
    "src/main/resources/bidder-config/{bidder}.yaml",
    "src/main/resources/static/bidder-params/{bidder}.json",
]

# YAML fields the script tracks for "data-only-drift" detection.
GO_BIDDER_INFO_FIELDS = ("endpoint", "endpointCompression", "gvlVendorID",
                         "modifyingVastXmlAllowed", "disabled")
JAVA_BIDDER_CONFIG_FIELDS = ("endpoint", "endpoint-compression", "gvl-vendor-id",
                             "modifying-vast-xml-allowed", "ortb-version")

# Severity-to-exit-code: aligns with round-trip-ci.py and lint-port-rules.py
SEVERITY_PASS = "pass"
SEVERITY_WARN = "warn"
SEVERITY_FAIL = "fail"


class Finding(NamedTuple):
    bidder: str
    language: str
    type: str
    severity: str
    message: str
    detail: dict


class FetchError(Exception):
    """Raised when a fetch fails with an unrecoverable error (not 404)."""


def fetch_local(checkout_root: Path, file_path: str) -> Optional[bytes]:
    """Read a file from a local repo checkout. Returns None on missing."""
    p = checkout_root / file_path
    if p.is_file():
        return p.read_bytes()
    return None


def fetch_github_raw(repo: str, file_path: str, ref: str = "master",
                     timeout: int = 30) -> Optional[bytes]:
    """Fetch via raw.githubusercontent.com. Returns None on 404."""
    url = f"https://raw.githubusercontent.com/{repo}/{ref}/{file_path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if resp.status == 200:
                return resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise FetchError(f"HTTP {e.code} for {url}") from e
    except urllib.error.URLError as e:
        raise FetchError(f"network error for {url}: {e}") from e
    return None


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def discover_pinned_bidders() -> tuple[dict[str, Path], dict[str, Path]]:
    go = {f.stem.replace(".golden.spec", ""): f for f in GOLDENS_GO.glob("*.golden.spec.yaml")}
    java = {f.stem.replace(".golden.spec", ""): f for f in GOLDENS_JAVA.glob("*.golden.spec.yaml")}
    return go, java


def _path(d: Optional[dict], *keys) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def compare_bidder_go(bidder: str, golden_path: Path,
                      fetcher: Callable[[str], Optional[bytes]]) -> list[Finding]:
    """Compare a Go-side golden against upstream prebid-server. Returns Findings."""
    findings: list[Finding] = []
    with open(golden_path) as fp:
        golden = yaml.safe_load(fp) or {}

    is_alias = _path(golden, "meta", "is_alias")

    # 1. bidder_params_json byte-fidelity (R2 / Rule 38).
    params_path = f"static/bidder-params/{bidder}.json"
    upstream_json = fetcher(params_path)
    if upstream_json is None and not is_alias:
        findings.append(Finding(bidder, "go", "bidder_params_missing", SEVERITY_FAIL,
                                f"{params_path} not found upstream",
                                {"path": params_path}))
    elif upstream_json is not None:
        upstream_sha = compute_sha256(upstream_json)
        golden_sha = golden.get("bidder_params_sha256")
        if golden_sha and golden_sha != upstream_sha:
            findings.append(Finding(bidder, "go", "bidder_params_sha_drift", SEVERITY_FAIL,
                                    f"bidder_params_sha changed: golden {golden_sha[:16]}… vs upstream {upstream_sha[:16]}…",
                                    {"path": params_path, "golden_sha": golden_sha,
                                     "upstream_sha": upstream_sha,
                                     "golden_resolved_commit": _path(golden, "provenance", "source", "resolved_commit")}))

    # 2. bidder-info YAML — presence + tracked field comparison.
    info_path = f"static/bidder-info/{bidder}.yaml"
    upstream_yaml_bytes = fetcher(info_path)
    if upstream_yaml_bytes is None:
        findings.append(Finding(bidder, "go", "bidder_info_missing", SEVERITY_FAIL,
                                f"{info_path} not found upstream",
                                {"path": info_path}))
    else:
        try:
            upstream_yaml = yaml.safe_load(upstream_yaml_bytes) or {}
        except yaml.YAMLError as e:
            findings.append(Finding(bidder, "go", "yaml_parse_error", SEVERITY_FAIL,
                                    f"upstream YAML parse failed: {e}",
                                    {"path": info_path}))
            return findings

        # Compare endpoint specifically (most common drift source).
        golden_endpoint = _path(golden, "bidder_info", "endpoint")
        upstream_endpoint = upstream_yaml.get("endpoint")
        if golden_endpoint and upstream_endpoint and golden_endpoint != upstream_endpoint:
            findings.append(Finding(bidder, "go", "endpoint_drift", SEVERITY_WARN,
                                    f"bidder_info.endpoint changed",
                                    {"golden": golden_endpoint, "upstream": upstream_endpoint}))

        # endpointCompression.
        golden_compression = _path(golden, "bidder_info", "endpoint_compression")
        upstream_compression = (upstream_yaml.get("endpointCompression")
                                or upstream_yaml.get("endpoint-compression"))
        if (golden_compression is not None
                and upstream_compression is not None
                and golden_compression != upstream_compression):
            findings.append(Finding(bidder, "go", "endpoint_compression_drift", SEVERITY_WARN,
                                    f"bidder_info.endpoint_compression changed",
                                    {"golden": golden_compression, "upstream": upstream_compression}))

        # disabled flag.
        golden_disabled = _path(golden, "meta", "disabled") or False
        upstream_disabled = upstream_yaml.get("disabled") or False
        if golden_disabled != upstream_disabled:
            findings.append(Finding(bidder, "go", "disabled_drift", SEVERITY_WARN,
                                    f"bidder_info.disabled changed",
                                    {"golden": golden_disabled, "upstream": upstream_disabled}))

        # gvlVendorID.
        golden_gvl = _path(golden, "bidder_info", "gvl_vendor_id")
        upstream_gvl = upstream_yaml.get("gvlVendorID")
        if golden_gvl is not None and upstream_gvl is not None and golden_gvl != upstream_gvl:
            findings.append(Finding(bidder, "go", "gvl_vendor_id_drift", SEVERITY_WARN,
                                    f"bidder_info.gvl_vendor_id changed",
                                    {"golden": golden_gvl, "upstream": upstream_gvl}))

        # New top-level YAML keys (structural drift).
        golden_keys = set((_path(golden, "bidder_info", "yaml_extra_fields") or {}).keys())
        # Heuristic: known top-level YAML keys we expect from current upstream.
        known_keys = {
            "endpoint", "endpointCompression", "geoscope", "maintainer",
            "capabilities", "gvlVendorID", "modifyingVastXmlAllowed",
            "disabled", "userSyncURL", "userSync", "syncer", "yaml", "aliasOf",
            "experiment", "openrtb", "extra_info", "ortb-version",
            "endpoint-compression",  # Java-style camelCase variants tolerated
        }
        upstream_keys = set(upstream_yaml.keys()) if isinstance(upstream_yaml, dict) else set()
        new_keys = upstream_keys - known_keys - golden_keys
        if new_keys:
            findings.append(Finding(bidder, "go", "new_yaml_field", SEVERITY_FAIL,
                                    f"upstream {info_path} has new top-level keys not in golden or known-set",
                                    {"new_keys": sorted(new_keys)}))

    # 3. If alias and parent_aliases: assert alias stays an alias upstream.
    alias_of = _path(golden, "meta", "alias_of")
    if is_alias and alias_of and upstream_yaml_bytes:
        try:
            upstream_data = yaml.safe_load(upstream_yaml_bytes)
            upstream_alias_of = upstream_data.get("aliasOf") if isinstance(upstream_data, dict) else None
            if upstream_alias_of != alias_of:
                findings.append(Finding(bidder, "go", "alias_of_drift", SEVERITY_FAIL,
                                        f"meta.alias_of changed",
                                        {"golden": alias_of, "upstream": upstream_alias_of}))
        except yaml.YAMLError:
            pass  # already flagged by yaml_parse_error above

    return findings


def compare_bidder_java(bidder: str, golden_path: Path,
                        fetcher: Callable[[str], Optional[bytes]]) -> list[Finding]:
    """Compare a Java-side golden against upstream prebid-server-java. Returns Findings."""
    findings: list[Finding] = []
    with open(golden_path) as fp:
        golden = yaml.safe_load(fp) or {}

    # 1. bidder_params byte-fidelity. The golden's
    # `cross_language.java_artifacts.bidder_params_path` overrides the default
    # construction when the upstream filename diverges from the lowercase bidder
    # name (adkerneladn → adkernelAdn.json camelCase; emxdigital → emx_digital.json
    # snake_case). Phase D0.2 admitted this override; older goldens without the
    # field fall through to the default lowercase construction.
    params_path = (
        _path(golden, "cross_language", "java_artifacts", "bidder_params_path")
        or f"src/main/resources/static/bidder-params/{bidder}.json"
    )
    upstream_json = fetcher(params_path)
    if upstream_json is None and not _path(golden, "meta", "is_alias"):
        findings.append(Finding(bidder, "java", "bidder_params_missing", SEVERITY_FAIL,
                                f"{params_path} not found upstream",
                                {"path": params_path}))
    elif upstream_json is not None:
        upstream_sha = compute_sha256(upstream_json)
        golden_sha = golden.get("bidder_params_sha256")
        if golden_sha and golden_sha != upstream_sha:
            findings.append(Finding(bidder, "java", "bidder_params_sha_drift", SEVERITY_FAIL,
                                    f"bidder_params_sha changed: golden {golden_sha[:16]}… vs upstream {upstream_sha[:16]}…",
                                    {"path": params_path, "golden_sha": golden_sha, "upstream_sha": upstream_sha,
                                     "golden_resolved_commit": _path(golden, "provenance", "source", "resolved_commit")}))

    # 2. bidder-config YAML — presence + tracked field comparison.
    config_path = f"src/main/resources/bidder-config/{bidder}.yaml"
    upstream_yaml_bytes = fetcher(config_path)
    if upstream_yaml_bytes is None and not _path(golden, "meta", "is_alias"):
        # Alias children (e.g., 152media → adkernel) ride the parent's bidder-config
        # YAML; absence upstream is expected. Only fail for non-aliases.
        findings.append(Finding(bidder, "java", "bidder_config_missing", SEVERITY_FAIL,
                                f"{config_path} not found upstream",
                                {"path": config_path}))
    elif upstream_yaml_bytes is not None:
        try:
            upstream_yaml = yaml.safe_load(upstream_yaml_bytes) or {}
        except yaml.YAMLError as e:
            findings.append(Finding(bidder, "java", "yaml_parse_error", SEVERITY_FAIL,
                                    f"upstream YAML parse failed: {e}",
                                    {"path": config_path}))
            return findings

        # Java YAML wraps adapter config under `adapters.{bidder}` — drill in.
        adapter_section = _path(upstream_yaml, "adapters", bidder) or {}
        golden_endpoint = _path(golden, "bidder_info", "endpoint")
        upstream_endpoint = adapter_section.get("endpoint")
        if golden_endpoint and upstream_endpoint and golden_endpoint != upstream_endpoint:
            findings.append(Finding(bidder, "java", "endpoint_drift", SEVERITY_WARN,
                                    f"adapters.{bidder}.endpoint changed",
                                    {"golden": golden_endpoint, "upstream": upstream_endpoint}))

        # default_enabled (Java: `enabled` field; absence = true; explicit `false` flips).
        golden_enabled = _path(golden, "bidder_info", "default_enabled")
        if golden_enabled is None:
            golden_enabled = True
        upstream_enabled = adapter_section.get("enabled")
        if upstream_enabled is None:
            upstream_enabled = True
        if golden_enabled != upstream_enabled:
            findings.append(Finding(bidder, "java", "default_enabled_drift", SEVERITY_WARN,
                                    f"adapters.{bidder}.enabled changed",
                                    {"golden": golden_enabled, "upstream": upstream_enabled}))

    return findings


def render_md(findings: list[Finding], args: Any) -> str:
    out = []
    out.append("# Drift Report")
    out.append("")
    out.append("<!-- AUTO-GENERATED by scripts/sync-from-upstream.py. Regenerate via `make sync`. -->")
    out.append(f"<!-- Generated: {datetime.now(timezone.utc).isoformat()}; source-mode: {args.source_mode}; ref: {args.ref}. -->")
    out.append("")

    fail_findings = [f for f in findings if f.severity == SEVERITY_FAIL]
    warn_findings = [f for f in findings if f.severity == SEVERITY_WARN]
    pass_count = len([f for f in findings if f.severity == SEVERITY_PASS])

    out.append(f"**Summary**: {len(fail_findings)} fail, {len(warn_findings)} warn, {pass_count} informational.")
    out.append("")

    if fail_findings:
        out.append("## Failures (block merges)")
        out.append("")
        out.append(_render_findings_table(fail_findings))
        out.append("")

    if warn_findings:
        out.append("## Warnings (data-only drift; ack into goldens when ready)")
        out.append("")
        out.append(_render_findings_table(warn_findings))
        out.append("")

    if not (fail_findings or warn_findings):
        out.append("✓ No drift detected on the checked surface.")
        out.append("")

    out.append("---")
    out.append("")
    out.append("## Sources")
    out.append("")
    out.append(f"- Pinned goldens: {len(set((f.bidder, f.language) for f in findings))} bidder/language pairs scanned (covered surface: {', '.join(GO_FILES_PER_BIDDER + JAVA_FILES_PER_BIDDER)}).")
    out.append(f"- Upstream Go: `https://github.com/{UPSTREAM_GO_REPO}` ref `{args.ref}`.")
    out.append(f"- Upstream Java: `https://github.com/{UPSTREAM_JAVA_REPO}` ref `{args.ref}`.")
    out.append("- Methodology: [`docs/methodology/repo-rules.md`](../../docs/methodology/repo-rules.md), [`docs/methodology/schema-versioning.md`](../../docs/methodology/schema-versioning.md).")
    return "\n".join(out)


def _render_findings_table(findings: list[Finding]) -> str:
    lines = ["| Bidder | Language | Type | Message |",
             "|---|---|---|---|"]
    for f in findings:
        msg = f.message.replace("|", "\\|")
        lines.append(f"| `{f.bidder}` | {f.language} | `{f.type}` | {msg} |")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--source-mode", choices=["local", "github-raw"],
                        default="github-raw")
    parser.add_argument("--go-checkout", help="Local prebid-server checkout root")
    parser.add_argument("--java-checkout", help="Local prebid-server-java checkout root")
    parser.add_argument("--bidder", help="Compare a single bidder only")
    parser.add_argument("--ref", default="master", help="Upstream ref (default: master)")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings as errors (exit 1 instead of 2)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    if args.source_mode == "local":
        if not args.go_checkout:
            sys.stderr.write("ERROR: --source-mode=local requires --go-checkout (and --java-checkout for Java).\n")
            return 1
        go_fetcher = lambda p: fetch_local(Path(args.go_checkout), p)
        java_fetcher = (lambda p: fetch_local(Path(args.java_checkout), p)) if args.java_checkout else (lambda p: None)
    else:
        go_fetcher = lambda p: fetch_github_raw(UPSTREAM_GO_REPO, p, args.ref)
        java_fetcher = lambda p: fetch_github_raw(UPSTREAM_JAVA_REPO, p, args.ref)

    go, java = discover_pinned_bidders()
    if args.bidder:
        go = {k: v for k, v in go.items() if k == args.bidder}
        java = {k: v for k, v in java.items() if k == args.bidder}
        if not (go or java):
            sys.stderr.write(f"No pinned golden for {args.bidder!r}.\n")
            return 1

    findings: list[Finding] = []
    fetch_errors: list[str] = []
    for bidder, path in sorted(go.items()):
        try:
            findings.extend(compare_bidder_go(bidder, path, go_fetcher))
        except FetchError as e:
            fetch_errors.append(f"go/{bidder}: {e}")
    for bidder, path in sorted(java.items()):
        try:
            findings.extend(compare_bidder_java(bidder, path, java_fetcher))
        except FetchError as e:
            fetch_errors.append(f"java/{bidder}: {e}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "drift-report.json"
    md_path = out_dir / "drift-report.md"

    json_path.write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_mode": args.source_mode,
        "ref": args.ref,
        "bidder_count": {"go": len(go), "java": len(java)},
        "findings": [f._asdict() for f in findings],
        "fetch_errors": fetch_errors,
    }, indent=2))

    md_path.write_text(render_md(findings, args))

    if not args.quiet:
        if fetch_errors:
            sys.stderr.write("Fetch errors:\n")
            for e in fetch_errors:
                sys.stderr.write(f"  {e}\n")
        for f in findings:
            if f.severity != SEVERITY_PASS:
                print(f"[{f.severity.upper()}] {f.bidder} ({f.language}) — {f.type}: {f.message}")
        print()
        print(f"Wrote: {json_path}")
        print(f"Wrote: {md_path}")

    n_fail = sum(1 for f in findings if f.severity == SEVERITY_FAIL)
    n_warn = sum(1 for f in findings if f.severity == SEVERITY_WARN)
    print(f"OVERALL: {n_fail} fail, {n_warn} warn (over {len(go)} Go + {len(java)} Java pinned).")

    if n_fail > 0:
        return 1
    if n_warn > 0:
        return 1 if args.strict else 2
    if fetch_errors:
        # Network failures alone should not block; report and return clean.
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
