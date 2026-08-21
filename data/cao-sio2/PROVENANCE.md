# CaO-SiO2-liquid.dat provenance

Every number in `CaO-SiO2-liquid.dat` and its source. The database is built by
`build_dat.py`; this file records where each input comes from and how the derived
quantities are computed. All primary sources are open or public domain.

## Primary sources

- **Robie & Hemingway (1995)**, "Thermodynamic Properties of Minerals and Related
  Substances at 298.15 K and 1 Bar Pressure and at Higher Temperatures," U.S. Geological
  Survey Bulletin 2131. Public domain (U.S. government work).
  URL: https://pubs.usgs.gov/bul/2131/report.pdf
- **NIST-JANAF (Chase 1998)**, M. W. Chase, "NIST-JANAF Thermochemical Tables, 4th ed.,"
  J. Phys. Chem. Ref. Data, Monograph 9; NIST SRD 13. Open.
  URL: https://janaf.nist.gov/
- Cross-check only, not a primary: Barin & Platzki (1995), "Thermochemical Data of Pure
  Substances," 3rd ed., VCH. Copyrighted compilation; used only to confirm the open
  values agree (they do, to <0.2 percent), never transcribed as a parameter.

## Pure-oxide inputs (per formula unit)

| Symbol | CaO | SiO2 | Source (table/page) |
|---|---|---|---|
| dHf(298), from elements | -635100 J/mol | -908400 J/mol | R&H 1995, p.15 (lime), p.19 (cristobalite) |
| S(298), third law | 38.1 J/mol/K | 43.4 J/mol/K | R&H 1995, p.15 / p.19 |
| Cp a (J/mol/K) | 51.85 | 72.75 | R&H 1995, p.47 (lime) / p.50 (beta-cristobalite) |
| Cp b (J/mol/K^2) | 2.444e-3 | 1.300e-3 | R&H 1995, same |
| Cp c (J K/mol) | -9.340e5 | -4.132e6 | R&H 1995, same |
| Tm (fusion) | 3200 K | 1996 K | NIST-JANAF |
| dHfus | 79500 J/mol | 9581 J/mol | NIST-JANAF |

Heat capacity is the Haas-Fisher form Cp = a + b*T + c*T^-2 (the R&H d*T^-0.5 and e*T^2
terms are zero for both oxides). SiO2 uses the beta-cristobalite branch; the alpha branch
below 523 K and the small alpha/beta displacive transition are not resolved (a v0
approximation whose effect is negligible above 1700 K, where the liquid endmember is
used).

### Carried flags (from the source evaluations)

- CaO fusion Tm = 3200 K is high versus modern reassessments (~2845-2900 K), and dHfus is
  a JANAF ESTIMATE (assumed equal to MgO). This affects the CaO-rich liquidus and should
  be revisited with a primary CaO melting source before the CaO-rich edge is trusted
  quantitatively.
- SiO2 dHf spans ~5 kJ/mol by polymorph reference (quartz -910.9, low-cristobalite
  -908.4, high-cristobalite -905.5); the cristobalite basis is chosen to match the
  melting endmember.

## Derived endmember Gibbs energy

Each pure liquid-oxide endmember Gibbs energy is assembled as

    G_liq(T) = G_solid(T) + dHfus * (1 - T/Tm)
    G_solid(T) = dHf(298) + INT_298.15^T Cp dT - T * [S(298) + INT_298.15^T (Cp/T) dT]

with dCp_fus = 0 (a v0 choice; the liquid heat capacities are recorded in the inventory
for a later refinement). Integrating the Haas-Fisher Cp gives the six ChemSage
coefficients on the term basis (1, T, T*lnT, T^2, T^3, 1/T); the closed forms are in
`build_dat.py` (`solid_gibbs_coeffs`). The resulting coefficients are:

- CaO(liq):  A=-574300.357, B=+290.30880, C=-51.85, D=-1.222e-3, E=0, F=+467000
- SiO2(liq): A=-934425.989, B=+462.67897, C=-72.75, D=-6.50e-4, E=0, F=+2066000

These are verified two ways in `validate.py`: (1) the C engine reads them back and they
match an independent H - T*S evaluation of the same R&H/JANAF data to ~1e-3 J/mol
(round-off from the 8-figure coefficients), and (2) they reproduce the published fusion
points, dG_fus = G_liq - G_solid = 0 at Tm(SiO2)=1996 K and Tm(CaO)=3200 K.

## Model-structure choices (not fitted physics, no proprietary content)

- **Species:** cations Ca+2, Si+4; anion O-2. Pairs CaO (Ca+2/O-2) and SiO2 (Si+4/O-2).
- **Coordination numbers Z:** charge-proportional, Z = 0.68872 * charge, i.e. Z(Ca+2)=Z(O-2)=1.37744,
  Z(Si+4)=2.75489. This is the standard FactSage-style oxide convention (base 1.3774438
  per divalent cation) and defines the ideal reference; it is a framework default, not an
  optimized value. The mixed-cation quadruplet coordination is derived by the engine from
  these pure values. Framework references: Pelton, Degterov, Eriksson, Robelin,
  Dessureault, "The modified quasichemical model I - Binary solutions," Metall. Mater.
  Trans. B 31 (2000) 651-659, DOI 10.1007/s11663-000-0103-2; Pelton & Chartrand, "The
  modified quasi-chemical model: Part II. Multicomponent solutions," Metall. Mater. Trans.
  A 32 (2001) 1355-1360, DOI 10.1007/s11661-001-0226-3.
- **Pair zeta:** 1.3774438 (the divalent-oxygen base value) for both pairs.
- **Excess (MQMX) parameters:** none. The interior mixing is ideal in v0.1. The ordering
  energy that produces the eutectics and the negative-deviation activities is intentionally
  absent because no open source publishes it in SUBQ form; it is neither fabricated nor
  taken from any proprietary source.

## Statement on sources

This database was built only from published, open, or public-domain sources (Robie &
Hemingway 1995; NIST-JANAF). No FactSage/FToxid parameters, no proprietary fitted TDB
parameters, and none of the assessment workspace's own-derived or ESPEI-fit liquid
interaction parameters were used. The independent H - T*S derivation in `build_dat.py`
happens to reproduce the workspace's separately built endmember functions to full
precision, which cross-validates both; the shared inputs are the open R&H/JANAF data, not
any fitted result.
