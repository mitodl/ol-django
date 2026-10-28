# mitol-dependency-floors

Checks that a repository's manifests and lockfile actually enforce the
dependency version floors it declares.

A **floor** is a minimum version of a dependency that has to hold, usually
because everything below it is vulnerable. Setting one is easy. Keeping it
correct as the dependency graph moves underneath you is the hard part, and it
fails quietly:

- A resolver cooldown (uv's `exclude-newer`, Renovate's `minimumReleaseAge`,
  npm's `min-release-age`) applies to every package with no carve-out for
  security releases, so an upgrade run can resolve *back under* a floor and
  nothing fails.
- A library that declares a floor in `[tool.uv] constraint-dependencies` rather
  than `[project] dependencies` publishes nothing. Constraints steer that
  repository's own resolution and never reach a consumer, so the floor looks
  set and propagates nothing.
- A package that gains the floored dependency *indirectly* — because something
  it already depends on added it — needs a floor it never had, and no
  vulnerability scanner will say so, because the version being resolved is
  fine. The published metadata is what is wrong.

This tool checks the thing a vulnerability scanner cannot see: whether the
floors you declared are the floors your packages actually publish.

It is not a vulnerability scanner, and does not replace one. Use
[osv-scanner](https://google.github.io/osv-scanner/) or
[pip-audit](https://pypi.org/project/pip-audit/) to find out *that* you need a
floor. Use this to make sure the floor sticks.

## Installation

```bash
uvx mitol-dependency-floors check     # no install
pip install mitol-dependency-floors
```

## Usage

```bash
dependency-floors check               # exit 0 clean, 1 violations, 2 bad config
dependency-floors check --format json
dependency-floors explain certifi     # why each package is classified as it is
```

`dependency-floors` and `mitol-dependency-floors` are the same command. The
long form exists so `uvx mitol-dependency-floors` resolves without `--from`;
use the short one in CI and hooks.

## Configuration

Everything lives in `[tool.dependency-floors]` in the repository's own
`pyproject.toml`.

```toml
[tool.dependency-floors.options]
lock = "uv.lock"                 # default
members = "src/*"                # omit for an application; see "Two modes"
exclude = ["src/testonly"]

[tool.dependency-floors.floors.certifi]
specifier = ">=2026.10.19"
reason = "eMudhra CA compromise"
advisory = "https://github.com/advisories/GHSA-6q48-6c7w-9gw2"
```

`specifier` has to place a lower bound on the version; a floor that does not
bound anything is a configuration error rather than a rule that always passes.

## Two modes

### Any repository

With no `members` set, two rules apply. This is the whole of what an
application needs, and it needs no workspace and nothing published.

| Check | |
|---|---|
| `lock-below-floor` | Every floored package the lockfile resolved satisfies its floor. This is the cooldown guard: a silent downgrade becomes a red build. |
| `constraint-below-floor` | Where a resolver constraint exists for a floored package, it is at least as strict as the floor, so the lockfile guard cannot drift away from it. |

`constraint-below-floor` only fires where a constraint is already present. A
constraint is **not** checked for *instead of* a declared dependency, because
an application publishes no metadata and so has nothing to propagate —
constraint-only is the correct shape there.

### A repository that publishes packages

Setting `members` to a glob of package directories (or `"."` for a
single-package repository) turns on the publishing rules. For each member, and
for the base install and each extra separately, exactly one of:

| Check | |
|---|---|
| `floor-not-declared` | The member reaches the floored package through its *own* non-workspace dependencies, so it must declare the floor itself. |
| `inherited-floor-unpinned` | The member reaches it only through a sibling in the same workspace, so it must require that sibling at a version which carries the floor. |
| `floor-declared-redundantly` | The member declares a floor it already inherits from a sibling. |
| `floor-not-needed` | The member does not reach the floored package at all, so it must not declare it. This is what sheds a floor once it stops being needed. |

```toml
[tool.dependency-floors.floors.certifi.workspace]
policy = "entry-point"
providers = { my-core-package = "2026.10.28" }
```

`providers` records the first released version of a sibling that declares the
floor. Recording it is what makes inheritance sound: a sibling dependency
declared without a lower bound can be satisfied by an old release that predates
the floor, so the floor does not actually hold.

Set `policy = "closure"` instead to drop the distinction: every member whose
dependency graph reaches the floored package declares the floor directly, and
`providers` is not used. That is simpler to explain at the cost of a
declaration in packages that would have inherited one.

## How reachability is decided

The lockfile is the source of truth. `dependencies` and every group under
`optional-dependencies` become graph edges; `dev-dependencies` deliberately do
not, since those describe what the repository needs to test itself rather than
what a consumer would resolve.

Three decisions all err toward *over*-reporting reachability, because the cost
of that is a floor declared where it was not strictly needed, while the cost of
under-reporting is a floor silently missing:

- Environment markers are ignored. An edge that only exists on one platform is
  still an edge a consumer can resolve.
- Where a lock carries more than one version of a package, their edges are
  unioned under one node.
- A requirement absent from the lock is treated as unreachable, which is how a
  marker-excluded dependency reads.

A requirement on the floored package *itself* is excluded when searching, so
that declaring a floor is not what makes the floor appear reachable.

That exclusion has one consequence worth knowing: a package that uses the
floored dependency **directly** — it imports it — reaches it through nothing
else, so `floor-not-needed` would otherwise tell it to drop a declaration it
genuinely needs. List those packages and they are held to the floor without the
reachability test:

```toml
[tool.dependency-floors.floors.certifi]
specifier = ">=2026.10.19"
direct = ["my-tls-helper"]
```

The check reads the lockfile as given. Run it where the lock is known to be
current — behind `uv lock --check` or equivalent — or it will describe a
resolution that no longer exists.

## As a pre-commit hook

```yaml
- repo: https://github.com/mitodl/ol-django
  rev: <tag>
  hooks:
  - id: dependency-floors
```

## Limitations

- `uv.lock` is the only lockfile format read today.
- `>` is treated as bounding at its own version, so `>1.0` is reported as not
  meeting a `>=1.0.1` floor even if no release sits between the two.
- Extras of *third-party* packages that this repository's own resolution never
  activates are not in the lock, so a floor reachable only through one of them
  is not seen.
