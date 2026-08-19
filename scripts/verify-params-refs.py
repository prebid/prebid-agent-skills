#!/usr/bin/env python3
"""R2c: every `bidder_params_ref` still describes the upstream bytes it names.

WHY THIS EXISTS SEPARATELY FROM R2
    R2 runs in `make ci` and is hermetic. It proves the blob in
    `read/test-fixtures/blobs/<sha256>` hashes to `ref.sha256` and is
    `ref.bytes` long, and that `bidder_params_sha256` mirrors the ref. What it
    cannot prove offline is the thing that actually matters: that those bytes are
    the bytes upstream holds at `ref.resolved_commit`. Nothing in the repo checked
    that until this script -- R2's own docstring claimed it "runs in the weekly
    upstream-sync job" while no such check existed, which is the same shape of
    defect as a jacoco `check` goal that was only ever `report`.

    A ref is a claim about someone else's repository. Verifying it needs their
    repository.

WHAT IT CHECKS, per golden
    ref.sha256  == sha256(upstream bytes at ref.resolved_commit:ref.path)
    ref.bytes   == len(those bytes)
    the blob, when present, is byte-identical to them

    The third is the one that catches a doctored blob: R2 hashes the blob and
    compares to the ref, so a blob and a ref that were changed together are
    self-consistent. Only upstream breaks that tie.

UNVERIFIABLE IS NOT PASS
    A commit the checkout cannot reach, a path deleted upstream, or a rename
    yields UNVERIFIABLE, reported separately and (unless --allow-unverifiable)
    exiting non-zero. A shallow clone reaches only the tip, and every golden here
    pins an older commit, so the script fetches the specific commits it needs --
    a silent "0 checked, 0 failed" is the failure mode this exists to prevent.

USAGE
    python3 scripts/verify-params-refs.py \\
        --go-checkout /path/to/prebid-server \\
        --java-checkout /path/to/prebid-server-java

Exit: 0 all refs verified; 1 at least one mismatch or unverifiable; 2 setup error.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("ERROR: PyYAML required (pip install -r requirements.txt)\n")
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIRS = {
    "go": REPO_ROOT / "prebid-server-go" / "read" / "test-fixtures",
    "java": REPO_ROOT / "prebid-server-java" / "read" / "test-fixtures",
}
UPSTREAM_REMOTE = {
    "go": "https://github.com/prebid/prebid-server.git",
    "java": "https://github.com/prebid/prebid-server-java.git",
}

PASS, FAIL, UNVERIFIABLE = "pass", "fail", "unverifiable"


class Result:
    # Not a dataclass: these scripts are loaded by their tests via
    # spec_from_file_location without being registered in sys.modules, and
    # @dataclass resolves annotations through sys.modules[cls.__module__].
    # Matches the plain-class idiom in verify-upstream-claims.py.
    def __init__(self, golden: str, status: str, detail: str) -> None:
        self.golden = golden
        self.status = status
        self.detail = detail

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Result({self.golden!r}, {self.status!r}, {self.detail!r})"


def _git(checkout: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(checkout), *args], capture_output=True)


def ensure_commit(checkout: Path, commit: str, remote: str, offline: bool) -> str | None:
    """Make `commit` readable, fetching it if the checkout is shallow.

    Returns None on success, or a reason string. GitHub serves a fetch by SHA, so
    one depth-1 fetch per distinct pinned commit is enough -- cheaper than
    cloning two full histories to read six trees.
    """
    if _git(checkout, "cat-file", "-e", f"{commit}^{{commit}}").returncode == 0:
        return None
    if offline:
        return f"commit {commit[:12]} not in checkout and --offline given"
    proc = _git(checkout, "fetch", "--depth=1", remote, commit)
    if proc.returncode != 0:
        return (f"commit {commit[:12]} unreachable: "
                f"{proc.stderr.decode(errors='replace').strip()[:200]}")
    if _git(checkout, "cat-file", "-e", f"{commit}^{{commit}}").returncode != 0:
        return f"commit {commit[:12]} still unreadable after fetch"
    return None


def verify_one(golden: Path, checkout: Path, remote: str, offline: bool) -> Result:
    spec = yaml.safe_load(golden.read_text(encoding="utf-8"))
    ref = spec.get("bidder_params_ref")
    if not ref:
        # 2.0.0 requires the ref; R2 fails a non-alias without one. Reaching here
        # means the golden is not migrated, which R2 reports at its own scope.
        return Result(golden.name, UNVERIFIABLE, "no bidder_params_ref (R2 owns this)")

    missing = [k for k in ("path", "resolved_commit", "sha256", "bytes")
               if ref.get(k) is None or str(ref.get(k)).strip() == ""]
    if missing:
        return Result(golden.name, FAIL, f"bidder_params_ref missing {missing}")

    # Shape check before the git call, because a malformed digest would otherwise
    # arrive at `git show` as a plausible-looking ref and come back UNVERIFIABLE
    # -- indistinguishable from "upstream renamed the file". Also catches YAML's
    # int-parse: a 40-character all-digit sha beginning with 0 loads as the
    # integer 0, which a falsy `missing` check reads as "absent" and `str()`
    # renders as "0". None of the 42 goldens hits that today; the guard costs a
    # line and the failure it prevents is a sha that silently became something
    # else.
    for key, width in (("resolved_commit", 40), ("sha256", 64)):
        raw = ref[key]
        if not isinstance(raw, str) or not re.fullmatch(rf"[0-9a-f]{{{width}}}", raw):
            return Result(golden.name, FAIL,
                          f"bidder_params_ref.{key} is not a {width}-char lowercase hex "
                          f"string: {raw!r} (type {type(raw).__name__})")
    if not isinstance(ref["bytes"], int) or ref["bytes"] < 0:
        return Result(golden.name, FAIL,
                      f"bidder_params_ref.bytes is not a non-negative integer: "
                      f"{ref['bytes']!r}")

    commit, path = ref["resolved_commit"], str(ref["path"])
    reason = ensure_commit(checkout, commit, remote, offline)
    if reason:
        return Result(golden.name, UNVERIFIABLE, reason)

    proc = _git(checkout, "show", f"{commit}:{path}")
    if proc.returncode != 0:
        return Result(golden.name, UNVERIFIABLE,
                      f"{path} absent at {commit[:12]} (renamed or deleted upstream?)")
    data = proc.stdout
    digest = hashlib.sha256(data).hexdigest()

    problems = []
    if digest != ref["sha256"]:
        problems.append(f"sha256 {ref['sha256']} != upstream {digest}")
    if len(data) != int(ref["bytes"]):
        problems.append(f"bytes {ref['bytes']} != upstream {len(data)}")

    blob = golden.parent / "blobs" / str(ref["sha256"])
    if blob.is_file():
        stored = blob.read_bytes()
        if stored != data:
            # R2 hashes the blob against the ref, so a blob and ref edited
            # together agree with each other. Upstream is the only witness that
            # breaks that tie.
            problems.append(f"stored blob ({len(stored)}B) differs from upstream ({len(data)}B) "
                            f"even though it hashes to the declared sha")
    else:
        problems.append(f"blob {str(ref['sha256'])[:12]} absent from blobs/")

    if problems:
        return Result(golden.name, FAIL, "; ".join(problems))
    return Result(golden.name, PASS, f"{path}@{commit[:12]} {len(data)}B")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--go-checkout", type=Path)
    ap.add_argument("--java-checkout", type=Path)
    ap.add_argument("--offline", action="store_true",
                    help="never fetch; commits absent from the checkout are UNVERIFIABLE")
    ap.add_argument("--allow-unverifiable", action="store_true",
                    help="exit 0 when the only findings are unverifiable refs. Use ONLY when "
                         "an upstream rename is already tracked; an unverifiable ref is not a "
                         "verified one.")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    checkouts = {}
    if args.go_checkout:
        checkouts["go"] = args.go_checkout
    if args.java_checkout:
        checkouts["java"] = args.java_checkout
    if not checkouts:
        sys.stderr.write("ERROR: pass --go-checkout and/or --java-checkout\n")
        return 2
    for lang, p in checkouts.items():
        if not (p / ".git").exists():
            sys.stderr.write(f"ERROR: not a git checkout: {p}\n")
            return 2

    results: list[Result] = []
    for lang, checkout in checkouts.items():
        goldens = sorted(GOLDEN_DIRS[lang].glob("*.golden.spec.yaml"))
        if not goldens:
            sys.stderr.write(f"ERROR: no goldens under {GOLDEN_DIRS[lang]} -- "
                             f"an empty scan set is a setup error, not a clean result\n")
            return 2
        for golden in goldens:
            results.append(verify_one(golden, checkout, UPSTREAM_REMOTE[lang], args.offline))

    fails = [r for r in results if r.status == FAIL]
    unver = [r for r in results if r.status == UNVERIFIABLE]
    passes = [r for r in results if r.status == PASS]

    for r in results:
        if r.status != PASS or args.verbose:
            print(f"[{r.status.upper():12}] {r.golden}: {r.detail}")

    print(f"\nR2c against {', '.join(sorted(checkouts))}: "
          f"{len(results)} refs   pass={len(passes)} fail={len(fails)} "
          f"unverifiable={len(unver)}")
    if fails:
        print("A ref no longer describes the upstream bytes it names. Either upstream moved "
              "(refresh the golden at a new resolved_commit) or the ref is wrong.")
    if unver and not args.allow_unverifiable:
        print("Unverifiable refs are not verified refs. Resolve them or pass "
              "--allow-unverifiable deliberately.")
    if fails or (unver and not args.allow_unverifiable):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
