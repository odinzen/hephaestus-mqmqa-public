# Spinel-hercynite (Mg,Fe)Al2O4 v0.1 provenance and limits

The fourth CEF solid solution in the open database, and the first on a new (cubic Fd-3m)
structure, built to exercise the MLIP-for-solids method on a spinel. Built 2026-08-26.

    SPINEL  (Mg,Fe)1 (Al)2 (O)4    endmembers spinel MgAl2O4 / hercynite FeAl2O4

Normal-spinel model: Fe and Mg mix on the tetrahedral A-site, Al is fixed on the
octahedral B-site (7 atoms per formula).

## Endmembers (assembled from open reference data)

| | dHf(298) kJ | S298 J/K | Cp298 J/K (Neumann-Kopp) |
|---|---|---|---|
| spinel MgAl2O4 | -2313.7 | 80.63 | 116.0 |
| hercynite FeAl2O4 | -1982.4 | 106.27 | 128.8 |

MgAl2O4 formation enthalpy is assembled from the binary oxides: dHf = dHf(MgO) +
dHf(Al2O3) + dHf_ox, with dHf_ox = -36.4845 kJ/mol from Navrotsky & Kleppa 1968
(oxide-melt solution calorimetry) and MgO/Al2O3 from the shipped builders (CODATA).
FeAl2O4 dHf and S298 are the TKV evaluation; MgAl2O4 S298 is the measured third-law value.
Cp(T) of both is Neumann-Kopp from the shipped oxide Cp models (MgO/FeO + Al2O3), the
Maier-Kelley form; it reproduces the TKV FeAl2O4 Cp298 to ~5 J/K.

## Mixing: IDEAL (no excess term)

The (Fe,Mg) A-site is shipped **ideal**. No open spinel-hercynite mixing calorimetry exists, so
the excess was first taken from a foundation MLIP; a seven-model triangulation against the one
Fe-Mg join with real calorimetry (olivine, Wood & Kleppa 1981; `data/olivine/_mlip/VALIDATION.md`)
then showed foundation MLIPs cannot pin it. The four viable models give L0 = -14915 (SevenNet),
-9949 (TensorNet), -3411 (MatterSim), +6953 (ORB) - a **22 kJ spread that does not even agree on
sign**, and the original shipped value came from MatterSim, which fails the olivine control.

With no measurement to arbitrate and no model agreement, an unconstrained excess is not shipped.
This costs nothing in phase behaviour: every model (both signs) gives complete Fe-Mg miscibility
with no gap above ~1000 K (ORB's positive L0 opens a gap only below ~420 K), so the slag-relevant
behaviour is model-independent. The ideal configurational entropy carries the mixing; the residual
excess is a near-ideal quantity of undetermined sign, below both MLIP and equilibrium resolution.

The `_mlip/` scripts and the 7-model comparison are retained as the documented basis for this
choice, and as the harness a future DFT or measured excess would drop into.

## Validation

- **The C engine's CEF Gibbs equals pycalphad's Model.GM to machine precision**
  (1.2e-10 J/mol-atom) across x and 1000-1600 K.
- The .dat excess reproduces the MLIP-fitted Redlich-Kister to < 0.05 J/mol.
- The endmembers reproduce their assembled dHf and S298; NK Cp298 within ~5 J/K of TKV.

## Known limits

- **Normal-spinel approximation.** The Mg/Fe/Al cation inversion (partial swapping of
  A- and B-site cations, the defining spinel disorder) is not modeled; it is a secondary
  effect on the Fe-Mg mixing and a v0.2 study (the MLIP could compute the inversion energy
  directly). MgAl2O4 has notable inversion at high T; hercynite is more normal.
- **Assembled endmembers.** MgAl2O4 dHf is assembled from dHf_ox; Cp(T) of both is
  Neumann-Kopp rather than a measured high-T fit (Cp298 within ~5 J/K).
- **Standalone.** Spinel needs Al, so it sits outside the CaO-FeO-MgO-SiO2 crystallization
  system; it connects to the Al-bearing CaO-Al2O3-SiO2 family and ships as its own
  validated .dat.

## Sources

- Navrotsky & Kleppa, *Thermodynamics of formation of simple spinels*, J. Inorg. Nucl.
  Chem. 30 (1968) 479, DOI 10.1016/0022-1902(68)80475-0 (MgAl2O4 dHf_ox from oxides).
- TKV evaluation (chem.msu.ru) for FeAl2O4 dHf, S298, Cp; MgO/FeO/Al2O3 from the shipped
  binary builders.
- Spinel structure COD 9010342 (ambient MgAl2O4); hercynite is the all-Fe A-site
  substitution, relaxed. The mixing excess is computed (MatterSim), not from a citation.

Repro: `endmembers.py` (assembled Gibbs, with a self-test), `build_dat.py` (writes
Spinel-CEF.dat), `_mlip/` (mlip_mix.py: the MLIP mixing pass and the Redlich-Kister fit).
