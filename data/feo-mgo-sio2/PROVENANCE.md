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
orthopyroxene appearing in the silica-rich field (`tests/test_ternary_minimizer.py`).

**End-to-end validation vs pycalphad (`build_combined_dat.py`, `validate_combined.py`,
`tests/test_ternary_combined_vs_pycalphad.py`).** `build_combined_dat.py` assembles ONE
ChemSage .dat holding every phase - the liquid SUBQ and the olivine/opx SUBL blocks spliced
verbatim from the shipped .dat files, plus three stoichiometric oxide blocks (cristobalite,
periclase, wustite) generated from the same solid Gibbs coefficients the minimizer uses (Gibbs
eq. type 1; they reproduce our `_solid_oxide_g` to ~1e-7 J/formula). pycalphad runs a full
multi-phase `equilibrium` on that file and the minimizer runs on the same model (with
the full model on both sides, since the opx enstatite correction is embedded in the .dat
adjustment absent from the .dat). Across bulk compositions at 1600/1700 K the stable phase SET
agrees 15/16 and the equilibrium Gibbs energy GM to 0-10 J/mol-atom at almost every point
(worst 73 J at one liquidus-boundary sliver); solid-solution and stoichiometric-phase cation
compositions agree to ~0.001-0.01. The soft liquid tie-line endpoints (a nearly flat liquid
surface) match to ~0.03-0.04, the 2-D minimizer's documented sampling-resolution limit - the
energy GM is well conditioned there, the lateral endpoint is not. The one phase-set miss is a
thin spurious opx at a liquid/liquid+opx boundary (our sampled hull sits 73 J above the true
minimum there); it is a boundary-resolution artifact, not a solver error. This closes the
end-to-end validation gap: our hull equilibrium reproduces pycalphad's independent global
minimization on the same model.

## Liquidus projection + enstatite reconciliation (`ternary_diagram.py`)

`liquidus_projection` sweeps temperature with the 2-D minimizer, records each bulk
composition's liquidus temperature and primary crystallizing phase, and draws the
primary-phase fields with liquidus isotherms on the cation ternary (Bowen-Schairer
orientation: SiO2 apex, MgO left, FeO right). It reproduces the topology of Bowen & Schairer
1935 Fig. 6 - olivine, orthopyroxene, cristobalite, periclase and wustite primary fields with
fusion surfaces sloping toward the FeO-SiO2 side.

**Enstatite high-T entropy correction (18.014 J/mol/K, now a second Gibbs interval in the opx database).** The Robie-Hemingway
opx Cp is fitted only to ~1000 K and extrapolated flat (dCp = 0) above it, which leaves
enstatite too stable near 1830-2000 K and put the forsterite + liquid -> enstatite peritectic
~236 K high (2066 vs measured 1830 K). A high-T entropy correction dG = ENSTATITE_B*(T - 1000)
on the enstatite (Mg2Si2O6) endmember, fit so the peritectic lands at 1830 K
(`fit_enstatite_b`), reconciles that extrapolation with the measured MgO-SiO2 diagram; it is
applied only to the ternary opx sampling and leaves olivine/forsterite/fayalite untouched.
This is a first-order correction to an acknowledged Cp extrapolation, NOT a full enstatite Cp
re-assessment (the rigorous version, fitting the opx Cp/S to multiple constraints, remains a
target).

## Bowen-Schairer Fig. 6 registered overlay (`bs_comparison.py`)

A direct, registered comparison of our liquidus isotherms with Bowen & Schairer's Fig. 6
(their multicomponent headline figure). Two panels: our primary-phase fields plus isotherms in
weight percent (their axis and orientation), and our isotherms drawn on top of the scanned
figure.

- **Units matched.** Bowen & Schairer's isotherms are in degC; ours are computed in K and
  overlaid at the SAME levels (1400-1700 degC = 1673-1973 K), so a coloured contour reads
  directly against the black contour of the same value. The 1200-1300 degC contours are
  essentially absent in our model because our liquid barely exists below fayalite melting
  (1478 K = 1205 degC), so nothing is fully liquid at 1200 degC.
- **Isotherms computed directly, one temperature at a time.** At fixed T the liquidus isotherm
  is the boundary of the single-phase-liquid field, i.e. the contour where the equilibrium
  liquid phase-fraction (from the 2-D hull) drops below one. This is exact - no temperature
  quantization, unlike contouring a coarse temperature-descent field - and inherently smooth.
  Each contour is clipped to its INTERIOR arc (the parts running along the composition-triangle
  edges, where the liquid field merely reaches a binary join, are not isotherms) and lightly
  spline-smoothed to remove the grid-scale staircase.
- **Registration.** The scan triangle vertices were detected from the dpi=300 render as
  corner-dot centroids: SiO2 = (962.7, 665.5), MgO = (372.9, 1715.0), FeO = (1538.6, 1711.9)
  px. The earlier equilateral-apex estimate was ~40 px low; the true triangle is slightly
  taller than equilateral. The registration was validated by mapping the three marked
  compounds - Fe2SiO4, Mg2SiO4, MgSiO3 - through the weight-fraction barycentric transform and
  confirming they land on their labelled points in the scan.
- **What the comparison shows.** Our model reproduces the QUALITATIVE topology - the isotherm
  fan sloping toward the FeO-SiO2 side, the olivine central primary field, orthopyroxene on its
  silica side, cristobalite/periclase/wustite at the corners. The absolute isotherm POSITIONS
  are displaced from Bowen & Schairer's, consistent with the documented liquidus running high
  in places (solid-reference reconciliations, the opx offset) and with the fact that Bowen &
  Schairer measured only below ~1520 degC in the central band while ours spans the full field.
  This is the first open-model overlay of the system, not a quantitative assessment-grade match.

Ours is drawn in weight percent to match their axis; the conversion assumes one cation per
oxide (oxide moles equal cation moles).

## Honest limits (next targets)

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
