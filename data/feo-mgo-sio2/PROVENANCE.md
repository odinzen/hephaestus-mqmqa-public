# FeO-MgO-SiO2-liquid.dat provenance

Open **FeO-MgO-SiO2 ternary** liquid-slag MQMQA database, **v0.1**. The iron-magnesium
silicate melt at the centre of the steel-slag and olivine families, and the liquid the
olivine + orthopyroxene + liquid diagram (vs Bowen & Schairer 1935) needs. **Iron-saturated /
fixed-valence**: Fe is Fe2+ only (no Fe3+), Mg2+, Si4+; a single anion O2-.

Built by `build_dat.py`; validated by `validate.py`. Run:

    C:/Users/busta/miniforge3/envs/calphad/python.exe data/feo-mgo-sio2/validate.py

## Assembly

The ternary liquid combines the two shipped silica binaries, an assessed FeO-MgO edge and two
ternary-level terms. Every binary parameter is read from its binary builder (single source of
truth, checked by the binary-reduction guard below):

| Edge or term | Excess on | Source | Terms |
|---|---|---|---|
| MgO-SiO2 | (Mg,Si,O,O) | `data/mgo-sio2`, three-way fit N1 | chi_Si^q for q = 0, 1, 2, 3, 5, 7 and chi_Mg^4, each a + bT |
| FeO-SiO2 | (Fe,Si,O,O) | `data/feo-sio2` v0.4 | four terms (see that file) |
| FeO-MgO | (Fe,Mg,O,O) | `assessment/assess.py` | 9064.5 J |
| Fe-Si with Mg | (Fe,Si,O,O) + Mg | `assessment/assess.py` | -6604.3 J |
| Mg-Si with Fe | (Mg,Si,O,O) + Fe | `assessment/assess.py` | +16774.8 J |

The three assessed terms (`build_dat.TERNARY_EXCESS`) were fitted on 2026-10-05 together with the
MgO-SiO2 liquid and the CaO-MgO-SiO2 face (`data/mgo-sio2/assessment/joint3.py`), against Bowen &
Schairer (1935) Table I and the Nafziger & Muan (1967) solidus.

- **Chemical groups: Fe and Mg in group 1, Si in group 2** (2026-09-29). The group decides how
  a binary excess is extrapolated into the ternary. Si alone makes the extrapolation of the
  two silicate binaries asymmetric (Toop-like, the basic oxides as one family), the usual
  choice for silicate slags. Through v0.1 all three cations shared group 1, a symmetric
  interpolation that grew a two-liquid region near the orthosilicate join (between about
  Fe 0.49 / Mg 0.18 / Si 0.33 and Fe 0.61 / Mg 0.01 / Si 0.38 cation fraction, from 1573 K
  up) that neither binary has, and a silica-rich two-liquid region reaching the middle of the
  triangle (down to 50% SiO2), wider than on either binary edge. With Si alone both are gone.
  The binary edges are unchanged exactly (the reduction guard below).
- **Mg-Si ordering.** The MgO-SiO2 liquid orders most at x_SiO2 = 0.3375, not 1/3; the file
  carries the same explicit (Mg,Si/O,O) coordination row as the binary
  (`tests/test_mgsi_ordering_consistency.py`).
- **Endmember liquids.** FeO(l) keeps the below-1650 K interval assessed with FeO-SiO2 v0.4
  (`FEO_LIQ_BETA = -28.34 J/mol/K`) and MgO(l) the heat-capacity excess assessed with MgO-SiO2
  (`MGO_LIQ_DCP = 26.0 J/mol/K`); both are properties of the endmember liquids, so they apply
  ternary-wide.
- **Endmembers.** FeO is iron-saturated wustite (Robie-Hemingway + SGTE Fe, `data/feo-sio2`),
  MgO is CODATA/JANAF periclase (`data/mgo-sio2`), SiO2 is the corrected beta-cristobalite
  shared by every silicate. The combined file adds olivine, the two-site orthopyroxene
  (`data/olivine-opx`), magnesiowustite (`data/magnesiowustite`) and cristobalite. Cation
  indexing in the .dat is Fe=1, Mg=2, Si=3; the single anion O=4.

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
minimization), plus the exact minimum (`vis3d.liquid_gibbs`) at every node of a 1/60
composition lattice; the liquid hull vertices are then locally minimized to tighten the
envelope. On draws alone the 1900 K liquidus end on the olivine join moved from 0.337 to 0.451
with the seed; with the lattice minima it lies within the lattice spacing of the model value.
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

## Liquidus against Bowen & Schairer 1935 Table I (`bs1935_liquidus.py`)

Their Table I (pp. 155-157) gives 38 liquid compositions with the temperature of completion of
melting and the primary phase; `bs1935_table1.csv` holds it as printed. The model liquidus at
each (refined hull, `vis3d.liquidus_point`), with their clinopyroxene scored against our
orthopyroxene and tridymite against cristobalite.

Shipped file (fit N1, 2026-10-05; the fit's own scorer, `assessment/assess.py`): olivine field 23
points, mean absolute miss 21 K; pyroxene 8 points, 19 K; silica 7 points, 11 K; 29 of 37 primary
phases as measured. Solidus against Nafziger & Muan (1967): 36 K low (olivine + pyroxene) and
42 K low (olivine + magnesiowustite).

The table below records the 2026-09-29 grouping comparison, on the files of that date:

| Primary field | Points | Mean miss, Si in own group | Mean miss, all one group (v0.1) |
|---|---|---|---|
| Olivine | 23 | 40 K (model low by 39 on average) | 57 K |
| Pyroxene | 8 | 16 K | 25 K |
| Silica | 7 | 113 K (up to 246 K low) | 41 K |
| Primary phase as measured | 37 | 21 | 14 |

The silica field is where the grouping costs: the v0.1 silica-rich two-liquid region held the
silica liquidus up there, and without it the model puts pyroxene first where they found
tridymite or cristobalite. The fix belongs to the FeO-SiO2 binary (below), not the grouping.

## Honest limits (next targets)

- **Solidus 36-42 K low.** Mostly a knock-on of the MgO(l) heat-capacity excess, which the
  MgO-SiO2 fit needs high because forsterite comes out too unstable (data/mgo-sio2, "Known
  shortfalls"); possibly also a quench-detection bias in the measured solidus.
- **Forsterite melts at 2080 K** in this file (measured 2163 K), the same shortfall.
- **Fayalite** is stable and melts congruently at 1475-1476 K in the full equilibrium (pycalphad
  on the shipped combined file; measured 1478 K). Until the two-site orthopyroxene and
  magnesiowustite (2026-09-30) it was not: ferrosilite + wustite lay below it.
- **FeO-SiO2 liquid gap.** The v0.4 binary has one (monotectic 1937 K, liquid 0.54 against the
  measured 1963 K and about 0.615); its silica-rich conjugate is the structural misfit recorded
  in data/feo-sio2.
- **SiO2 solid Cp below ~500 K.** The Haas-Fisher fit shared by every silicate here gives
  26.7 J/mol/K at 298 K (JANAF: 44.6); integrated from 298 K it leaves solid (and liquid)
  SiO2 3.1, 4.7, 5.5 and 6.0 kJ too high at 1000, 1273, 1400 and 1480 K. SiO2 cancels in
  melting, but not in compound formation from the oxides.
- **No ferric iron.** The file is iron saturated (Fe2+ only), as are the slags it describes.
- **One pyroxene phase.** At 1 atm and liquidus temperatures the Mg-Fe pyroxene is
  protopyroxene or pigeonite, not orthopyroxene; the model has one pyroxene for both.

## What is deliberately excluded

No FactSage/FToxid or optimized-TDB parameters. Every number traces to the two open binary
assessments in this repo (themselves literature-only) or to open single-substance evaluated
data (JANAF, CODATA, Robie-Hemingway). Bowen & Schairer 1935 is a validation target only.
