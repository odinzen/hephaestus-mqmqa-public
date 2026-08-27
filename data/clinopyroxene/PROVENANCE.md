# Clinopyroxene (diopside-hedenbergite) v0.2 provenance and limits

The third CEF solid solution in the open slag database, after olivine and orthopyroxene,
and the first Ca-bearing pyroxene. Clinopyroxene dominates the pyroxene field of
CaO-FeO-MgO-SiO2 slags. Built 2026-08-26. Model:

    CLINOPYROXENE  (Ca)1 (Mg,Fe)1 (Si)2 (O)6     endmembers diopside / hedenbergite

Only the M1 (Mg,Fe) sublattice mixes; Ca, Si and O are fixed. Unlike orthopyroxene, no
endmember doubling is needed (diopside already carries Si2O6). 10 atoms per formula.

## Endmembers (Robie & Hemingway 1995, USGS Bull. 2131, public domain)

| | dHf(298) kJ | S298 J/K | Cp298 J/K | Cp fit range |
|---|---|---|---|---|
| diopside CaMgSi2O6 | -3201.5 | 142.7 | 166.78 | 298-1600 K |
| hedenbergite CaFeSi2O6 | -2839.9 | 174.2 | 175.30 | 298-1300 K |

Both minerals sit in the same Bull. 2131 high-temperature phase table, so the two
endmembers share one self-consistent scale. The five-term Robie-Hemingway Cp form
(Cp = A1 + A2*T + A3*T^-2 + A4*T^-0.5 + A5*T^2) is least-squares fitted to the tabulated
Cp values (max residual < 0.01 J/mol/K over the whole crystal range; that basis is well
conditioned, so this is a faithful reproduction of the published Cp, not a re-derivation).
Independent anchor (not used, cross-check only): Navrotsky & Coons 1976 oxide-melt
calorimetry gives diopside dHf consistent with the Bull. 2131 value.

## Mixing (v0.2, MLIP-triangulated)

No open diopside-hedenbergite mixing calorimetry exists, and the standard activity model
(Davidson & Lindsley 1985) is a paywalled phase-equilibrium assessment, not ingestible
measured data. So the (Fe,Mg) M1 excess is **computed from a foundation MLIP** (MatterSim
v1.0.0-5M), the same triangulation used for the CaO-SiO2 / MgO-SiO2 liquids and now
extended to a CEF solid solution. Because the enthalpy of mixing is a *difference* between
the alloy and its endmembers, the MLIP's systematic per-atom error largely cancels.

Method (data/clinopyroxene/_mlip): the diopside C2/c cell (COD 1000007) is the common
framework; for each Fe/Mg ordering on the M1 sublattice, the cell and positions are
relaxed at 0 GPa. A doubled cell (8 M1 sites, up to 8 orderings per composition) gives the
configurational-average H_mix(x). A Redlich-Kister excess is fit, uncertainty-weighted:

    G_xs = y_Fe*y_Mg*[L0 + L1*(y_Fe - y_Mg)],  L0 = -576, L1 = +3442 J/mol formula

**The result is a small, near-ideal excess** (|H_mix| < 0.5 kJ/mol), too small to open a
miscibility gap - di-hed is a complete solid solution at all temperatures. The .dat excess
reproduces the fitted RK to < 0.05 J/mol. T-independent (no excess-entropy evidence).

**Near-ideal is robust across models; the precise L0, L1 are MLIP estimates (~+/-few kJ).**
A seven-model triangulation against measured olivine mixing (`data/olivine/_mlip/VALIDATION.md`)
re-ran di-hed with four viable models: L0 = +1259 (SevenNet), -576 (MatterSim), -1843
(TensorNet), -5440 (ORB). Unlike spinel (a 22 kJ spread), these **cluster near zero** - every
model agrees di-hed is essentially ideal, so the shipped MatterSim value is safe as a small
central estimate. The L1 (composition dependence) is not resolved by any model and should not
be over-read.

## Validation

- **The C engine's CEF Gibbs energy equals pycalphad's Model.GM to machine precision**
  (worst |diff| = 1.2e-10 J/mol-atom) across x_di = 0..1 at T = 1000/1400/1600 K, on the
  written .dat. The four-sublattice phase (with the diopside T^0.5 Cp term) round-trips
  exactly through the reader and the CEF kernel.
- The endmembers reproduce the Robie-Hemingway Cp(298), dHf and S298.
- The written .dat excess reproduces the MLIP-fitted Redlich-Kister to < 0.05 J/mol.

## Known limits

- **The excess is small and MLIP-derived.** |H_mix| < 0.5 kJ/mol, so di-hed is near-ideal
  either way; the MLIP resolves the *sign and asymmetry* (clean at the symmetry-locked
  x = 0.125 / 0.875 endpoints) but the mid-composition points carry ~0.1 kJ/mol scatter.
  A direct solution-calorimetry H_mix (if one is ever located, open) would tighten it, but
  would not change the phase behaviour (no gap). MatterSim over-expands both endmember
  cells by ~4 %, a systematic offset that cancels in the mixing energy.
- **T-independent excess.** No excess-entropy evidence, so the RK terms carry no b*T.
- **Standalone.** Clinopyroxene lives in CaO-FeO-MgO-SiO2 and slots into neither shipped
  ternary yet (FeO-MgO-SiO2 has no Ca; CaO-Al2O3-SiO2 has no Fe), so it ships as its own
  validated .dat, exactly as olivine was introduced before entering a multicomponent
  assembly. Its Fe-Mg exchange K_D against olivine/orthopyroxene is a natural cross-check
  once a Ca-Fe-Mg-Si system is assembled.

## Sources

- Robie & Hemingway, *Thermodynamic Properties of Minerals and Related Substances at
  298.15 K and 1 Bar Pressure and at Higher Temperatures*, USGS Bull. 2131 (1995), public
  domain (diopside and hedenbergite endmembers: dHf, S298, high-T Cp table).
- Navrotsky & Coons, *Thermochemistry of some pyroxenes and related compounds*, Geochim.
  Cosmochim. Acta 40 (1976) 1281, DOI 10.1016/0016-7037(76)90162-9 (diopside formation
  enthalpy cross-check, not fitted).
- Diopside structure COD 1000007 (Thompson & Downs 2008); hedenbergite is the all-Fe M1
  substitution, relaxed. The mixing excess is computed (MatterSim), not from a citation.

Repro: `endmembers.py` (diopside/hedenbergite Gibbs coefficients, with a self-test),
`build_dat.py` (writes Clinopyroxene-CEF.dat), `validate_cpx.py` (engine vs pycalphad),
`_mlip/` (mlip_mix.py, mlip_mix2.py, fit_excess.py: the MLIP mixing-enthalpy pass and the
Redlich-Kister fit; README.md documents the method).
