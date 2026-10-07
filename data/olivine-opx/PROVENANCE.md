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

    OLIVINE        (Mg,Fe)_2 (Si)_1 (O)_4                endmembers forsterite / fayalite
    ORTHOPYROXENE  (Mg,Fe)[M1] (Mg,Fe)[M2] (Si)_2 (O)_6   four endmembers (Fe:Fe, Fe:Mg, Mg:Fe, Mg:Mg)

Olivine mixes Fe and Mg on one metal sublattice (two sites per M2SiO4). Orthopyroxene, since
2026-09-30, resolves its two metal sites: Fe strongly prefers the distorted M2 site, and the
phase is taken at internal order equilibrium wherever it is sampled
(`mqmqa_ph_cef_line_gibbs` in the engine; pycalphad does the same by itself). The model is
defined once in `orthopyroxene.py`, which both this file and data/olivine-opx-cpx write from.

## Endmember Gibbs energies (Robie & Hemingway 1995, public domain)

USGS Bulletin 2131, one consistent scale; the R&H five-term Cp integrated to G(T)
(`data/olivine/endmembers.py`, whose self-test reproduces each R&H Cp(298) and whose G
matches the R&H tables within 7 J).

| | Forsterite | Fayalite | Enstatite | Ferrosilite |
|---|---|---|---|---|
| formula | Mg2SiO4 | Fe2SiO4 | MgSiO3 | FeSiO3 |
| dHf(298) kJ/mol | -2173.0 | -1478.2 | -1545.6 | -1195.2 +- 3.0 |
| S(298) J/mol/K | 94.11 | 151.00 | 66.27 | 94.60 +- 0.3 |
| R&H Cp fit range | 298-1800 K | 298-1490 K | 298-1000 K | 298-800 K |

Enstatite above 800 K takes the drop-calorimetry heat capacity of Thieblot, Tequi & Richet 1999
(Am. Mineral. 84:848, Table 3, Eq. 3, orthoenstatite; DOI 10.2138/am-1999-5-618; trove
oxide-slag/references), with G, H and S continuous at 800 K, where the two curves agree to 0.1 J/K.
Their protoenstatite is within 3%. Extrapolated past its 1000 K limit, the R&H T^2 term gave
176 J/K at 1830 K against 133 measured, made the crystal too stable at liquidus temperatures, and
put orthopyroxene back above the liquid near 3100 K. Guarded by `tests/test_enstatite_heat_capacity.py`.

## Orthopyroxene: the two-site model (assessed 2026-09-30)

Per M2Si2O6, with y the Fe fraction on each site:

- G(Mg:Mg) = 2 enstatite, with the high-T correction assessed in data/mgo-sio2.
- G(Fe:Fe) = 2 ferrosilite + 2 [2411.8 J + 6.461 J/K (T - 800 K) above 800 K]. The
  constant is inside R&H's +-3 kJ; the slope replaces the extrapolation of a Cp measured
  only to 800 K.
- G(Fe:Mg) - G(Mg:Fe) = 10951.4 - 2.4556 T J (the exchange Fe(M2) + Mg(M1) = Fe(M1) + Mg(M2)).
- G(Fe:Mg) + G(Mg:Fe) - G(Mg:Mg) - G(Fe:Fe) = -6053.2 J (reciprocal).
- Site interactions W(M1) = 6582.9 J, W(M2) = 5216.4 J.

Assessed (`assessment/assess.py`, `assessment/dataset.py`) by weighted least squares against:

| Data | Source (open access unless noted) | Result |
|---|---|---|
| Fe on M1/M2, 29 samples, 773-1073 K | Saxena & Ghose 1971, Am. Mineral. 56:532, Table 2 | RMS 0.71 sigma, worst 1.6 (sigma 0.015) |
| olivine-pyroxene tie-lines, 1473 K, 1 atm | Nafziger & Muan 1967, Am. Mineral. 52:1364, Table 5 | within 1.2 sigma to Fs 0.3, up to +4 sigma (olivine too Fe-rich) above |
| ferrosilite = fayalite + quartz, 973-1323 K | Bohlen, Essene & Boettcher 1980, EPSL 47:1 | within 2.6 sigma (sigma 0.3 kJ) |
| enthalpy of mixing, disordering | Chatillon-Colinet et al. 1983, GCA 47:1597 (trove) | disordering -0.9 sigma; mixing -2.8 sigma |

Total cost 45.3, weighted RMS 1.32. The Saxena-Ghose table was read from the scan and every
row checked against (X_M1 + X_M2)/2 = X_bulk; the R&H quartz table was extracted from the
bulletin's text layer with its identity check.

**Limits.** The iron-rich tie-lines at 1473 K and the high-temperature end of the Bohlen
curve pull in opposite directions: Bohlen's orthoferrosilite (high pressure) needs pure
FeSiO3 destabilized as T rises, while Nafziger & Muan's iron-rich pyroxene at 1 atm and
1473 K needs it more stable. At 1 atm and liquidus temperatures the Mg-Fe pyroxene is not
orthopyroxene but protopyroxene / pigeonite (Bowen & Schairer 1935 logged it as
clinopyroxene), and the model has one pyroxene phase for both, as its enstatite correction
already stands for protoenstatite. The fitted mixing enthalpy comes out slightly negative
against Chatillon-Colinet's small positive W_H; the reciprocal energy is negative where
Chatillon-Colinet inferred a positive one without site interactions. Letting the olivine
excess float (to 7.0 kJ, against its own activities at 11-12 kJ) did not resolve either.

## The exchange equilibrium

Reaction (SiO2-conserving): Mg2SiO4(ol) + 2 FeSiO3(opx) = Fe2SiO4(ol) + 2 MgSiO3(opx). At
equilibrium the Fe-Mg exchange potential is equal in both phases, per two-cation formula

    dG_ol/dX_Fe |_{X_Fe,ol}  =  dG_opx/dX_Fe |_{X_Fe,opx},

with the orthopyroxene G taken at its order equilibrium at each X_Fe. `exchange.py` computes
the isotherm and K_D = (X_Fe/X_Mg)_ol / (X_Fe/X_Mg)_opx through the engine.

## Validation

1. **Engine vs pycalphad vs the assessment's model**: the orthopyroxene Gibbs energy at
   order equilibrium agrees to 6e-6 J/mol-atom at 900-1700 K across composition, with the
   same site fractions (`tests/test_opx_two_site.py`); the exchange isotherm matches
   pycalphad's two-phase equilibrium to ~1e-9 in olivine X_Fe.
2. **K_D**: 1.17-1.31 at X_Fe,opx 0.1 over 900-1300 K; Nafziger & Muan measured 1.0-1.28 at
   1473 K and 1 atm. von Seckendorff & O'Neill 1993 (DOI 10.1007/BF00283228, hardcopy,
   1.6 GPa) report K_D near 1; held as a cross-check. Iron-rich orthopyroxene at low
   temperature gives large K_D because it is unstable there, as Bohlen's data require.
3. **FeO-MgO-SiO2 liquidus** (Bowen & Schairer 1935, data/feo-mgo-sio2/bs1935_liquidus.py):
   mean absolute error 52 -> 33 K in the olivine field and 65 -> 41 K in the pyroxene field
   against the one-site model on the same liquid; 26 of 37 primary phases right (was 20).

## What is deliberately excluded

No FactSage/FToxid or optimized-TDB parameters. The endmembers are R&H compilation values;
the orthopyroxene parameters are fitted here to primary measurements; olivine uses the
Wood & Kleppa 1981 calorimetric excess (GCA 45:529, DOI 10.1016/0016-7037(81)90185-X).

## Enstatite high-T correction

The Mg2Si2O6 endmember carries a further Gibbs step above 1360 K (the ortho to
proto-enstatite break), linear in T from the break, assessed with the MgO-SiO2 liquid against
the enstatite peritectic and eutectic (data/mgo-sio2/assessment) and defined once in
`data/olivine/endmembers.py` (`ENSTATITE_DG_1830`, J per Mg2Si2O6 at 1830 K). On the measured
heat capacity it fell from 9.3 to 4.0 kJ (2026-10-02), most of the old value having stood in for
the extrapolated Cp. The heat-capacity change reaches the exchange and site-order data only
slightly (158 J per MgSiO3 at 1273 K); re-running the assessment above without refitting took
its cost from 46.9 to 36.5, every olivine-pyroxene tie-line moving toward the measurement.