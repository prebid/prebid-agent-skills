"""The topmost CHANGELOG header must match the live corpus versions.

WHY
    CHANGELOG.md's preamble says every entry header lists all four versioned
    artifacts "at their current state for reproducibility." The topmost header is
    therefore a claim about the corpus as it stands, not a frozen historical
    snapshot like the entries below it.

    That claim went stale silently. Rules 47/48/49 landed with the rules corpus at
    0.4.0 and the taxonomy at 1.2.0 while the top header still read 0.3.0 and
    1.0.0, so a reader checking which corpus a rules bump was documented against
    would have found no entry for it at all. Nothing checked, so nothing said --
    the same shape as a rule claiming template wiring that does not exist.

SCOPE
    Only the FIRST header. Historical entries carry the versions that were current
    when they were written and must not be rewritten; `test_doc_count_claims.py`
    excludes CHANGELOG.md wholesale for exactly that reason, and this gate is the
    narrow exception for the one header that is a present-tense claim.

    `port_report_version` is not checked: `port-report.schema.json` declares no
    version field anywhere, so the number has no artifact to compare against. That
    is worth fixing in the schema; until then the gate would be asserting one piece
    of prose against another.

Run: python3 -m unittest scripts.tests.test_changelog_header_currency -v
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
SHARED = REPO_ROOT / "prebid-server-go" / "read" / "skills" / "shared"

HEADER_RE = re.compile(
    r"^## \[adapter_spec_version (?P<spec>[\d.]+)\]"
    r" · \[taxonomy_version (?P<taxonomy>[\d.]+)\]"
    r" · \[port_translation_rules_version (?P<rules>[\d.]+)\]",
    re.M)


def live_versions() -> dict[str, str]:
    """The three versions that have a machine-readable source.

    `adapter_spec_version` is NOT pinned by a constant in the schema -- the
    property carries only a SemVer `pattern`, so the schema admits every version
    it has ever had, deliberately, because a spec emitted by an older skill build
    still declares one of them. The shipped goldens are the authority instead:
    they all declare the current version, and a separate gate keeps the read
    orchestrators emitting it. Unanimity is required here, so a half-migrated
    corpus fails rather than silently picking a winner.
    """
    declared = set()
    for lang in ("go", "java"):
        for golden in sorted((REPO_ROOT / f"prebid-server-{lang}" / "read" /
                              "test-fixtures").glob("*.golden.spec.yaml")):
            spec = yaml.safe_load(golden.read_text(encoding="utf-8"))
            declared.add(str(spec.get("adapter_spec_version")))
    return {
        "spec": declared.pop() if len(declared) == 1 else None,
        "taxonomy": yaml.safe_load(
            (SHARED / "behavior-taxonomy.yaml").read_text(encoding="utf-8"))["taxonomy_version"],
        "rules": yaml.safe_load(
            (SHARED / "port-translation-rules.yaml").read_text(encoding="utf-8"))["rules_version"],
    }


class TestChangelogHeaderCurrency(unittest.TestCase):
    def test_a_header_is_parseable(self):
        """If the header form changes, this gate stops checking anything. Say so
        rather than passing."""
        self.assertIsNotNone(
            HEADER_RE.search(CHANGELOG.read_text(encoding="utf-8")),
            "no CHANGELOG header matched the expected form -- the gate below is "
            "checking nothing until the regex is updated")

    def test_live_versions_are_all_readable(self):
        live = live_versions()
        missing = [k for k, v in live.items() if not v]
        self.assertEqual([], missing,
                         f"could not read the live version for {missing} -- an "
                         f"unreadable source makes the comparison vacuous. For "
                         f"'spec' this also fires when the goldens do not all "
                         f"declare the same adapter_spec_version.")

    def test_topmost_header_matches_the_corpus(self):
        m = HEADER_RE.search(CHANGELOG.read_text(encoding="utf-8"))
        assert m is not None  # covered by test_a_header_is_parseable
        live = live_versions()
        drift = [f"{key}: CHANGELOG says {m.group(key)!r}, corpus says {live[key]!r}"
                 for key in ("spec", "taxonomy", "rules")
                 if m.group(key) != live[key]]
        self.assertEqual(
            [], drift,
            "the topmost CHANGELOG header no longer describes the corpus:\n  "
            + "\n  ".join(drift)
            + "\n\nA version bump needs its own entry. Do not edit an older "
              "header -- those record what was current when they were written.")


if __name__ == "__main__":
    unittest.main()
