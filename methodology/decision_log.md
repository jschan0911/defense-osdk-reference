# Decision log

## D-001 — Use Defense OSDK as a reference model, not as the initial ontology generator

Reason: the research goal is to measure how much of an independently derived scenario ontology is covered by OSDK.
Looking at OSDK during initial derivation would contaminate the comparison.

## D-002 — Preserve interfaces, properties, inheritance, and link constraints separately

Reason: name-only matching is insufficient. Coverage must be judged from semantics and graph structure.

## D-003 — Use `sdk_id` as the canonical key

Reason: display names have changed across public documentation versions.

## D-004 — Preserve reified relationship interfaces

Reason: OSDK frequently models relationship semantics, temporal validity, or relationship-specific properties through
intermediary interfaces.

## D-005 — Distinguish `Gap` from `Unknown`

Reason: absence from public Defense OSDK documentation is not proof of absence from a deployed Gotham ontology.

## D-006 — Track root-navigation membership separately from official page existence

Reason: current official interface pages were observed that were not listed in the root navigation snapshot.
