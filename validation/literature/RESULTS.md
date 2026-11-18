# Held-out literature test, round 1: results

480 measured points from 7 sources, sealed 14 November 2026 (SHA-256 237cd910...), predicted by
`predict.py` with the engine of 28cca36 and committed in e28c1d7 before the values were opened.
Unsealed on Michael's go, 16 November 2026, and scored once by `score.py`. The first result is
`score_round1.md`, unchanged. The activity rows are reported corrected beside it
(`score_round1_corrected.md`): the predictor had computed the SiO2 activity for every activity
row, though 158 of them name CaO, AlO1.5 or MgO (RULES.md, "Changes after unsealing"). Errors are
calculated minus measured. Baseline: the same database with the liquid's ternary terms removed.

## Activities (log10, corrected; the first result in brackets)

| System | Points | RMS | Mean | Baseline RMS |
|---|---|---|---|---|
| CaO-Al2O3-SiO2 (Kume; Kang) | 151 | 0.28 (1.33) | +0.13 | 0.41 |
| CaO-MgO-SiO2 face of CaO-FeO-MgO-SiO2 (Kume) | 75 | 0.17 (1.32) | +0.05 | 0.17 |
| CaO-SiO2 (Kume) | 24 | 0.18 (1.49) | +0.13 | 0.18 |
| MgO-SiO2 (Kume) | 4 | 0.09 (0.39) | -0.07 | 0.09 |

By oxide: SiO2 activities RMS 0.03 (CaO-SiO2), 0.06 (CaO-MgO-SiO2), 0.19 (CaO-Al2O3-SiO2);
AlO1.5 0.24; MgO 0.10 to 0.11. CaO activities are high in every system, mean +0.22 to +0.30
(about a factor 1.8), the lime-activity shortfall Table 2 already states for CaO-SiO2. The
CaO-Al2O3-SiO2 ternary terms lower the RMS from 0.41 to 0.28; on the other faces the baseline
equals the database, which has no ternary terms touching those points.

## Temperatures, CaO-FeO-SiO2 face (Bowen, Schairer and Posnjak 1933, iron-saturated)

| Quantity | Points | RMS (K) | Median abs (K) | Mean (K) | Within uncertainty |
|---|---|---|---|---|---|
| Liquidus | 85 | 79 | 69 | +58 | 4% |
| Solidus | 15 | 48 | 35 | -7 | 0% |

Liquidus errors by the reported primary phase: pseudowollastonite +48 K (26 points), wollastonite
solid solution +89 K (20), Ca-Fe olivine +83 K (21), rankinite +90 K (3), Ca2SiO4 +47 K (4),
tridymite -28 K (11). The reported primary phase is calculated at 58% of the liquidus points (not
blind: the conditions name it). This face has no fitted CaO-FeO-SiO2 terms (CaO-FeO is ideal) and
the paper calls it a prediction; the baseline equals the database here. The databases also hold
no Ca in olivine and no Fe in wollastonite, which the measured solid solutions carry.

## Mixing enthalpy, FeO-SiO2 (Ban-ya 1985, 25 points, 1693 K)

RMS 10.2 kJ/mol, mean -10.0: the database is about four times too exothermic (-15 kJ/mol near
25% SiO2 against a measured -3 to -4). Its FeO-SiO2 liquid term is -58.7 kJ + 40.3 T J, a large
enthalpy offset by a large entropy, fitted to activities and the phase diagram with no
calorimetry; it reproduces those data and not the measured heat of mixing.

## Invariant points

None computed. 82 rows (20 invariant temperatures, 62 liquid or solid compositions) name phases
the databases lack (akermanite, monticellite, merwinite-like 5CaO.2MgO.6SiO2, kirschsteinite,
Ca in olivine) or polymorphs they do not distinguish, and are listed as not represented. 16 rows
(3 invariants with their compositions) name phases the database has, but the database holds
another assemblage there; they count as misses.

## Salt

NaCl-KCl-MgCl2 (Wang 2021): solidus 8 K low against the measured onset (baseline 29 K high). The
two Xu 2018 points are excluded (RULES.md).
