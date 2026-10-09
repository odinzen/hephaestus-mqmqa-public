# CaO-Al2O3 v0.2 (dry) - provenance and limits

## Scope: dry slags only (2026-10-01)

These files describe the **dry** CaO-Al2O3 system: no water in the melt or the solids.
Ca12Al14O33 (C12A7, mayenite) is therefore not a phase. It is stable only when the solid holds a
little absorbed water (under 1 mass%) and does not form in a dry atmosphere (Nurse, Welch & Majumdar
1965, Trans. Br. Ceram. Soc. 64, 409-418; confirmed by DTA in argon by Jerebtsov & Mikhailov 2001,
Ceram. Int. 27, 25-28, doi:10.1016/S0272-8842(00)00037-7). In the dry system every calcium
aluminate melts peritectically. Water is unlikely in a molten slag, so the dry diagram is the one
that applies to slag practice; the older air measurements (Shepherd, Rankin & Wright 1909; Rankin &
Wright 1915) are used only where they do not involve Ca12Al14O33.

Literature-only open database: MQMQA liquid (components CaO, AlO1.5) + six stoichiometric
solids. Built 2026-08-25 from the paper set gathered for this system (Rankin & Wright 1915;
Coughlin 1956; Bonnickson 1955; Geiger 1988) plus open compilations (CODATA, NIST-JANAF,
Barin 1995, TKV). No value derives from any prior assessment or commercial database.

## v0.2: the dry assessment (shipped 2026-10-07)

The shipped liquid and solids are the dry fit of `assessment/assess.py`, stored in `build_dat.py`
(`ASSESSED_EXCESS`, `DHF_SHIFT`, `HIBONITE_DS_SHIFT`). Six solids: lime, corundum, Ca3Al2O6,
CaAl2O4, CaAl4O7 (Bonnickson 1955 heat contents) and hibonite (oxide sum, Geiger 1988). Fitted in
one weighted least squares to the Jerebtsov & Mikhailov (2001) dry DTA invariants and fusion
heats and the Shepherd, Rankin & Wright (1909) liquidus, each liquidus point scored only where the
liquid is stable. Liquid excess: five terms (a + bT) chi_Ca^p chi_Al^q, (p, q) = (0,0), (1,0),
(0,1), (2,0), (0,2). Cost 1240 (v0.1 liquid on these solids) -> 60.6, RMS residual 0.97.

The fit moves measured solid data, under priors:

| Quantity | Shift | Prior (1 sigma) |
|---|---|---|
| CaAl4O7 enthalpy of formation | +14.07 kJ | 4.7 kJ (Geiger's spread) |
| Ca3Al2O6 enthalpy of formation | -6.76 kJ | 3 kJ |
| CaAl2O4 enthalpy of formation | +1.76 kJ | 3 kJ |
| CaAl12O19 enthalpy of formation | +1.10 kJ | 5 kJ |
| CaAl12O19 entropy of formation | +2.99 J/K (to 27.3) | 15 J/K |

The CaAl4O7 shift is 3.0 sigma and the Ca3Al2O6 shift 2.3 sigma off their calorimetry. No newer
calorimetry exists for either, so the dry phase diagram decides them (Michael, 2026-10-07); the
shifted values are fitted, not measured, and the measured ones stay in `build_dat.py` (`MEASURED`).
The 298 K aqueous database (data/wet-slag) reads the measured values, not the shifted ones.

Re-derived from the shipped file with pycalphad, stable phases only:

| Invariant | Model | Measured (Jerebtsov & Mikhailov 2001) |
|---|---|---|
| CaAl12O19 = Al2O3 + L | 2190 K | 2125 K |
| CaAl4O7 = CaAl12O19 + L | 2048 K | 2035 K |
| CaAl2O4 = CaAl4O7 + L | 1836 K | 1877 K |
| Ca3Al2O6 + CaAl2O4 = L | 1651 K | 1644 K |
| Ca3Al2O6 = CaO + L | 1833 K | 1813 K |

Fusion heats (fit tool): CaAl12O19 606 vs 710 +- 30 kJ, CaAl4O7 176 vs 210 +- 10, CaAl2O4 83 vs
84 +- 10, Ca3Al2O6 166 vs 145 +- 30. Hibonite melts 65 K high and with too small a fusion heat;
CaAl2O4 breaks down 41 K low.

The sections below record v0.1 (Rankin & Wright 1915 invariants, with Ca12Al14O33) for history.

## Endmembers

- **CaO**: dbbuild starter library (dHf/S298 CODATA; Cp Haas-Fisher; Tm 2845 K CRC;
  dHfus 79.5 kJ JANAF/analog). Same endmember as the shipped CaO-SiO2 system.
- **Al2O3 (corundum / AlO1.5 liquid unit)**: dHf -1675.692 kJ/mol (TKV = JANAF = CODATA),
  S298 50.92 (CODATA), Cp Maier-Kelley J-based (Kelley; Cp298 = 79.09 vs Barin sheet 79.038).
  Fusion from the Barin 1995 corundum sheet (= JANAF): Tm 2327 K, dHfus 111.085 kJ/mol.
  The liquid component is AlO1.5 (charge-neutral per-cation unit, half of Al2O3 everywhere).

## Stoichiometric compounds

dHf assembled as sum(CODATA oxide dHf) + measured formation-from-oxides enthalpy. Note
Coughlin's element-basis values embed 1956 oxide enthalpies; his from-oxide values on modern
endmembers land within 0.5 kJ of Barin's element-basis sheets (consistency check, 2026-08-25).

| Compound | dHf_ox (kJ/mol) | source | S298 (J/mol/K) | Cp source |
|---|---|---|---|---|
| Ca3Al2O6 (C3A) | -6.65 | Coughlin 1956 | 205.899 (Barin p.445) | workspace M-K fit to Barin pts (298-1000 K) |
| Ca12Al14O33 (C12A7) | -79.37 | Coughlin 1956 | 1046.837 (Barin) | workspace M-K fit (298-1000 K) |
| CaAl2O4 (CA) | -15.44 | Coughlin 1956 | 114.223 (Barin p.443 sheet) | Bonnickson 1955 drop calorimetry (298-1800 K), cal->J |
| CaAl4O7 (CA2) | -25.6 | Geiger 1988 Eqn (2)/Table 2 | 177.820 (Barin) | workspace M-K fit (298-1000 K) |

CA2 dHf_ox spread: Geiger Eqn (3) alternative -20.9; Barin sheet implies -39.3. The primary
calorimetric determination (-25.6) is adopted. CA6 (hibonite) is NOT in v0.1: no S298 at
298 K in the gathered set (Geiger reports S at 1100 K), and Rankin & Wright did not observe
it; its narrow field near Al2O3 is absent by construction.

## Liquid excess (fitted)

Delta_g(Ca,Al)/O = (-156581.1 + 2.159*T) + 133468.2*chi_Ca  J/mol  (two Q-code terms)

Fitted 2026-08-25 by least squares to six Rankin & Wright (1915) invariants (four eutectic
temperatures + compositions, two congruent meltings), scan pp. 10-12 + Fig. 3, spot-checked
against the rendered scan in the assessment workspace (2026-06-18). A 4-term fit improved
cost only marginally by going unphysical (positive enthalpy, -172 J/K entropy: the
degenerate-valley pattern) and was rejected.

## Reproduction of the fitted targets (v0.1)

| Invariant | measured (R&W) | model | dT |
|---|---|---|---|
| eutectic C3A + C12A7 | 1668 K | 1693 K | +24 |
| C12A7 congruent | 1728 K | 1719 K | -9 |
| eutectic C12A7 + CA | 1673 K | 1715 K | +42 |
| CA congruent | 1873 K | 1794 K | -79 |
| eutectic CA + CA2 | 1863 K | 1796 K | -67 |
| eutectic CA2 + corundum | 1973 K | 2066 K | +93 |

Reported, not fitted: C3A correctly decomposes peritectically below its melting point
(R&W: 1808 K, decomposing to CaO + liquid) — the hull confirms C3A unstable at 1808 K.

## Known limits (read before trusting a number)

- v0.1 reproduces the measured invariants to about ±90 K worst-case: honest for screening
  and teaching, not a quantitative assessment. Liquid activities are unconstrained (the
  Allibert 1981 activity data are paywalled and not yet in the set) — the next data set
  that would tighten this.
- Compound identities follow the modern revision: R&W's "5CaO.3Al2O3" and "3CaO.5Al2O3" are
  fitted as C12A7 and CA2 (nearly coincident compositions); R&W's Al-rich congruent point
  (1993 K at x_AlO1.5 = 0.769) is superseded by the CA2 stoichiometry (x = 0.8) and was not
  used as a hard target.
- Compound Cp fits for C3A/C12A7/CA2 are nominally 298-1000 K and extrapolate above;
  CA (Bonnickson) is measured to 1800 K.
- Validation: engine and pycalphad agree on all six stoichiometric phases to machine
  precision and on the liquid at grid tolerance (2026-08-25, this folder's scripts).

## Hibonite entropy (2026-10-07)

Hibonite's entropy of formation from the oxides has one source, Geiger (1988, Eqn 10): +24.3 J/K at
1100 K from two electrochemical studies; there is no low-temperature calorimetry. The fit moves it
by +3 J/K. Machine-learned phonon calculations gave 42-50 J/K (Orb-v3, MACE-MP-0; branch
`station2-caal-phonons`), but the same potentials miss the measured entropies of CaAl2O4, CaAl4O7
and Ca3Al2O6 (King 1955) by 2, 5-6 and 12-13 J/K. Unvalidated, they cannot settle a dispute with
Geiger's value; only a low-temperature heat capacity measurement of hibonite can.

Repro: `build_dat.py` writes CaO-Al2O3.dat from the stored v0.2 assessment; `assessment/assess.py`
reports it (`--fit` re-optimizes from it). `v01_fit.py` is the v0.1 tool, kept for history.
