# FeO-MgO-SiO2-liquid.dat provenance

Open **FeO-MgO-SiO2 ternary** liquid-slag MQMQA database, **v0.1**. The iron-magnesium
silicate melt at the centre of the steel-slag and olivine families, and the liquid the
olivine + orthopyroxene + liquid diagram (vs Bowen & Schairer 1935) needs. **Iron-saturated /
fixed-valence**: Fe is Fe2+ only (no Fe3+), Mg2+, Si4+; a single anion O2-.

Built by `build_dat.py`; validated by `validate.py`. Run:

    C:/Users/busta/miniforge3/envs/calphad/python.exe data/feo-mgo-sio2/validate.py

## Assembly - no new ternary fit

The ternary liquid is assembled entirely from the two shipped binary liquids plus a
near-ideal FeO-MgO edge; every parameter is reused verbatim (single source of truth, checked
by the binary-reduction guard below):

| Edge | Excess on | Source | Terms |
|---|---|---|---|
| MgO-SiO2 | (Mg,Si,O,O) | `data/mgo-sio2` (assessed) | 5 silica-weighted (0,q)=chi_Si^q, q=0,1,3,5,7, each a+bT |
| FeO-SiO2 | (Fe,Si,O,O) | `data/feo-sio2` v0.3 (activity-pinned) | symmetric Delta_g(Fe,Si)/O = -42839.4 + 17.83*T |
| FeO-MgO | (Fe,Mg,O,O) | - | **ideal** (no term) |

- **FeO-MgO is treated as ideal** for v0.1. Molten (Fe,Mg)O is a near-ideal solution of two
  similar divalent oxides (complete miscibility; magnesiowustite, the solid, is itself nearly
  ideal). A small interaction from a dedicated assessment is a documented v0.2 target.
- **Ternary (3-cation) excess = 0** (Muggianu extrapolation from the binaries), the standard
  MQMQA default when no ternary data force a correction.
- The **FeO(l) below-1650 K phase-diagram recalibration** from FeO-SiO2 v0.3 (a second
  temperature interval on the FeO endmember, `beta = -69.84 J/mol/K`) carries over unchanged -
  it is a property of the FeO liquid endmember, so it applies ternary-wide.
- An **MgO(l) below-3098 K liquidus calibration** (`MGO_LIQ_BETA = +2.975 J/mol/K`, a second
  temperature interval on the MgO endmember) is applied here so the liquid melts the measured
  (Robie-Hemingway) forsterite - the olivine CEF endmember, `data/olivine` - congruently at
  2163 K. It is orthogonal to the MgO-SiO2 activities (a pure MgO endmember shift), and is the
  Mg analogue of the FeO(l) treatment: both put the liquid on the same measured olivine
  endmembers the solid solution uses. The shipped MgO-SiO2 *binary* keeps its own assessment
  (its forsterite melts ~2130 K against its co-optimized solid); unifying MgO(l) across the
  binary and the ternary is a documented cleanup. `fit_mgo_beta` in `olivine_join.py`
  reproduces the value.
- Endmembers: FeO (JANAF, with the v0.3 correction), MgO (CODATA/JANAF, `data/mgo-sio2`),
  SiO2 (Robie-Hemingway solid + JANAF fusion, identical in both binaries). Cation indexing in
  the .dat is Fe=1, Mg=2, Si=3; the single anion O=4.

## Validation

Both checks are at the model level (a fixed quadruplet distribution, so they are exact and
independent of any equilibrium solver):

1. **Engine vs pycalphad.** The C engine's ternary molar Gibbs energy matches pycalphad's
   `ModelMQMQA.GM` to **~6e-11 J/mol-atom** over random quadruplet distributions - the
   3-cation .dat is read correctly and the combined excess is assembled exactly.
2. **Reduction to the shipped binaries** (transcription guard). At a binary edge (only the
   Fe-Si quadruplets populated, all Mg quadruplets zero) the ternary gives exactly the
   FeO-SiO2 binary .dat energy (|diff| = 0); the Mg-Si edge matches the MgO-SiO2 binary to
   2e-4 J (that binary stores its endmember coefficients at 8 significant figures; the ternary
   is full precision). A mis-typed excess coefficient would be hundreds of J, far above this.

## 2-D ternary global minimizer (`ternary_diagram.py`, `python/mqmqa/ternary.py`)

The full FeO-MgO-SiO2 equilibrium (liquid + olivine + orthopyroxene + the stoichiometric
oxide solids cristobalite/periclase/wustite) is computed by grid-sampling each phase's Gibbs
energy across the cation simplex and taking the lower convex hull - the standard global
method. Basis: Gibbs per mole of CATIONS with composition = cation fractions (x_Fe, x_Si),
valid because every phase here is fixed-valence and iron-saturated so oxygen is charge-slaved
identically. Each lower-hull facet is a tie-triangle/edge; the assemblage at any bulk
composition is read off the covering facet by barycentric amounts (lever rule).

The liquid surface is sampled directly in quadruplet space (fast, no per-composition
minimization); the liquid hull vertices are then locally minimized to tighten the envelope.
VALIDATION: every phase Gibbs energy is validated separately (liquid vs pycalphad ~1e-10; the
CEF solids in their own tests), and the hull logic is checked against the independently
validated 1-D olivine loop - the 2-D liquid<->olivine tie-line on the x_Si=1/3 section matches
it to ~0.01-0.03 in X_Fe - plus a lever-rule-consistent three-phase tie-triangle and
orthopyroxene appearing in the silica-rich field (`tests/test_ternary_minimizer.py`). A full
end-to-end check against pycalphad `equilibrium` on a combined liquid+solids .dat is the next
validation step (it needs that .dat assembled). NOTE: orthopyroxene phase boundaries inherit
the enstatite solid-reference gap (below), so opx fields are not yet quantitative.

## Honest limits (v0.2 / next targets)

- **FeO-MgO ideal** is a first approximation (see above).
- **Olivine melting loop (`olivine_join.py`).** The Mg2SiO4-Fe2SiO4 join (liquid <-> olivine
  CEF, common tangent along x_SiO2 = 1/3) computed with our own stack now reproduces BOTH
  congruent endpoints - forsterite 2163 K and fayalite 1476 K (measured 2163 / 1478) - after
  the MgO(l) reconciliation above, and its lens shape/width matches Bowen & Schairer. The
  interior liquidus still carries small facets from the few-J ternary liquid-minimizer noise
  (warm-started, polynomial-smoothed multi-start); an exact ternary minimizer / the C
  multiphase hull is the fix. The olivine solid side is exact. The full olivine +
  orthopyroxene + liquid diagram (adding `data/olivine-opx`) follows from the same machinery.
- The engine's general multi-cation **equilibrium solver** (SLSQP) is not accurate enough for
  a phase diagram (the binary work uses an exact 1-D solve for the same reason); an accurate
  ternary minimizer / the C-port of the multiphase hull is an engine-roadmap item. Diagram
  work leans on pycalphad reading this same open .dat until then.

## What is deliberately excluded

No FactSage/FToxid or optimized-TDB parameters. Every number traces to the two open binary
assessments in this repo (themselves literature-only) or to open single-substance evaluated
data (JANAF, CODATA, Robie-Hemingway). Bowen & Schairer 1935 is a validation target only.
