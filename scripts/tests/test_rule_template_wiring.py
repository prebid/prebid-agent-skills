"""A rule that claims a port skill wires something must name a real ctx variable.

WHY
    Rules 47 and 49 shipped carrying notes about template support that did not
    exist:

        Rule 47: "port-java2go ctx.batching_per_key per F-new-7 EXT-A;
                  port-go2java ctx.batching_per_key per F-new-107"
        Rule 49: "port-go2java bidder-config.yaml.j2 emits
                  modifying-vast-xml-allowed explicitly ... in BOTH polarities"

    The port-go2java templates had neither. A porter reading the corpus is told
    the translation is mechanical, reaches for a ctx variable the template never
    consumes, and the render either silently drops it or falls through to the
    hand-fill TODO. Nothing in the repo connected a rule's claim about a template
    to that template, so the corpus and the shipped artifacts could disagree
    indefinitely.

    This is the same failure shape as a docstring claiming a check runs weekly
    while no such job exists: the claim reads as evidence.

WHAT IT CHECKS
    Every sentence in the rules corpus that names a port skill AND a `ctx.X`
    variable or a `<file>.j2` in the same breath must resolve against that
    skill's own templates directory. Sentence scope is what binds the skill to
    the token -- a rule may legitimately discuss both skills, so the whole-rule
    text would cross-attribute one skill's variable to the other.

WHAT IT DOES NOT CHECK
    That the wiring is CORRECT -- only that the named surface exists. A rule
    claiming a LinkedHashMap while the template emits a HashMap passes here; the
    template's own tests own that. Claims phrased without a `ctx.` variable or a
    template filename (Rule 49's "emits ... in BOTH polarities") are invisible
    to this gate and are pinned by the site anchors in scripts/upstream-claims.yaml
    instead.

Run: python3 -m unittest scripts.tests.test_rule_template_wiring -v
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_YAML = REPO_ROOT / "prebid-server-go" / "read" / "skills" / "shared" / "port-translation-rules.yaml"

# Note the inversion: the skill that TARGETS Java lives under the Java tree.
SKILL_TEMPLATE_DIRS = {
    "port-go2java": REPO_ROOT / "prebid-server-java" / "port-go2java" / "templates",
    "port-java2go": REPO_ROOT / "prebid-server-go" / "port-java2go" / "templates",
}

CTX_RE = re.compile(r"`ctx\.([A-Za-z_][A-Za-z0-9_]*)")
J2_RE = re.compile(r"`([A-Za-z0-9._-]+\.j2)`")
SENTENCE_SPLIT = re.compile(r"(?<=[.;])\s+")

# Set by the sample-size guard below; raising it is fine, lowering it means a
# claim was deleted rather than fixed.
MIN_BINDINGS = 4


def _bindings() -> list[tuple[int, str, list[str], list[str]]]:
    data = yaml.safe_load(RULES_YAML.read_text(encoding="utf-8"))
    out = []
    for section in data["sections"]:
        for rule in section.get("rules", []):
            text = "\n".join(v for v in rule.values() if isinstance(v, str))
            for sentence in SENTENCE_SPLIT.split(text):
                for skill in SKILL_TEMPLATE_DIRS:
                    if skill not in sentence:
                        continue
                    ctxs = sorted(set(CTX_RE.findall(sentence)))
                    j2s = sorted(set(J2_RE.findall(sentence)))
                    if ctxs or j2s:
                        out.append((rule["id"], skill, ctxs, j2s))
    return out


def _ctx_vars(templates_dir: Path) -> set[str]:
    found: set[str] = set()
    for tpl in templates_dir.glob("*.j2"):
        found |= set(re.findall(r"ctx\.([A-Za-z_][A-Za-z0-9_]*)",
                                tpl.read_text(encoding="utf-8")))
    return found


class TestRuleTemplateWiring(unittest.TestCase):
    def test_scan_finds_bindings(self):
        """An empty scan is a setup error, not a clean result -- the regex is
        the instrument, and a corpus reword that stops matching would otherwise
        read as 'no claims to check'."""
        bindings = _bindings()
        self.assertGreaterEqual(
            len(bindings), MIN_BINDINGS,
            f"only {len(bindings)} rule sentences bind a port skill to a ctx "
            f"variable or template (expected at least {MIN_BINDINGS}). Either "
            f"the corpus dropped a wiring claim or the extraction regex no "
            f"longer matches how those claims are phrased.")

    def test_every_named_ctx_variable_exists_in_that_skills_templates(self):
        available = {skill: _ctx_vars(d) for skill, d in SKILL_TEMPLATE_DIRS.items()}
        for skill, names in available.items():
            self.assertTrue(names, f"no ctx variables found under {SKILL_TEMPLATE_DIRS[skill]}")

        missing = []
        for rule_id, skill, ctxs, _ in _bindings():
            for name in ctxs:
                if name not in available[skill]:
                    missing.append(f"rule {rule_id} claims {skill} wires "
                                   f"ctx.{name}, absent from "
                                   f"{SKILL_TEMPLATE_DIRS[skill].relative_to(REPO_ROOT)}")
        self.assertEqual([], missing,
                         "rules claim template wiring that does not exist:\n  "
                         + "\n  ".join(missing))

    def test_every_named_template_file_exists(self):
        missing = []
        for rule_id, skill, _, j2s in _bindings():
            for name in j2s:
                if not (SKILL_TEMPLATE_DIRS[skill] / name).is_file():
                    missing.append(f"rule {rule_id} names {skill} template "
                                   f"{name}, which does not exist")
        self.assertEqual([], missing, "\n  ".join(missing))


if __name__ == "__main__":
    unittest.main()
