# Held-out literature test, round1: scores

Errors are calculated minus measured: K for temperatures, log10 units for activities, kJ/mol for enthalpies, absolute fractions for compositions. Phase identity is not blind (RULES.md).

## hephaestus

| System, quantity | n | RMS | median abs | mean | within unc. |
|---|---|---|---|---|---|
| CaO-Al2O3-SiO2 | activity | 151 | 1.334 | 0.4203 | 0.5634 |  |
| CaO-FeO-MgO-SiO2 (CaO-FeO-SiO2 face, iron-saturated) | liquidus_T | 85 | 79.07 | 69.08 | 57.69 | 0.04 |
| CaO-FeO-MgO-SiO2 (CaO-FeO-SiO2 face, iron-saturated) | solidus_T | 15 | 47.95 | 35.47 | -6.863 | 0.00 |
| CaO-FeO-MgO-SiO2 (CaO-MgO-SiO2 face) | activity | 75 | 1.32 | 0.38 | 0.7312 |  |
| CaO-SiO2 | activity | 24 | 1.488 | 0.4834 | 0.9953 |  |
| FeO-SiO2 | enthalpy_of_mixing | 25 | 10.21 | 10.7 | -9.962 |  |
| MgO-SiO2 | activity | 4 | 0.3852 | 0.2643 | 0.2425 |  |
| NaCl-KCl-MgCl2 | solidus_T | 1 | 8.135 | 8.135 | -8.135 | 0.00 |

Classes of every point:

- CaO-Al2O3-SiO2 | activity: 151 computed
- CaO-FeO-MgO-SiO2 (CaO-FeO-SiO2 face, iron-saturated) | coexisting_solid_composition: 8 not_represented, 4 wrong_assemblage
- CaO-FeO-MgO-SiO2 (CaO-FeO-SiO2 face, iron-saturated) | invariant_T: 8 not_represented, 3 wrong_assemblage
- CaO-FeO-MgO-SiO2 (CaO-FeO-SiO2 face, iron-saturated) | invariant_liquid_composition: 18 not_represented, 9 wrong_assemblage
- CaO-FeO-MgO-SiO2 (CaO-FeO-SiO2 face, iron-saturated) | liquidus_T: 85 computed
- CaO-FeO-MgO-SiO2 (CaO-FeO-SiO2 face, iron-saturated) | solidus_T: 15 computed
- CaO-FeO-MgO-SiO2 (CaO-MgO-SiO2 face) | activity: 75 computed
- CaO-FeO-MgO-SiO2 (CaO-MgO-SiO2 face) | invariant_T: 12 not_represented
- CaO-FeO-MgO-SiO2 (CaO-MgO-SiO2 face) | invariant_liquid_composition: 36 not_represented
- CaO-SiO2 | activity: 24 computed
- FeO-SiO2 | enthalpy_of_mixing: 25 computed
- MgO-SiO2 | activity: 4 computed
- NaCl-KCl-MgCl2 | solidus_T: 1 computed, 2 excluded

Primary phase as reported (not blind): 0.5764705882352941

## baseline

| System, quantity | n | RMS | median abs | mean | within unc. |
|---|---|---|---|---|---|
| CaO-Al2O3-SiO2 | activity | 151 | 1.424 | 0.5137 | 0.7532 |  |
| CaO-FeO-MgO-SiO2 (CaO-FeO-SiO2 face, iron-saturated) | liquidus_T | 85 | 79.07 | 69.08 | 57.69 | 0.04 |
| CaO-FeO-MgO-SiO2 (CaO-FeO-SiO2 face, iron-saturated) | solidus_T | 15 | 47.95 | 35.47 | -6.863 | 0.00 |
| CaO-FeO-MgO-SiO2 (CaO-MgO-SiO2 face) | activity | 75 | 1.32 | 0.3785 | 0.732 |  |
| CaO-SiO2 | activity | 24 | 1.488 | 0.4834 | 0.9953 |  |
| FeO-SiO2 | enthalpy_of_mixing | 25 | 10.21 | 10.7 | -9.962 |  |
| MgO-SiO2 | activity | 4 | 0.3852 | 0.2643 | 0.2425 |  |
| NaCl-KCl-MgCl2 | solidus_T | 1 | 28.88 | 28.88 | 28.88 | 0.00 |

Classes of every point:

- CaO-Al2O3-SiO2 | activity: 151 computed
- CaO-FeO-MgO-SiO2 (CaO-FeO-SiO2 face, iron-saturated) | coexisting_solid_composition: 8 not_represented, 4 wrong_assemblage
- CaO-FeO-MgO-SiO2 (CaO-FeO-SiO2 face, iron-saturated) | invariant_T: 8 not_represented, 3 wrong_assemblage
- CaO-FeO-MgO-SiO2 (CaO-FeO-SiO2 face, iron-saturated) | invariant_liquid_composition: 18 not_represented, 9 wrong_assemblage
- CaO-FeO-MgO-SiO2 (CaO-FeO-SiO2 face, iron-saturated) | liquidus_T: 85 computed
- CaO-FeO-MgO-SiO2 (CaO-FeO-SiO2 face, iron-saturated) | solidus_T: 15 computed
- CaO-FeO-MgO-SiO2 (CaO-MgO-SiO2 face) | activity: 75 computed
- CaO-FeO-MgO-SiO2 (CaO-MgO-SiO2 face) | invariant_T: 12 not_represented
- CaO-FeO-MgO-SiO2 (CaO-MgO-SiO2 face) | invariant_liquid_composition: 36 not_represented
- CaO-SiO2 | activity: 24 computed
- FeO-SiO2 | enthalpy_of_mixing: 25 computed
- MgO-SiO2 | activity: 4 computed
- NaCl-KCl-MgCl2 | solidus_T: 1 computed, 2 excluded

Primary phase as reported (not blind): 0.5764705882352941

