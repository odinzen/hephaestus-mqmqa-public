# CaO-FeO-MgO-SiO2 oxide liquid (Ca-Fe-Mg-Si slag melt) provenance and limits

The four-oxide silicate melt of the steel-slag / basalt family: a single MQMQA (SUBQ)
liquid over Ca, Fe, Mg, Si and O. It is the melt that crystallizes the ferromagnesian
silicates (olivine, orthopyroxene, clinopyroxene, data/olivine-opx-cpx). Built 2026-08-26.
Nothing quaternary is fitted: the melt is the Muggianu combination of the shipped binary
liquids, and in every binary limit it reduces to the corresponding shipped binary exactly.

## Liquid (SUBQ; Ca+2 / Fe+2 / Mg+2 / Si+4 / O; charge-proportional Z)

Endmembers and excesses are reused verbatim from the shipped binary databases (single
source of truth):

| edge | excess | source |
|---|---|---|
| CaO-SiO2 | Delta_g(Ca,Si)/O = (-189763.5 + 15.706 T) + 57170.8 chi_Ca | CaO-SiO2 v0.3 |
| FeO-SiO2 | Delta_g(Fe,Si)/O = -42839.4 + 17.83 T (symmetric) | FeO-SiO2 v0.3 |
| MgO-SiO2 | assessed 5-term silica-weighted set, (0,q) = chi_Si^q, q = 0,1,3,5,7 | MgO-SiO2 v0.5 |
| CaO-FeO, CaO-MgO, FeO-MgO | **ideal** (no term) | see limits |

Endmember Gibbs energies from the binary builders; FeO and MgO carry their below-melting
liquid recalibrations (the v0.3 FeO(l) interval below 1650 K; the MgO(l) interval fit so
MgO-SiO2 melts forsterite congruently at 2163 K). CaO (Tm 2845 K) and SiO2 (cristobalite,
identical across all three binaries) are the plain fusion liquids.

## Validation

- **Exact binary-limit reduction.** In each two-oxide limit the quaternary liquid Gibbs
  energy equals the shipped binary's, checked with the engine's exact 1-D binary solver:
  CaO-SiO2 within 0.001 J/formula, FeO-SiO2 and MgO-SiO2 to 0.0000 J/formula, at
  x_SiO2 = 0.3/0.5/0.7, 1800 K. The excess terms are the binaries' own, only re-indexed;
  the basic edges carry no term, so they mix ideally by construction.
- **pycalphad reads the quaternary** (one liquid phase over Ca-Fe-Mg-Si-O).
- The C engine's own 4-cation equilibrium minimizer is slightly looser than pycalphad's
  global solver at interior compositions (< ~10 J/mol-atom at 2000 K), so **pycalphad is
  the reference for multicomponent equilibria**, as elsewhere in the project.

## Known limits

- **No ternary or quaternary term** (Muggianu extrapolation). The three silica binaries are
  assessed; the interior of the quaternary is a prediction. Ternary MQMX terms (the CaO-SiO2
  + Mg / + Fe kind, as in CaO-Al2O3-SiO2) are the v0.2 refinement if open ternary slag data
  are digitized.
- **The basic edges (CaO-FeO, CaO-MgO, FeO-MgO) are ideal.** All three are near-ideal
  mixtures of divalent oxides (complete miscibility); small assessed interactions (CaO-FeO
  and CaO-MgO have modest positive excesses in full assessments) are a documented v0.2
  target, orthogonal to the silica-side excesses.
- **Liquid only.** This file has no solid phases; it computes the melt itself. Coexisting it
  with the ferromagnesian silicates (data/olivine-opx-cpx) into one file is the multiphase
  melting/crystallization step beyond this assembly.
- **Engine multicomponent solver.** The absolute quaternary equilibrium is taken from
  pycalphad; the engine's own 4-cation minimizer is documented as looser (a solver, not a
  model, gap: the .dat reduces to the binaries exactly).

## Sources

The four binary PROVENANCE files (data/cao-sio2, data/feo-sio2, data/mgo-sio2, and the
data/feo-mgo-sio2 ternary) carry every citation and fitted parameter; nothing new is
introduced here.

Repro: `build_dat.py` (writes CaO-FeO-MgO-SiO2-liquid.dat from the shipped binaries),
`validate.py` (binary-limit reductions + the pycalphad comparison).
