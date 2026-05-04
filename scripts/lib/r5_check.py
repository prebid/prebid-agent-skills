"""scripts/lib/r5_check.py — R5 cross-language structural-parity comparator.

Lifts R5 (rule 5: cross-language structural parity for port pairs) from
`scripts/round-trip-ci.py` into a comparator-neutral library so that both
the CI harness and the upcoming Phase D port skills (`port-go2java`,
`port-java2go`) can compute R5 against the same source of truth.

Public API
----------

- ``compare_pair(go_spec, java_spec, *, assertions=None, overall=None) -> R5Result``
    Run the full R5 comparison and return both the per-key diagnostics
    and the aggregated state. Inputs are duck-typed via ``SpecView``.

- ``aggregate_state(diagnostics, pair_present) -> (state, byte_equal, warn, fail)``
    Reduce a list of ``R5Diagnostic`` to one of the four harness-computable
    states plus categorized key lists.

The ``R5_PORT_STATES`` tuple is the full schema enum (six values). Two of
those — ``warn-target-strengthens-source`` and
``fail-source-omits-target-constraint`` — are computed by the port skill
at port-time using direction-specific source-vs-target spec analysis,
not by this library.

The constants ``R5_STRICT_KEYS``, ``R5_FORM_DIVERGENT_KEYS``, and
``R5_ADVISORY_DIVERGENT_KEYS``, plus the helpers ``deep_eq``,
``_list_set_eq``, ``_maintainer_eq``, and ``normalize_endpoint_macros``,
are re-exported by ``scripts/round-trip-ci.py`` for backward compatibility
with existing tests in ``scripts/tests/test_round_trip_ci.py``.
"""

from __future__ import annotations

import dataclasses
import json
import re
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple


# ---------------------------------------------------------------------------
# Severity primitives + state enum
# ---------------------------------------------------------------------------

PASS = "pass"
WARN = "warn"
FAIL = "fail"

# Harness-computable subset (four of the six schema states). The aggregation
# function below emits one of these.
STATE_PASS = "pass"
STATE_WARN_BYTE_ONLY = "warn-byte-only-divergence"
STATE_FAIL_SEMANTIC = "fail-semantic-divergence"
STATE_SKIPPED_NO_PAIR = "skipped-no-pair-fixture"

# Full port-report `r5_check.state` enum. The two non-harness states are
# emitted by the port skill at port-time:
#   - "warn-target-strengthens-source": the destination spec carries a
#     constraint absent in the source (Connatix-style: Java adds
#     minimum/maximum that Go lacks; port preserves the constraint).
#   - "fail-source-omits-target-constraint": the source spec lacks a
#     constraint the destination language requires; port cannot emit a
#     valid target without operator intervention (aax-style; surfaces
#     in `human_todos[]` for upstream confirmation).
R5_PORT_STATES: Tuple[str, ...] = (
    STATE_PASS,
    STATE_WARN_BYTE_ONLY,
    "warn-target-strengthens-source",
    STATE_FAIL_SEMANTIC,
    "fail-source-omits-target-constraint",
    STATE_SKIPPED_NO_PAIR,
)


# ---------------------------------------------------------------------------
# Duck-typed spec view + diagnostic dataclasses
# ---------------------------------------------------------------------------

class SpecView(Protocol):
    """Read-only view of a golden spec.

    The harness's ``Spec`` dataclass implements this naturally. Port-skill
    callers can pass any object that exposes the same triple of attributes.
    """

    bidder: str
    raw: Dict[str, Any]

    def get(self, dotted: str, default: Any = None) -> Any: ...


@dataclasses.dataclass
class R5Diagnostic:
    """One R5 finding, comparator-neutral.

    Callers wrap to the harness ``Finding`` dataclass (round-trip-ci.py)
    or to the schema dict shape consumed by ``port-report.json``'s
    ``r5_check.diagnostics[]`` field.
    """

    key: str
    severity: str
    detail: str
    category: str = ""


@dataclasses.dataclass
class R5Result:
    diagnostics: List[R5Diagnostic]
    state: str


# ---------------------------------------------------------------------------
# Equality helpers
# ---------------------------------------------------------------------------


def deep_eq(a: Any, b: Any) -> bool:
    """Order-insensitive equality via JSON-serialized comparison."""
    return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


def _list_set_eq(a: Any, b: Any) -> bool:
    """Set-equality for list-valued runtime fields where order is not
    semantically load-bearing. Wave 11b B5 #2: corrects the false-positive
    class where Go's ``sort.Strings()`` and Java's ``LinkedHashSet`` produce
    legitimately different iteration orders for the same set.

    Both ``None`` → equal. Both lists → set-equal (compared via
    JSON-serialized member representations to admit nested dicts/lists).
    Mixed types or non-lists fall through to ``deep_eq``.
    """
    if a is None and b is None:
        return True
    if not isinstance(a, list) or not isinstance(b, list):
        return deep_eq(a, b)
    return sorted(json.dumps(x, sort_keys=True, default=str) for x in a) == \
           sorted(json.dumps(x, sort_keys=True, default=str) for x in b)


def _maintainer_eq(a: Any, b: Any) -> bool:
    """Maintainer-block equality: only the email is the runtime invariant.
    Wave 11b B5 #2: prevents stale-FAILs when one language adds extra
    maintainer fields (phone, team, slack handle) the other doesn't carry.
    Both ``None`` → equal. Compares case-insensitive email after stripping
    whitespace; missing email on either side compares as empty string.
    """
    em_a = (a or {}).get("email") if isinstance(a, dict) else None
    em_b = (b or {}).get("email") if isinstance(b, dict) else None
    return (em_a or "").strip().lower() == (em_b or "").strip().lower()


# ---------------------------------------------------------------------------
# Key registries
# ---------------------------------------------------------------------------

# Wave 11b B5 #2: R5_STRICT_KEYS uses (spec_field, dual_key, comparator)
# three-tuples for per-key comparator selection:
# - LIST-VALUED keys (capabilities, geoscope, schema_interpretation.*) use
#   _list_set_eq (order-independent set equality).
# - PROSE-BEARING keys (maintainer) use _maintainer_eq (compares only the
#   runtime-invariant subfield, not advisory fields).
# - PURE-DATA keys (gvl_vendor_id, endpoint_compression, modifying_vast_xml_allowed)
#   use deep_eq (scalar equality).
#
# When the dual-spec assertion says severity:warn, downgrade to WARN.
# When dual-spec says severity:pass but runtime disagrees → FAIL (stale-pass).
R5_STRICT_KEYS: Tuple[Tuple[str, str, Callable[[Any, Any], bool]], ...] = (
    ("bidder_info.capabilities",                       "bidder_info_capabilities",                _list_set_eq),
    # params.schema_interpretation is decomposed into runtime-invariant
    # subfields only. The whole block contains prose-bearing fields
    # (properties[].description, properties[].notes) that legitimately
    # differ across languages — Java may reference Pattern.matches semantics,
    # Go may reference regexp substring semantics, etc. Comparing the whole
    # block via deep_eq fired stale-pass FAILs on dual-spec assertions that
    # were correctly capturing semantic equivalence (e.g., thetradedesk).
    ("params.schema_interpretation.required_fields",   "params_schema_interpretation",            _list_set_eq),
    ("params.schema_interpretation.combinators_used",  "params_schema_interpretation",            _list_set_eq),
    ("params.schema_interpretation.flexible_types",    "params_schema_interpretation",            _list_set_eq),
    ("bidder_info.gvl_vendor_id",                      "bidder_info_gvl_vendor_id",               deep_eq),
    ("bidder_info.endpoint_compression",               "bidder_info_endpoint_compression",        deep_eq),
    ("bidder_info.geoscope",                           "bidder_info_geoscope",                    _list_set_eq),
    ("bidder_info.maintainer",                         "bidder_info_maintainer",                  _maintainer_eq),
    ("bidder_info.modifying_vast_xml_allowed",         "bidder_info_modifying_vast_xml_allowed",  deep_eq),
)

# Wave 11b B4 C1: R5 divergent keys split into two buckets.
#
# R5_FORM_DIVERGENT_KEYS: macro form differs by language but the URL/value
# after normalization MUST be equal. normalize_endpoint_macros() canonicalizes
# Go's ``{{.X}}`` template form, Java's ``${X}`` printf, Spring EL ``#{X}``,
# and raw ``{{X}}`` to a single ``{{X}}`` form. Real semantic divergence
# (different macro names, different URL paths) surfaces as FAIL after
# normalization. Absence of dual-spec assertion when normalized values DIFFER
# → FAIL ``assertion_missing`` (Wave 11b strictness; aax's
# bidder_info_endpoint assertion was added as prerequisite to land this gate).
R5_FORM_DIVERGENT_KEYS: Tuple[Tuple[str, str], ...] = (
    ("bidder_info.endpoint",                    "bidder_info_endpoint"),
)

# R5_ADVISORY_DIVERGENT_KEYS: cross-language metadata that legitimately
# diverges per-language; honor only the assertion's severity (no runtime
# FAIL on divergence; absence of assertion is silent — these are
# documentation-only checks). bidder_info.endpoint_construction stays here
# because the divergence is SEMANTIC (different macro NAMES per language,
# e.g., adverxo Go uses ``AdUnit`` / Java uses ``adUnitId``) not just
# macro syntax — normalization can't paper that over and the dual-spec is
# the right surface to document the per-language idiom.
R5_ADVISORY_DIVERGENT_KEYS: Tuple[Tuple[Optional[str], str], ...] = (
    ("bidder_info.endpoint_construction",       "bidder_info_endpoint_construction"),
    ("bidder_info.default_enabled",             "bidder_info_default_enabled"),
    ("meta.alias_metadata",                     "alias_metadata"),
    (None,                                      "lifecycle_rename"),
    (None,                                      "port_lineage"),
    (None,                                      "reviewer_cohort"),
    (None,                                      "test_fixture_cost"),
)


def normalize_endpoint_macros(s: Any) -> Any:
    """Normalize endpoint URL macro syntax across languages to canonical
    ``{{X}}`` form. Used by R5_FORM_DIVERGENT_KEYS so that pure-syntax
    divergence (Go template vs Java property reference) doesn't fire false
    structural-parity FAILs.

    Recognized forms:
      - ``{{.X}}``     → ``{{X}}``   (Go html/text template)
      - ``${X}``       → ``{{X}}``   (Java property reference / shell-style)
      - ``#{X}``       → ``{{X}}``   (Spring Expression Language)
      - ``{{X}}``      → ``{{X}}``   (already canonical)

    ``%s`` (printf positional) is intentionally NOT normalized — it has no
    name to canonicalize against, so any pair using ``%s`` on one side and
    ``{{X}}`` on the other will surface as a real divergence (and should be
    documented in dual-spec or fixed in the corpus).
    """
    if not isinstance(s, str):
        return s
    s = re.sub(r"\{\{\.(\w+)\}\}", r"{{\1}}", s)   # Go {{.X}} → {{X}}
    s = re.sub(r"\$\{(\w+)\}",      r"{{\1}}", s)  # Java ${X} → {{X}}
    s = re.sub(r"#\{([^}]+)\}",     r"{{\1}}", s)  # Spring EL #{X} → {{X}}
    return s


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compare_pair(
    go_spec: Optional[SpecView],
    java_spec: Optional[SpecView],
    *,
    assertions: Optional[Dict[str, Any]] = None,
    overall: Optional[Dict[str, Any]] = None,
) -> R5Result:
    """Cross-language structural-parity comparison.

    Runtime values are the source of truth; the dual-spec assertion is an
    EXPECTATION verified against runtime, not a free pass. Polarity contract:
    when dual-spec says severity:pass but runtime values disagree, FAIL —
    the assertion is stale.

    Returns an ``R5Result`` containing per-key diagnostics plus the
    aggregated four-state harness-computable ``state``.
    """
    diagnostics: List[R5Diagnostic] = []
    pair_present = go_spec is not None and java_spec is not None

    if go_spec is None and java_spec is None:
        return R5Result(diagnostics=[], state=STATE_SKIPPED_NO_PAIR)

    assertions = assertions or {}
    overall = overall or {}

    cls_state = (overall.get("cross_language_state") or "").lower() if isinstance(overall, dict) else ""
    blocker_count = overall.get("blocker_count") if isinstance(overall, dict) else 0
    if cls_state == "divergent-semantic" and isinstance(blocker_count, int) and blocker_count > 0:
        diagnostics.append(R5Diagnostic(
            key="overall.cross_language_state",
            severity=FAIL,
            detail=f"overall.cross_language_state=divergent-semantic with {blocker_count} blocker(s)",
            category="overall",
        ))
    elif cls_state.startswith("divergent") and isinstance(blocker_count, int) and blocker_count > 0:
        diagnostics.append(R5Diagnostic(
            key="overall.cross_language_state",
            severity=WARN,
            detail=f"overall.cross_language_state={cls_state} with {blocker_count} blocker(s)",
            category="overall",
        ))

    # bidder_params_sha256 — load-bearing R5 contract.
    go_sha = go_spec.raw.get("bidder_params_sha256") if go_spec else None
    java_sha = java_spec.raw.get("bidder_params_sha256") if java_spec else None
    sha_assert = assertions.get("bidder_params_sha256") if isinstance(assertions, dict) else None

    if go_spec is not None and java_spec is not None:
        if go_sha == java_sha and go_sha is not None:
            diagnostics.append(R5Diagnostic(
                key="bidder_params_sha256",
                severity=PASS,
                detail=f"bidder_params_sha256 equal ({go_sha[:12]})",
                category="byte-equal",
            ))
        else:
            severity = WARN
            explanation = "differs"
            category = ""
            if isinstance(sha_assert, dict):
                sev = (sha_assert.get("severity") or "").lower()
                if sev in ("fail", "error"):
                    severity = FAIL
                elif sev == "pass":
                    # POLARITY INVERSION: runtime says different but dual-spec
                    # claims byte_equal — the assertion is stale. FAIL.
                    severity = FAIL
                    explanation = "stale-pass-assertion (dual-spec claims byte_equal but runtime SHAs differ)"
                    category = "stale-pass"
                elif sev in ("warn", "warning"):
                    severity = WARN
                if explanation == "differs":
                    kind = sha_assert.get("divergence_kind") or ""
                    if sha_assert.get("semantically_equal") is True:
                        explanation = f"byte-only divergence ({kind})" if kind else "byte-only divergence"
                        category = "byte-only-divergence"
                    elif sha_assert.get("semantically_equal") is False:
                        explanation = f"semantic divergence ({kind})" if kind else "semantic divergence"
                        category = "semantic-divergence"
                    else:
                        explanation = kind or explanation
            else:
                # Heuristic fallback: scan quirks for byte-vs-semantic signals.
                blobs = [
                    " ".join(str(q.get(k, "")) for k in ("id", "summary", "edge_case_taxon")).lower()
                    for q in (go_spec.raw.get("quirks") or []) + (java_spec.raw.get("quirks") or [])
                    if isinstance(q, dict)
                ]
                byte_divergence = any("byte" in b and "divergen" in b for b in blobs)
                semantic_divergence = any(
                    "semantic" in b and "divergen" in b
                    and "semantically identical" not in b
                    and "semantic match" not in b
                    for b in blobs
                )
                if semantic_divergence:
                    severity = FAIL
                    explanation = "semantic divergence (per quirk)"
                    category = "semantic-divergence"
                elif byte_divergence:
                    severity = WARN
                    explanation = "whitespace/byte divergence (per quirk)"
                    category = "byte-only-divergence"
            diagnostics.append(R5Diagnostic(
                key="bidder_params_sha256",
                severity=severity,
                detail=f"bidder_params_sha256 {explanation}: go={go_sha or 'none'} java={java_sha or 'none'}",
                category=category,
            ))
    elif sha_assert is not None:
        # One side missing a fixture; surface the asymmetry (PASS — informational).
        sev_for_msg = sha_assert.get("severity", "?") if isinstance(sha_assert, dict) else "?"
        diagnostics.append(R5Diagnostic(
            key="bidder_params_sha256",
            severity=PASS,
            detail=f"only-one-side fixture; dual-spec sha-assertion noted (severity={sev_for_msg})",
            category="one-side-only",
        ))

    # R5-strict keys: runtime divergence FAILs unless dual-spec downgrades to WARN.
    # Wave 11b B5 #2: per-key comparator selection (set-equality for list-valued
    # keys, email-only for maintainer, deep_eq for pure-data scalars).
    for spec_field, dual_key, eq_fn in R5_STRICT_KEYS:
        if go_spec is None or java_spec is None:
            continue
        a = go_spec.get(spec_field)
        b = java_spec.get(spec_field)
        if a is None and b is None:
            continue
        dual_assert = assertions.get(dual_key) if isinstance(assertions, dict) else None
        if not eq_fn(a, b):
            severity = FAIL
            stale = False
            category = "semantic-divergence"
            if isinstance(dual_assert, dict):
                sev = (dual_assert.get("severity") or "").lower()
                if sev in ("warn", "warning"):
                    severity = WARN
                    category = "byte-only-divergence"
                elif sev == "pass":
                    stale = True
            if stale:
                diagnostics.append(R5Diagnostic(
                    key=spec_field,
                    severity=FAIL,
                    detail=f"{spec_field} runtime divergence but dual-spec claims pass — stale",
                    category="stale-pass",
                ))
            else:
                diagnostics.append(R5Diagnostic(
                    key=spec_field,
                    severity=severity,
                    detail=f"{spec_field} differs across languages",
                    category=category,
                ))

    # R5_FORM_DIVERGENT keys: normalize macro syntax + deep_eq. Real
    # divergence (different macro names, different URLs) FAILs unless the
    # dual-spec assertion documents it; absence of assertion when normalized
    # values differ → FAIL assertion_missing (Wave 11b B4 C1 strictness).
    for spec_field, dual_key in R5_FORM_DIVERGENT_KEYS:
        if go_spec is None or java_spec is None:
            continue
        a = go_spec.get(spec_field)
        b = java_spec.get(spec_field)
        if a is None and b is None:
            continue
        a_norm = normalize_endpoint_macros(a) if isinstance(a, str) else a
        b_norm = normalize_endpoint_macros(b) if isinstance(b, str) else b
        dual_assert = assertions.get(dual_key) if isinstance(assertions, dict) else None
        if a_norm == b_norm:
            # Normalized forms agree; emit per assertion if present.
            if isinstance(dual_assert, dict):
                sev = (dual_assert.get("severity") or "").lower()
                if sev in ("fail", "error"):
                    diagnostics.append(R5Diagnostic(
                        key=spec_field,
                        severity=FAIL,
                        detail=f"{spec_field}: dual-spec claims divergence but normalized forms equal — stale-fail-assertion",
                        category="stale-fail",
                    ))
                # severity=pass or warn with normalized-equal: no finding (correct).
            continue
        # Normalized forms still differ — real divergence beyond macro syntax.
        if not isinstance(dual_assert, dict):
            diagnostics.append(R5Diagnostic(
                key=spec_field,
                severity=FAIL,
                detail=(
                    f"{spec_field}: assertion_missing — normalized forms differ but no dual-spec entry "
                    f"under '{dual_key}' (Wave 11b B4 C1: FORM_DIVERGENT keys require explicit assertion)"
                ),
                category="assertion-missing",
            ))
            continue
        sev = (dual_assert.get("severity") or "").lower()
        summary = dual_assert.get("divergence_summary") or "divergent per dual-spec"
        if sev in ("fail", "error"):
            diagnostics.append(R5Diagnostic(
                key=spec_field,
                severity=FAIL,
                detail=f"{spec_field}: {summary}",
                category="semantic-divergence",
            ))
        elif sev in ("warn", "warning"):
            diagnostics.append(R5Diagnostic(
                key=spec_field,
                severity=WARN,
                detail=f"{spec_field}: {summary}",
                category="byte-only-divergence",
            ))
        elif sev == "pass":
            # Polarity inversion: assertion claims pass but normalized forms differ.
            diagnostics.append(R5Diagnostic(
                key=spec_field,
                severity=FAIL,
                detail=(
                    f"{spec_field}: stale-pass-assertion — normalized forms differ "
                    f"(assertion claims equivalent: {summary})"
                ),
                category="stale-pass",
            ))

    # R5_ADVISORY_DIVERGENT keys: honor only the assertion severity. No
    # runtime FAIL on divergence; silent on absence (these are
    # cross-language metadata where divergence is documentation, not contract).
    for spec_field, dual_key in R5_ADVISORY_DIVERGENT_KEYS:
        dual_assert = assertions.get(dual_key) if isinstance(assertions, dict) else None
        if not isinstance(dual_assert, dict):
            continue
        sev = (dual_assert.get("severity") or "").lower()
        summary = dual_assert.get("divergence_summary") or "divergent per dual-spec"
        if sev in ("fail", "error"):
            diagnostics.append(R5Diagnostic(
                key=dual_key,
                severity=FAIL,
                detail=f"{dual_key}: {summary}",
                category="semantic-divergence",
            ))
        elif sev in ("warn", "warning"):
            diagnostics.append(R5Diagnostic(
                key=dual_key,
                severity=WARN,
                detail=f"{dual_key}: {summary}",
                category="byte-only-divergence",
            ))

    state, _, _, _ = aggregate_state(diagnostics, pair_present)
    return R5Result(diagnostics=diagnostics, state=state)


def aggregate_state(
    diagnostics: List[R5Diagnostic],
    pair_present: bool,
) -> Tuple[str, List[str], List[str], List[str]]:
    """Reduce a list of R5 diagnostics to one of the four harness-computable
    states plus categorized key lists.

    Returns ``(state, byte_equal_keys, warn_keys, fail_keys)`` where:

    - ``state`` is one of ``STATE_SKIPPED_NO_PAIR`` / ``STATE_FAIL_SEMANTIC``
      / ``STATE_WARN_BYTE_ONLY`` / ``STATE_PASS``. Precedence:
      pair-absent → skipped; any FAIL → fail-semantic; any WARN →
      warn-byte-only; otherwise → pass.
    - ``byte_equal_keys`` lists keys whose comparison passed (values agreed
      after normalization).
    - ``warn_keys`` lists keys reported WARN.
    - ``fail_keys`` lists keys reported FAIL.

    The two extended schema states (``warn-target-strengthens-source``,
    ``fail-source-omits-target-constraint``) are emitted by the port skill
    at port-time using direction-specific source-vs-target spec analysis,
    not by this function.
    """
    if not pair_present:
        return STATE_SKIPPED_NO_PAIR, [], [], []
    byte_equal = [d.key for d in diagnostics if d.severity == PASS]
    warn = [d.key for d in diagnostics if d.severity == WARN]
    fail = [d.key for d in diagnostics if d.severity == FAIL]
    if fail:
        return STATE_FAIL_SEMANTIC, byte_equal, warn, fail
    if warn:
        return STATE_WARN_BYTE_ONLY, byte_equal, warn, fail
    return STATE_PASS, byte_equal, warn, fail
