# Scenario ontology ↔ Defense OSDK mapping rules

This file defines the comparison labels to be used only **after** the scenario ontology has been independently frozen.

## Direct

One OSDK interface/property/link expresses substantially the same concept and semantics.

## Partial

OSDK contains the core concept, but scope, constraints, properties, or relation semantics are materially incomplete
for the scenario requirement.

## Composite

The scenario concept can be represented only by combining two or more OSDK interfaces/properties/links.

## Gap

No adequate representation was found in the reviewed public Defense OSDK reference.

This means "gap in the reviewed public reference", not "Palantir Gotham cannot represent this".

## Unknown

Public documentation is insufficient or contradictory, so support cannot be determined reliably.

## Required evidence for a mapping

Every mapping row should contain:
- scenario concept / relation / query,
- candidate OSDK `sdk_id`,
- mapping class,
- semantic rationale,
- relevant properties/links,
- source URL(s),
- snapshot date,
- uncertainty / version-drift note if applicable.

## Anti-circularity rule

Do not use Defense OSDK to generate the initial scenario ontology.
Freeze the independently derived scenario ontology first, then open this reference and perform mapping.
