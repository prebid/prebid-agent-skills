"""SKILL.md budget gates — body length and frontmatter description length.

CONTRIBUTING.md ("Editing a SKILL.md") states a 500-line ceiling for SKILL.md
bodies, with depth pushed into `references/`. Nothing enforced it, and four
files had drifted past it. This module makes the stated limit mechanical.

It also replaces the workflow's description-length step, which was
informational-only (`exit 0` unconditionally, `::notice` output) and scoped to
the two `read/skills` trees — 8 of the repo's 18 skills. See
`TestDescriptionBudget` for why the 600-char number is kept and what changed.

## Scope

Every `SKILL.md` under all six skill roots: `prebid-server-{go,java}/read/skills`,
`prebid-server-{go,java}/review/skills`, `prebid-server-go/port-java2go`, and
`prebid-server-java/port-go2java`. `SKILL_ROOTS` is asserted non-empty per root
so a moved or renamed tree fails the gate instead of silently leaving it.

## How the budget is measured

Total lines in the file, i.e. what `wc -l` reports. The ~5-line YAML
frontmatter is included. That reading is marginally stricter than
CONTRIBUTING's word "bodies" and it keeps the numbers here directly
comparable to `wc -l` output, which is how anyone will check them.

## Waivers

`BODY_LINE_WAIVERS` lists the four files that already exceed the limit, each
with the line count accepted, the date accepted, and why. The limit itself is
NOT raised — the gate is live for every other skill from the moment it lands.

The waiver list is a two-way ratchet:

- a waived file that GROWS fails (the accepted number is a ceiling, not a
  licence);
- a waived file that drops to or below the limit fails as a STALE waiver, so
  the list shrinks when the trimming PR lands instead of lingering;
- a waiver naming a file that does not exist fails.

Shrinking while still over the limit passes, and the run prints the slack so
the accepted number can be tightened in the same PR that shrank the file.

Run via:
    python3 -m unittest scripts.tests.test_skill_budgets -v
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import NamedTuple

import yaml

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

# CONTRIBUTING.md, "Editing a SKILL.md": "Keep SKILL.md bodies under 500 lines
# (per Anthropic skill-creator guidance). Use `references/` files for depth."
MAX_SKILL_LINES = 500

# See TestDescriptionBudget for the rationale behind this number.
MAX_DESCRIPTION_CHARS = 600


class Waiver(NamedTuple):
    accepted_lines: int
    accepted_on: str
    reason: str


# Files over MAX_SKILL_LINES when this gate landed. Individually listed and
# dated so each one is visible and separately removable. Keys are
# repo-relative POSIX paths.
BODY_LINE_WAIVERS: dict[str, Waiver] = {
    "prebid-server-java/review/skills/pr-triage-java/SKILL.md": Waiver(
        789, "2026-08-18",
        "Over budget when the gate landed. Trimming is a separate PR; the "
        "routing tables and per-file-category checklists are the bulk and "
        "belong in references/.",
    ),
    "prebid-server-go/review/skills/pr-triage/SKILL.md": Waiver(
        662, "2026-08-18",
        "Over budget when the gate landed. Go-side analog of pr-triage-java; "
        "same trimming shape.",
    ),
    "prebid-server-java/review/skills/bidder-config-pr-review/SKILL.md": Waiver(
        669, "2026-08-18",
        "Over budget when the gate landed. The unified bidder-config YAML "
        "field walkthrough is the bulk.",
    ),
    "prebid-server-go/review/skills/bidder-info-pr-review/SKILL.md": Waiver(
        647, "2026-08-18",
        "Over budget when the gate landed. The bidder-info YAML field "
        "walkthrough is the bulk.",
    ),
}


FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)


def discover_skills() -> list[Path]:
    """Every SKILL.md under SKILL_ROOTS, sorted, deduplicated."""
    out: set[Path] = set()
    for root in SKILL_ROOTS:
        if not root.is_dir():
            continue
        out.update(root.rglob("SKILL.md"))
    return sorted(out)


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def line_count(path: Path) -> int:
    """Total lines, matching `wc -l` (a trailing newline does not add a line)."""
    text = path.read_text(encoding="utf-8")
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def frontmatter(path: Path) -> dict:
    """Parse the leading YAML frontmatter block; {} when absent or not a mapping."""
    m = FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    if not m:
        return {}
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def description_length(path: Path) -> int:
    """Length of the frontmatter `description`, whitespace-collapsed.

    Collapsing matches how the value is read: a YAML folded/multi-line
    description renders as one line, so raw newlines must not inflate or
    deflate the count relative to what a dispatcher sees.
    """
    desc = frontmatter(path).get("description")
    if not isinstance(desc, str):
        return 0
    return len(" ".join(desc.split()))


class TestSkillDiscovery(unittest.TestCase):
    """The gate must actually see every skill surface."""

    def test_every_root_contributes_a_skill(self):
        """An empty root is a finding, not a pass.

        Without this, moving or renaming a tree drops it from both budget
        gates while the run still reports OK.
        """
        found = discover_skills()
        self.assertTrue(found, "no SKILL.md discovered under any root")
        for root in SKILL_ROOTS:
            with self.subTest(root=root.relative_to(REPO_ROOT).as_posix()):
                self.assertTrue(root.is_dir(), f"skill root missing: {root}")
                self.assertTrue(
                    any(p.is_relative_to(root) for p in found),
                    f"skill root contributed zero SKILL.md files: {root}",
                )

    def test_all_repo_skills_are_under_a_root(self):
        """No SKILL.md outside SKILL_ROOTS.

        A skill added in a new tree must be brought into the gate
        deliberately, not left unwatched.
        """
        everywhere = {
            p for p in REPO_ROOT.rglob("SKILL.md")
            if ".git" not in p.parts and "node_modules" not in p.parts
        }
        missed = sorted(rel(p) for p in everywhere - set(discover_skills()))
        self.assertEqual(
            [], missed,
            "SKILL.md files outside SKILL_ROOTS — add their tree to "
            "SKILL_ROOTS so the budget gates cover them:\n  - "
            + "\n  - ".join(missed),
        )


class TestBodyLineBudget(unittest.TestCase):
    """CONTRIBUTING's 500-line SKILL.md ceiling, enforced."""

    def test_no_unwaived_skill_exceeds_the_line_budget(self):
        over: list[str] = []
        for path in discover_skills():
            key = rel(path)
            if key in BODY_LINE_WAIVERS:
                continue
            n = line_count(path)
            if n > MAX_SKILL_LINES:
                over.append(f"{key}: {n} lines (limit {MAX_SKILL_LINES}, over by {n - MAX_SKILL_LINES})")
        self.assertEqual(
            [], over,
            f"SKILL.md files over the {MAX_SKILL_LINES}-line budget "
            f"(CONTRIBUTING.md, 'Editing a SKILL.md'):\n  - "
            + "\n  - ".join(over)
            + "\n\nMove depth into references/. Do not raise MAX_SKILL_LINES; "
            "if the overrun is genuinely unavoidable, add a dated entry to "
            "BODY_LINE_WAIVERS with the reason.",
        )

    def test_waived_skills_do_not_grow(self):
        """A waiver is a ceiling at the accepted count, not a licence to grow."""
        grown: list[str] = []
        for key, waiver in sorted(BODY_LINE_WAIVERS.items()):
            path = REPO_ROOT / key
            if not path.is_file():
                continue  # covered by test_waivers_reference_existing_files
            n = line_count(path)
            if n > waiver.accepted_lines:
                grown.append(
                    f"{key}: {n} lines, waiver accepted {waiver.accepted_lines} "
                    f"on {waiver.accepted_on} (grew by {n - waiver.accepted_lines})"
                )
        self.assertEqual(
            [], grown,
            "waived SKILL.md files grew past their accepted line counts:\n  - "
            + "\n  - ".join(grown)
            + "\n\nThe waiver freezes the overrun; it does not permit more of "
            "it. Trim back to at most the accepted count, or trim under "
            f"{MAX_SKILL_LINES} and delete the waiver.",
        )

    def test_no_stale_waivers(self):
        """A waived file that now fits the budget must lose its waiver."""
        stale: list[str] = []
        for key, waiver in sorted(BODY_LINE_WAIVERS.items()):
            path = REPO_ROOT / key
            if not path.is_file():
                continue
            n = line_count(path)
            if n <= MAX_SKILL_LINES:
                stale.append(f"{key}: now {n} lines (limit {MAX_SKILL_LINES})")
        self.assertEqual(
            [], stale,
            "BODY_LINE_WAIVERS entries whose files now fit the budget:\n  - "
            + "\n  - ".join(stale)
            + "\n\nDelete these entries. A waiver that no longer waives "
            "anything hides the fact that the gate is doing the work.",
        )

    def test_waivers_reference_existing_files(self):
        missing = sorted(k for k in BODY_LINE_WAIVERS if not (REPO_ROOT / k).is_file())
        self.assertEqual(
            [], missing,
            "BODY_LINE_WAIVERS names files that do not exist (moved or "
            "deleted); delete or repoint these entries:\n  - "
            + "\n  - ".join(missing),
        )

    def test_waiver_metadata_is_present(self):
        """Every waiver carries an ISO date and a non-trivial reason."""
        bad: list[str] = []
        for key, waiver in sorted(BODY_LINE_WAIVERS.items()):
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", waiver.accepted_on):
                bad.append(f"{key}: accepted_on {waiver.accepted_on!r} is not YYYY-MM-DD")
            if len(waiver.reason.strip()) < 20:
                bad.append(f"{key}: reason is too short to be a reason")
            if waiver.accepted_lines <= MAX_SKILL_LINES:
                bad.append(
                    f"{key}: accepted_lines {waiver.accepted_lines} is within the "
                    f"{MAX_SKILL_LINES}-line budget — no waiver needed"
                )
        self.assertEqual([], bad, "malformed BODY_LINE_WAIVERS entries:\n  - " + "\n  - ".join(bad))


class TestDescriptionBudget(unittest.TestCase):
    """Frontmatter `description` length, enforced across every skill.

    This replaces the workflow's "Description-length lint (informational)"
    step, which had two defects. It ran over
    `prebid-server-{go,java}/read/skills` only — 8 of 18 skills, and not the
    review or port skills that run against real upstream PRs. And it could
    not fail: the body ended in an unconditional `exit 0` and emitted a
    `::notice` annotation, so exceeding the threshold changed nothing.

    The 600-char number is kept, and it is the part worth justifying. It was
    never written down anywhere but that workflow comment, and no skill
    currently reaches it — the corpus runs 406 to 591 chars. There is no
    threshold inside that band that encodes a decision anyone made: anything
    above 591 flags nothing, and a round number like 500 would flag a third
    of the corpus for no stated reason. What 600 does give is a ratchet
    directly above the current high-water mark: the longest description in
    the repo is 9 chars from tripping it, so the next description that grows
    by a sentence has to justify itself. Descriptions load into context on
    every dispatch, so a bound on their growth is worth having even though
    byte count is a weak proxy for dispatch quality.

    So the number stays and the two real defects are fixed: all 18 skills,
    and a failing assertion instead of a notice.
    """

    def test_every_skill_has_a_nonempty_description(self):
        bad: list[str] = []
        for path in discover_skills():
            fm = frontmatter(path)
            if not isinstance(fm.get("name"), str) or not fm.get("name", "").strip():
                bad.append(f"{rel(path)}: frontmatter `name` missing or empty")
            if description_length(path) == 0:
                bad.append(f"{rel(path)}: frontmatter `description` missing or empty")
        self.assertEqual([], bad, "SKILL frontmatter problems:\n  - " + "\n  - ".join(bad))

    def test_no_skill_description_exceeds_the_budget(self):
        over: list[str] = []
        for path in discover_skills():
            n = description_length(path)
            if n > MAX_DESCRIPTION_CHARS:
                over.append(
                    f"{rel(path)}: {n} chars (limit {MAX_DESCRIPTION_CHARS}, "
                    f"over by {n - MAX_DESCRIPTION_CHARS})"
                )
        self.assertEqual(
            [], over,
            f"SKILL frontmatter descriptions over the "
            f"{MAX_DESCRIPTION_CHARS}-char budget:\n  - "
            + "\n  - ".join(over)
            + "\n\nTighten to the trigger conditions — what the skill is for, "
            "when to use it, when not to. Detail belongs in the body.",
        )


if __name__ == "__main__":
    unittest.main()
