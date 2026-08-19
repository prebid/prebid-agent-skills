"""Every relative link in the deployed surface resolves to a file that exists.

WHY
    Six links in the Go review skills pointed at `field-index.md` and
    `adapter-code-index.md` from a SKILL.md whose siblings live under
    `references/`. They were added by the same change that added the
    "Regenerate: <command>" lines they sit on, so the one thing they exist to do
    -- let a reader re-run the command that produced a number -- 404'd. Nothing
    checked, so nothing said.

    Skills are read by an agent following the link. A dead link is not cosmetic
    there: it is a reference the reader cannot reach, and the fallback is to
    invent the content or drop the check.

SCOPE
    The trees that ship: read skills, review skills, both port skills, the
    shared references, plus the root-level docs a contributor starts from. Run
    docs under `docs/runs/` are archived traces of runs that happened and are
    deliberately excluded -- a link that was live at the time is a historical
    fact, not a defect to edit.

FALSE POSITIVES
    Markdown link syntax collides with Go generics in table cells:
    `ptrutil.Clone[T](*T)` parses as a link to `*T`. Targets that cannot be
    filesystem paths are skipped rather than waived one by one.

Run: python3 -m unittest scripts.tests.test_doc_links -v
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Trees whose links an agent or contributor actually follows.
CHECKED_PREFIXES = (
    "prebid-server-go/read/", "prebid-server-java/read/",
    "prebid-server-go/review/", "prebid-server-java/review/",
    "prebid-server-go/port-java2go/", "prebid-server-java/port-go2java/",
    "prebid-server-go/references/", "prebid-server-java/references/",
    "cross-language-pairs/", "docs/decisions/", "docs/methodology/",
    "review-evals/", "templates/",
)
ROOT_DOCS = ("README.md", "CONTRIBUTING.md", "ROADMAP.md", "CHANGELOG.md", "NOTICE")

# Archived traces: a link that was live when the run happened is a record, not a
# defect. They are refreshed or archived by the docs pass, not by this gate.
EXCLUDED_PREFIXES = ("docs/runs/",)

LINK_RE = re.compile(r"\[[^\]]*\]\(\s*([^)\s]+?)\s*\)")

# A target that is not a path at all. `*T` is Go generics in a table cell.
NOT_A_PATH = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|[#*<{$]|\.\.\.)")


def tracked_markdown() -> list[str]:
    out = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-files", "*.md"],
                         capture_output=True, text=True, check=True).stdout.split()
    keep = []
    for f in out:
        if f.startswith(EXCLUDED_PREFIXES):
            continue
        if f in ROOT_DOCS or f.startswith(CHECKED_PREFIXES):
            keep.append(f)
    return sorted(keep)


class TestDocLinks(unittest.TestCase):
    def test_scan_set_is_not_empty(self):
        """An empty scan is a setup error, not a clean result."""
        files = tracked_markdown()
        self.assertGreater(len(files), 30,
                           f"only {len(files)} files matched CHECKED_PREFIXES — the "
                           f"prefixes have drifted away from the tree layout")

    def test_every_relative_link_target_exists(self):
        broken: list[str] = []
        for rel in tracked_markdown():
            path = REPO_ROOT / rel
            text = path.read_text(encoding="utf-8", errors="replace")
            for m in LINK_RE.finditer(text):
                target = m.group(1)
                if NOT_A_PATH.match(target):
                    continue
                # Strip an anchor; anchors are not checked here.
                filepart = target.split("#", 1)[0]
                if not filepart:
                    continue
                resolved = (path.parent / filepart).resolve()
                if not resolved.exists():
                    line = text[:m.start()].count("\n") + 1
                    broken.append(f"{rel}:{line} -> {target}")
        self.assertEqual([], broken,
                         "broken relative links (a reference the reader cannot "
                         "reach):\n  " + "\n  ".join(broken))

    def test_sibling_reference_links_carry_their_directory(self):
        """The specific shape that broke: a SKILL.md linking a `references/`
        file as if it were a sibling. Caught by the test above too, but named
        separately because it is the mistake that recurs -- the file exists, so
        the link looks right until someone clicks it."""
        offenders = []
        for rel in tracked_markdown():
            path = REPO_ROOT / rel
            if path.name != "SKILL.md":
                continue
            refs = path.parent / "references"
            if not refs.is_dir():
                continue
            names = {p.name for p in refs.iterdir() if p.is_file()}
            text = path.read_text(encoding="utf-8", errors="replace")
            for m in LINK_RE.finditer(text):
                filepart = m.group(1).split("#", 1)[0]
                if filepart in names and not (path.parent / filepart).exists():
                    line = text[:m.start()].count("\n") + 1
                    offenders.append(f"{rel}:{line} -> {filepart} "
                                     f"(exists at references/{filepart})")
        self.assertEqual([], offenders, "\n  ".join(offenders))


if __name__ == "__main__":
    unittest.main()
