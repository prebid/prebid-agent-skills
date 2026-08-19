#!/usr/bin/env python3
"""Verify the claims this repo makes about upstream prebid-server / -java.

The skills assert hundreds of facts about two repositories that move weekly:
that a symbol exists, that a struct has N fields, that a config key defaults to
true, that CI enforces a threshold. Those assertions drive FAIL verdicts on real
pull requests, so a stale one either blocks a good PR or waves through a bad
adapter. Nothing checked them until this script.

Two modes, deliberately separated:

  --check-sites     Hermetic. Asserts each claim's `sites` still contain the text
                    the manifest says they do. Catches a doc edit that drifts
                    away from the registered claim. Safe for `make ci`.

  --upstream        Networked/clone-backed. Re-derives every claim from upstream
                    source and diffs against `expect`. This is the check that
                    would have caught the deleted UsersyncerCreator, the
                    single-brace macro migration, and the 18-vs-22 macro list.

  --discover        Reports claim-shaped strings in the skill corpus that are NOT
                    registered in the manifest, so coverage can grow deliberately
                    instead of by accident.

Claim kinds
-----------
symbol         a definition exists in an upstream package (generics-aware)
absence        a name does NOT exist upstream -- load-bearing, because several
               checks now FAIL when an emission contains a deleted API
path           an upstream file exists at a path
struct_fields  a named struct's field set (membership and count)
config_value   a value at a dotted path in an upstream YAML
enforcement    "upstream enforces X" -- must name the enforcing artifact and the
               construct that does the enforcing. This kind exists because the
               repo twice asserted an enforcement that did not exist (a Jacoco
               coverage gate with no `check` goal; a "maintainer-mandatory" docs
               PR with no instance in the target repo). A symbol check cannot
               catch that class; only naming the enforcing construct can.
count          a corpus count, recorded with the query that regenerates it.
               Counts move legitimately, so drift is WARN unless strict: true.

Exit codes: 0 all good, 1 a claim failed, 2 warnings only, 3 usage/setup error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - dependency is in requirements.txt
    sys.stderr.write("ERROR: PyYAML required (pip install -r requirements.txt)\n")
    sys.exit(3)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "scripts" / "upstream-claims.yaml"

PASS, WARN, FAIL = "pass", "warn", "fail"


class Result:
    def __init__(self, claim_id: str, status: str, detail: str) -> None:
        self.claim_id = claim_id
        self.status = status
        self.detail = detail

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<{self.status} {self.claim_id}: {self.detail}>"


# --------------------------------------------------------------------------
# extractors -- each returns (ok: bool, detail: str)
# --------------------------------------------------------------------------

def _read(root: Path, rel: str) -> str | None:
    p = root / rel
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None


def check_symbol(root: Path, claim: dict) -> tuple[bool, str]:
    """A Go/Java definition exists. Generics-aware: `func Clone[T any](` counts."""
    name = claim["symbol"]
    search_dir = root / claim["upstream_path"]
    if not search_dir.exists():
        return False, f"path not found: {claim['upstream_path']}"
    files = [search_dir] if search_dir.is_file() else sorted(search_dir.rglob(claim.get("glob", "*.go")))
    patterns = [
        rf"^func\s+{re.escape(name)}\s*[\[(]",           # func Name( / func Name[T any](
        rf"^func\s+\([^)]*\)\s*{re.escape(name)}\s*[\[(]",  # method
        rf"^type\s+{re.escape(name)}[\s\[]",
        rf"^(?:var|const)\s+{re.escape(name)}\b",
        rf"^\s+{re.escape(name)}\s+[A-Za-z\[\*\(]",       # struct field / const block
        rf"^\s*(?:public|private|protected|static|final|\s)*[\w<>\[\], ]+\s+{re.escape(name)}\s*\(",  # java method
        rf"^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?class\s+{re.escape(name)}\b",
    ]
    compiled = [re.compile(p, re.M) for p in patterns]
    for f in files:
        if f.suffix not in (".go", ".java"):
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        for rx in compiled:
            if rx.search(text):
                return True, f"{f.relative_to(root)}"
    return False, f"no definition of {name} under {claim['upstream_path']}"


def check_absence(root: Path, claim: dict) -> tuple[bool, str]:
    """A name must NOT appear upstream. Several checks FAIL on its presence."""
    needle = claim["absent"]
    scope = root / claim.get("upstream_path", ".")
    if not scope.exists():
        return False, f"scope not found: {claim.get('upstream_path', '.')}"
    globs = claim.get("glob_list") or [claim.get("glob", "*.java")]
    hits: list[str] = []
    for g in globs:
        for f in scope.rglob(g):
            if not f.is_file():
                continue
            try:
                if needle in f.read_text(encoding="utf-8", errors="replace"):
                    hits.append(str(f.relative_to(root)))
            except OSError:
                continue
            if len(hits) >= 5:
                break
    if hits:
        return False, f"{needle} still present in {len(hits)}+ file(s): {hits[:3]}"
    return True, f"{needle} absent under {claim.get('upstream_path', '.')}"


def check_path(root: Path, claim: dict) -> tuple[bool, str]:
    exists = (root / claim["upstream_path"]).exists()
    want = claim.get("expect_exists", True)
    if exists == want:
        return True, f"{claim['upstream_path']} {'exists' if exists else 'absent'} as expected"
    return False, f"{claim['upstream_path']} {'exists' if exists else 'is missing'}; expected {'present' if want else 'absent'}"


def check_struct_fields(root: Path, claim: dict) -> tuple[bool, str]:
    text = _read(root, claim["upstream_path"])
    if text is None:
        return False, f"path not found: {claim['upstream_path']}"
    m = re.search(rf"type\s+{re.escape(claim['struct'])}\s+struct\s*\{{(.*?)\n\}}", text, re.S)
    if not m:
        return False, f"struct {claim['struct']} not found"
    fields = re.findall(r"^\s*(\w+)\s+[\w\[\]\*\.]+", m.group(1), re.M)
    exp = claim["expect"]
    problems = []
    if "count" in exp and len(fields) != exp["count"]:
        problems.append(f"count {len(fields)} != {exp['count']}")
    missing = [f for f in exp.get("contains", []) if f not in fields]
    if missing:
        problems.append(f"missing {missing}")
    unexpected = [f for f in fields if f not in exp.get("contains", fields)]
    if exp.get("exact") and unexpected:
        problems.append(f"unregistered {unexpected}")
    if problems:
        return False, "; ".join(problems) + f" (actual: {fields})"
    return True, f"{len(fields)} fields match"


def check_config_value(root: Path, claim: dict) -> tuple[bool, str]:
    text = _read(root, claim["upstream_path"])
    if text is None:
        return False, f"path not found: {claim['upstream_path']}"
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return False, f"unparseable YAML: {exc}"
    node: Any = doc
    for part in claim["key"].split("."):
        if not isinstance(node, dict) or part not in node:
            return False, f"key path {claim['key']} absent at {part!r}"
        node = node[part]
    if node != claim["expect"]:
        return False, f"{claim['key']} == {node!r}, expected {claim['expect']!r}"
    return True, f"{claim['key']} == {node!r}"


def check_enforcement(root: Path, claim: dict) -> tuple[bool, str]:
    """'Upstream enforces X' -- verify the construct that does the enforcing.

    `enforced: true`  the construct MUST be present in the named artifact.
    `enforced: false` it must be ABSENT -- this is how a phantom gate is caught.
    """
    found_in: list[str] = []
    for art in claim["artifacts"]:
        text = _read(root, art)
        if text is None:
            continue
        if re.search(claim["construct"], text, re.S):
            found_in.append(art)
    want = claim["enforced"]
    if want and not found_in:
        return False, f"claimed enforcement not found in {claim['artifacts']}"
    if not want and found_in:
        return False, f"claimed-absent enforcement IS present in {found_in}"
    return True, (f"enforced in {found_in}" if want else "confirmed not enforced")


def check_count(root: Path, claim: dict) -> tuple[bool, str]:
    scope = root / claim.get("upstream_path", ".")
    if not scope.exists():
        return False, f"scope not found: {claim.get('upstream_path', '.')}"
    rx = re.compile(claim["pattern"])
    n = 0
    for f in scope.rglob(claim.get("glob", "*")):
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if claim.get("mode", "files") == "files":
            n += 1 if rx.search(text) else 0
        else:
            n += len(rx.findall(text))
    if n == claim["expect"]:
        return True, f"count {n} matches"
    return False, f"count {n} != {claim['expect']} (regenerate: {claim.get('regenerate', 'n/a')})"


CHECKERS = {
    "symbol": check_symbol,
    "absence": check_absence,
    "path": check_path,
    "struct_fields": check_struct_fields,
    "config_value": check_config_value,
    "enforcement": check_enforcement,
    "count": check_count,
}


# --------------------------------------------------------------------------
# modes
# --------------------------------------------------------------------------

def check_sites(manifest: dict) -> list[Result]:
    """Hermetic: every claim's cited sites still say what the manifest says."""
    out: list[Result] = []
    for claim in manifest["claims"]:
        sites = claim.get("sites") or []
        if not sites:
            out.append(Result(claim["id"], WARN, "no sites registered -- claim is unanchored"))
            continue
        for site in sites:
            p = REPO_ROOT / site["path"]
            if not p.is_file():
                out.append(Result(claim["id"], FAIL, f"site missing: {site['path']}"))
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if site["assert"] not in text:
                out.append(Result(claim["id"], FAIL,
                                  f"{site['path']} no longer contains {site['assert']!r}"))
            else:
                out.append(Result(claim["id"], PASS, f"{site['path']} anchored"))
    return out


def check_upstream(manifest: dict, roots: dict[str, Path]) -> list[Result]:
    out: list[Result] = []
    for claim in manifest["claims"]:
        repo = claim["repo"]
        root = roots.get(repo)
        if root is None:
            out.append(Result(claim["id"], WARN, f"no checkout supplied for repo={repo}"))
            continue
        fn = CHECKERS.get(claim["kind"])
        if fn is None:
            out.append(Result(claim["id"], FAIL, f"unknown kind {claim['kind']}"))
            continue
        ok, detail = fn(root, claim)
        if ok:
            out.append(Result(claim["id"], PASS, detail))
        else:
            soft = claim["kind"] == "count" and not claim.get("strict")
            out.append(Result(claim["id"], WARN if soft else FAIL, detail))
    return out


DISCOVERY_TREES = (
    "prebid-server-go/review/skills", "prebid-server-java/review/skills",
    "prebid-server-go/port-java2go", "prebid-server-java/port-go2java",
    "prebid-server-go/read/skills", "prebid-server-java/read/skills",
)
DISCOVERY_PATTERNS = {
    "go-symbol": re.compile(r"\b(?:adapters|openrtb_ext|jsonutil|errortypes|macros|ptrutil|iterutil|config|usersync|exchange)\.[A-Z]\w+"),
    "enforcement-phrase": re.compile(r"(?i)\b(?:enforces|enforced by|blocks the build|fails CI|mandatory per|required by upstream)\b"),
}


def discover(manifest: dict) -> tuple[list[Result], dict[str, set[str]]]:
    """Report claim-shaped strings that are not registered, so coverage grows."""
    registered = set()
    for claim in manifest["claims"]:
        registered.add(claim.get("symbol") or claim.get("absent") or claim.get("struct") or claim["id"])
    hits: dict[str, set[str]] = {k: set() for k in DISCOVERY_PATTERNS}
    for tree in DISCOVERY_TREES:
        for f in (REPO_ROOT / tree).rglob("*.md"):
            text = f.read_text(encoding="utf-8", errors="replace")
            for kind, rx in DISCOVERY_PATTERNS.items():
                for m in rx.finditer(text):
                    frag = m.group(0)
                    if kind == "go-symbol" and frag.split(".", 1)[1] in registered:
                        continue
                    hits[kind].add(f"{f.relative_to(REPO_ROOT)}: {frag}")
    out: list[Result] = []
    for kind, found in hits.items():
        out.append(Result(f"discover.{kind}", WARN if found else PASS,
                          f"{len(found)} unregistered occurrence(s)"))
    return out, hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--check-sites", action="store_true", help="hermetic anchor check (CI-safe)")
    ap.add_argument("--upstream", action="store_true", help="re-derive claims from upstream checkouts")
    ap.add_argument("--go-checkout", type=Path, help="path to a prebid/prebid-server checkout")
    ap.add_argument("--java-checkout", type=Path, help="path to a prebid/prebid-server-java checkout")
    ap.add_argument("--discover", action="store_true", help="list unregistered claim-shaped strings")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    if not args.manifest.is_file():
        sys.stderr.write(f"ERROR: manifest not found: {args.manifest}\n")
        return 3
    manifest = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
    if not manifest.get("claims"):
        sys.stderr.write("ERROR: manifest declares no claims -- an empty scan set is a setup error, not a pass\n")
        return 3

    results: list[Result] = []
    if args.check_sites or not (args.upstream or args.discover):
        results += check_sites(manifest)
    if args.upstream:
        roots: dict[str, Path] = {}
        if args.go_checkout:
            roots["go"] = args.go_checkout
        if args.java_checkout:
            roots["java"] = args.java_checkout
        if not roots:
            sys.stderr.write("ERROR: --upstream needs --go-checkout and/or --java-checkout\n")
            return 3
        results += check_upstream(manifest, roots)
    if args.discover:
        disc, hits = discover(manifest)
        results += disc
        for kind, found in hits.items():
            for line in sorted(found)[:40]:
                print(f"  [{kind}] {line}")

    fails = [r for r in results if r.status == FAIL]
    warns = [r for r in results if r.status == WARN]
    passes = [r for r in results if r.status == PASS]

    for r in results:
        if r.status != PASS or args.verbose:
            print(f"[{r.status.upper():4}] {r.claim_id}: {r.detail}")

    print(f"\nclaims file: {args.manifest.relative_to(REPO_ROOT) if args.manifest.is_relative_to(REPO_ROOT) else args.manifest}")
    print(f"registered claims: {len(manifest['claims'])}   checks run: {len(results)}   "
          f"pass={len(passes)} warn={len(warns)} fail={len(fails)}")
    if fails:
        return 1
    return 2 if warns else 0


if __name__ == "__main__":
    sys.exit(main())
