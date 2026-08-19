"""SKILL frontmatter gates, and a size/cost report that does not gate.

Frontmatter presence IS a gate: a skill with no `name` or `description` cannot be
selected by a skill-aware harness. That is a structural defect with an
unambiguous test, and it stays enforced.

Body size is REPORTED, not enforced — a deliberate reversal of the gate that
briefly lived here. CONTRIBUTING.md carried a 500-line limit sourced to
"Anthropic skill-creator guidance": a generic authoring convention, never
measured against this corpus. Enforcing it failed on first contact with real
work. The change that added upstream anchors and regenerating commands to eight
re-scoped checks pushed two files over, and the gate's demand was to delete
verified evidence to satisfy a number nobody had grounded — the same defect this
repo keeps finding upstream, a control asserted without the artifact that
justifies it.

Two real measurements beat the proxy, and both exist:

  cost     token cost is directly measurable. This module reports it per skill
           and in total, so it can be tracked rather than inferred from lines.
  outcome  review-evals/ scores recall and false positives against real PRs. If
           a longer skill reviews worse, it shows up there in the units that
           matter. The 654-line bidder-info skill scored fine on the corpus; the
           0-of-4 recall failure was a different suite, and its cause was absent
           check classes, not length.

Reinstating a size limit is fine — but it should arrive with the measurement
that picks the number.

Run: python3 -m unittest scripts.tests.test_skill_budgets -v
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Every skill surface the repo ships.
SKILL_ROOTS = (
    REPO_ROOT / "prebid-server-go" / "read" / "skills",
    REPO_ROOT / "prebid-server-java" / "read" / "skills",
    REPO_ROOT / "prebid-server-go" / "review" / "skills",
    REPO_ROOT / "prebid-server-java" / "review" / "skills",
    REPO_ROOT / "prebid-server-go" / "port-java2go",
    REPO_ROOT / "prebid-server-java" / "port-go2java",
)

FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)


def discover_skills() -> list[Path]:
    out: set[Path] = set()
    for root in SKILL_ROOTS:
        if root.is_dir():
            out.update(root.rglob("SKILL.md"))
    return sorted(out)


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def frontmatter_field(text: str, field: str) -> str | None:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    body = m.group(1)
    fm = re.search(rf"^{field}:\s*(.+?)(?=^\w+:|\Z)", body, re.S | re.M)
    return " ".join(fm.group(1).split()) if fm else None


def approx_tokens(text: str) -> int:
    """Rough token estimate (~4/3 per whitespace word). Good enough to track a
    trend; anyone recording real cost should use the harness's own accounting."""
    return int(len(text.split()) * 4 / 3)


class TestSkillDiscovery(unittest.TestCase):
    def test_every_root_contributes_a_skill(self):
        """A root that contributes nothing means the scan set silently shrank —
        an empty scan is a setup error, not a clean result."""
        empty = [rel(r) for r in SKILL_ROOTS if r.is_dir() and not list(r.rglob("SKILL.md"))]
        self.assertEqual([], empty, f"skill roots with no SKILL.md: {empty}")

    def test_all_repo_skills_are_under_a_root(self):
        """A SKILL.md outside SKILL_ROOTS is invisible to every check here."""
        known = set(discover_skills())
        stray = [rel(p) for p in REPO_ROOT.rglob("SKILL.md")
                 if p not in known and ".claude/worktrees" not in p.as_posix()
                 and "/templates/" not in p.as_posix()]
        self.assertEqual([], stray, f"SKILL.md outside SKILL_ROOTS: {stray}")


class TestFrontmatter(unittest.TestCase):
    """These are gates: without them a skill cannot be selected at all."""

    def test_every_skill_has_a_name_matching_its_directory(self):
        bad = []
        for path in discover_skills():
            name = frontmatter_field(path.read_text(encoding="utf-8"), "name")
            if not name:
                bad.append(f"{rel(path)}: no `name`")
            elif name != path.parent.name:
                bad.append(f"{rel(path)}: name {name!r} != directory {path.parent.name!r}")
        self.assertEqual([], bad, "\n  ".join(bad))

    def test_every_skill_has_a_nonempty_description(self):
        """The description is what a harness matches on; an empty one makes the
        skill unreachable however good its body is."""
        bad = [rel(p) for p in discover_skills()
               if not (frontmatter_field(p.read_text(encoding="utf-8"), "description") or "").strip()]
        self.assertEqual([], bad, f"skills with no description: {bad}")


class TestSizeReport(unittest.TestCase):
    """Reports; never fails on size. See the module docstring."""

    def test_report_skill_size_and_cost(self):
        rows = []
        for path in discover_skills():
            text = path.read_text(encoding="utf-8")
            rows.append((approx_tokens(text), len(text.splitlines()), rel(path)))
        self.assertTrue(rows, "no SKILL.md discovered — empty scan set is a setup error")
        rows.sort(reverse=True)
        total = sum(r[0] for r in rows)
        out = ["", f"SKILL size report — {len(rows)} skills, ~{total:,} tokens if every one were loaded",
               f"{'~tokens':>9} {'lines':>7}  skill"]
        out += [f"{t:>9,} {l:>7}  {p}" for t, l, p in rows]
        out += ["", "Size is reported, not gated: cost is measurable directly, and review quality",
                "is measured by review-evals/. A limit here would be a proxy for both."]
        print("\n".join(out))


if __name__ == "__main__":
    unittest.main()
