# Normalization rules

## R1. Interface is not an Object Type

Defense OSDK `Interface` records are treated as abstract API shapes that define shared properties and
link constraints. They are not asserted to be the concrete backing Object Types used in a Gotham deployment.

## R2. Canonical identity is `sdk_id`

Display names may change over time. Matching and version tracking use `sdk_id` as the canonical key.

Example:
- older display: `Ammunition Type`
- newer display: `Munition Type`
- stable observed SDK id: `com.palantir.ontology.defense-types.ammunitionType`

Old labels are preserved as aliases where known.

## R3. Declared properties remain declared properties

Properties shown on a child interface are stored in `declared_properties`.
Inherited properties are not copied into the child record.

An effective/inherited view may be computed later, but it must be derived separately.

## R4. Direction is preserved

Outgoing and incoming link constraints are stored separately as documented.
They are not automatically flattened into a single undirected relation.

## R5. Reified relationship patterns are preserved

If OSDK models a relation through an intermediary interface, the intermediary is retained.

Example:
`Unit -> Unit Hierarchy Node Relationship -> Unit`

This must not be simplified to a bare `PARENT_OF` edge in the canonical reference.

## R6. Official text and interpretation are separate

`official_description` stores source-derived description text.
`semantic_summary_ko` is an interpretation aid and must not be presented as Palantir's wording.

## R7. Missing public evidence is not product absence

If a concept cannot be found in the public Defense OSDK reference, record the comparison as `Unknown`
unless the evidence is strong enough to classify it as a public-reference gap.
Do not infer that the deployed Gotham ontology lacks the concept.

## R8. Counterpart evidence is labeled

When a relation is reconstructed from the opposite interface's official incoming/outgoing constraint,
mark its evidence as `counterpart_official_page` rather than `direct_official_page`.
