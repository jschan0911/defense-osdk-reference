# Defense OSDK Reference

Unofficial, versioned research reference for the public Palantir Defense OSDK API.

The purpose of this repository is not to reproduce a deployed Gotham ontology. It is to create a traceable reference
that can later be compared with an independently derived defense-scenario ontology.

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

## Validate the baseline

```bash
make validate
```

or:

```bash
python3 tools/validate_reference.py   data/snapshots/2026-10-01/normalized/defense_osdk_reference.json
```

## Run a new crawl

Full:

```bash
make crawl
```

Common + Order of Battle pilot:

```bash
make crawl-oob
```

Crawler output is written under `out/` and is ignored by Git by default.

## Evidence model

The reference intentionally separates:

- source-derived official description,
- declared properties,
- inheritance,
- outgoing/incoming link constraints,
- analyst-authored Korean semantic summary,
- version-drift notes.

The canonical matching key is `sdk_id`, not the display name.

## Important limitation

The `2026-10-01` baseline is a hybrid verified reference assembled from official Palantir pages and consistency checks.
It was not produced by a single network-enabled end-to-end crawl in this execution environment. A later release should
prefer a one-session crawl and preserve page hashes.

## Public-repository caution

This repository is best kept private until third-party documentation reuse is reviewed. Raw HTML is excluded by default.
See `THIRD_PARTY_NOTICE.md`.
