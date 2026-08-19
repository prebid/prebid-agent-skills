#!/usr/bin/env python3
"""scripts/sync-from-upstream.py — Phase 4.1 drift detection.

Compares each pinned bidder golden against current upstream master and
emits a structured drift report. Per audit B3, this is the
deterministic-subset of the orchestrator's mechanical checks — it does
NOT run the full Claude SKILL. It encodes byte-fact comparisons (file
SHA, file presence, key field values) only.

Watched surface
---------------
The scan set is derived per golden, not hard-coded. Every upstream path a
golden already names is watched:

- `static/bidder-info/{bidder}.yaml` / `src/main/resources/bidder-config/{bidder}.yaml`
  (field comparison, driven by GO_BIDDER_INFO_FIELDS / JAVA_BIDDER_CONFIG_FIELDS)
- the bidder-params JSON (sha256 comparison)
- every entry in `code.file_layout.files[]`, resolved against
  `cross_language.{go,java}_artifacts.bidder_dir` (presence)
- `params.ext_struct.file`, `params.params_test.file`,
  `cross_language.go_artifacts.*_file`, `iab_category_storage.go_data_file` (presence)
- registration sites: Go bidder constant in `openrtb_ext/bidders.go` and
  `exchange/adapter_builders.go`; Java `registry.test_application_properties`
  entries (substring presence)
- every `tests.fixture_inventory.*[]` entry that carries a real sha256
  (sha256 comparison), presence-only when the golden recorded a placeholder

Drift classification:
- `no-drift`   — upstream and golden match on the checked surface.
- `data-only`  — a YAML field changed value (endpoint URL, gvl_vendor_id,
                  default_enabled, etc.) but the file shape is unchanged. Warns.
- `structural` — a file appeared/disappeared, a sha changed, a new top-level
                  YAML key showed up. Fails; needs a human read+update.
- `lifecycle`  — the bidder was renamed or removed upstream, or one of its
                  artifacts moved to a new path. Fails, with a finding type
                  distinct from data drift and from deletion.

Output:
    scripts/output/drift-report.json   — machine-readable per-bidder findings.
    scripts/output/drift-report.md     — human-readable summary.

Usage:
    python3 scripts/sync-from-upstream.py                              # github-raw, all pinned
    python3 scripts/sync-from-upstream.py --source-mode=local --go-checkout=/path/to/prebid-server
    python3 scripts/sync-from-upstream.py --bidder=kobler              # single-bidder run
    python3 scripts/sync-from-upstream.py --scan-tier=core             # legacy 2-glob surface
    python3 scripts/sync-from-upstream.py --shard=1/4                  # shard the corpus
    python3 scripts/sync-from-upstream.py --strict                     # warns become exit 1

Exit codes: 0 (clean), 1 (fail OR warns under --strict), 2 (warns only),
3 (instrument failure — empty scan set, or every fetch errored).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import fnmatch
import hashlib
import json
import os
import posixpath
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, NamedTuple, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDENS_GO = REPO_ROOT / "prebid-server-go" / "read" / "test-fixtures"
GOLDENS_JAVA = REPO_ROOT / "prebid-server-java" / "read" / "test-fixtures"
DEFAULT_OUT_DIR = REPO_ROOT / "scripts" / "output"

UPSTREAM_GO_REPO = "prebid/prebid-server"
UPSTREAM_JAVA_REPO = "prebid/prebid-server-java"

# Per-bidder file lists. These two artifacts are the `core` scan tier and
# the only ones compared field-by-field; the wider tiers derive their paths
# from each golden instead of from a fixed glob list.
GO_FILES_PER_BIDDER = [
    "static/bidder-info/{bidder}.yaml",
    "static/bidder-params/{bidder}.json",
]
JAVA_FILES_PER_BIDDER = [
    "src/main/resources/bidder-config/{bidder}.yaml",
    "src/main/resources/static/bidder-params/{bidder}.json",
]

# How each core artifact is checked, and which golden field may override its
# path. Keyed by template so the lists above stay the single source of truth.
CORE_ARTIFACT_ROLES = {
    GO_FILES_PER_BIDDER[0]: ("bidder_info", "field", None),
    GO_FILES_PER_BIDDER[1]: ("bidder_params", "sha", None),
    JAVA_FILES_PER_BIDDER[0]: (
        "bidder_config", "field",
        ("cross_language", "java_artifacts", "yaml_path")),
    JAVA_FILES_PER_BIDDER[1]: (
        "bidder_params", "sha",
        ("cross_language", "java_artifacts", "bidder_params_path")),
}

# Go registration sites. A bidder that is registered upstream has its
# constant in both files; losing either is a structural break.
GO_BIDDER_REGISTRY = "openrtb_ext/bidders.go"
GO_BUILDER_REGISTRY = "exchange/adapter_builders.go"

JAVA_IT_RESOURCE_ROOT = "src/test/resources/org/prebid/server/it/"

# Go fixture-inventory categories that map to `{test_root}/{category}/`.
# `extrainfo_*` maps to `{test_root}-extrainfo/{suffix}/` (msft).
GO_FIXTURE_CATEGORIES = (
    "exemplary", "supplemental", "amp", "video", "videosupplemental", "dooh",
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Severity-to-exit-code: aligns with round-trip-ci.py and lint-port-rules.py
SEVERITY_PASS = "pass"
SEVERITY_WARN = "warn"
SEVERITY_FAIL = "fail"

# Scan tiers, widest last.
TIER_CORE = "core"        # the two field-compared artifacts only (legacy surface)
TIER_SOURCE = "source"    # + declared source files + registration sites
TIER_FULL = "full"        # + test-fixture sha comparison
SCAN_TIERS = (TIER_CORE, TIER_SOURCE, TIER_FULL)


class FieldSpec(NamedTuple):
    """One tracked YAML field: where it lives in the golden, and upstream.

    `upstream_keys` are dotted paths inside the upstream mapping (the Java
    adapter section, or the Go bidder-info root); the first one that
    resolves wins. `absent_default` is the value upstream is understood to
    mean when the key is missing — `None` means "cannot compare, skip".
    """
    name: str
    golden_keys: tuple
    upstream_keys: tuple
    severity: str
    absent_default: Any = None


# YAML fields the script tracks for "data-only-drift" detection. These
# tables drive compare_bidder_go / compare_bidder_java — adding a row here
# is the only step needed to start watching a field.
GO_BIDDER_INFO_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("endpoint", ("bidder_info", "endpoint"), ("endpoint",), SEVERITY_WARN),
    FieldSpec("endpoint_compression", ("bidder_info", "endpoint_compression"),
              ("endpointCompression", "endpoint-compression"), SEVERITY_WARN),
    FieldSpec("gvl_vendor_id", ("bidder_info", "gvl_vendor_id"),
              ("gvlVendorID",), SEVERITY_WARN, absent_default=0),
    FieldSpec("modifying_vast_xml_allowed", ("bidder_info", "modifying_vast_xml_allowed"),
              ("modifyingVastXmlAllowed",), SEVERITY_WARN, absent_default=False),
    FieldSpec("ortb_version", ("bidder_info", "ortb_version"),
              ("openrtb.version", "ortb-version"), SEVERITY_WARN),
    FieldSpec("disabled", ("meta", "disabled"), ("disabled",), SEVERITY_WARN,
              absent_default=False),
    FieldSpec("alias_of", ("meta", "alias_of"), ("aliasOf",), SEVERITY_FAIL),
)

JAVA_BIDDER_CONFIG_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("endpoint", ("bidder_info", "endpoint"), ("endpoint",), SEVERITY_WARN),
    FieldSpec("endpoint_compression", ("bidder_info", "endpoint_compression"),
              ("endpoint-compression",), SEVERITY_WARN),
    FieldSpec("gvl_vendor_id", ("bidder_info", "gvl_vendor_id"),
              ("meta-info.vendor-id",), SEVERITY_WARN, absent_default=0),
    FieldSpec("modifying_vast_xml_allowed", ("bidder_info", "modifying_vast_xml_allowed"),
              ("modifying-vast-xml-allowed",), SEVERITY_WARN, absent_default=False),
    FieldSpec("ortb_version", ("bidder_info", "ortb_version"),
              ("ortb-version",), SEVERITY_WARN),
    FieldSpec("default_enabled", ("bidder_info", "default_enabled"),
              ("enabled",), SEVERITY_WARN, absent_default=True),
)

# Top-level keys current upstream Go bidder-info YAML is known to use.
# Anything outside this set is structural drift the golden has not modelled.
GO_KNOWN_YAML_KEYS = {
    "endpoint", "endpointCompression", "endpoint-compression", "geoscope",
    "maintainer", "capabilities", "gvlVendorID", "modifyingVastXmlAllowed",
    "disabled", "enabled", "userSyncURL", "userSync", "usersync", "syncer",
    "yaml", "aliasOf", "experiment", "openrtb", "extra_info", "ortb-version",
    "platform_id", "whiteLabelOnly", "xapi", "debug",
}


class Finding(NamedTuple):
    bidder: str
    language: str
    type: str
    severity: str
    message: str
    detail: dict


class WatchedPath(NamedTuple):
    """One upstream path in the scan set, and how it is checked."""
    path: str
    kind: str          # bidder_info | bidder_params | source | registration | fixture
    check: str         # field | sha | presence | entries
    origin: str        # golden field that declared it
    expect_sha: Optional[str] = None
    detail: dict = {}


class ScanSet(NamedTuple):
    """What was actually scanned. Reported verbatim; never inferred from findings."""
    pairs: list          # [(bidder, language)] actually compared
    skipped: list        # [(bidder, language, reason)] discovered but not compared
    paths: list          # [WatchedPath] across every compared pair
    tier: str
    shard: Optional[str]
    unresolvable: list   # golden fixture entries that name no usable path


class FetchError(Exception):
    """Raised when a fetch fails with an unrecoverable error (not 404)."""


def fetch_local(checkout_root: Path, file_path: str) -> Optional[bytes]:
    """Read a file from a local repo checkout. Returns None on missing."""
    p = checkout_root / file_path
    if p.is_file():
        return p.read_bytes()
    return None


def list_local_paths(checkout_root: Path) -> set[str]:
    """Every tracked-looking path in a local checkout, repo-relative, posix."""
    root = Path(checkout_root)
    out: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        rel_dir = os.path.relpath(dirpath, root)
        for fn in filenames:
            rel = fn if rel_dir == "." else os.path.join(rel_dir, fn)
            out.add(rel.replace(os.sep, "/"))
    return out


def fetch_github_raw(repo: str, file_path: str, ref: str = "master",
                     timeout: int = 30) -> Optional[bytes]:
    """Fetch via raw.githubusercontent.com. Returns None on 404."""
    url = f"https://raw.githubusercontent.com/{repo}/{ref}/{file_path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if resp.status == 200:
                return resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise FetchError(f"HTTP {e.code} for {url}") from e
    except urllib.error.URLError as e:
        raise FetchError(f"network error for {url}: {e}") from e
    return None


def list_github_tree(repo: str, ref: str = "master", timeout: int = 60) -> set[str]:
    """One recursive tree call per repo — makes presence checks free.

    Uses GITHUB_TOKEN when present (raises the API rate limit on CI).
    Raises FetchError so the caller can degrade to per-path fetches.
    """
    url = f"https://api.github.com/repos/{repo}/git/trees/{ref}?recursive=1"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "prebid-agent-skills-sync-from-upstream",
    })
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise FetchError(f"HTTP {e.code} for {url}") from e
    except (urllib.error.URLError, ValueError) as e:
        raise FetchError(f"tree listing failed for {url}: {e}") from e
    if payload.get("truncated"):
        raise FetchError(f"tree listing truncated for {repo}@{ref}")
    return {e["path"] for e in payload.get("tree", []) if e.get("type") == "blob"}


class UpstreamSource:
    """A fetch+list view of one upstream repo, with a process-lifetime cache.

    `paths()` returns the full blob path set when the backend can produce one
    (local walk, or the GitHub tree API). Presence checks then cost nothing.
    When no listing is available `exists()` falls back to a content fetch.
    """

    def __init__(self, label: str,
                 fetch_fn: Callable[[str], Optional[bytes]],
                 list_fn: Optional[Callable[[], set[str]]] = None):
        self.label = label
        self._fetch_fn = fetch_fn
        self._list_fn = list_fn
        self._cache: dict[str, Optional[bytes]] = {}
        self._paths: Optional[frozenset[str]] = None
        self._paths_tried = False
        self.fetch_count = 0
        self.list_errors: list[str] = []

    # -- content ---------------------------------------------------------
    def fetch(self, path: str) -> Optional[bytes]:
        if path in self._cache:
            return self._cache[path]
        data = self._fetch_fn(path)
        self.fetch_count += 1
        self._cache[path] = data
        return data

    def prefetch(self, paths, max_workers: int = 8) -> list[str]:
        """Warm the cache concurrently. Returns fetch-error strings."""
        todo = [p for p in dict.fromkeys(paths) if p not in self._cache]
        errors: list[str] = []
        if not todo:
            return errors
        if max_workers <= 1:
            for p in todo:
                try:
                    self.fetch(p)
                except FetchError as e:
                    errors.append(f"{self.label}:{p}: {e}")
            return errors
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(self._fetch_fn, p): p for p in todo}
            for fut in concurrent.futures.as_completed(futures):
                p = futures[fut]
                try:
                    self._cache[p] = fut.result()
                except FetchError as e:
                    errors.append(f"{self.label}:{p}: {e}")
                except Exception as e:                      # pragma: no cover
                    errors.append(f"{self.label}:{p}: {e}")
                else:
                    self.fetch_count += 1
        return errors

    # -- listing ---------------------------------------------------------
    def paths(self) -> Optional[frozenset[str]]:
        if self._paths_tried:
            return self._paths
        self._paths_tried = True
        if self._list_fn is None:
            return None
        try:
            self._paths = frozenset(self._list_fn())
        except FetchError as e:
            self.list_errors.append(str(e))
            self._paths = None
        return self._paths

    def exists(self, path: str) -> bool:
        known = self.paths()
        if known is not None:
            return path in known
        return self.fetch(path) is not None

    def glob(self, pattern: str) -> list[str]:
        """Paths matching a glob. Empty when no listing backend is available."""
        known = self.paths()
        if not known:
            return []
        return sorted(p for p in known if fnmatch.fnmatch(p, pattern))


def as_source(source_or_fetcher, label: str = "upstream") -> UpstreamSource:
    """Accept an UpstreamSource or a bare fetcher callable."""
    if isinstance(source_or_fetcher, UpstreamSource):
        return source_or_fetcher
    return UpstreamSource(label, source_or_fetcher, None)


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def discover_pinned_bidders() -> tuple[dict[str, Path], dict[str, Path]]:
    go = {f.stem.replace(".golden.spec", ""): f for f in GOLDENS_GO.glob("*.golden.spec.yaml")}
    java = {f.stem.replace(".golden.spec", ""): f for f in GOLDENS_JAVA.glob("*.golden.spec.yaml")}
    return go, java


def _path(d: Optional[dict], *keys) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _dotted(d: Optional[dict], dotted_key: str) -> Any:
    return _path(d, *dotted_key.split("."))


def _join(base: Optional[str], name: str) -> Optional[str]:
    """Resolve a golden-declared file name against its bidder directory."""
    if not name:
        return None
    if not base:
        return None
    return posixpath.normpath(posixpath.join(base.rstrip("/"), name))


def _looks_like_file(name: Any) -> bool:
    """Golden fixture inventories carry prose placeholders as well as paths.

    beachfront records `"40 supplemental fixtures (error paths ...)"` in place
    of an enumeration; spaces and parentheses are the tell.
    """
    if not isinstance(name, str) or not name.strip():
        return False
    return not (" " in name or "(" in name)


def _as_fixture_filename(name: str, default_suffix: str = ".json") -> str:
    """Some goldens record fixture stems (`204status`) rather than filenames."""
    if posixpath.splitext(posixpath.basename(name))[1]:
        return name
    return name + default_suffix


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256_RE.match(value))


def _scalar_equal(a: Any, b: Any) -> bool:
    """Compare two YAML scalars across the quoting difference.

    Upstream writes `version: 2.6` (YAML float); goldens record
    `ortb_version: "2.6"` (string). Those are the same value, and reporting
    them as drift would bury the real omissions this table exists to catch.
    Booleans keep strict identity so `true` never equals `1`.
    """
    if isinstance(a, bool) or isinstance(b, bool):
        # `True == 1` in Python; a YAML `true` is not a YAML `1`.
        return isinstance(a, bool) and isinstance(b, bool) and a is b
    if a == b:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return False
    return str(a).strip() == str(b).strip()


# ---------------------------------------------------------------------------
# Scan-set derivation
# ---------------------------------------------------------------------------

def derive_watched_paths(bidder: str, golden: dict, language: str,
                         tier: str = TIER_FULL) -> tuple[list[WatchedPath], list[str]]:
    """Every upstream path this golden puts under watch, plus unusable entries.

    Pure: no I/O. The returned list IS the per-pair scan set the report
    prints — the report never re-derives it from the findings.
    """
    watched: list[WatchedPath] = []
    unresolvable: list[str] = []
    seen: set[str] = set()

    def add(path: Optional[str], kind: str, check: str, origin: str,
            expect_sha: Optional[str] = None, detail: Optional[dict] = None):
        if not path or path in seen:
            return
        seen.add(path)
        watched.append(WatchedPath(path, kind, check, origin, expect_sha, detail or {}))

    templates = GO_FILES_PER_BIDDER if language == "go" else JAVA_FILES_PER_BIDDER
    for template in templates:
        kind, check, override_keys = CORE_ARTIFACT_ROLES[template]
        path = template.format(bidder=bidder)
        origin = template
        if override_keys:
            # `emxdigital` -> `emx_digital.json`: the golden's own override
            # wins over the lowercase-bidder-name construction.
            override = _path(golden, *override_keys)
            if override:
                path, origin = override, ".".join(override_keys)
        add(path, kind, check, origin,
            golden.get("bidder_params_sha256") if check == "sha" else None)

    if tier == TIER_CORE:
        return watched, unresolvable

    arts_key = "go_artifacts" if language == "go" else "java_artifacts"
    bidder_dir = _path(golden, "cross_language", arts_key, "bidder_dir")

    # 1. Declared source files, resolved against the bidder directory.
    for entry in (_path(golden, "code", "file_layout", "files") or []):
        name = entry.get("name") if isinstance(entry, dict) else entry
        if not isinstance(name, str) or not name:
            continue
        if name.endswith("/"):
            # A directory stand-in (beachfront `model/`); no file to check.
            unresolvable.append(f"{language}/{bidder}: code.file_layout.files[] dir entry {name!r}")
            continue
        resolved = _join(bidder_dir, name)
        if resolved is None:
            unresolvable.append(
                f"{language}/{bidder}: code.file_layout.files[] {name!r} has no bidder_dir")
            continue
        add(resolved, "source", "presence", "code.file_layout.files[]")

    # 2. Other single-file declarations.
    if language == "go":
        for key in ("impl_file", "test_file", "params_test_file", "ext_struct_file",
                    "alias_yaml_path"):
            add(_path(golden, "cross_language", "go_artifacts", key), "source",
                "presence", f"cross_language.go_artifacts.{key}")
        add(_path(golden, "params", "ext_struct", "file"), "source", "presence",
            "params.ext_struct.file")
        add(_path(golden, "params", "params_test", "file"), "source", "presence",
            "params.params_test.file")
        add(_path(golden, "iab_category_storage", "go_data_file"), "source",
            "presence", "iab_category_storage.go_data_file")
        # 3. Registration sites.
        constant = _path(golden, "cross_language", "go_artifacts", "bidder_constant")
        if constant:
            short = constant.split(".")[-1]
            add(GO_BIDDER_REGISTRY, "registration", "entries",
                "cross_language.go_artifacts.bidder_constant",
                detail={"entries": [f"{short} "], "label": short})
            add(GO_BUILDER_REGISTRY, "registration", "entries",
                "cross_language.go_artifacts.bidder_constant",
                detail={"entries": [f"{constant}:"], "label": constant})
    else:
        reg_file = _path(golden, "registry", "test_application_properties", "file")
        entries = _path(golden, "registry", "test_application_properties", "entries") or []
        entries = [e for e in entries if isinstance(e, str) and e.strip()]
        if reg_file and entries:
            add(reg_file, "registration", "entries",
                "registry.test_application_properties",
                detail={"entries": entries, "label": "test-application.properties"})

    if tier != TIER_FULL:
        return watched, unresolvable

    # 4. Test fixtures. sha256-compared when the golden recorded a real digest;
    #    presence-only when it recorded a `pending-operator-fetch` placeholder.
    for path, sha, origin, bad in _derive_fixture_paths(bidder, golden, language):
        if bad:
            unresolvable.append(bad)
            continue
        add(path, "fixture", "sha" if sha else "presence", origin, sha)

    return watched, unresolvable


def _derive_fixture_paths(bidder: str, golden: dict, language: str):
    """Yield (path, expect_sha, origin, unresolvable_note) per fixture entry."""
    inventory = _path(golden, "tests", "fixture_inventory") or {}
    if not isinstance(inventory, dict):
        return

    if language == "go":
        bidder_dir = _path(golden, "cross_language", "go_artifacts", "bidder_dir")
        test_root = _path(golden, "tests", "test_root_directory")
        for category, items in sorted(inventory.items()):
            if not isinstance(items, list):
                continue
            if category.startswith("extrainfo_"):
                sub = f"{test_root}-extrainfo/{category[len('extrainfo_'):]}"
            elif category in GO_FIXTURE_CATEGORIES:
                sub = f"{test_root}/{category}"
            else:
                continue
            for item in items:
                name = item.get("filename") if isinstance(item, dict) else item
                origin = f"tests.fixture_inventory.{category}[]"
                if not _looks_like_file(name):
                    yield None, None, origin, f"go/{bidder}: {origin} entry is not a path"
                    continue
                if not bidder_dir or not test_root:
                    yield None, None, origin, f"go/{bidder}: {origin} has no bidder_dir/test_root"
                    continue
                sha = item.get("sha256") if isinstance(item, dict) else None
                filename = _as_fixture_filename(name)
                yield (_join(bidder_dir, f"{sub}/{filename}"),
                       (sha if _is_sha256(sha) else None), origin, None)
        return

    for item in (inventory.get("integration") or []):
        name = item.get("filename") if isinstance(item, dict) else item
        origin = "tests.fixture_inventory.integration[]"
        if not _looks_like_file(name):
            yield None, None, origin, f"java/{bidder}: {origin} entry is not a path"
            continue
        # `generic` records folder-qualified names; canonical goldens record
        # bare filenames under `openrtb2/{bidder}/`.
        filename = _as_fixture_filename(name)
        rel = filename if "/" in filename else f"openrtb2/{bidder}/{filename}"
        sha = item.get("sha256") if isinstance(item, dict) else None
        yield JAVA_IT_RESOURCE_ROOT + rel, (sha if _is_sha256(sha) else None), origin, None


# ---------------------------------------------------------------------------
# Lifecycle triage: renamed vs removed vs deleted
# ---------------------------------------------------------------------------

def _normalize_bidder_token(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def find_relocated_artifact(source: UpstreamSource, missing_path: str,
                            bidder: str, expect_sha: Optional[str],
                            match_bidder_token: bool = False) -> Optional[dict]:
    """Look for a declared artifact that moved rather than disappeared.

    Upstream renames of a params file keep the bytes and change the name
    (`emx_digital.json` -> `emxdigital.json`). A sibling in the same
    directory whose name normalizes to the same token, or whose bytes hash
    to the golden's recorded sha, is a relocation, not a deletion.

    `match_bidder_token` is for artifacts *named after the bidder* — the
    bidder-params and bidder-config files. It must stay off for ordinary
    source files, where it would happily call `params_test.go` a rename of
    `adkernelAdn.go` because both sit in the `adkernelAdn` package.
    """
    directory = posixpath.dirname(missing_path)
    suffix = posixpath.splitext(missing_path)[1]
    candidates = [
        p for p in source.glob(f"{directory}/*{suffix}")
        if p != missing_path
    ]
    if not candidates:
        return None
    wanted = {_normalize_bidder_token(posixpath.splitext(posixpath.basename(missing_path))[0])}
    if match_bidder_token:
        wanted.add(_normalize_bidder_token(bidder))
    by_name = [p for p in candidates
               if _normalize_bidder_token(posixpath.splitext(posixpath.basename(p))[0])
               in wanted]
    for candidate in by_name:
        data = source.fetch(candidate)
        if data is None:
            continue
        actual = compute_sha256(data)
        return {"candidate": candidate, "upstream_sha": actual,
                "content_identical": bool(expect_sha) and actual == expect_sha,
                "matched_by": "name"}
    if not expect_sha:
        return None
    for candidate in candidates:
        data = source.fetch(candidate)
        if data is not None and compute_sha256(data) == expect_sha:
            return {"candidate": candidate, "upstream_sha": expect_sha,
                    "content_identical": True, "matched_by": "content"}
    return None


def find_alias_successor(source: UpstreamSource, bidder: str, language: str,
                         budget: int = 400, max_workers: int = 8) -> Optional[str]:
    """Find the bidder that absorbed a renamed one.

    An upstream rename leaves the old name behind as an alias of the new
    one (`magnite.yaml` declares `adapters.magnite.aliases.rubicon`). Only
    runs when a bidder's whole implementation set has vanished, so the cost
    is paid once per lifecycle event, not on every run of a healthy corpus.

    Go has no equivalent signal: a renamed Go bidder keeps its own
    `static/bidder-info/{old}.yaml` carrying `aliasOf: {new}`, so the file
    is still there and `alias_of_drift` fires instead of this path.
    """
    if language != "java":
        return None
    candidates = source.glob("src/main/resources/bidder-config/*.yaml")[:budget]
    if not candidates:
        return None
    source.prefetch(candidates, max_workers=max_workers)
    for path in candidates:
        data = source.fetch(path)
        if not data:
            continue
        try:
            doc = yaml.safe_load(data) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(doc, dict):
            continue
        for parent, section in (doc.get("adapters") or {}).items():
            if not isinstance(section, dict):
                continue
            aliases = section.get("aliases") or {}
            if isinstance(aliases, dict) and bidder in aliases:
                return parent
    return None


# ---------------------------------------------------------------------------
# Field comparison
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def resolve_java_adapter_section(doc: dict, bidder: str, golden: dict) -> dict:
    """The effective `adapters.*` mapping for this bidder.

    A Java alias has no top-level section of its own: `152media` lives at
    `adapters.adkernel.aliases.152media` and inherits everything else from
    `adapters.adkernel`. Goldens record the *effective* values, so the
    comparison needs the merged view — reading only `adapters.152media`
    yields an empty mapping and reports every inherited field as drift.
    """
    own = _path(doc, "adapters", bidder)
    if isinstance(own, dict):
        return own
    parent = _path(golden, "meta", "alias_of")
    if not parent:
        return {}
    parent_section = _path(doc, "adapters", parent)
    if not isinstance(parent_section, dict):
        return {}
    overrides = _path(parent_section, "aliases", bidder)
    base = {k: v for k, v in parent_section.items() if k != "aliases"}
    if isinstance(overrides, dict):
        return _deep_merge(base, overrides)
    # Tilde-inherit form (`152media: ~`) — pure inheritance, no overrides.
    return base


def resolve_go_bidder_info(doc: dict, golden: dict, source: UpstreamSource) -> dict:
    """The effective `static/bidder-info/{bidder}.yaml` mapping for this bidder.

    A Go alias file carries `aliasOf` plus only the fields it overrides --
    `152media.yaml` is `aliasOf: adkernel` and `gvlVendorID: 1111`, nothing else.
    Go fills the rest from the parent at load time (`config/bidderinfo.go`
    applies the parent's value wherever the alias's is empty), and goldens record
    those effective values, so comparing against the alias file alone leaves every
    inherited field unchecked.

    Unchecked, not merely unequal: `compare_fields` skips a field whose upstream
    key is absent and whose FieldSpec declares no `absent_default`, which is the
    case for `endpoint` and `endpointCompression`. So an inherited endpoint could
    change in the parent and no finding would fire. The Java path has had
    `resolve_java_adapter_section` for this since it was written; this is its
    Go counterpart.

    Falls back to the alias's own doc when the parent is unreadable, so a missing
    parent degrades to the previous behaviour instead of raising.
    """
    parent = doc.get("aliasOf") or _path(golden, "meta", "alias_of")
    if not parent:
        return doc
    raw = source.fetch(f"static/bidder-info/{parent}.yaml")
    if raw is None:
        return doc
    try:
        parent_doc = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        return doc
    if not isinstance(parent_doc, dict):
        return doc
    base = {k: v for k, v in parent_doc.items() if k != "aliases"}
    overrides = {k: v for k, v in doc.items() if k != "aliasOf"}
    return _deep_merge(base, overrides)


def compare_fields(bidder: str, language: str, golden: dict, upstream: dict,
                   specs: tuple[FieldSpec, ...], where: str) -> list[Finding]:
    """Compare every tracked field. Drives both language paths."""
    findings: list[Finding] = []
    for spec in specs:
        golden_value = _path(golden, *spec.golden_keys)
        upstream_value = None
        found = False
        for key in spec.upstream_keys:
            candidate = _dotted(upstream, key)
            if candidate is not None:
                upstream_value, found = candidate, True
                break
        if not found:
            # Upstream is silent and the field has no defined "absent" meaning,
            # so there is nothing to compare against.
            if spec.absent_default is None:
                continue
            upstream_value = spec.absent_default
        if golden_value is None and spec.absent_default is not None:
            golden_value = spec.absent_default
        if _scalar_equal(golden_value, upstream_value):
            continue
        findings.append(Finding(
            bidder, language, f"{spec.name}_drift", spec.severity,
            f"{where}.{spec.name} changed",
            {"golden": golden_value, "upstream": upstream_value,
             "upstream_keys": list(spec.upstream_keys)}))
    return findings


# ---------------------------------------------------------------------------
# Per-bidder comparison
# ---------------------------------------------------------------------------

def _load_golden(golden_path: Path) -> dict:
    with open(golden_path) as fp:
        return yaml.safe_load(fp) or {}


def _check_presence(bidder: str, language: str, source: UpstreamSource,
                    watched: list[WatchedPath]) -> list[Finding]:
    findings: list[Finding] = []
    for w in watched:
        if w.check != "presence" or w.kind not in ("source", "fixture"):
            continue
        if source.exists(w.path):
            continue
        relocated = find_relocated_artifact(source, w.path, bidder, w.expect_sha,
                                            match_bidder_token=False)
        if relocated:
            findings.append(Finding(
                bidder, language, "artifact_renamed_upstream", SEVERITY_FAIL,
                f"{w.path} moved to {relocated['candidate']}",
                {"path": w.path, "origin": w.origin, **relocated}))
            continue
        findings.append(Finding(
            bidder, language, f"{w.kind}_file_missing", SEVERITY_FAIL,
            f"{w.path} not found upstream",
            {"path": w.path, "origin": w.origin}))
    return findings


def _check_fixture_shas(bidder: str, language: str, source: UpstreamSource,
                        watched: list[WatchedPath]) -> list[Finding]:
    findings: list[Finding] = []
    for w in watched:
        if w.kind != "fixture" or w.check != "sha":
            continue
        data = source.fetch(w.path)
        if data is None:
            findings.append(Finding(
                bidder, language, "fixture_file_missing", SEVERITY_FAIL,
                f"{w.path} not found upstream",
                {"path": w.path, "origin": w.origin}))
            continue
        actual = compute_sha256(data)
        if actual != w.expect_sha:
            findings.append(Finding(
                bidder, language, "fixture_content_drift", SEVERITY_WARN,
                f"{w.path} content changed",
                {"path": w.path, "origin": w.origin,
                 "golden_sha": w.expect_sha, "upstream_sha": actual}))
    return findings


def _check_registration(bidder: str, language: str, source: UpstreamSource,
                        watched: list[WatchedPath]) -> list[Finding]:
    findings: list[Finding] = []
    for w in watched:
        if w.kind != "registration":
            continue
        data = source.fetch(w.path)
        if data is None:
            findings.append(Finding(
                bidder, language, "registration_file_missing", SEVERITY_FAIL,
                f"{w.path} not found upstream",
                {"path": w.path, "origin": w.origin}))
            continue
        text = data.decode("utf-8", errors="replace")
        missing = [e for e in w.detail.get("entries", []) if e not in text]
        if missing:
            findings.append(Finding(
                bidder, language, "registration_entry_missing", SEVERITY_FAIL,
                f"{w.detail.get('label', bidder)} no longer registered in {w.path}",
                {"path": w.path, "origin": w.origin, "missing_entries": missing}))
    return findings


IMPLEMENTATION_KINDS = ("bidder_info", "bidder_config", "bidder_params", "source")


def _artifact_set_vanished(source: UpstreamSource, watched: list[WatchedPath],
                           is_alias: bool, language: str) -> bool:
    """True when every implementation artifact a bidder owns is gone upstream.

    Only config/params/source count. Test fixtures and registration files
    routinely survive a rename — upstream kept `openrtb2/rubicon/` after
    rubicon became an alias of magnite — so including them would hide the
    lifecycle event behind thirty individual deletion findings.

    Alias children legitimately own no bidder-params file (and, on the Java
    side, no bidder-config either); those kinds are excluded so an alias is
    never mistaken for a removed bidder.
    """
    exempt = set()
    if is_alias:
        exempt.add("bidder_params")
        if language == "java":
            exempt.add("bidder_config")
    owned = [w for w in watched
             if w.kind in IMPLEMENTATION_KINDS and w.kind not in exempt]
    if len(owned) < 2:
        return False
    return all(not source.exists(w.path) for w in owned)


def _lifecycle_finding(bidder: str, language: str, source: UpstreamSource,
                       watched: list[WatchedPath], rename_budget: int,
                       max_workers: int) -> Finding:
    paths = [w.path for w in watched if w.kind in IMPLEMENTATION_KINDS]
    successor = find_alias_successor(source, bidder, language,
                                     budget=rename_budget, max_workers=max_workers)
    if successor:
        return Finding(
            bidder, language, "bidder_renamed_upstream", SEVERITY_FAIL,
            f"{bidder} was renamed upstream; it is now an alias of {successor}",
            {"successor": successor, "vanished_paths": paths,
             "vanished_count": len(paths)})
    return Finding(
        bidder, language, "bidder_removed_upstream", SEVERITY_FAIL,
        f"{bidder} no longer exists upstream ({len(paths)} declared paths gone)",
        {"successor": None, "vanished_paths": paths, "vanished_count": len(paths)})


def compare_bidder_go(bidder: str, golden_path: Path, source_or_fetcher,
                      tier: str = TIER_CORE, rename_budget: int = 400,
                      max_workers: int = 8) -> list[Finding]:
    """Compare a Go-side golden against upstream prebid-server. Returns Findings."""
    source = as_source(source_or_fetcher, "go")
    golden = _load_golden(golden_path)
    watched, _ = derive_watched_paths(bidder, golden, "go", tier)
    return _compare(bidder, "go", golden, watched, source,
                    GO_BIDDER_INFO_FIELDS, "bidder_info", rename_budget, max_workers)


def compare_bidder_java(bidder: str, golden_path: Path, source_or_fetcher,
                        tier: str = TIER_CORE, rename_budget: int = 400,
                        max_workers: int = 8) -> list[Finding]:
    """Compare a Java-side golden against upstream prebid-server-java."""
    source = as_source(source_or_fetcher, "java")
    golden = _load_golden(golden_path)
    watched, _ = derive_watched_paths(bidder, golden, "java", tier)
    return _compare(bidder, "java", golden, watched, source,
                    JAVA_BIDDER_CONFIG_FIELDS, f"adapters.{bidder}",
                    rename_budget, max_workers)


def _compare(bidder: str, language: str, golden: dict, watched: list[WatchedPath],
             source: UpstreamSource, field_specs: tuple[FieldSpec, ...],
             where: str, rename_budget: int, max_workers: int) -> list[Finding]:
    findings: list[Finding] = []
    is_alias = bool(_path(golden, "meta", "is_alias"))

    # Whole-bidder lifecycle event short-circuits the per-file noise: one
    # finding that says renamed or removed, not N deletions.
    if _artifact_set_vanished(source, watched, is_alias, language):
        return [_lifecycle_finding(bidder, language, source, watched,
                                   rename_budget, max_workers)]

    info_kind = "bidder_info" if language == "go" else "bidder_config"
    for w in watched:
        if w.kind == "bidder_params":
            findings.extend(_compare_params(bidder, language, golden, w, source, is_alias))
        elif w.kind == info_kind:
            findings.extend(_compare_info(bidder, language, golden, w, source,
                                          field_specs, where, is_alias))

    findings.extend(_check_presence(bidder, language, source, watched))
    findings.extend(_check_fixture_shas(bidder, language, source, watched))
    findings.extend(_check_registration(bidder, language, source, watched))
    return findings


def _compare_params(bidder: str, language: str, golden: dict, w: WatchedPath,
                    source: UpstreamSource, is_alias: bool) -> list[Finding]:
    upstream_json = source.fetch(w.path)
    if upstream_json is None:
        if is_alias:
            # Alias children ride the parent's params file; absence is expected.
            return []
        relocated = find_relocated_artifact(source, w.path, bidder, w.expect_sha,
                                            match_bidder_token=True)
        if relocated:
            note = ("byte-identical" if relocated["content_identical"]
                    else f"content also changed ({relocated['upstream_sha'][:16]}…)")
            return [Finding(
                bidder, language, "bidder_params_renamed_upstream", SEVERITY_FAIL,
                f"bidder-params moved to {relocated['candidate']} ({note})",
                {"path": w.path, "origin": w.origin,
                 "golden_sha": w.expect_sha, **relocated})]
        return [Finding(bidder, language, "bidder_params_missing", SEVERITY_FAIL,
                        f"{w.path} not found upstream",
                        {"path": w.path, "origin": w.origin})]
    upstream_sha = compute_sha256(upstream_json)
    golden_sha = w.expect_sha
    if golden_sha and golden_sha != upstream_sha:
        return [Finding(
            bidder, language, "bidder_params_sha_drift", SEVERITY_FAIL,
            f"bidder_params_sha changed: golden {golden_sha[:16]}… vs upstream {upstream_sha[:16]}…",
            {"path": w.path, "golden_sha": golden_sha, "upstream_sha": upstream_sha,
             "golden_resolved_commit": _path(golden, "provenance", "source", "resolved_commit")})]
    return []


def _compare_info(bidder: str, language: str, golden: dict, w: WatchedPath,
                  source: UpstreamSource, field_specs: tuple[FieldSpec, ...],
                  where: str, is_alias: bool) -> list[Finding]:
    kind = w.kind
    raw = source.fetch(w.path)
    if raw is None:
        if language == "java" and is_alias:
            # Alias children (152media -> adkernel) ride the parent's config.
            return []
        relocated = find_relocated_artifact(source, w.path, bidder, None,
                                            match_bidder_token=True)
        if relocated:
            return [Finding(
                bidder, language, "artifact_renamed_upstream", SEVERITY_FAIL,
                f"{w.path} moved to {relocated['candidate']}",
                {"path": w.path, "origin": w.origin, **relocated})]
        return [Finding(bidder, language, f"{kind}_missing", SEVERITY_FAIL,
                        f"{w.path} not found upstream",
                        {"path": w.path, "origin": w.origin})]
    try:
        doc = yaml.safe_load(raw) or {}
    except yaml.YAMLError as e:
        return [Finding(bidder, language, "yaml_parse_error", SEVERITY_FAIL,
                        f"upstream YAML parse failed: {e}", {"path": w.path})]
    if not isinstance(doc, dict):
        return [Finding(bidder, language, "yaml_parse_error", SEVERITY_FAIL,
                        "upstream YAML is not a mapping", {"path": w.path})]

    if language == "java":
        section = resolve_java_adapter_section(doc, bidder, golden)
        return compare_fields(bidder, language, golden, section, field_specs, where)

    # Merged view for field comparison; the raw doc for the new-key check below,
    # so a parent's key does not read as a new key on the alias.
    effective = resolve_go_bidder_info(doc, golden, source) if is_alias else doc
    findings = compare_fields(bidder, language, golden, effective, field_specs, where)
    golden_keys = set((_path(golden, "bidder_info", "yaml_extra_fields") or {}).keys())
    new_keys = set(doc.keys()) - GO_KNOWN_YAML_KEYS - golden_keys
    if new_keys:
        findings.append(Finding(
            bidder, language, "new_yaml_field", SEVERITY_FAIL,
            f"upstream {w.path} has new top-level keys not in golden or known-set",
            {"new_keys": sorted(new_keys)}))
    return findings


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def render_md(findings: list[Finding], args: Any,
              scan: Optional[ScanSet] = None) -> str:
    out = []
    out.append("# Drift Report")
    out.append("")
    out.append("<!-- AUTO-GENERATED by scripts/sync-from-upstream.py. Regenerate via `make sync`. -->")
    out.append(f"<!-- Generated: {datetime.now(timezone.utc).isoformat()}; source-mode: {args.source_mode}; ref: {args.ref}. -->")
    out.append("")

    fail_findings = [f for f in findings if f.severity == SEVERITY_FAIL]
    warn_findings = [f for f in findings if f.severity == SEVERITY_WARN]
    pass_count = len([f for f in findings if f.severity == SEVERITY_PASS])

    out.append(f"**Summary**: {len(fail_findings)} fail, {len(warn_findings)} warn, {pass_count} informational.")
    out.append("")

    if fail_findings:
        out.append("## Failures (block merges)")
        out.append("")
        out.append(_render_findings_table(fail_findings))
        out.append("")

    if warn_findings:
        out.append("## Warnings (data-only drift; ack into goldens when ready)")
        out.append("")
        out.append(_render_findings_table(warn_findings))
        out.append("")

    if not (fail_findings or warn_findings):
        out.append("✓ No drift detected on the checked surface.")
        out.append("")

    out.append("---")
    out.append("")
    out.append("## Scan set")
    out.append("")
    if scan is None:
        out.append("- Scan set not recorded for this run.")
    else:
        go_pairs = sum(1 for _, lang in scan.pairs if lang == "go")
        java_pairs = sum(1 for _, lang in scan.pairs if lang == "java")
        by_check: dict[str, int] = {}
        for w in scan.paths:
            by_check[w.check] = by_check.get(w.check, 0) + 1
        out.append(f"- Pairs scanned: **{len(scan.pairs)}** ({go_pairs} Go + {java_pairs} Java) "
                   f"at scan tier `{scan.tier}`"
                   + (f", shard `{scan.shard}`" if scan.shard else "") + ".")
        out.append(f"- Upstream paths watched: **{len(scan.paths)}** "
                   f"({', '.join(f'{v} {k}' for k, v in sorted(by_check.items()))}).")
        out.append(f"- Findings emitted: **{len(findings)}** over "
                   f"{len(set((f.bidder, f.language) for f in findings))} pair(s).")
        if scan.skipped:
            out.append(f"- Pairs discovered but NOT scanned: **{len(scan.skipped)}** — "
                       + "; ".join(f"`{b}` ({l}): {r}" for b, l, r in scan.skipped))
        if scan.unresolvable:
            out.append(f"- Golden entries naming no usable upstream path: **{len(scan.unresolvable)}**.")
        if not scan.pairs:
            out.append("- **The scan set is empty. This report is not an all-clear.**")
    out.append("")
    out.append("## Sources")
    out.append("")
    out.append(f"- Upstream Go: `https://github.com/{UPSTREAM_GO_REPO}` ref `{args.ref}`.")
    out.append(f"- Upstream Java: `https://github.com/{UPSTREAM_JAVA_REPO}` ref `{args.ref}`.")
    out.append("- Methodology: [`docs/methodology/repo-rules.md`](../../docs/methodology/repo-rules.md), [`docs/methodology/schema-versioning.md`](../../docs/methodology/schema-versioning.md).")
    return "\n".join(out)


def _render_findings_table(findings: list[Finding]) -> str:
    lines = ["| Bidder | Language | Type | Message |",
             "|---|---|---|---|"]
    for f in findings:
        msg = f.message.replace("|", "\\|")
        lines.append(f"| `{f.bidder}` | {f.language} | `{f.type}` | {msg} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_shard(spec: Optional[str]) -> Optional[tuple[int, int]]:
    if not spec:
        return None
    m = re.fullmatch(r"(\d+)/(\d+)", spec.strip())
    if not m:
        raise ValueError(f"--shard expects i/n (1-based), got {spec!r}")
    index, total = int(m.group(1)), int(m.group(2))
    if total < 1 or not (1 <= index <= total):
        raise ValueError(f"--shard out of range: {spec!r}")
    return index, total


def apply_shard(pairs: list, shard: Optional[tuple[int, int]]) -> list:
    if shard is None:
        return pairs
    index, total = shard
    return [p for i, p in enumerate(sorted(pairs)) if i % total == index - 1]


def build_sources(args) -> tuple[Optional[UpstreamSource], Optional[UpstreamSource], list[str]]:
    notes: list[str] = []
    if args.source_mode == "local":
        go_src = java_src = None
        if args.go_checkout:
            root = Path(args.go_checkout)
            go_src = UpstreamSource("go", lambda p, r=root: fetch_local(r, p),
                                    lambda r=root: list_local_paths(r))
        else:
            notes.append("--source-mode=local without --go-checkout: Go goldens not scanned")
        if args.java_checkout:
            root = Path(args.java_checkout)
            java_src = UpstreamSource("java", lambda p, r=root: fetch_local(r, p),
                                      lambda r=root: list_local_paths(r))
        else:
            notes.append("--source-mode=local without --java-checkout: Java goldens not scanned")
        return go_src, java_src, notes
    go_src = UpstreamSource(
        "go", lambda p: fetch_github_raw(UPSTREAM_GO_REPO, p, args.ref),
        lambda: list_github_tree(UPSTREAM_GO_REPO, args.ref))
    java_src = UpstreamSource(
        "java", lambda p: fetch_github_raw(UPSTREAM_JAVA_REPO, p, args.ref),
        lambda: list_github_tree(UPSTREAM_JAVA_REPO, args.ref))
    return go_src, java_src, notes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--source-mode", choices=["local", "github-raw"],
                        default="github-raw")
    parser.add_argument("--go-checkout", help="Local prebid-server checkout root")
    parser.add_argument("--java-checkout", help="Local prebid-server-java checkout root")
    parser.add_argument("--bidder", help="Compare a single bidder only")
    parser.add_argument("--ref", default="master", help="Upstream ref (default: master)")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--scan-tier", choices=SCAN_TIERS, default=TIER_FULL,
                        help="core = legacy 2-glob surface; source = + declared "
                             "source files and registration sites; full = + fixture shas")
    parser.add_argument("--shard", help="Scan a slice of the corpus, as i/n (1-based)")
    parser.add_argument("--max-workers", type=int, default=8,
                        help="Concurrent fetches when warming the content cache")
    parser.add_argument("--rename-scan-budget", type=int, default=400,
                        help="Max upstream configs read when hunting a rename successor")
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings as errors (exit 1 instead of 2)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    try:
        shard = parse_shard(args.shard)
    except ValueError as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 3

    if args.source_mode == "local" and not (args.go_checkout or args.java_checkout):
        sys.stderr.write("ERROR: --source-mode=local requires --go-checkout and/or --java-checkout.\n")
        return 3

    go_src, java_src, source_notes = build_sources(args)

    go, java = discover_pinned_bidders()
    if args.bidder:
        go = {k: v for k, v in go.items() if k == args.bidder}
        java = {k: v for k, v in java.items() if k == args.bidder}
        if not (go or java):
            sys.stderr.write(f"No pinned golden for {args.bidder!r}.\n")
            return 3

    all_pairs = ([(b, "go") for b in go] + [(b, "java") for b in java])
    selected = set(apply_shard(all_pairs, shard))

    scanned: list[tuple[str, str]] = []
    skipped: list[tuple[str, str, str]] = []
    watched_all: list[WatchedPath] = []
    unresolvable_all: list[str] = []
    findings: list[Finding] = []
    fetch_errors: list[str] = []

    plan: list[tuple[str, str, Path, UpstreamSource, list[WatchedPath]]] = []
    for bidder, language in sorted(all_pairs):
        golden_path = (go if language == "go" else java)[bidder]
        source = go_src if language == "go" else java_src
        if (bidder, language) not in selected:
            skipped.append((bidder, language, f"not in shard {args.shard}"))
            continue
        if source is None:
            skipped.append((bidder, language, "no upstream checkout supplied"))
            continue
        golden = _load_golden(golden_path)
        watched, unresolvable = derive_watched_paths(bidder, golden, language, args.scan_tier)
        plan.append((bidder, language, golden_path, source, watched))
        watched_all.extend(watched)
        unresolvable_all.extend(unresolvable)

    # Warm the content cache concurrently; comparisons then read from cache
    # in a fixed order, so output stays deterministic.
    for source in (go_src, java_src):
        if source is None:
            continue
        source.paths()
        for err in source.list_errors:
            fetch_errors.append(f"{source.label} tree listing: {err}")
        wanted = [w.path for _, lang, _, src, ws in plan if src is source
                  for w in ws if w.check in ("sha", "field", "entries")]
        fetch_errors.extend(source.prefetch(wanted, max_workers=max(1, args.max_workers)))

    compare_fn = {"go": compare_bidder_go, "java": compare_bidder_java}
    for bidder, language, golden_path, source, _ in plan:
        try:
            findings.extend(compare_fn[language](
                bidder, golden_path, source, tier=args.scan_tier,
                rename_budget=args.rename_scan_budget,
                max_workers=max(1, args.max_workers)))
        except FetchError as e:
            fetch_errors.append(f"{language}/{bidder}: {e}")
            skipped.append((bidder, language, f"fetch error: {e}"))
            continue
        scanned.append((bidder, language))

    scan = ScanSet(pairs=scanned, skipped=skipped, paths=watched_all,
                   tier=args.scan_tier, shard=args.shard,
                   unresolvable=unresolvable_all)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "drift-report.json"
    md_path = out_dir / "drift-report.md"

    json_path.write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_mode": args.source_mode,
        "ref": args.ref,
        "scan_tier": args.scan_tier,
        "shard": args.shard,
        "scan_set": {
            "pairs_scanned": len(scanned),
            "pairs_scanned_list": [f"{b}/{l}" for b, l in scanned],
            "pairs_skipped": [{"bidder": b, "language": l, "reason": r} for b, l, r in skipped],
            "paths_watched": len(watched_all),
            "paths_watched_by_check": {
                c: sum(1 for w in watched_all if w.check == c)
                for c in sorted({w.check for w in watched_all})},
            "golden_entries_unresolvable": unresolvable_all,
            "upstream_fetches": {
                s.label: s.fetch_count for s in (go_src, java_src) if s is not None},
        },
        "bidder_count": {"go": len(go), "java": len(java)},
        "finding_count": len(findings),
        "findings": [f._asdict() for f in findings],
        "fetch_errors": fetch_errors,
        "source_notes": source_notes,
    }, indent=2))

    md_path.write_text(render_md(findings, args, scan))

    if not args.quiet:
        for note in source_notes:
            sys.stderr.write(f"NOTE: {note}\n")
        if fetch_errors:
            sys.stderr.write("Fetch errors:\n")
            for e in fetch_errors[:40]:
                sys.stderr.write(f"  {e}\n")
            if len(fetch_errors) > 40:
                sys.stderr.write(f"  … {len(fetch_errors) - 40} more\n")
        for f in findings:
            if f.severity != SEVERITY_PASS:
                print(f"[{f.severity.upper()}] {f.bidder} ({f.language}) — {f.type}: {f.message}")
        print()
        print(f"Wrote: {json_path}")
        print(f"Wrote: {md_path}")

    n_fail = sum(1 for f in findings if f.severity == SEVERITY_FAIL)
    n_warn = sum(1 for f in findings if f.severity == SEVERITY_WARN)
    print(f"SCANNED: {len(scanned)} bidder/language pairs, "
          f"{len(watched_all)} upstream paths (tier={args.scan_tier}"
          + (f", shard={args.shard}" if args.shard else "") + ").")
    print(f"OVERALL: {n_fail} fail, {n_warn} warn, {len(findings)} findings total.")

    if not scanned:
        sys.stderr.write(
            "ERROR: the scan set is empty — 0 bidder/language pairs compared. "
            "A zero-input run is an instrument failure, not a clean verdict.\n")
        return 3

    if n_fail > 0:
        return 1
    if n_warn > 0:
        return 1 if args.strict else 2
    if fetch_errors:
        # Network failures alone should not block; report and return warn.
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
