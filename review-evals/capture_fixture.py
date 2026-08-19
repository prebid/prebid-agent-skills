#!/usr/bin/env python3
"""Capture a review-eval fixture from a live GitHub PR.

This is the ONLY networked component of the review-eval harness. It snapshots a
pull request's changed-file list (with patches) at a chosen *review SHA* so that
`scripts/score_review_evals.py` can run entirely offline.

Why a review SHA and not the PR head
------------------------------------
A merged PR's head is the state *after* the maintainers' findings were fixed.
Scoring against it measures nothing: the defects are gone. Every fixture is
therefore captured at the commit the maintainers actually reviewed --
`original_commit_id` on the review comment that raised the finding.

Usage
-----
    python3 review-evals/capture_fixture.py \
        --repo prebid/prebid-server \
        --pr 4765 \
        --review-sha 6367a39cc3118e21f57642a53912d9c096591ae8 \
        --outcome defective \
        --language go

Writes `review-evals/fixtures/{repo-basename}-{pr}/{meta.yaml,files.json}`.
`expected.yaml` is hand-authored: every entry must trace to a real review
comment URL or a real merged-diff fact. This script never invents one.

Re-running against an existing fixture directory refreshes `meta.yaml` and
`files.json` and leaves `expected.yaml` untouched.
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import subprocess
import sys

# Per-file patch cap. Documented truncation boundary: we cut at the last
# complete diff line at or before this many characters and record the file in
# meta.yaml `truncation.truncated_files`. 20k chars comfortably holds a whole
# adapter implementation while keeping the corpus reviewable in a diff.
PATCH_CHAR_LIMIT = 20000

# GitHub's compare API returns at most 300 files. Recorded in meta.yaml when hit.
COMPARE_FILE_LIMIT = 300

TRUNCATION_MARKER = "\n[TRUNCATED by review-evals/capture_fixture.py: {omitted} of {total} patch characters omitted]"

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "review-evals" / "fixtures"


def gh_api(path: str) -> dict | list:
    proc = subprocess.run(
        ["gh", "api", path], capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise SystemExit(f"gh api {path} failed: {proc.stderr.strip()[:400]}")
    return json.loads(proc.stdout)


def truncate_patch(patch: str) -> tuple[str, bool]:
    """Cut `patch` at the last complete line at or before PATCH_CHAR_LIMIT."""
    if patch is None or len(patch) <= PATCH_CHAR_LIMIT:
        return patch, False
    head = patch[:PATCH_CHAR_LIMIT]
    cut = head.rfind("\n")
    if cut > 0:
        head = head[:cut]
    marker = TRUNCATION_MARKER.format(omitted=len(patch) - len(head), total=len(patch))
    return head + marker, True


def capture(repo: str, pr: int, review_sha: str, outcome: str, language: str,
            fixture_id: str | None) -> pathlib.Path:
    pr_data = gh_api(f"repos/{repo}/pulls/{pr}")
    base_ref = pr_data["base"]["ref"]
    compare = gh_api(f"repos/{repo}/compare/{base_ref}...{review_sha}")

    files = []
    truncated = []
    for f in compare.get("files", []):
        patch, was_truncated = truncate_patch(f.get("patch"))
        if was_truncated:
            truncated.append(f["filename"])
        files.append({
            "filename": f["filename"],
            "status": f["status"],
            "additions": f["additions"],
            "deletions": f["deletions"],
            "changes": f["changes"],
            "previous_filename": f.get("previous_filename"),
            "patch": patch,
        })

    reviews = gh_api(f"repos/{repo}/pulls/{pr}/reviews")
    states = [r["state"] for r in reviews if r["state"] != "COMMENTED"]

    fid = fixture_id or f"{repo.split('/')[-1]}-{pr}"
    out_dir = FIXTURES_DIR / fid
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "fixture_id": fid,
        "repo": repo,
        "pr_number": pr,
        "title": pr_data["title"],
        "language": language,
        "base_ref": base_ref,
        "review_sha": review_sha,
        "merge_base_sha": compare["merge_base_commit"]["sha"],
        "head_sha": pr_data["head"]["sha"],
        "merge_state": "merged" if pr_data.get("merged") else pr_data["state"],
        "merged_at": (pr_data.get("merged_at") or "")[:10] or None,
        "review_decision": " -> ".join(states) if states else "COMMENTED_ONLY",
        "outcome": outcome,
        "captured_at": datetime.date.today().isoformat(),
        "capture_command": (
            f"gh api repos/{repo}/compare/{base_ref}...{review_sha}"
        ),
        "file_count": len(files),
        "truncation": {
            "patch_char_limit": PATCH_CHAR_LIMIT,
            "truncated_files": truncated,
            "compare_file_limit_hit": len(files) >= COMPARE_FILE_LIMIT,
        },
    }

    (out_dir / "files.json").write_text(json.dumps(files, indent=2) + "\n")
    (out_dir / "meta.yaml").write_text(_dump_meta(meta))
    return out_dir


def _dump_meta(meta: dict) -> str:
    """Emit meta.yaml without a PyYAML dependency at capture time."""
    import yaml  # local import: capture-time only

    header = (
        "# Captured by review-evals/capture_fixture.py. Do not hand-edit.\n"
        "# review_sha is the commit the maintainers REVIEWED, not the merged head:\n"
        "# scoring against a merged head measures a diff whose defects are already fixed.\n"
    )
    return header + yaml.safe_dump(meta, sort_keys=False, default_flow_style=False)


def validate(fixture_id: str) -> int:
    """Assert every expected/forbidden anchor is actually findable in files.json.

    A fixture whose expected anchor does not occur in the captured patches is
    broken: no reviewer could reach that finding from this snapshot. Run this
    after hand-authoring expected.yaml.

    Delegates to the scorer so there is exactly one definition of anchor
    normalization; a second copy here would drift and let a fixture validate
    under one rule and score under another.
    """
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import score_review_evals as scorer  # noqa: E402

    fx = scorer.load_fixture(fixture_id, FIXTURES_DIR)
    problems = scorer.validate_fixture(fx)
    for p in problems:
        print(f"BROKEN {p}")
    if not problems:
        print(f"OK {fixture_id}: {len(fx['expected'])} expected + {len(fx['forbidden'])} "
              f"forbidden anchors all resolve inside the captured patches")
    return len(problems)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", help="owner/name, e.g. prebid/prebid-server")
    ap.add_argument("--pr", type=int)
    ap.add_argument("--review-sha", help="commit the maintainers reviewed")
    ap.add_argument("--outcome", choices=["defective", "clean"],
                    help="clean = the correct review outcome raises no blocking finding")
    ap.add_argument("--language", choices=["go", "java"])
    ap.add_argument("--fixture-id", help="override the default {repo}-{pr} directory name")
    ap.add_argument("--validate", metavar="FIXTURE_ID",
                    help="offline: assert expected.yaml anchors occur in files.json")
    args = ap.parse_args(argv)

    if args.validate:
        return 1 if validate(args.validate) else 0

    missing = [n for n in ("repo", "pr", "review_sha", "outcome", "language")
               if getattr(args, n) is None]
    if missing:
        ap.error(f"missing required options: {', '.join('--' + m.replace('_', '-') for m in missing)}")

    out = capture(args.repo, args.pr, args.review_sha, args.outcome, args.language,
                  args.fixture_id)
    print(f"captured -> {out}")
    print("next: hand-author expected.yaml, then re-run with "
          f"--validate {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
