"""Pin the executable macro registry to the registered upstream claim.

`endpoint-macros.yaml` is the admission set R8 loads in round-trip-ci.py. It is
the file that *executes*, and it had drifted badly from upstream while the prose
that described it was being corrected: sixteen entries, seven of which name no
field upstream, thirteen real fields missing. R8 therefore warned on the genuine
`{{.TokenID}}`, `{{.SourceId}}` and `{{.SupplyId}}`, and those three false
positives were subsequently frozen into the accepted-warnings baseline as
decisions.

The lesson generalises: anchoring a claim to prose leaves the executable copy
free to disagree with it. So the chain is two hops, both mechanical:

    endpoint-macros.yaml  ==  upstream-claims.yaml    (here, every CI run, hermetic)
    upstream-claims.yaml  ==  macros.EndpointTemplateParams
                                        (verify-upstream-claims.py --upstream, weekly)

Neither hop alone is sufficient. The first without the second freezes a stale
list; the second without the first lets the harness run on a different list from
the one that was verified.

Run: python3 -m unittest scripts.tests.test_endpoint_macro_registry -v
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "prebid-server-go" / "read" / "skills" / "shared" / "endpoint-macros.yaml"
MANIFEST = REPO_ROOT / "scripts" / "upstream-claims.yaml"
CLAIM_ID = "go.macros.endpoint-template-params"


def _registry() -> dict:
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))


def _claim() -> dict:
    doc = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    for claim in doc["claims"]:
        if claim["id"] == CLAIM_ID:
            return claim
    raise AssertionError(f"{CLAIM_ID} is not registered in {MANIFEST.name}")


class TestGoTemplateMacroRegistry(unittest.TestCase):
    def test_registry_matches_the_registered_claim_exactly(self):
        """Set equality, not containment: an extra name silently admits a macro
        that aborts config.New at startup, and a missing one is a false WARN on
        a legitimate endpoint. Both directions are defects."""
        registry = set(_registry()["go_template_macros"])
        claimed = set(_claim()["expect"]["contains"])
        self.assertEqual(
            registry, claimed,
            f"endpoint-macros.yaml has drifted from {CLAIM_ID}. "
            f"Only in registry: {sorted(registry - claimed)}. "
            f"Only in claim: {sorted(claimed - registry)}.",
        )

    def test_claim_declares_an_exact_field_set(self):
        """A `contains` list without `exact: true` would let upstream grow a
        field while both this test and the upstream check stayed green."""
        expect = _claim()["expect"]
        self.assertTrue(expect.get("exact"),
                        f"{CLAIM_ID} must declare exact: true, or a new upstream field "
                        f"passes both hops of the chain unnoticed")
        self.assertEqual(expect["count"], len(expect["contains"]))

    def test_registry_has_no_duplicates(self):
        names = _registry()["go_template_macros"]
        self.assertEqual(len(names), len(set(names)))

    def test_the_seven_invented_names_stay_gone(self):
        """Regression pin. These named no field upstream and had zero uses in any
        golden or any upstream bidder-info file, yet R8 admitted them."""
        invented = {"BidderCode", "PartnerID", "RegionID", "SiteID",
                    "SourceID", "TagID", "Username"}
        present = invented & set(_registry()["go_template_macros"])
        self.assertEqual(set(), present,
                         f"invented macro name(s) reintroduced: {sorted(present)}")

    def test_macros_used_by_goldens_are_admitted(self):
        """The registry is an admission set; every Go-template macro any golden
        actually uses must be in it, or R8 warns on the corpus it validates."""
        import re
        used: set[str] = set()
        for golden in (REPO_ROOT / "prebid-server-go" / "read" / "test-fixtures").glob("*.golden.spec.yaml"):
            used.update(re.findall(r"\{\{\.([A-Za-z]+)\}\}", golden.read_text(encoding="utf-8")))
        doc = _registry()
        admitted = set(doc["go_template_macros"]) | set(doc.get("user_sync_macros", [])) \
            | set(doc.get("openrtb_macros", []))
        missing = sorted(used - admitted)
        self.assertEqual([], missing,
                         f"golden endpoints use macro(s) no registry key admits: {missing}")



class TestMacroRecordForm(unittest.TestCase):
    """`macros_used` entries must be BARE identifiers, in every golden.

    R8 extracts placeholder names from the endpoint string and compares them
    against this field, so a wrapped entry (`{{AdUnit}}`) never matches its own
    placeholder and the macro reads as unsubstituted. Two goldens carried the
    wrapped form and one recorded `%s`, which is a String.format placeholder and
    not a macro name at all.

    Prose entries are a separate, milder defect and are reported separately: R8
    normalises to the leading identifier so `t (TMax milliseconds...)` still
    matches `t`, which is why the corpus's two prose sites do not break
    recognition. They are still not the recorded form, and the drift pass should
    move the descriptions out.
    """

    PATHS = (
        ("bidder_info", "endpoint_construction", "macros_used"),
        ("code", "make_requests", "endpoint_resolution", "macros_used"),
        ("code", "make_requests", "endpoint_resolution", "macro_field_set"),
    )
    BARE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def _entries(self):
        for lang in ("go", "java"):
            base = REPO_ROOT / f"prebid-server-{lang}" / "read" / "test-fixtures"
            for golden in sorted(base.glob("*.golden.spec.yaml")):
                doc = yaml.safe_load(golden.read_text(encoding="utf-8")) or {}
                for path in self.PATHS:
                    node = doc
                    for key in path:
                        node = (node or {}).get(key) if isinstance(node, dict) else None
                    for entry in (node or []):
                        yield f"{lang}/{golden.name}", ".".join(path), entry

    def test_no_single_token_entry_is_wrapped_or_a_format_specifier(self):
        """Scoped to single-token entries deliberately.

        An earlier version checked every entry for `{}$#` and flagged a prose
        entry because its description happened to contain `${json-unit.any-number}`
        -- the same overlapping-gate mistake as reporting one defect twice under
        two names. A prose entry is a different, milder defect, reported by the
        test below. What this one owns is an entry that is TRYING to be an
        identifier and has the wrong form.
        """
        bad = []
        for where, path, entry in self._entries():
            if not isinstance(entry, str):
                bad.append(f"{where} {path}: non-string entry {entry!r}")
                continue
            if entry != entry.strip():
                bad.append(f"{where} {path}: {entry!r} has surrounding whitespace")
            token = entry.strip()
            if any(c.isspace() for c in token):
                continue  # prose; owned by test_prose_entries_are_reported
            if any(c in token for c in "{}$#"):
                bad.append(f"{where} {path}: {token!r} is wrapped — record the bare identifier")
            elif "%" in token:
                bad.append(f"{where} {path}: {token!r} is a format specifier, not a macro name")
            elif not self.BARE.match(token):
                bad.append(f"{where} {path}: {token!r} is not a bare identifier")
        self.assertEqual([], bad, "\n  ".join(bad))

    def test_prose_entries_are_reported(self):
        """Not a failure: R8 tolerates these via leading-identifier matching, and
        the descriptions carry real information that needs somewhere to go. This
        prints them so the drift pass has the list."""
        prose = [f"{w} {p}: {e!r}" for w, p, e in self._entries()
                 if isinstance(e, str) and not self.BARE.match(e.strip())]
        if prose:
            print("\nmacros_used entries that are prose rather than bare identifiers "
                  f"({len(prose)}):")
            for line in prose:
                print(f"  {line}")
            print("  R8 matches these by leading identifier, so recognition is intact; "
                  "the descriptions belong in a quirk.")
        self.assertLessEqual(
            len(prose), 6,
            "prose entries grew — the form rule is not being followed by new reads:\n  "
            + "\n  ".join(prose))

if __name__ == "__main__":
    unittest.main()
