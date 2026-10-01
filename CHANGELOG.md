# Changelog

## crawler-v0.2 — 2026-10-01

- Replaced root-only interface discovery with fixed-point graph discovery.
- Every fetched interface/overview page is scanned for additional `interfaceTypes/...` URLs.
- Added XML sitemap discovery as an independent catalogue source.
- Added per-interface discovery provenance (`root_navigation`, `sitemap`, `domain_overview`, `interface_cross_link`).
- Added `fixed_point_reached` and root/non-root discovery counts to the crawl manifest.
- A crawl that hits `--limit` is now explicitly marked incomplete.
- Fixed UTF-8 decoding when a server omits the HTML charset, preventing corruption of `→` / `↗` parser tokens.
- Added regression tests for the exact `Materiel` / `Equipment` omission failure mode.

## v1-candidate — 2026-10-01

- Added all 62 interfaces listed in the observed Defense OSDK root navigation.
- Added 3 additional official interface pages observed outside the root navigation:
  `Physical Assessment`, `Target List`, `Target List Assignment`.
- Added Sustainment domain.
- Resolved all interface link targets in the normalized reference.
- Resolved outgoing/incoming pair asymmetry in the working snapshot.
- Preserved two external/common inheritance references:
  `Defense Tracked Entity -> Tracked Entity`,
  `Defense Geotemporal Observation -> Geotemporal Observation`.
- Added version-drift handling for naming/deprecation inconsistencies.
