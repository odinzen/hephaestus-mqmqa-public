# Olivine + orthopyroxene Fe-Mg exchange provenance

Two coexisting CEF solid solutions and their Fe-Mg exchange equilibrium - the first
multi-phase equilibrium between two solid solutions in this engine, and the strategic
capability for multicomponent silicate/slag systems. Every number traces to open,
measured data; no FactSage/FToxid or optimized-TDB parameter is used.

Build/validation: `build_dat.py` writes both phases into one ChemSage SUBL `.dat`
(`Olivine-Opx-CEF.dat`); `exchange.py` computes the exchange isotherm and K_D through the
C CEF kernel and validates against pycalphad; `tests/test_olivine_opx_exchange_vs_pycalphad.py`
is the regression. Run:

    C:/Users/busta/miniforge3/envs/calphad/python.exe data/olivine-opx/exchange.py

## The two phases

    OLIVINE        (Mg,Fe)_2 (Si)_1 (O)_4     endmembers forsterite / fayalite
    ORTHOPYROXENE  (Mg,Fe)_2 (Si)_2 (O)_6     endmembers enstatite / ferrosilite

Both mix Fe and Mg on a two-site metal sublattice. Orthopyroxene is written per M2Si2O6 (two
cations) so both phases carry two mixing sites and the exchange bookkeeping is symmetric.
Orthopyroxene's real M1/M2 site distinction and Fe-Mg ordering are not resolved; this is the
standard macroscopic (disordered) mixing model.

## Endmember Gibbs energies (Robie & Hemingway 1995, public domain)

USGS Bulletin 2131. All four minerals are in the same ortho-silicate section, one consistent
scale; heat capacity is the R&H five-term form integrated to G(T) (see
`data/olivine/endmembers.py`, with the self-test reproducing each R&H Cp(298)).

| | Forsterite | Fayalite | Enstatite | Ferrosilite |
|---|---|---|---|---|
| formula | Mg2SiO4 | Fe2SiO4 | MgSiO3 | FeSiO3 |
| dHf(298) kJ/mol | -2173.0 | -1478.2 | -1545.6 | -1195.2 |
| S(298) J/mol/K | 94.11 | 151.00 | 66.27 | 94.60 |
| Cp(298) reproduced | 118.61 | 131.84 | 83.09 | 90.63 |
| R&H Cp fit range | 298-1800 K | 298-1490 K | 298-1000 K | 298-800 K |

The orthopyroxene endmember energies are doubled to the M2Si2O6 formula. **Extrapolation
caveat:** enstatite's and ferrosilite's R&H Cp fits end at 1000 and 800 K; above those the
polynomials are extrapolated smoothly (they stay physical, Cp ~ 143-145 J/mol/K by 1400 K,
no divergence) rather than switched to a Neumann-Kopp tail. The engine-vs-pycalphad agreement
is exact regardless (both read the same G(T)); only the absolute K_D vs real data carries this
caveat. Ferrosilite is metastable at 1 atm (it breaks down to fayalite + quartz); it is used
only as the Fe-endmember reference for the solid solution.

## Excess mixing (measured enthalpies of mixing, T-independent)

- **Olivine** - Wood & Kleppa 1981 (GCA 45:529, DOI 10.1016/0016-7037(81)90185-X), the same
  subregular excess as `data/olivine` (L0 = 12552, L1 = 4184 J/mol-M2SiO4).
- **Orthopyroxene** - Chatillon-Colinet, Newton, Perkins & Kleppa 1983 (GCA 47:1597,
  DOI 10.1016/0016-7037(83)90186-2, in the trove): solution calorimetry of five synthetic
  disordered orthopyroxenes on the MgSiO3-FeSiO3 join gives a small positive, **symmetric**
  enthalpy of mixing W_H = 950 cal/MSiO3 = 7949.6 J per M2Si2O6. The same authors note the
  net Gibbs mixing is nearly ideal (M1-M2 ordering counterbalances the positive enthalpy);
  a single-parameter CEF captures the calorimetric enthalpy, not that ordering, so this is
  the disordered-mixing model.

Both excesses are the measured calorimetric enthalpies used directly (T-independent),
matching how the olivine model was built. DOIs Crossref-verified.

## The exchange equilibrium

Reaction (SiO2-conserving): Mg2SiO4(ol) + 2 FeSiO3(opx) = Fe2SiO4(ol) + 2 MgSiO3(opx). At
equilibrium the Fe-Mg exchange chemical potential is equal in both phases, which per
two-cation formula is simply equal Gibbs slopes:

    dG_ol/dX_Fe |_{X_Fe,ol}  =  dG_opx/dX_Fe |_{X_Fe,opx}.

For each orthopyroxene composition this fixes the coexisting olivine composition (the
exchange isotherm) and the distribution coefficient K_D = (X_Fe/X_Mg)_ol / (X_Fe/X_Mg)_opx.
Both slopes come from the C CEF kernel (`cef_gibbs`, per formula unit) by finite difference.

## Validation

1. **Engine vs pycalphad** - the exchange isotherm reproduces pycalphad's own two-phase
   equilibrium() on the same `.dat` to ~1e-9 in olivine X_Fe, across bulk composition at
   1000 K. This validates the C SUBL reader (two CEF phases at once), the C CEF kernel, and
   the exchange-potential formulation together against an independent solver.
2. **vs measured data (von Seckendorff & O'Neill 1993, DOI 10.1007/BF00283228, hardcopy)** -
   they report K_D ~ 1, near-ideal, with ol/opx deviations cancelling near Fe/(Mg+Fe) ~ 0.1
   (mantle compositions). The model gives K_D = 0.92 at X_Fe,opx = 0.1 / 1273 K, and K_D
   staying within ~0.85-1.3 over the geologically relevant range - reproducing the measured
   near-ideal magnitude. Their phase-equilibrium Gibbs interaction (W_G(opx) = 2145 J,
   W_G(ol) = 5450 J at 1 bar) is smaller than the calorimetric enthalpies used here (the
   ordering effect); it is held as a cross-check, not fitted.

## What is deliberately excluded

No FactSage/FToxid or optimized-TDB parameters. The endmembers are R&H compilation values
(single-substance, allowed as inputs); the excesses are primary calorimetric enthalpies
(Wood-Kleppa, Chatillon-Colinet); von Seckendorff-O'Neill enters only as an agreement check.
