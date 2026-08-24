# Olivine (Mg,Fe)2SiO4 solid-solution provenance

The first **compound-energy-formalism (CEF)** solid solution in the open slag database:
olivine, the forsterite (Mg2SiO4) - fayalite (Fe2SiO4) join, the canonical mineral/slag
solid solution. It exercises the CEF Gibbs kernel (`cef/cef.py`) on a real system, the
way `cao-sio2` and `mgo-sio2` exercise the MQMQA liquid engine. Every number traces to a
published, open source; no FactSage/FToxid or other optimized-TDB parameter is used.

Build/validation: `endmembers.py` (the two endmember Gibbs functions, with a self-test),
`olivine.py` (the CEF model + mixing/activity/solvus helpers), `validate_olivine.py`
(cross-check vs pycalphad + the physical checks). Run:

    C:/Users/busta/miniforge3/envs/calphad/python.exe data/olivine/validate_olivine.py

## The model

Sublattice model, the standard CALPHAD olivine model:

    (Mg, Fe)_2 (SiO4)_1        Mg and Fe mix on a two-site metal sublattice; SiO4 fixed.

For a clean, exact map onto pycalphad the orthosilicate group is written as its elements,
`(Mg,Fe)2(Si)1(O)4` (three sublattices). Only the metal sublattice mixes, so Si and O add
no configurational entropy and the model is identical to `(Mg,Fe)2(SiO4)1`. Per formula
unit there are 2 + 1 + 4 = 7 atoms (the per-mole-of-atoms divisor). The two endmembers are
forsterite (metal sublattice = Mg) and fayalite (metal sublattice = Fe).

Molar Gibbs energy per formula unit:

    G = y_Fe G_fa(T) + y_Mg G_fo(T)                                 (endmember reference)
      + 2 R T [ y_Fe ln y_Fe + y_Mg ln y_Mg ]                       (ideal, two-site)
      + y_Fe y_Mg [ L0 + L1 (y_Fe - y_Mg) ]                         (subregular excess)

## Endmember Gibbs energies (Robie & Hemingway 1995, public domain)

R. A. Robie, B. S. Hemingway, *Thermodynamic Properties of Minerals and Related Substances
at 298.15 K and 1 Bar Pressure and at Higher Temperatures*, U.S. Geological Survey Bulletin
2131 (1995). Public domain (USGS). Both minerals are in the same ortho-silicate section, so
the two endmembers sit on one internally consistent scale. Heat capacity uses the R&H
five-term form Cp = A1 + A2 T + A3 T^-2 + A4 T^-0.5 + A5 T^2; the standard-state Gibbs
energy from the elements is G = dHf(298) + INT Cp dT - T[S298 + INT Cp/T dT].

| Quantity | Forsterite Mg2SiO4 | Fayalite Fe2SiO4 |
|---|---|---|
| dHf(298), from elements | -2173.0 kJ/mol | -1478.2 kJ/mol |
| S(298), third law | 94.11 J/mol/K | 151.00 J/mol/K |
| Cp A1 | 87.36 | 176.02 |
| Cp A2 (T) | 8.717e-2 | -8.808e-3 |
| Cp A3 (T^-2) | -3.699e6 | -3.889e6 |
| Cp A4 (T^-0.5) | 843.6 | 0 (no term) |
| Cp A5 (T^2) | -2.237e-5 | 2.471e-5 |
| Cp fit range | 298-1800 K | 298-1490 K (melts incongruently at 1490 K) |
| Cp(298) reproduced | 118.61 (table 118.61) | 131.84 (table 131.84) |

The forsterite Cp carries a T^-0.5 term (A4), which integrates to a T^0.5 term in G; the
CEF kernel `eval_gibbs` was extended to that term basis (fayalite has no such term). The
term-basis coefficient derivation is checked against a direct H - T*S integration to
~1e-9 J/mol in `endmembers.py`. These are the same forsterite numbers already used by the
`mgo-sio2` solid model.

Only the *mixing* behaviour depends on the excess and the ideal entropy; the absolute
endmember values set the reference but do not affect the enthalpy of mixing or the
activity coefficients.

## Excess mixing: L(Mg,Fe) from open calorimetry

**Wood & Kleppa (1981)**, "Thermochemistry of forsterite-fayalite olivine solutions,"
*Geochim. Cosmochim. Acta* 45(4), 529-534. DOI [10.1016/0016-7037(81)90185-X](https://doi.org/10.1016/0016-7037(81)90185-X)
(Crossref-verified). Enthalpies of solution in Pb2B2O5 melt at 970 K. Forsterite heat of
solution 15.62 +/- 0.30 kcal/mol, fayalite 9.39 +/- 0.14 kcal/mol. The intermediate
olivines show a small positive, Fe-asymmetric deviation, represented by the subregular
excess enthalpy

    H_xs = 2 (1000 + 1000 X_Fe) X_Fe X_Mg      cal / mol-formula.

Wood & Kleppa state explicitly that this calorimetric enthalpy is consistent with the
high-temperature phase-equilibrium activity-composition data **without any excess entropy
term**, so the model excess is purely enthalpic (L is T-independent). Converting the
subregular form to a two-term Redlich-Kister interaction in the [Fe, Mg] constituent order
(the order pycalphad sorts to), with the thermochemical calorie (4.184 J):

    L0 = 3000 cal = 12552 J/mol,     L1 = 1000 cal = 4184 J/mol.

`validate_olivine.py` confirms the CEF excess reproduces the Wood & Kleppa H_xs at every
composition to 1e-13 J/mol. H_xs at the midpoint is 3138 J/mol (0.75 kcal/mol) - small and
positive, the signature of a near-ideal solution.

### Independent open confirmation (not fitted, cross-check only)

- **Dachs & Geiger (2007)**, "Entropies of mixing and subsolidus phase relations of
  forsterite-fayalite (Mg2SiO4-Fe2SiO4) solid solution," *Am. Mineral.* 92, 699-702.
  DOI [10.2138/am.2007.2465](https://doi.org/10.2138/am.2007.2465) (Crossref-verified).
  Low-temperature calorimetry gives an interaction enthalpy W_H = 5.3 +/- 1.7 kJ/mol on a
  *one-cation-site* basis, and an excess entropy statistically indistinguishable from zero.
  Our symmetric part L0 = 12552 J/mol-formula is 6.28 kJ per cation site, inside the Dachs
  1-sigma band, and the zero-excess-entropy finding matches the T-independent L.
- **Williams (1972)**, "Activity-composition relations in the fayalite-forsterite solid
  solution between 900 and 1300 C at low pressures," *Earth Planet. Sci. Lett.* 15,
  296-300. DOI [10.1016/0012-821X(72)90176-8](https://doi.org/10.1016/0012-821X(72)90176-8).
  One of the activity-composition datasets Wood & Kleppa's calorimetry was shown to be
  consistent with; the small positive deviation from the ideal a_fo = X_fo^2 line that the
  model produces is the same behaviour these measurements record.

## Validation results

1. **GM vs pycalphad** (equivalent TDB, `_olivine.tdb`, generated by the script): agrees to
   ~1e-5 J/mol-atom across x_fo = 0..1 and T = 1000, 1400 K - float64 machine precision
   (~3e-11 relative), including the forsterite T^0.5 endmember term.
2. **Enthalpy of mixing**: reproduces Wood & Kleppa exactly (1e-13 J/mol). Small, positive,
   Fe-asymmetric (peak near x_fo = 0.4).
3. **Activities** (1200 K): positive deviation from ideality, all activity coefficients >= 1,
   larger on the Fe end (gamma_fa > gamma_fo) - the measured asymmetry.
4. **Metastable solvus**: the calorimetric interaction gives a consolute at ~447 K (174 C),
   x_fo ~ 0.33. Olivine crystallizes near 2000 K, so this solvus is deeply sub-solidus and
   metastable: forsterite-fayalite is a **complete solid solution** at all geologically and
   metallurgically relevant temperatures, exactly as the calorimetry and petrology require.
   (This is well below the ~600 C sometimes quoted; the value here is the one the open
   Wood & Kleppa / Dachs calorimetry actually implies, not an assessed or assumed solvus.)

## Engine-readable SUBL database and the C/WASM kernel

`build_subl_dat.py` writes the same model as a ChemSage **SUBL** (compound-energy) `.dat`
file, `Olivine-CEF.dat`, which the engine's C ChemSage reader now parses (the reader gained
SUBL-block support alongside the existing SUBQ/SUBG). The forsterite T^0.5 term rides in the
file's "additional terms" slot as a (coefficient, exponent) pair, which both the reader and
pycalphad evaluate as c6*T^0.5. The CEF Gibbs kernel is ported to C (`src/cef.c`,
`mqmqa_cef_gibbs`) and compiles into the native library and the in-browser WASM build.

`validate_cef_c.py` reads `Olivine-CEF.dat` with the C reader, computes GM with the C kernel,
and compares to pycalphad's Model.GM on the same file: agreement to ~1e-10 J/mol-atom across
composition and temperature. The reader and kernel are further regression-tested against a
real-world SUBL database (Viitala Pb-Zn-Cu-Fe-Cl) in `tests/test_cef_vs_pycalphad.py`, which
exercises multi-interval endmembers, log(T) terms, charged species, and vacancies (the
per-mole-of-atoms normalization excludes vacancies, matching pycalphad).

## What is deliberately excluded

No FactSage/FToxid parameters and no proprietary or optimized-TDB interaction parameters.
The excess is the published Wood & Kleppa subregular enthalpy, converted (not re-fitted) to
the Redlich-Kister form and cross-checked against the independent Dachs and Williams data.
