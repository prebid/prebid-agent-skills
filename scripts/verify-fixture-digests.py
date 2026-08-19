#!/usr/bin/env python3
"""Every fixture-inventory digest, checked against upstream at its golden's pin.

WHY THIS IS SEPARATE FROM THE DRIFT SCAN
    `sync-from-upstream.py` already resolves fixture entries to upstream paths and
    compares their digests -- against current MASTER. That answers "did upstream
    move?". It cannot answer "was this digest ever right?", because a digest that
    never described the file is equally unequal to master and to the pinned commit,
    and the drift report says the same thing either way.

    This checks the other question, the one `verify-params-refs.py` asks of
    `bidder_params_ref`: at `provenance.source.resolved_commit`, does each recorded
    digest and byte length describe the file it names? A golden is a point-in-time
    read, so that is the commit its claims are about.

    The failure this exists to catch has already happened once. Fourteen digests in
    the Go adverxo golden were 40 hex characters -- sha1 length, and not the sha1 of
    the file either. Every `bytes` value beside them was exactly right, so the
    lengths had been measured and the digests had not. A shape gate now requires 64
    lowercase hex or nothing, but a shape gate cannot tell a well-formed digest
    from the right one.

ONE RESOLVER, NOT TWO
    Bucket-to-path resolution is imported from `sync-from-upstream.py`
    (`_derive_fixture_paths`), which already handles the Go categories, the
    `extrainfo_*` sibling tree, and the Java `integration` bucket's
    `openrtb2/{bidder}/` root plus the folder-qualified names `generic` uses. A
    second resolver would be a second thing to keep correct, and the failure mode
    is quiet: a bare filename resolved to the first upstream path that ends in it
    reports correct digests as wrong, because `simple-banner.json` exists in over a
    hundred adapter directories.

WHAT EACH STATUS MEANS
    VERIFIED      every value the entry records matches the file at the pin.
    MISMATCH      a recorded value disagrees. Either the read was wrong or the
                  entry was edited without re-reading.
    UNMEASURED    the entry records no usable digest, and its `bytes` is absent or
                  0. Nothing to check. `bytes: 0` is indistinguishable from a
                  genuinely empty file, which is why these are worth filling rather
                  than tolerating.
    UNVERIFIABLE  the path is not present at the pin, or the entry is prose rather
                  than a filename (beachfront records "40 supplemental fixtures
                  (...)" in place of an enumeration). Not a pass.

USAGE
    python3 scripts/verify-fixture-digests.py \\
        --go-checkout /path/to/prebid-server \\
        --java-checkout /path/to/prebid-server-java

Exit: 0 all recorded claims verified; 1 a mismatch, an unverifiable entry, or
coverage below --min-coverage; 2 setup error.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("sfu", REPO_ROOT / "scripts" / "sync-from-upstream.py")
if _spec is None or _spec.loader is None:  # pragma: no cover
    sys.stderr.write("ERROR: cannot load sync-from-upstream.py; it owns the path resolution\n")
    raise SystemExit(2)
sfu = importlib.util.module_from_spec(_spec)
sys.modules["sfu"] = sfu
_spec.loader.exec_module(sfu)

UPSTREAM_REMOTE = {
    "go": "https://github.com/prebid/prebid-server.git",
    "java": "https://github.com/prebid/prebid-server-java.git",
}

VERIFIED, MISMATCH, UNMEASURED, UNVERIFIABLE = "verified", "mismatch", "unmeasured", "unverifiable"


class Result:
    # Plain class, not a dataclass: these scripts are loaded by their tests via
    # spec_from_file_location without being registered in sys.modules, and
    # @dataclass resolves annotations through sys.modules[cls.__module__].
    # Matches verify-params-refs.py and verify-upstream-claims.py.
    def __init__(self, language: str, bidder: str, origin: str, name: str,
                 status: str, detail: str) -> None:
        self.language = language
        self.bidder = bidder
        self.origin = origin
        self.name = name
        self.status = status
        self.detail = detail

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Result({self.language}/{self.bidder} {self.name!r} {self.status})"


def _git(checkout: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(checkout), *args], capture_output=True)


def ensure_commit(checkout: Path, commit: str, remote: str, offline: bool) -> str | None:
    """Make `commit` readable, fetching it when the checkout is shallow.

    The upstream-sync workflow clones at `fetch-depth: 1` and every golden pins
    something older than either tip, so without this the whole run is
    unverifiable -- and a run that reaches nothing reports zero failures. Mirrors
    verify-params-refs.py.
    """
    if _git(checkout, "cat-file", "-e", f"{commit}^{{commit}}").returncode == 0:
        return None
    if offline:
        return f"commit {commit[:12]} not in checkout and --offline given"
    proc = _git(checkout, "fetch", "--depth=1", remote, commit)
    if proc.returncode != 0:
        return (f"commit {commit[:12]} unreachable: "
                f"{proc.stderr.decode(errors='replace').strip()[:160]}")
    if _git(checkout, "cat-file", "-e", f"{commit}^{{commit}}").returncode != 0:
        return f"commit {commit[:12]} still unreadable after fetch"
    return None


def _entry_claims(golden: dict, bucket: str, filename: str) -> dict:
    """The recorded {sha256, bytes} for one entry.

    `_derive_fixture_paths` yields only a usable sha256, so `bytes` and a
    placeholder digest have to be read back off the inventory. Matched on bucket
    plus filename, and tolerant of the goldens that record a stem (`204status`)
    where the file is `204status.json`.
    """
    items = ((golden.get("tests") or {}).get("fixture_inventory") or {}).get(bucket) or []
    for item in items:
        if not isinstance(item, dict):
            continue
        recorded = str(item.get("filename"))
        if recorded == filename or f"{recorded}.json" == filename:
            return {"sha256": item.get("sha256"), "bytes": item.get("bytes")}
    return {}


def verify_golden(golden_path: Path, language: str, checkout: Path,
                  remote: str, offline: bool) -> list[Result]:
    golden = sfu._load_golden(golden_path)
    bidder = ((golden.get("meta") or {}).get("bidder_name")
              or golden_path.name.split(".")[0])
    pin = ((golden.get("provenance") or {}).get("source") or {}).get("resolved_commit")
    out: list[Result] = []
    if not pin:
        return [Result(language, bidder, "provenance.source.resolved_commit", "-",
                       UNVERIFIABLE, "golden has no resolved_commit, so its claims "
                                     "are about no particular commit")]

    reason = ensure_commit(checkout, pin, remote, offline)
    if reason:
        return [Result(language, bidder, "provenance.source.resolved_commit", "-",
                       UNVERIFIABLE, reason)]

    inventory = (golden.get("tests") or {}).get("fixture_inventory") or {}
    consumed: set[str] = set()

    for path, sha, origin, note in sfu._derive_fixture_paths(bidder, golden, language):
        consumed.add(origin.split(".")[2].removesuffix("[]"))
        if note or path is None:
            out.append(Result(language, bidder, origin, "-", UNVERIFIABLE,
                              note or "entry did not resolve to a path"))
            continue
        bucket = origin.split(".")[2].removesuffix("[]")
        filename = path.rsplit("/", 1)[-1]
        claims = _entry_claims(golden, bucket, filename)
        declared_bytes = claims.get("bytes")
        raw_sha = claims.get("sha256")

        if sha is None and (declared_bytes in (None, 0)):
            out.append(Result(language, bidder, origin, filename, UNMEASURED,
                              f"no usable sha256 ({raw_sha!r}) and bytes={declared_bytes!r}; "
                              f"bytes 0 cannot be told from an empty file"))
            continue

        proc = _git(checkout, "show", f"{pin}:{path}")
        if proc.returncode != 0:
            out.append(Result(language, bidder, origin, filename, UNVERIFIABLE,
                              f"{path} absent at {pin[:12]}"))
            continue
        data = proc.stdout
        problems = []
        if sha is not None:
            actual = hashlib.sha256(data).hexdigest()
            if actual != sha:
                problems.append(f"sha256 {sha[:16]}… != upstream {actual[:16]}…")
        if isinstance(declared_bytes, int):
            if len(data) != declared_bytes:
                problems.append(f"bytes {declared_bytes} != upstream {len(data)}")
        if problems:
            out.append(Result(language, bidder, origin, filename, MISMATCH,
                              "; ".join(problems) + f" ({path} at {pin[:12]})"))
        else:
            out.append(Result(language, bidder, origin, filename, VERIFIED,
                              f"{len(data)}B at {pin[:12]}"))

    # A bucket the resolver never yields for is neither checked nor reported by
    # the drift scan either -- it is simply invisible. `java/huaweiads` records 23
    # entries under `integration_subdirs`, and the Java arm of the resolver reads
    # only `integration`, so nothing ever looked at them. Silence is not a pass.
    for bucket, items in sorted(inventory.items()):
        if not isinstance(items, list) or not items or bucket in consumed:
            continue
        out.append(Result(language, bidder, f"tests.fixture_inventory.{bucket}[]", "-",
                          UNVERIFIABLE,
                          f"{len(items)} entries in a bucket the path resolver does not "
                          f"handle for {language}, so none of them is checked anywhere"))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--go-checkout", type=Path)
    ap.add_argument("--java-checkout", type=Path)
    ap.add_argument("--offline", action="store_true",
                    help="never fetch; a commit absent from the checkout is UNVERIFIABLE")
    ap.add_argument("--allow-unverifiable", action="store_true",
                    help="exit 0 when the only findings are unverifiable entries. An "
                         "unverifiable entry is not a verified one; pass this only for a "
                         "gap that is already tracked.")
    ap.add_argument("--min-coverage", type=float, default=None,
                    help="fail when the share of resolvable entries carrying a checkable "
                         "claim falls below this fraction (e.g. 0.95). Guards against new "
                         "entries landing unmeasured.")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    checkouts: dict[str, Path] = {}
    for lang, path in (("go", args.go_checkout), ("java", args.java_checkout)):
        if path is None:
            continue
        if not (path / ".git").exists():
            sys.stderr.write(f"ERROR: not a git checkout: {path}\n")
            return 2
        checkouts[lang] = path
    if not checkouts:
        sys.stderr.write("ERROR: pass --go-checkout and/or --java-checkout\n")
        return 2

    results: list[Result] = []
    for lang, checkout in checkouts.items():
        goldens = sorted((REPO_ROOT / f"prebid-server-{lang}" / "read" / "test-fixtures")
                         .glob("*.golden.spec.yaml"))
        if not goldens:
            sys.stderr.write(f"ERROR: no goldens for {lang} -- an empty scan set is a "
                             f"setup error, not a clean result\n")
            return 2
        for golden in goldens:
            results.extend(verify_golden(golden, lang, checkout, UPSTREAM_REMOTE[lang],
                                         args.offline))
    if not results:
        sys.stderr.write("ERROR: no fixture entries examined -- a zero-entry run is not a "
                         "clean verdict\n")
        return 2

    by_status = collections.Counter(r.status for r in results)
    for r in results:
        if r.status != VERIFIED or args.verbose:
            print(f"[{r.status.upper():12}] {r.language}/{r.bidder} {r.origin} {r.name}: {r.detail}")

    checkable = by_status[VERIFIED] + by_status[MISMATCH]
    resolvable = checkable + by_status[UNMEASURED]
    coverage = (checkable / resolvable) if resolvable else 0.0
    print(f"\nfixture digests against {', '.join(sorted(checkouts))}: {len(results)} entries   "
          f"verified={by_status[VERIFIED]} mismatch={by_status[MISMATCH]} "
          f"unmeasured={by_status[UNMEASURED]} unverifiable={by_status[UNVERIFIABLE]}")
    print(f"coverage: {checkable}/{resolvable} resolvable entries carry a checkable claim "
          f"({coverage:.1%})")

    status = 0
    if by_status[MISMATCH]:
        print("A recorded digest or byte length does not describe the file it names at the "
              "golden's own pinned commit. Either the read was wrong, or the entry was "
              "edited without re-reading.")
        status = 1
    if by_status[UNVERIFIABLE] and not args.allow_unverifiable:
        print("Unverifiable entries are not verified entries. Resolve them, or pass "
              "--allow-unverifiable deliberately.")
        status = 1
    if args.min_coverage is not None and coverage < args.min_coverage:
        print(f"Coverage {coverage:.1%} is below the --min-coverage floor "
              f"{args.min_coverage:.1%}.")
        status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
