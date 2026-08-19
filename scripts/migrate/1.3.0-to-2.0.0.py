#!/usr/bin/env python3
"""Migrate goldens from an inlined bidder-params transcription to a reference.

WHY
    R2 was `sha256(bidder_params_json)` -- a hash of the reader's own output. Two
    beachfront goldens embed text that was never upstream (the same ~30-byte
    elision on both language sides, plus a lost trailing space on the Go one) and
    both PASS R2, because a corrupted transcription yields a self-consistent
    hash. No hermetic check can see that.

    This migration does not repair those two files. It removes the category:
    every ref is derived from upstream bytes at the golden's own pinned commit,
    so there is nothing left to transcribe and nothing left to elide. The
    beachfront defect disappears as a side effect of the representation change.

WHAT IT WRITES
    bidder_params_ref: {path, resolved_commit, sha256, bytes}
    read/test-fixtures/blobs/<sha256>          the exact upstream bytes
    bidder_params_sha256                       re-derived from upstream, not copied

    `bidder_params_json` is left in place by default: phase 1 of the migration
    keeps both shapes valid so consumers can move while the tree stays green.
    `--drop-inline` removes it, and is the final step once nothing reads it.

REFUSALS
    A golden whose pinned bytes cannot be fetched is NOT migrated and NOT
    silently left alone -- it is reported as unmigratable and the exit code says
    so. Falling back to the inline text would carry forward exactly the data this
    change exists to distrust. `rubicon` (renamed to magnite upstream) and
    `emxdigital` (params file moved) are expected to land here; they are the
    drift refresh's work, not this migration's.

USAGE
    python3 scripts/migrate/1.3.0-to-2.0.0.py \\
        --go-checkout /path/to/prebid-server \\
        --java-checkout /path/to/prebid-server-java [--dry-run] [--drop-inline]

Exit: 0 migrated cleanly, 1 at least one golden unmigratable, 2 setup error.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("ERROR: PyYAML required (pip install -r requirements.txt)\n")
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIRS = {
    "go": REPO_ROOT / "prebid-server-go" / "read" / "test-fixtures",
    "java": REPO_ROOT / "prebid-server-java" / "read" / "test-fixtures",
}
PARAMS_PATH = {
    "go": "static/bidder-params/{name}.json",
    "java": "src/main/resources/static/bidder-params/{name}.json",
}


class Unmigratable(Exception):
    """The upstream bytes could not be obtained. Never fall back to the inline copy."""


def git_show(checkout: Path, commit: str, path: str) -> bytes:
    """Exact bytes at a commit. Text mode would normalise newlines and defeat the point."""
    proc = subprocess.run(["git", "-C", str(checkout), "show", f"{commit}:{path}"],
                          capture_output=True)
    if proc.returncode != 0:
        raise Unmigratable(f"{path} @ {commit[:12]}: {proc.stderr.decode(errors='replace').strip()}")
    return proc.stdout


def declared_params_path(spec: dict, language: str, name: str) -> str:
    """Prefer the path the spec itself records; fall back to the convention."""
    cross = spec.get("cross_language") or {}
    for key in (f"{language}_artifacts",):
        art = cross.get(key) or {}
        for field in ("bidder_params_path", "bidder_params_file"):
            if isinstance(art.get(field), str) and art[field].strip():
                return art[field].strip()
    return PARAMS_PATH[language].format(name=name)


def migrate_one(golden: Path, language: str, checkout: Path,
                blobs_dir: Path, dry_run: bool, drop_inline: bool) -> dict:
    raw = golden.read_text(encoding="utf-8")
    spec = yaml.safe_load(raw)
    name = (spec.get("meta") or {}).get("bidder_name") or golden.name.split(".")[0]

    if (spec.get("meta") or {}).get("is_alias"):
        # An alias inherits its parent's params; it has no upstream file of its own.
        return {"golden": golden.name, "status": "skipped-alias", "detail": "inherits parent params"}

    commit = ((spec.get("provenance") or {}).get("source") or {}).get("resolved_commit")
    if not commit:
        raise Unmigratable("no provenance.source.resolved_commit")
    path = declared_params_path(spec, language, name)

    data = git_show(checkout, commit, path)
    digest = hashlib.sha256(data).hexdigest()
    recorded = spec.get("bidder_params_sha256")
    inline = spec.get("bidder_params_json")
    inline_digest = hashlib.sha256(inline.encode("utf-8")).hexdigest() if isinstance(inline, str) else None

    if not dry_run:
        blobs_dir.mkdir(parents=True, exist_ok=True)
        (blobs_dir / digest).write_bytes(data)

    ref_block = (
        f"bidder_params_ref:\n"
        f"  path: {path}\n"
        f"  resolved_commit: {commit}\n"
        f"  sha256: {digest}\n"
        f"  bytes: {len(data)}\n"
    )
    new = raw
    if "bidder_params_ref:" not in new:
        # Insert immediately before the sha it mirrors, so the two read together.
        marker = "bidder_params_sha256:"
        idx = new.index(marker)
        line_start = new.rfind("\n", 0, idx) + 1
        new = new[:line_start] + ref_block + new[line_start:]
    import re
    new = re.sub(r"^bidder_params_sha256:.*$", f"bidder_params_sha256: {digest}", new,
                 count=1, flags=re.M)
    if drop_inline and isinstance(inline, str):
        new = re.sub(r"^bidder_params_json: [|>][-+]?\n(?:(?:[ \t]+.*)?\n)*", "", new,
                     count=1, flags=re.M)
        new = re.sub(r"^bidder_params_json:.*\n", "", new, count=1, flags=re.M)

    if not dry_run:
        golden.write_text(new, encoding="utf-8")

    return {
        "golden": golden.name, "status": "migrated", "path": path, "sha256": digest,
        "bytes": len(data),
        "recorded_sha_was_correct": recorded == digest,
        "inline_matched_upstream": inline_digest == digest if inline_digest else None,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--go-checkout", type=Path, required=True)
    ap.add_argument("--java-checkout", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--drop-inline", action="store_true",
                    help="remove bidder_params_json (final step; only once nothing reads it)")
    args = ap.parse_args(argv)

    for p in (args.go_checkout, args.java_checkout):
        if not (p / ".git").exists():
            sys.stderr.write(f"ERROR: not a git checkout: {p}\n")
            return 2

    results, failures = [], []
    for language, gdir in GOLDEN_DIRS.items():
        checkout = args.go_checkout if language == "go" else args.java_checkout
        blobs = gdir / "blobs"
        for golden in sorted(gdir.glob("*.golden.spec.yaml")):
            try:
                results.append(migrate_one(golden, language, checkout, blobs,
                                           args.dry_run, args.drop_inline))
            except Unmigratable as exc:
                failures.append({"golden": f"{language}/{golden.name}", "reason": str(exc)})

    migrated = [r for r in results if r["status"] == "migrated"]
    aliases = [r for r in results if r["status"] == "skipped-alias"]
    corrupt = [r for r in migrated if r["inline_matched_upstream"] is False]
    wrong_sha = [r for r in migrated if not r["recorded_sha_was_correct"]]

    print(f"migrated {len(migrated)}   aliases skipped {len(aliases)}   unmigratable {len(failures)}"
          f"{'   (dry run)' if args.dry_run else ''}")
    if corrupt:
        print(f"\ninline text did NOT match upstream in {len(corrupt)} golden(s) -- "
              f"the defect this migration removes:")
        for r in corrupt:
            print(f"  {r['golden']}: upstream {r['bytes']}B sha {r['sha256'][:12]}…")
    if wrong_sha:
        print(f"\nrecorded bidder_params_sha256 was wrong in {len(wrong_sha)} golden(s), now re-derived:")
        for r in wrong_sha:
            print(f"  {r['golden']} -> {r['sha256'][:12]}…")
    if failures:
        print(f"\nUNMIGRATABLE -- not touched, and NOT falling back to the inline copy:")
        for f in failures:
            print(f"  {f['golden']}: {f['reason']}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
