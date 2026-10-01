# Version-drift policy

Defense OSDK public documentation changes over time. The repository therefore treats documentation drift
as data rather than as an error to be silently corrected.

## Rules

1. Keep `sdk_id` stable when only a display name changes.
2. Preserve old names in `aliases`.
3. Do not merge contradictory schemas without evidence that they are simultaneous/current.
4. Store deprecation status explicitly.
5. Record root-navigation membership separately from existence of an official interface page.
6. Prefer a single-timestamp crawl for any release designated as canonical.
7. If two official pages disagree, keep the discrepancy in validation/version-drift notes.

## Known 2026-10-01 cases

- `Change Assessment` is deprecated in favor of `Physical Assessment`.
- `Target Assessment` / `Serviced Assessment` show naming/schema drift for the same observed SDK id.
- `Ammunition Type` / `Munition Type` show display-name drift.
- `Target List`, `Target List Assignment`, and `Physical Assessment` were observed as official pages even
  though they were not present in the root-navigation snapshot used during this work.
