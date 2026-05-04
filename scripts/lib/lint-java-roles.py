#!/usr/bin/env python3
"""scripts/lib/lint-java-roles.py — Wave 4 file-role enum gate.

Validates `code.file_layout.files[].role` values match the closed 5-value
enum:

    implementation, models, parsers, types, utils

Walks ONLY top-level `code.file_layout.files[]` — does NOT recurse into
hypothetical nested file lists (e.g., `code.file_layout.subdirectories[*].files[]`).
The 40-golden corpus does not currently emit nested file lists; if a future
fixture introduces them, this lint will silently miss those entries until
Wave 11b plan B5 finding-4 lands the recursive walker.

By default the lint covers Java goldens only. Pass `--include-go` to also
lint Go goldens against the 6-value Go enum (the 5 above + `data-table`).
The extra Go value reflects the Go-side IAB-category-table file (e.g.,
`adapters/msft/iab_categories.go`); Java records the same data as
`iab_category_storage.storage_kind: yaml-inlined` per ADR-001 D2 and never
ships a separate file. `make ci` and `.github/workflows/round-trip-ci.yml`
both invoke with `--include-go`, so CI does cover both languages — but
ad-hoc invocations without the flag silently skip Go. Wave 11b B5 #4
deferred the default-on flip (no nested file_layout fixtures in the
corpus today; the recursive walker that would benefit from default-on
isn't yet needed); a future wave can revisit when nested-fixture goldens
land.

Aliases (`meta.is_alias: true`) are exempt — alias goldens may legitimately
have empty `code.file_layout` because the layout is inherited from the parent.

Filename → role mapping rules live in
`prebid-server-java/read/skills/read-bidder-class/references/file-role-heuristics.md`.

Usage:
    python3 scripts/lib/lint-java-roles.py
    python3 scripts/lib/lint-java-roles.py --bidder appnexus
    python3 scripts/lib/lint-java-roles.py --include-go
    python3 scripts/lib/lint-java-roles.py --strict       # warns become exit 1
    python3 scripts/lib/lint-java-roles.py --quiet        # only summary

Exit codes (matches scripts/lib/lint-port-rules.py):
    0 — no warns, no fails
    1 — at least one fail (always blocking) OR warns with --strict
    2 — warns only, treated as success by Makefile (matches round-trip-ci.py)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, NamedTuple, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDENS_GO = REPO_ROOT / "prebid-server-go" / "read" / "test-fixtures"
GOLDENS_JAVA = REPO_ROOT / "prebid-server-java" / "read" / "test-fixtures"

JAVA_ROLES = frozenset({"implementation", "models", "parsers", "types", "utils"})
GO_ROLES = JAVA_ROLES | {"data-table"}


class Finding(NamedTuple):
    severity: str
    language: str
    bidder: str
    message: str

    def format(self) -> str:
        return f"[file-role] {self.severity.upper():<4} {self.language}/{self.bidder}: {self.message}"


def _path(d: Optional[dict], *keys) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def lint_one(spec: dict, language: str, allowed: frozenset[str]) -> list[Finding]:
    bidder = _path(spec, "meta", "bidder_name") or "unknown"
    findings: list[Finding] = []

    fl = _path(spec, "code", "file_layout") or {}
    files = fl.get("files") if isinstance(fl, dict) else None
    is_alias = bool(_path(spec, "meta", "is_alias"))

    if not files:
        if is_alias:
            findings.append(Finding(
                "pass", language, bidder,
                "alias spec — empty file_layout inherited from parent (Rule 1 of file-role-heuristics.md edge case 1)",
            ))
        else:
            findings.append(Finding(
                "warn", language, bidder,
                "non-alias spec has empty code.file_layout.files[]; expected at least one role=implementation entry",
            ))
        return findings

    seen_roles: set[str] = set()
    has_implementation = False
    for entry in files:
        if not isinstance(entry, dict):
            findings.append(Finding(
                "fail", language, bidder,
                f"non-dict entry in file_layout.files[]: {entry!r}",
            ))
            continue
        name = entry.get("name") or "<no name>"
        role = entry.get("role")
        if role is None:
            findings.append(Finding(
                "warn", language, bidder,
                f"file {name!r} has role=null; per file-role-heuristics.md Rule 8 a quirks[] entry is expected",
            ))
            continue
        if role not in allowed:
            findings.append(Finding(
                "fail", language, bidder,
                f"file {name!r} has role={role!r}; not in enum {sorted(allowed)} — see file-role-heuristics.md",
            ))
            continue
        seen_roles.add(role)
        if role == "implementation":
            has_implementation = True

    if not has_implementation and not is_alias:
        findings.append(Finding(
            "warn", language, bidder,
            "no role=implementation file in non-alias spec — every bidder needs a {Xyz}Bidder.java",
        ))

    if not findings or all(f.severity == "pass" for f in findings):
        findings.append(Finding(
            "pass", language, bidder,
            f"file_layout role enum OK ({len(files)} files; roles={sorted(seen_roles)})",
        ))

    return findings


def discover(directory: Path, bidder_filter: Optional[str]) -> list[Path]:
    paths: list[Path] = []
    for p in sorted(directory.glob("*.golden.spec.yaml")):
        bidder = p.stem.replace(".golden.spec", "")
        if bidder_filter and bidder_filter != bidder:
            continue
        paths.append(p)
    return paths


def load_spec(path: Path) -> Optional[dict]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bidder", help="Lint only this bidder name")
    parser.add_argument("--include-go", action="store_true", help="Also lint Go goldens against the 6-value Go enum")
    parser.add_argument("--strict", action="store_true", help="Treat warns as failure (exit 1 instead of 2)")
    parser.add_argument("--quiet", action="store_true", help="Print only the summary; suppress per-finding lines")
    args = parser.parse_args(argv)

    all_findings: list[Finding] = []

    java_paths = discover(GOLDENS_JAVA, args.bidder)
    for p in java_paths:
        spec = load_spec(p)
        if spec is None:
            all_findings.append(Finding("fail", "java", p.stem, "YAML parse error"))
            continue
        all_findings.extend(lint_one(spec, "java", JAVA_ROLES))

    if args.include_go:
        go_paths = discover(GOLDENS_GO, args.bidder)
        for p in go_paths:
            spec = load_spec(p)
            if spec is None:
                all_findings.append(Finding("fail", "go", p.stem, "YAML parse error"))
                continue
            all_findings.extend(lint_one(spec, "go", GO_ROLES))

    if not args.quiet:
        for f in all_findings:
            if f.severity != "pass":
                print(f.format())
        if any(f.severity != "pass" for f in all_findings):
            print()

    counts = {"pass": 0, "warn": 0, "fail": 0}
    for f in all_findings:
        counts[f.severity] += 1
    total_specs = len({(f.language, f.bidder) for f in all_findings})

    print("=== Summary ===")
    print(f"  specs linted: {total_specs}  pass={counts['pass']}  warn={counts['warn']}  fail={counts['fail']}")

    if counts["fail"] > 0:
        return 1
    if counts["warn"] > 0:
        return 1 if args.strict else 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
