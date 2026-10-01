# Defense OSDK Reference

Unofficial, versioned research reference for the public Palantir Defense OSDK API.

The purpose of this repository is not to reproduce a deployed Gotham ontology. It is to create a traceable reference that can later be compared with an independently derived defense-scenario ontology.

## Why this repository exists

The planned experiment is:

```text
Defense scenario
  -> problem definition
  -> KQ / CQ
  -> required concepts and relations
  -> independent scenario ontology
  -> freeze/tag
  -> compare with Defense OSDK reference
  -> Direct / Partial / Composite / Gap / Unknown
```

The Defense OSDK reference is therefore versioned before scenario mapping begins.

## Current baseline

Snapshot date: **2026-10-01**

The current canonical baseline remains the original verified snapshot:

- 6 Defense OSDK domains
- 62 / 62 interfaces from the observed root navigation
- 3 additional retrievable official interface pages kept separately
- 65 normalized interface records total
- 0 duplicate SDK IDs
- 0 unresolved interface link targets
- 0 unresolved Defense-OSDK inheritance references
- 2 explicit external/common parent-interface references

See:

- `data/snapshots/2026-10-01/validation/VALIDATION.md`
- `methodology/normalization_rules.md`
- `methodology/version_drift_policy.md`

## Latest live crawl observation

A first live fixed-point crawl with crawler v0.2 discovered **67 interfaces**.

Compared with the 65-record canonical baseline, the live crawl additionally surfaced:

- `Materiel`
- `Equipment`

The live crawl also observed the updated relationship surface, including:

- `Engagement` with 8 outgoing link constraints
- `Organization` with 6 outgoing link constraints
- `Materiel Type` with 4 outgoing link constraints
- `Materiel` with links to `Materiel Type` and `Organization`
- `Equipment` extending `Materiel Type`

The same crawl exposed DOM-rendering artifacts in inheritance and link parsing, including:

- duplicated relationship target labels
- repeated or concatenated `optional` / `required` tokens
- next-section heading text leaking into inheritance lists

These parser defects are addressed in crawler v0.2.1 and covered by regression tests based on the malformed patterns observed during the live crawl.

The 67-interface observation has **not yet been promoted to the canonical snapshot**. A clean live re-crawl with v0.2.1 must be completed and validated first.

## Repository structure

```text
defense-osdk-reference/
├── README.md
├── CHANGELOG.md
├── THIRD_PARTY_NOTICE.md
├── requirements.txt
├── Makefile
├── tools/
│   ├── crawl_defense_osdk.py
│   └── validate_reference.py
├── tests/
│   └── test_crawler_discovery.py
├── methodology/
│   ├── collection_method.md
│   ├── normalization_rules.md
│   ├── version_drift_policy.md
│   ├── mapping_rules.md
│   ├── provenance_policy.md
│   └── decision_log.md
├── docs/
│   └── modeling_patterns.md
└── data/
    └── snapshots/
        └── 2026-10-01/
            ├── manifest.json
            ├── normalized/
            │   ├── defense_osdk_reference.json
            │   ├── interfaces_catalog.csv
            │   ├── relations.csv
            │   └── inheritance.csv
            ├── validation/
            │   ├── validation_report.json
            │   ├── VALIDATION.md
            │   └── version_drift.json
            └── raw/
                └── .gitkeep
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Crawler v0.2 / v0.2.1 strategy

Crawler v0.2 no longer treats the root navigation as an authoritative complete catalogue.

Discovery combines:

- root-navigation interface links
- the XML sitemap when available
- links found on Defense OSDK overview pages
- cross-links found on individual interface pages

The crawler continues discovery until no new interface `sdk_id` is found.

This fixed-point approach was introduced after the original root-only collection method failed to discover interfaces such as `Materiel` and `Equipment`.

Crawler v0.2 also records discovery provenance, including whether an interface was observed through:

- `root_navigation`
- `sitemap`
- `domain_overview`
- `interface_cross_link`

A crawl that hits a configured interface limit is explicitly marked incomplete rather than being treated as a complete snapshot.

### Parser hardening in v0.2.1

Crawler v0.2.1 retains the fixed-point discovery strategy and hardens parsing against live Palantir documentation DOM rendering artifacts.

The parser now handles:

- section-heading leakage into inheritance lists
- duplicated rendered interface or relationship target labels
- repeated `optional` / `required` tokens
- concatenated tokens such as `optionaloptional`
- semantic qualifiers such as `[DEPRECATED]` without stripping them from stored labels

Regression tests reproduce the malformed patterns observed during the first 67-interface live crawl.

Run the regression suite:

```bash
make test
```

A successful full crawl should report:

```text
fixed_point_reached: true
```

The crawl manifest also distinguishes root-discovered, sitemap-only, cross-link-only, and other non-root interfaces.

## Validate the baseline

```bash
make validate
```

or:

```bash
python3 tools/validate_reference.py \
  data/snapshots/2026-10-01/normalized/defense_osdk_reference.json
```

The baseline validator checks structural consistency of the stored reference. Structural consistency alone does not prove that the public Defense OSDK catalogue has been exhaustively collected, which is why discovery completeness is handled separately by the crawler.

## Run a new crawl

Full crawl:

```bash
make crawl
```

Common + Order of Battle pilot:

```bash
make crawl-oob
```

Or run the crawler directly:

```bash
python3 tools/crawl_defense_osdk.py \
  --out out/full
```

Crawler output is written under `out/` and is ignored by Git by default.

A live crawl should be reviewed before being promoted into `data/snapshots/`.

## Evidence model

The reference intentionally separates:

- source-derived official descriptions
- declared properties
- inheritance
- outgoing link constraints
- incoming link constraints
- analyst-authored semantic interpretation
- discovery provenance
- source page hashes
- version-drift notes

The canonical matching key is `sdk_id`, not the display name.

Interface display names may change across documentation versions while the underlying SDK identifier remains stable.

## Version drift

Palantir Defense OSDK documentation can change over time and may expose naming or catalogue differences across pages or deployment/cache states.

Observed examples include:

- deprecated interfaces replaced by newer assessment interfaces
- display-name changes while preserving the same SDK identifier
- terminology changes such as ammunition / munition naming
- relationship additions becoming visible on newer page versions
- interfaces becoming visible in navigation after previously being accessible only through direct pages or cross-links

For this reason, documentation visibility and sidebar membership should be treated as observations tied to a capture time and source rather than as timeless properties of the ontology.

See:

- `methodology/version_drift_policy.md`
- `data/snapshots/2026-10-01/validation/version_drift.json`

## Important modeling notes

Defense OSDK interfaces are treated as abstract API shapes exposed by the public documentation.

They should not automatically be interpreted as:

- directly instantiable ontology object types
- physical database tables
- evidence of a customer's complete deployed Gotham ontology

Relationship and inheritance comparisons should therefore be semantic rather than based only on display-name equality.

For later scenario-to-OSDK comparison, the intended mapping categories are:

- `Direct`
- `Partial`
- `Composite`
- `Gap`
- `Unknown`

A concept not observed in the public documentation should be recorded as a gap in the **public reference**, not as proof that the capability does not exist in deployed Palantir systems.

## Important limitation

The current `2026-10-01` 65-record canonical baseline is a hybrid verified reference assembled from official Palantir pages and consistency checks.

It was not produced by a single network-enabled end-to-end crawl in the original execution environment.

A later live crawl with crawler v0.2 discovered 67 interfaces, but that first run also exposed parser artifacts. Those parser issues were addressed in v0.2.1.

The canonical baseline should therefore remain at 65 records until a clean v0.2.1 live crawl is completed, validated, compared against the existing baseline, and explicitly promoted as a new snapshot.

A fixed point means that no new interface was found from the discovery sources visited during that crawl. It does **not**, by itself, prove that no unlinked or otherwise undiscoverable public interface exists.

## Public-repository caution

This repository contains an independently normalized research reference derived from publicly accessible Palantir documentation.

Raw HTML capture is excluded from version control by default.

Third-party documentation content, licensing, and redistribution constraints should be reviewed before expanding the amount of source-derived material stored in the public repository.

See:

- `THIRD_PARTY_NOTICE.md`
```
