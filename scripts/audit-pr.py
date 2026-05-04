#!/usr/bin/env python3
"""scripts/audit-pr.py — Phase 4.2 PR novelty classification.

Given a PR URL on `prebid/prebid-server` or `prebid/prebid-server-java`,
fetches the diff via `gh`, loads the current taxonomy + rules + Java
edge-case catalog, and asks Claude (when CLAUDE_API_KEY is set) to
classify whether the PR introduces a pattern not yet captured.

Output:
    scripts/output/audit-<PR-NUMBER>.json   — structured findings.
    scripts/output/audit-<PR-NUMBER>.md     — human-readable summary.

Two modes:

1. **API mode** (CLAUDE_API_KEY env var set): calls Anthropic Messages
   API directly via urllib (no SDK dependency). Returns Claude's
   classification verdict + rationale + a concrete proposal if novel.

2. **Manual mode** (no API key): builds the prompt and writes it to
   scripts/output/audit-<PR-NUMBER>.prompt.txt. The maintainer pastes
   the prompt into Claude.ai or claude-code manually and feeds the
   answer back via `--manual-answer=<file>` to render the report.

Usage:
    export CLAUDE_API_KEY=sk-ant-...
    python3 scripts/audit-pr.py https://github.com/prebid/prebid-server/pull/4639

    # OR manual mode (when no API key available)
    python3 scripts/audit-pr.py https://github.com/prebid/prebid-server/pull/4639
    # → writes scripts/output/audit-4639.prompt.txt; user pastes into Claude.ai
    python3 scripts/audit-pr.py https://github.com/prebid/prebid-server/pull/4639 \
        --manual-answer=path/to/answer.txt

Exit codes: 0 (no novelty detected), 1 (gh/network failure), 2 (novelty
detected — informational, never blocks).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TAXONOMY_PATH = REPO_ROOT / "prebid-server-go" / "read" / "skills" / "shared" / "behavior-taxonomy.yaml"
RULES_PATH = REPO_ROOT / "prebid-server-go" / "read" / "skills" / "shared" / "port-translation-rules.yaml"
JAVA_EDGE_CASES_PATH = REPO_ROOT / "prebid-server-java" / "references" / "java-edge-cases.md"
DEFAULT_OUT_DIR = REPO_ROOT / "scripts" / "output"

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_MAX_TOKENS = 4096

# PR URL: github.com/{owner}/{repo}/pull/{N}
_PR_URL_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)/?$")


class GhError(Exception):
    """gh CLI failed (not installed, not authed, or API error)."""


def parse_pr_url(url: str) -> tuple[str, str, int]:
    m = _PR_URL_RE.match(url.strip())
    if not m:
        raise ValueError(f"Not a recognized PR URL: {url!r}")
    owner, repo, number = m.group(1), m.group(2), int(m.group(3))
    return owner, repo, number


def fetch_pr_via_gh(owner: str, repo: str, number: int) -> dict:
    """Use `gh pr view` to fetch PR metadata + diff. Requires `gh` installed and authed."""
    try:
        meta_proc = subprocess.run(
            ["gh", "pr", "view", str(number),
             "--repo", f"{owner}/{repo}",
             "--json", "title,body,author,state,mergedAt,headRefName,headRefOid,files,additions,deletions"],
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError as e:
        raise GhError(f"gh CLI not found in PATH: {e}") from e
    if meta_proc.returncode != 0:
        raise GhError(f"gh pr view failed: {meta_proc.stderr.strip()}")
    meta = json.loads(meta_proc.stdout)

    diff_proc = subprocess.run(
        ["gh", "pr", "diff", str(number), "--repo", f"{owner}/{repo}"],
        capture_output=True, text=True, check=False,
    )
    if diff_proc.returncode != 0:
        raise GhError(f"gh pr diff failed: {diff_proc.stderr.strip()}")
    meta["diff"] = diff_proc.stdout
    return meta


def load_taxonomy_taxa() -> list[dict]:
    with open(TAXONOMY_PATH) as fp:
        data = yaml.safe_load(fp) or {}
    return data.get("quirks_taxa") or []


def load_rule_summaries() -> list[dict]:
    with open(RULES_PATH) as fp:
        data = yaml.safe_load(fp) or {}
    out = []
    for sec in data.get("sections", []):
        if sec.get("kind") == "rules":
            for r in sec.get("rules", []):
                out.append({
                    "id": r["id"],
                    "title": r["title"],
                    "pattern": (r.get("pattern") or "")[:200],
                })
    return out


def load_java_edge_cases() -> str:
    if JAVA_EDGE_CASES_PATH.is_file():
        return JAVA_EDGE_CASES_PATH.read_text()
    return ""


# ─── Prompt construction ──────────────────────────────────────────────────

PROMPT_HEADER = """\
You classify a prebid-server adapter PR for "novelty" against an existing
catalog of patterns. Your job is to answer:

1. **Does this PR introduce a pattern (behavioral, structural, or
   port-translation) that is NOT yet captured in our existing taxonomy,
   port-translation rules, or Java edge-case catalog?**

2. If novel: describe the pattern in one paragraph, suggest the closest
   existing taxon/rule it would extend or supersede, and propose a new
   taxon ID + behavior taxonomy entry OR a new port-translation rule
   number + signature.

3. If NOT novel: cite the existing taxon ID(s) / rule number(s) / Java
   edge case number(s) that already capture the pattern.

Existing taxonomy taxa ({taxa_count}):
{taxa_summary}

Existing port-translation rules ({rule_count}):
{rule_summary}

Java edge cases #18-#34 catalog (excerpt):
{java_edge_cases_excerpt}

The PR to classify:

URL: {pr_url}
Title: {pr_title}
Author: {pr_author}
State: {pr_state}; merged: {pr_merged}
Head SHA: {head_sha}
Files changed: {file_count} (+{additions} / -{deletions})

PR description:
{pr_body}

Diff (truncated to 12000 chars if longer):
```
{pr_diff}
```

Respond as JSON, no prose outside the JSON. Schema:
{{
  "verdict": "no-novelty" | "novel-pattern" | "ambiguous",
  "rationale": "<one paragraph>",
  "matched_taxa": ["<existing taxon id>", ...],
  "matched_rules": [<rule id int>, ...],
  "matched_java_edge_cases": [<edge case number int>, ...],
  "novel_pattern_proposal": {{
    "name": "<short kebab-case>",
    "description": "<one paragraph>",
    "extends_existing": "<existing id>" | null,
    "proposed_artifact": "taxon" | "rule" | "edge_case",
    "rationale_for_promotion": "<one sentence>"
  }} | null
}}
"""


def build_prompt(pr_meta: dict, pr_url: str, taxa: list[dict],
                 rules: list[dict], java_edge_cases: str) -> str:
    taxa_summary = "\n".join(f"- `{t['id']}` — {(t.get('description') or '')[:120]}" for t in taxa)
    rule_summary = "\n".join(f"- Rule {r['id']:2d}: **{r['title']}** — {r['pattern']}" for r in rules)
    edge_cases_excerpt = (java_edge_cases.split("## Notes")[0] if "## Notes" in java_edge_cases else java_edge_cases)[:5000]

    diff = pr_meta.get("diff", "")
    if len(diff) > 12000:
        diff = diff[:12000] + "\n\n[... truncated for prompt size ...]"

    return PROMPT_HEADER.format(
        taxa_count=len(taxa),
        taxa_summary=taxa_summary,
        rule_count=len(rules),
        rule_summary=rule_summary,
        java_edge_cases_excerpt=edge_cases_excerpt,
        pr_url=pr_url,
        pr_title=pr_meta.get("title", ""),
        pr_author=(pr_meta.get("author") or {}).get("login", "?"),
        pr_state=pr_meta.get("state", "?"),
        pr_merged=pr_meta.get("mergedAt", "—"),
        head_sha=pr_meta.get("headRefOid", "?"),
        file_count=len(pr_meta.get("files", [])),
        additions=pr_meta.get("additions", 0),
        deletions=pr_meta.get("deletions", 0),
        pr_body=(pr_meta.get("body") or "")[:2000],
        pr_diff=diff,
    )


# ─── Anthropic API call ───────────────────────────────────────────────────

def call_claude_api(prompt: str, api_key: str, model: str = DEFAULT_MODEL,
                     max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    """POST the prompt to Anthropic Messages API; return the assistant's text."""
    payload = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=payload,
        method="POST",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Anthropic API HTTP {e.code}: {err_body[:500]}") from e
    except urllib.error.URLError as e:
        raise SystemExit(f"Anthropic API network error: {e}") from e

    parsed = json.loads(body)
    # Concatenate all text-block content
    out_parts = []
    for block in parsed.get("content", []):
        if block.get("type") == "text":
            out_parts.append(block.get("text", ""))
    return "\n".join(out_parts).strip()


def parse_claude_json(text: str) -> dict:
    """Pluck the first JSON object out of Claude's response."""
    # Look for ```json ... ``` first.
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    blob = m.group(1) if m else None
    if blob is None:
        # Fall back: find the first balanced { ... }.
        start = text.find("{")
        if start == -1:
            raise ValueError("No JSON object in Claude response")
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    blob = text[start:i + 1]
                    break
        if blob is None:
            raise ValueError("Unbalanced braces in Claude response")
    try:
        return json.loads(blob)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude returned non-JSON: {e}\n\nText was:\n{blob[:500]}") from e


# ─── Render helpers ───────────────────────────────────────────────────────

def render_md(verdict: dict, pr_meta: dict, pr_url: str) -> str:
    out = []
    out.append(f"# PR audit — {pr_url}")
    out.append("")
    out.append(f"<!-- AUTO-GENERATED by scripts/audit-pr.py at {datetime.now(timezone.utc).isoformat()} -->")
    out.append("")
    out.append(f"**Title**: {pr_meta.get('title', '?')}")
    out.append(f"**Author**: @{(pr_meta.get('author') or {}).get('login', '?')}")
    out.append(f"**Files changed**: {len(pr_meta.get('files', []))} (+{pr_meta.get('additions', 0)} / -{pr_meta.get('deletions', 0)})")
    out.append(f"**Head SHA**: `{pr_meta.get('headRefOid', '?')}`")
    out.append("")
    out.append(f"## Verdict: `{verdict.get('verdict', '?')}`")
    out.append("")
    out.append(verdict.get("rationale", "") or "(no rationale)")
    out.append("")

    if verdict.get("matched_taxa"):
        out.append("**Matched taxa**: " + ", ".join(f"`{t}`" for t in verdict["matched_taxa"]))
        out.append("")
    if verdict.get("matched_rules"):
        out.append("**Matched rules**: " + ", ".join(f"Rule {r}" for r in verdict["matched_rules"]))
        out.append("")
    if verdict.get("matched_java_edge_cases"):
        out.append("**Matched Java edge cases**: " + ", ".join(f"#{e}" for e in verdict["matched_java_edge_cases"]))
        out.append("")

    novel = verdict.get("novel_pattern_proposal")
    if novel:
        out.append("## Proposed novel pattern")
        out.append("")
        out.append(f"- **Name**: `{novel.get('name', '?')}`")
        out.append(f"- **Description**: {novel.get('description', '?')}")
        out.append(f"- **Extends**: {novel.get('extends_existing') or '(no existing pattern)'}")
        out.append(f"- **Proposed artifact**: `{novel.get('proposed_artifact', '?')}`")
        out.append(f"- **Promotion rationale**: {novel.get('rationale_for_promotion', '?')}")
        out.append("")
        out.append("**Next step**: open a PR adding this entry. See `docs/methodology/pr-ingestion.md`.")
        out.append("")

    out.append("---")
    out.append("")
    out.append("## Sources")
    out.append("")
    out.append("- Taxonomy: [`prebid-server-go/read/skills/shared/behavior-taxonomy.yaml`](../../prebid-server-go/read/skills/shared/behavior-taxonomy.yaml)")
    out.append("- Port rules: [`prebid-server-go/read/skills/shared/port-translation-rules.yaml`](../../prebid-server-go/read/skills/shared/port-translation-rules.yaml)")
    out.append("- Java edge cases: [`prebid-server-java/references/java-edge-cases.md`](../../prebid-server-java/references/java-edge-cases.md)")
    out.append("- Methodology: [`docs/methodology/pr-ingestion.md`](../../docs/methodology/pr-ingestion.md)")
    return "\n".join(out)


# ─── Main ─────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("pr_url", help="https://github.com/{owner}/{repo}/pull/{N}")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--manual-answer", help="Path to a file containing Claude's manual response (when CLAUDE_API_KEY is unset)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--print-prompt", action="store_true",
                        help="Print the prompt and exit (no API call, no manual round-trip)")
    args = parser.parse_args(argv)

    try:
        owner, repo, number = parse_pr_url(args.pr_url)
    except ValueError as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 1

    # Fetch PR.
    try:
        pr_meta = fetch_pr_via_gh(owner, repo, number)
    except GhError as e:
        sys.stderr.write(f"ERROR fetching PR via gh: {e}\n")
        return 1

    # Build prompt.
    taxa = load_taxonomy_taxa()
    rules = load_rule_summaries()
    edge_cases = load_java_edge_cases()
    prompt = build_prompt(pr_meta, args.pr_url, taxa, rules, edge_cases)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = out_dir / f"audit-{number}.prompt.txt"
    prompt_path.write_text(prompt)

    if args.print_prompt:
        sys.stdout.write(prompt)
        return 0

    # Decide mode: manual answer file, or API call.
    api_key = os.environ.get("CLAUDE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    raw_response: Optional[str] = None
    if args.manual_answer:
        raw_response = Path(args.manual_answer).read_text()
    elif api_key:
        sys.stderr.write(f"Calling Anthropic API ({args.model})...\n")
        raw_response = call_claude_api(prompt, api_key, model=args.model)
    else:
        sys.stderr.write(
            f"No CLAUDE_API_KEY / ANTHROPIC_API_KEY set; manual mode.\n"
            f"  Prompt written to: {prompt_path}\n"
            f"  Paste into Claude.ai or claude-code, save the response, then re-run with --manual-answer.\n"
        )
        return 0

    # Parse Claude's verdict.
    try:
        verdict = parse_claude_json(raw_response)
    except ValueError as e:
        sys.stderr.write(f"ERROR parsing Claude's response: {e}\n")
        # Save the raw response so the human can recover.
        raw_path = out_dir / f"audit-{number}.raw.txt"
        raw_path.write_text(raw_response)
        sys.stderr.write(f"Raw response saved to: {raw_path}\n")
        return 1

    # Emit JSON + MD.
    json_path = out_dir / f"audit-{number}.json"
    md_path = out_dir / f"audit-{number}.md"
    json_path.write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "pr_url": args.pr_url,
        "pr_meta": {k: v for k, v in pr_meta.items() if k != "diff"},
        "verdict": verdict,
    }, indent=2))
    md_path.write_text(render_md(verdict, pr_meta, args.pr_url))

    sys.stderr.write(f"Wrote: {json_path}\n")
    sys.stderr.write(f"Wrote: {md_path}\n")
    sys.stderr.write(f"Verdict: {verdict.get('verdict')}\n")

    return 2 if verdict.get("verdict") == "novel-pattern" else 0


if __name__ == "__main__":
    sys.exit(main())
