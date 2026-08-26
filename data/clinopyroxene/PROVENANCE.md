# Clinopyroxene (diopside-hedenbergite) v0.1 provenance and limits

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

## Mixing

**Ideal on the M1 sublattice (Redlich-Kister L0 = 0).** No open diopside-hedenbergite
mixing calorimetry exists (the workspace holds only endmember and formation data for the
pyroxenes), so the configurational entropy of Fe-Mg mixing is the only non-endmember
contribution in v0.1. Activities are therefore ideal (a_di = x_di).

## Validation

- **The C engine's CEF Gibbs energy equals pycalphad's Model.GM to machine precision**
  (worst |diff| = 1.2e-10 J/mol-atom) across x_di = 0..1 at T = 1000/1400/1600 K, on the
  written .dat. The four-sublattice phase (with the diopside T^0.5 Cp term) round-trips
  exactly through the reader and the CEF kernel.
- The endmembers reproduce the Robie-Hemingway Cp(298), dHf and S298.

## Known limits and the v0.2 path

- **Ideal mixing.** The real diopside-hedenbergite join has small positive deviations and
  a low-temperature miscibility gap; neither is captured by L0 = 0. A measured subregular
  excess, converted to Redlich-Kister (the Wood-Kleppa -> RK move used for olivine), is
  the v0.2 refinement, from a targeted open-data pull (candidate primaries: Wood 1987-type
  di-hed solution calorimetry, or Davidson-Lindsley activities). Not FactSage-assessed W.
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

Repro: `endmembers.py` (diopside/hedenbergite Gibbs coefficients, with a self-test),
`build_dat.py` (writes Clinopyroxene-CEF.dat), `validate_cpx.py` (engine vs pycalphad).
