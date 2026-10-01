# Targeting & Fires modeling patterns

## 1. Real-world entity vs targeting task
`Targetable Entity` is the corporeal military-significant asset.
`Target` is a task/attempt to impose an effect on that entity.

Targetable Entity --Targets--> Target

Do not map an enemy weapon/platform directly to `Target` simply because it is "a target" in natural language.

## 2. Target list membership is reified
Recent official pages expose:

Target -- Target List Assignment -- Target List

`Target List Assignment` carries list-specific `Priority`, so it is not equivalent to a plain membership edge.

## 3. Targeting guidance is operation-scoped
`Targeting Operation` extends `Operation` and connects to:
- High Payoff Target List
- Attack Guidance Matrix
- Target Selection Standard Matrix
- Target Engagement Authority
- Targeting Area
- Target / Target List
- Collateral Concern Guidance

## 4. Engagement and assessment are separated
`Engagement` is the executable action after a target is authorized.
Post-action assessment is represented through separate assessment interfaces such as:
- Physical Assessment
- Functional Assessment
- Collateral Damage Assessment
- Munition Effectiveness Assessment
- Serviced Assessment

## 5. Effects and effector employment are modeled separately
Target -> Target Effect Solution -> Effector Employment -> Aimpoint Weapon Employment

This separates:
- desired/intended target effect,
- an effect solution,
- actual effector/weapon employment,
- aimpoint and munition details.

## 6. Version drift must be treated as data
The public Defense OSDK is explicitly mutable. Never silently merge old/new schemas.
Keep SDK id, display name, aliases, page evidence, and capture timestamp separately.
