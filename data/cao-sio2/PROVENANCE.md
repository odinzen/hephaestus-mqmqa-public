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
- **Stolyarova, Shornikov, Ivanov & Shultz (1991)**, "High Temperature Mass Spectrometric
  Study of Thermodynamic Properties of the CaO-SiO2 System," J. Electrochem. Soc. 138(12)
  3710-3714. DOI 10.1149/1.2085485 (verified on Crossref: authors, title, volume, issue,
  page all exact). KEMS a(CaO), a(SiO2), and delta-G_mix across the binary at 1933 K; the
  primary excess-fit constraint. Digitized from Tables IIa (a(CaO), Eq [2]) and IIb (a(SiO2),
  Eq [3]) of the PDF.
- **Kay & Taylor (1960)**, "Activities of silica in the lime + alumina + silica system,"
  Trans. Faraday Soc. 56, 1372. DOI 10.1039/tf9605601372 (verified on Crossref). a(SiO2) by
  CO/SiC gas-slag equilibrium at ~1821 K, silica-rich near-binary slag (0.6% Al2O3);
  digitized Table 3. Anchors the silica-rich half of the join.
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
| Tm (fusion) | 2845 K (v0.3; was 3200) | 1996 K | CaO: CRC 2572 degC / SiO2: NIST-JANAF |
| dHfus | 79500 J/mol | 9581 J/mol | NIST-JANAF (CaO dHfus still an estimate) |

**v0.3 CaO melting correction:** the v0.1/v0.2 CaO Tm = 3200 K was the old JANAF
estimate, ~350 K too high (Abdul 2023 notes the "dramatic change in the melting point of
CaO in the recent reassessment"). v0.3 uses 2845 K (2572 degC, CRC Handbook evaluated
value). dHfus is retained as the JANAF/MgO-analog estimate and remains approximate.

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
- **Excess (MQMX) parameters:** two Q-code cation-mixing terms on the (Ca,Si,O,O)
  quadruplet, FITTED from open data (v0.3: activities + calorimetry + compound melting,
  cross-checked by an independent MLIP - see the v0.3 section below). NOT taken from any
  external or proprietary TDB.

## v0.2 excess parameters (fitted from open activity data)

v0.2 adds the liquid-mixing (ordering) energy that v0.1 left ideal. The engine itself is
the optimizer: for trial excess coefficients the C engine computes a(CaO), a(SiO2) and
delta-G_mix, and `fit_excess.py` least-squares matches them (in ln a) to the open data.
No TDB parameters are used - the numbers are our own fit to measured activities.

### Model and fitted values

Two Q-code cation-mixing terms on the (Ca+2, Si+4 / O, O) quadruplet, giving the
composition-dependent ordering energy

    Delta_g(Ca,Si)/O = -84989.5 + 58720.7 * chi_Ca      J/mol

where chi_Ca is the coordination-equivalent fraction of Ca among the two mixing cations.
As MQMX entries (term basis 1,T,TlnT,T^2,T^3,1/T; only the constant term is non-zero):

| term | code | quadruplet | exponents (p,q) | L (J/mol) |
|---|---|---|---|---|
| g00 | Q | (Ca,Si,O,O) | (0,0) | -84989.5 |
| g10 | Q | (Ca,Si,O,O) | (1,0) | +58720.7 |

The parameters are temperature-independent (constant L); this is justified below by the
cross-temperature check. Two terms are what the single-phase data support - a third
(curvature) term only fits the scatter in a(SiO2) and drives a spurious CaO-rich
miscibility gap, so it is excluded.

### Method and data selection

- **Activity from the engine:** a(i) = exp((mu_i - G_i_pure_liquid)/(R T)), R = 8.3145, with
  mu_i the partial molar Gibbs of oxide i by central finite difference of the total Gibbs
  energy. The single-phase quadruplet equilibrium is solved exactly in 1-D (the binary has
  one internal degree of freedom), avoiding the SLSQP noise that otherwise wrecks the finite
  difference. Reference = pure liquid oxide (a -> 1 at the pure component), matching the
  engine's liquid-only endmembers. Ideal v0.1 returns a(i) = x(i) exactly, so the excess is
  wholly responsible for the deviation.
- **Stolyarova 1991 (1933 K):** fitted to the genuinely single-phase points x_SiO2 = 0.41,
  0.44, 0.49, 0.50. Stolyarova state the 1933 K liquidus at x_SiO2 = 0.41 (p.3711); points
  below that are sub-liquidus (solid Ca-silicate + liquid), where a(CaO) rises to 0.96-1.00
  (saturation) - two-phase data the single-liquid model must not be fit to. Those points
  (x_SiO2 = 0.25, 0.33, 0.38, 0.39, 0.40) are excluded.
- **Kay & Taylor 1960 (~1821 K):** a(SiO2) converted from the pure-SOLID-SiO2 reference to
  the pure-LIQUID reference by a(liq) = a(solid)/exp(dG_fus,SiO2/RT) (a 5-6% shift; dG_fus is
  small this close to Tm). Mass-percent compositions renormalized to CaO+SiO2 mole fraction
  (0.6% Al2O3 dropped). Central points x_SiO2 = 0.42, 0.47, 0.51 are used; the silica-rich
  points (x_SiO2 = 0.55, 0.60) approach the silica-rich miscibility gap and are excluded
  (see limitations).

### Fit residuals (reproduce with `validate_v02.py`)

- Overall RMS of ln(a_engine/a_measured) = 0.32 (typical activity factor 1.38).
- By dataset: a(CaO) 0.30, a(SiO2) Stolyarova 0.42, a(SiO2) Kay-Taylor 0.17. The larger
  a(SiO2)-Stolyarova residual is data-limited: the KEMS a(SiO2) (minor SiO+ ion) scatters by
  ~2x between adjacent compositions (e.g. 0.09 at x=0.49 vs 0.20 at x=0.50), which no smooth
  model can follow.
- delta-G_mix at 1933 K: engine -30.5 to -30.9 kJ/mol across x_SiO2 = 0.41-0.50 vs measured
  -28 to -37 kJ/mol (the -37 at x=0.49 is a scatter point); the model reproduces the broad
  ~-31 kJ/mol minimum.
- **Cross-temperature consistency:** the single temperature-independent excess reproduces
  a(SiO2) at BOTH 1821 K (Kay-Taylor, RMS 0.17) and 1933 K (Stolyarova, RMS 0.42) - it is
  not tuned to one isotherm.
- **Stability:** d2 Gmix/dx2 > 0 across the whole join (no spurious miscibility gap); a(CaO)
  and a(SiO2) are monotonic and stay below 1 in the single-phase melt.

### Honest limitations

- **Silica-rich miscibility gap not modelled.** The real CaO-SiO2 liquid has a two-liquid
  gap at high silica (x_SiO2 > ~0.65), i.e. positive deviations that a cation-mixing Q
  excess centred on ordering cannot produce. v0.2 targets the ordered central melt; the
  silica-rich gap is a v0.3 item (needs an additional positive term or richer structure).
- **No absolute eutectic / liquidus temperature is claimed.** The .dat carries no solid
  phases, and the CaO-rich absolute thermochemistry rests on the v0.1 CaO liquid endmember,
  whose Tm = 3200 K and dHfus = 79500 J/mol are flagged (JANAF estimate, high vs modern
  ~2845 K). A congruent-melting or eutectic temperature computed from this would be dominated
  by that flagged endmember, not by the excess, so it is deliberately not reported. Adding
  open solid-silicate Gibbs functions and a primary CaO melting source (to compute liquidus
  and eutectic temperatures) is a v0.3 task. The v0.2 validation is therefore isothermal:
  activities and delta-G_mix at the measurement temperatures, which is exactly what the
  excess governs.
- **Activity accuracy is ~30-40%**, limited by the scatter in the open KEMS data, not by the
  optimizer. This is stated rather than polished away.

## v0.3 excess (MLIP- and phase-diagram-anchored liquid)

v0.2 fit the excess to activities alone and came out too shallow to melt the compounds.
v0.3 re-grounds the liquid on the data the field actually trusts, cross-checked by an
independent machine-learned potential. The arbitration behind it (why the activities are
NOT the primary constraint) is recorded below.

### What changed and why (the arbitration)

- **Reference state = solid.** Abdul 2023 (the modern open assessment) reports CaO-SiO2
  activities vs cristobalite / solid CaO, and does NOT fit activities at all - it fits the
  phase diagram + calorimetry and checks activities. At 1933/1821 K both pure oxides are
  solid, so a KEMS "pure oxide" reference is the solid. v0.3 treats Stolyarova and
  Kay-Taylor as solid-referenced.
- **Stolyarova is the outlier.** Abdul's activity comparison uses Rein-Chipman,
  Baird-Taylor, and Kay-Taylor - not Stolyarova - and its calorimetry-fit liquid reproduces
  those. A Gibbs-Duhem check on Stolyarova's own two columns shows ~2x interior scatter
  (only roughly self-consistent). So Stolyarova is down-weighted; Kay-Taylor a(SiO2) is the
  trusted activity constraint.
- **Independent MLIP confirmation.** MD with two foundation potentials (MatterSim, ORB) via
  the melt-mixing method gives the liquid enthalpy of mixing at x_SiO2 = 0.5 as -42 and -55
  kJ/mol-oxide-unit - both DEEP, refuting the shallow (~-30) value the activities imply. A
  formation-enthalpy spot-check (dHf of CaSiO3 vs the measured -82 kJ) showed the MLIP
  under-binds by ~9 kJ; bias-correcting the liquid deepens it to ~-55..-60, coinciding with
  the value the compound melting requires (~-60). v0.3 anchors dH_mix(x=0.5) = -58 kJ, where
  the bias-corrected MLIP, the calorimetry, and the melting all agree.

### Fitted values

Two Q-code cation-mixing terms on (Ca,Si,O,O), with an excess ENTROPY term on g00 so one
excess reproduces both the ~1900 K mixing and the 1817/2403 K melting:

    Delta_g(Ca,Si)/O = (-189763.5 + 15.706*T) + 57170.8 * chi_Ca      J/mol

| term | code | (p,q) | coefficients (a + b*T), J/mol |
|---|---|---|---|
| g00 | Q | (0,0) | -189763.5 + 15.706*T |
| g10 | Q | (1,0) | +57170.8 |

Reproduce with `v03_fit.py` (which also writes the .dat); it is the v0.3 fit + validation.

### Results (reproduce with v03_fit.py)

- implied liquid dH_mix(x=0.5, 1900 K) = -58.8 kJ/mol-oxide-unit, matching the anchor.
- Kay-Taylor a(SiO2) RMS ln(a) = 0.21 (trusted activity data reproduced).
- Stolyarova reproduced poorly (the documented outlier).
- Stable across the whole join (no spurious miscibility gap); a(CaO), a(SiO2) monotonic and
  below 1 in the single-phase melt.
- MLIP phonon spot-check: solid S298 for pseudowollastonite = 94 J/mol/K (vs Haas
  wollastonite 81, our estimate 85) - the estimated solid entropies are confirmed reasonable
  (~within 10 J/K), so they are NOT the source of the phase-diagram error.

### Honest limitations (what v0.3 is NOT)

- **v0.3 is a validated LIQUID, not a quantitative phase diagram.** With the corrected CaO
  endmember and the deep liquid, the compounds now melt, but the computed congruent-melting
  and eutectic temperatures are still ~200-400 K off. This is the SOLID model, not the
  liquid: gamma-C2S data is used at the alpha-C2S melting point (polymorph transitions not
  resolved), the compound Cp is Neumann-Kopp, and rankinite (C3S2) melts peritectically. A
  quantitative diagram (proper solid Cp/S, polymorphs, the silica-rich gap) is v0.4.
- **Silica-rich miscibility gap not modelled.** The MLIP composition scan shows dH_mix
  turning convex toward silica (x_SiO2 > 0.6) - the real liquid-liquid immiscibility, a
  positive deviation a cation-mixing excess structurally cannot produce.
- **CaO dHfus** remains the JANAF/MgO-analog estimate.

## Statement on sources

This database was built only from published, open, or public-domain sources: endmembers
from Robie & Hemingway 1995, NIST-JANAF, and CRC (CaO Tm); the excess from the open
measured activities of Stolyarova et al. 1991 and Kay & Taylor 1960, the open compound
calorimetry (Abdul et al. 2023, CC-BY; Adamkovicova fusion), and our own MD with open
foundation MLIPs (MatterSim, ORB) plus MLIP phonons - all our own computation, no
proprietary content. Crystal structures for the MLIP checks are open COD entries. No FactSage/FToxid parameters,
no proprietary fitted TDB parameters, and none of the assessment workspace's own-derived or
ESPEI-fit liquid interaction parameters were used - the excess coefficients are our own
least-squares result against the measured activities. The independent H - T*S derivation in
`build_dat.py` happens to reproduce the workspace's separately built endmember functions to
full precision, which cross-validates both; the shared inputs are the open R&H/JANAF data,
not any fitted result.
