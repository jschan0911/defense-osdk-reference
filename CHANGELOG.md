# Changelog

## crawler-v0.2.1 — 2026-10-01

- Hardened parsing against rendering artifacts observed during the first live fixed-point crawl of the Palantir Defense OSDK documentation.
- Prevented next-section heading text such as `OSDK Examples` and `Link constraints` from leaking into inheritance lists.
- Normalized duplicated rendered relationship target labels.
- Added handling for repeated or concatenated `optional` / `required` tokens, including patterns such as `optionaloptional`.
- Preserved semantic qualifiers such as `[DEPRECATED]` while normalizing rendered labels.
- Added regression tests reproducing the malformed DOM patterns observed during the live crawl.
- The first live fixed-point crawl discovered 67 interfaces, including `Materiel` and `Equipment`, which were absent from the 65-record canonical baseline.
- The live crawl also observed updated relationship surfaces, including 8 outgoing links for `Engagement`, 6 for `Organization`, and 4 for `Materiel Type`.
- The 67-interface result has not yet been promoted to the canonical snapshot. Promotion is deferred until a clean v0.2.1 live re-crawl and validation are completed.

## crawler-v0.2 — 2026-10-01

- Replaced root-only interface discovery with fixed-point graph discovery.
- Every fetched interface/overview page is scanned for additional `interfaceTypes/...` URLs.
- Added XML sitemap discovery as an independent catalogue source when available.
- Added per-interface discovery provenance (`root_navigation`, `sitemap`, `domain_overview`, `interface_cross_link`).
- Added `fixed_point_reached` and root/non-root discovery counts to the crawl manifest.
- A crawl that hits `--limit` is now explicitly marked incomplete.
- Fixed UTF-8 decoding when a server omits the HTML charset, preventing corruption of `→` / `↗` parser tokens.
- Added regression tests for the `Materiel` / `Equipment` omission failure mode caused by root-only discovery.

## v1-candidate — 2026-10-01

- Added the initial canonical Defense OSDK reference snapshot.
- Added all 62 interfaces listed in the observed Defense OSDK root navigation.
- Added 3 additional official interface pages observed outside the root navigation:
  `Physical Assessment`, `Target List`, and `Target List Assignment`.
- Established a 65-record normalized canonical baseline.
- Added Sustainment domain coverage.
- Resolved all interface link targets in the normalized reference.
- Resolved outgoing/incoming relationship pair asymmetry in the working snapshot.
- Preserved two external/common inheritance references:
  `Defense Tracked Entity -> Tracked Entity` and
  `Defense Geotemporal Observation -> Geotemporal Observation`.
- Added version-drift handling for naming and deprecation inconsistencies.
