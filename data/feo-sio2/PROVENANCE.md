# FeO-SiO2-liquid.dat provenance

Open FeO-SiO2 liquid-slag MQMQA database, **v0.2 (fitted excess)**. The Fe-side counterpart
of `data/mgo-sio2`, and the second binary the FeO-MgO-SiO2 ternary slag needs (for the
olivine + orthopyroxene + liquid diagram). **Iron-saturated**: all iron is Fe2+ / FeO, no
Fe3+ - matching the iron-crucible conditions of Bowen & Schairer's phase-equilibrium work,
and avoiding redox for now.

Built by `build_dat.py` (endmembers) and `v02_fit.py` (excess); validated by `validate.py`
(endmembers) and `validate_v02.py` (excess). Run:

    C:/Users/busta/miniforge3/envs/calphad/python.exe data/feo-sio2/validate_v02.py

## Pure-oxide liquid endmembers (open)

| Quantity | FeO | SiO2 | Source | Access |
|---|---|---|---|---|
| dHf(298) from elements | -272.044 kJ/mol | -908.4 kJ/mol (cristobalite) | NIST-JANAF (Chase 1998) / R&H 1995 | open |
| S(298), third law | 60.752 J/mol/K | 43.4 J/mol/K | NIST-JANAF / R&H 1995 | open |
| Cp(T) solid, Haas-Fisher a,b,c | 50.663, 8.711e-3, -3.134e5 | 72.75, 1.300e-3, -4.132e6 | fit to JANAF FeO(cr) 298-1500 K (max resid 0.35) / R&H | open |
| Fusion Tm | 1650 K | 1996 K | NIST-JANAF | open |
| Fusion dHfus | 24.058 kJ/mol | 9.581 kJ/mol | NIST-JANAF | open |

The FeO numbers are the NIST-JANAF (Chase 1998) critically-evaluated values for stoichiometric
FeO, already digitized in the assessment workspace
(`assessments/FeO-SiO2/data_tables/paper_nist_janaf__table_JANAF_web_table_Fe-020.csv`); the
Haas-Fisher Cp is a least-squares fit to the six tabulated FeO(crystal) Cp points (298-1500 K).
SiO2 is identical to `data/mgo-sio2` (Robie-Hemingway solid, JANAF fusion). Both endmember Gibbs
energies read back by the engine match a direct H - T*S evaluation to ~1e-7 J/mol, and both
reproduce their fusion temperatures exactly (dG_fus = 0 at Tm).

## v0.2 excess (phase-diagram anchored, MLIP-informed depth)

A symmetric cation-mixing excess on (Fe,Si,O,O), `Delta_g(Fe,Si)/O = a00 + b00*T`
(a10 = 0; no measured activities justify a composition skew), fitted to two anchors
(`v02_fit.py`):

- **fayalite Fe2SiO4 congruent melting = 1478 K** (Bowen & Schairer 1932, digitized in the
  trove, `assessments/FeO-SiO2/.../paper_bowen_schairer1932__table_1__pheq.csv`). The measured,
  decisive anchor: fayalite melts LOW (unlike refractory forsterite at 2163 K), so the liquid
  must be SHALLOW - a deep liquid would melt fayalite far below 1478 K.
- **enthalpy of mixing dH_mix(x=1/3) ~ -9.5 kJ/mol-oxide**, from (a) the compound-stability
  scaling of the MgO-SiO2 v0.2 depth: dH_mix scales with the measured oxide formation enthalpy,
  and fayalite is 0.39x as bound as forsterite (dHf_ox = -23.4 vs -60.25 kJ/mol), so
  -24.5 x 0.39 = -9.5 kJ; and (b) the MLIP over-binding bias-check (`_mlip/mlip_hf.py`):
  MatterSim over-binds fayalite by +8.1 kJ/oxide, so its raw melt-mixing dH is too deep -
  correcting it points the same way (shallow).

Result: `a00 = -96776, b00 = +78.62 J/mol`. The model reproduces fayalite congruent melting
exactly (1478 K), a shallow dH_mix (-9.5/-9.9 kJ at x = 1/3, 1/2), single-welled delta_g_mix
(no spurious gap), and negative-deviation activities (a(FeO), a(SiO2) < 1). Validated in
`validate_v02.py`.

### Honest limits (v0.3 targets)

- The **full liquid MLIP melt-mixing MD** (`_mlip/mlip_mix.py`) was implemented and run, but did
  not converge in practical time on the available CPU (the dense FeO endmember melt was
  pathologically slow). The enthalpy depth is therefore anchored on the dHf_ox scaling + the MLIP
  over-binding bias-check, which the measured congruent melting independently corroborates. A
  converged MLIP MD (faster hardware / GPU) is a v0.3 refinement, as are measured **FeO-SiO2
  activities** to pin the depth and any skew directly:
  - **Schuhmann & Ensio 1951**, JOM 3:401, DOI 10.1007/BF03397323 (iron-saturated a(FeO), a(SiO2)).
  - **Michal & Schuhmann 1952**, JOM 4:723, DOI 10.1007/BF03398131 (silica-saturated).
- The **large positive b00** reflects a calibration offset: the ideal MQMQA liquid melts fayalite
  ~170 K below 1478 K, so a positive excess entropy is needed to raise it. A recalibrated FeO
  liquid endmember (or the measured activities above) would reduce it. The shipped model is
  nonetheless well-behaved (no gap, physical activities).

## What is deliberately excluded

No FactSage/FToxid or optimized-TDB parameters. Bjorkman 1985 and the Shishin/Jak
FeO-Fe2O3-SiO2 assessments are validation targets only, never a parameter source. The FeO
endmember is a JANAF single-substance evaluated value (allowed as an input).
