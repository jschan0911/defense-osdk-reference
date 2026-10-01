# Collection method

## Goal

Build a reproducible reference snapshot of the public Palantir Defense OSDK API so that a separately
derived scenario ontology can later be compared against it.

## Collection boundary

The crawler starts at the official Defense OSDK API root and accepts only URLs matching:

`.../docs/defense-osdk/api/<domain>/interfaceTypes/<interface>`

It does **not** assume that the root/sidebar is a complete catalogue. Discovery uses three bounded sources:

1. root/sidebar interface links,
2. the site's XML sitemap,
3. interface links found on domain-overview and interface pages.

Discovered interface pages are followed until the SDK-ID set reaches a fixed point. The crawler still does not recursively crawl unrelated Palantir documentation.

## Raw vs normalized

The intended pipeline is:

1. Capture the API root and interface pages.
2. Preserve the raw source snapshot.
3. Parse interface identity, official description, declared properties, inheritance, outgoing link constraints,
   and incoming link constraints.
4. Normalize those fields into JSON/CSV.
5. Run integrity checks.
6. Add interpretation only in separate fields/documents.

Parser output must never overwrite the raw source snapshot.

## Current baseline provenance

The `2026-10-01` baseline in this repository is a **hybrid verified reference**:
- official Palantir Defense OSDK pages were inspected,
- the schema was normalized into the repository format,
- cross-interface consistency was checked,
- but this execution environment could not perform a single network-enabled end-to-end crawl.

Therefore this baseline should be treated as a verified working snapshot, not as an official schema export.

## Refresh policy

For a future refresh, prefer one network-enabled crawl session and record:
- retrieval timestamp,
- root catalog count,
- page URL,
- source hash,
- parser version,
- validation result.

Do not silently mix pages fetched on materially different dates.
