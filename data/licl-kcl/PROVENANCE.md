# LiCl-KCl v0.1 — provenance and limits

First non-oxide system in the open family: the pyroprocessing / thermal-battery
electrolyte. MQMQA liquid (Li+1, K+1 / Cl-1) + the two endmember solids. Built
2026-08-25 from evaluated endmember data and the measured eutectic, with a measured
fusion enthalpy as the third, independently-satisfied target. No value derives from
any prior assessment or commercial database.

## Endmembers (per mole salt)

| | dHf(298) kJ | S298 J/K | Tm K | dHfus kJ | source |
|---|---|---|---|---|---|
| LiCl | -408.358 | 59.287 | 883 | 19.748 | TKV evaluation (workspace Chlorides reference system) |
| KCl | -436.558 | 82.55 | 1044 | 26.317 | TKV evaluation (same) |

Solid Cp: own Maier-Kelley fits (Cp = a + bT + c/T^2) to Barin (1995) points over each
solid's stable range, plus Cp298:
- LiCl (298-800 K): a = 43.6024, b = 2.071321e-2, c = -1.5510e5 (max resid 0.011 J/mol/K)
- KCl (298-1000 K): a = 40.5254, b = 2.498808e-2, c = +2.9839e5 (max resid 0.097 J/mol/K)

Barin's 900+ K (LiCl) and 1200+ K (KCl) points are liquid-phase and were excluded.
The liquid inherits the solid Cp plus the fusion term (the family convention).

## Eutectic adoption (and the INL report's units slip)

Adopted: 626.15 K (353 °C) at x_LiCl = 0.585. Janz (1992, "eutectic 59-41 mol%") and
Solomons (1958, "58 mol% LiCl") agree; the INL 2011 report states "44.3 mol% KCl -
55.7 mol% LiCl", which is inconsistent with the rest of the literature but converts to
the standard 58 mol% LiCl eutectic if its numbers are read as WEIGHT fractions - a
units slip in that report, documented here rather than averaged in.

## Coordination convention (a real finding)

Z = 6 for all ions, the published MQM convention for monovalent molten salts. This is a
deliberate departure from the charge-proportional Z used by the oxide systems in this
family: with charge-proportional Z (Z = 0.689 for +1 ions) the short-range-order entropy
dominates the liquid shape and the eutectic COMPOSITION is pinned near x_KCl = 0.458 for
any cation-mixing excess (temperature fits, composition cannot) - measured is 0.415.
At Z = 6 both fit. write_dat gained the z_per_charge override for this.

## Liquid excess (fitted at Z = 6)

Delta_g(Li,K)/Cl = (-9467.3 + 7.92*T) - 1112.5*chi_Li   J/mol   (two Q-code terms)

Three targets, three parameters, all satisfied (least squares 2026-08-25):

| target | measured | model |
|---|---|---|
| eutectic temperature | 626.15 K | 626.0 K |
| eutectic composition x_KCl | 0.415 | 0.407 |
| eutectic fusion enthalpy (Solomons 1958, p.249) | 13.39 kJ/mol | 13.41 kJ/mol |

The fusion-enthalpy target is drop-calorimetric (Powers & Blalock 1953 measured the same
quantity; Solomons' value is the adopted one) and constrains the mixing enthalpy scale;
the fitted excess is consistent with the known mildly negative LiCl-KCl mixing.

## Validation

- Both solids match pycalphad to machine precision (600 K spot check, this folder's
  scripts).
- The liquid Gibbs energy converges onto pycalphad's sampled minimum as the composition
  bin tightens (-5.4 -> -1.6 J/mol-atom at bin ±1e-4, sampling-limited), 900 K.
- Full engine test suite passes.

## Known limits

- v0.1 is anchored at the eutectic and the endmember meltings; the liquidus SHAPE
  between anchors is a model prediction, not fitted to liquidus data (Powers & Blalock
  and the INL handbook carry diagram figures that could be digitized for a v0.2).
- Solid solubility of LiCl in KCl (a few mol% near the eutectic temperature) is
  neglected; both solids are line compounds here.
- Liquid Cp inherits the solid Cp form (family convention); fine near the anchors,
  progressively cruder far above the liquidus.

Repro: `build_dat.py` (writes LiCl-KCl.dat with the stored excess), `v01_fit.py`
(evaluates; `--fit` re-optimizes all three targets).
