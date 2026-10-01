# Provenance policy

The repository should make it possible to answer:

1. Which public source page supported this record?
2. When was it observed?
3. Was the field read directly, derived from a counterpart relation, or interpreted?
4. What normalization rule was applied?
5. Which repository version was used for a later scenario comparison?

## Evidence categories

- `direct_official_page`: read directly from the interface page.
- `counterpart_official_page`: inferred from the opposite side of an official link constraint.
- `verified_recent_index_not_root_sidebar`: an official interface page was observed outside the root navigation snapshot.
- interpretation fields such as `semantic_summary_ko`: analyst-authored, not official text.

## Release discipline

Before starting scenario mapping:
- commit the reference snapshot,
- create a Git tag,
- do not rewrite that tag,
- perform scenario ontology derivation in later commits,
- create a second tag when the independent scenario ontology is frozen,
- only then begin OSDK mapping.
