# MgO-SiO2-liquid.dat provenance

Open MgO-SiO2 liquid-slag MQMQA database. Built by `build_dat.py`, validated by
`validate.py`. Second system in the open slag family (after CaO-SiO2); chosen because
it exercises the phenomena a simple cation-mixing excess cannot yet capture - a
liquid-liquid **miscibility gap** and an **incongruent (peritectic) melting** - so it
is the proving ground for the v0.x model-form and hull-classifier upgrades.

## Primary sources (all open)

- **CODATA Key Values** (Cox, Wagman, Medvedev 1989): MgO dHf(298) = -601.5 kJ/mol,
  S(298) = 26.95 J/mol/K.
- **NIST-JANAF** (Chase 1998): MgO periclase Cp tabulation (298-2000 K) - the
  Haas-Fisher coefficients below are a least-squares fit to it (max residual 0.32
  J/mol/K). MgO melting Tm = 3098 K (2825 degC), dHfus ~ 77 kJ/mol. SiO2 fusion.
- **Robie & Hemingway 1995** (USGS Bull. 2131, public domain): SiO2 (cristobalite)
  endmember, cross-check on MgO S298/Cp.
- Phase-equilibrium data for the coming excess fit (not yet used in v0.1):
  **Greig 1927** (Am. J. Sci.) - the silica-rich liquid-liquid immiscibility dome:
  monotectic at 1968 K with conjugate liquids at ~68 and ~99 wt% SiO2. **Bowen &
  Andersen 1914** - forsterite congruent melting 2163 K, periclase-forsterite eutectic
  2123 K. Enstatite (MgSiO3) melts incongruently. Compound formation enthalpies:
  Charlu-Newton-Kleppa 1975 (Mg2SiO4 -60.25, MgSiO3 -36.86 kJ/mol from oxides).

## v0.1 endmembers (per formula unit)

| Symbol | MgO | SiO2 | Source |
|---|---|---|---|
| dHf(298) | -601500 J/mol | -908400 J/mol | CODATA / R&H (cristobalite) |
| S(298) | 26.95 J/mol/K | 43.4 J/mol/K | CODATA / R&H |
| Cp a,b,c (a+bT+cT^-2) | 48.2425, 3.906e-3, -1.1082e6 | 72.75, 1.300e-3, -4.132e6 | MgO: fit to JANAF Cp; SiO2: R&H |
| Tm | 3098 K | 1996 K | NIST-JANAF |
| dHfus | 77000 J/mol | 9581 J/mol | NIST-JANAF |

MgO Cp coefficients are a Haas-Fisher fit to the open JANAF periclase Cp points
(reproduces Cp(298)=37.1 and Cp(2000)=55.7 within 0.3 J/mol/K). SiO2 uses the same
cristobalite endmember as CaO-SiO2 (consistency across the slag family).

## Model-structure choices (v0.1, no fitted physics)

- Cations Mg+2, Si+4; anion O-2. Pairs MgO, SiO2.
- Charge-proportional coordination Z = 0.68872*charge (framework default, not fitted),
  same convention as CaO-SiO2.
- **Excess: none in v0.1 (ideal).** The interior mixing - including the silica-rich
  immiscibility (Greig 1927) and the enstatite peritectic - is the v0.x target and will
  be fit from the open data above, cross-checked by MLIP as in CaO-SiO2.

## Statement on sources

Built only from open/public-domain data (CODATA, NIST-JANAF, Robie-Hemingway 1995;
Greig 1927 and Bowen-Andersen 1914 for the coming phase-diagram fit). No FactSage/FToxid
or other external-TDB optimized parameters.
