# Al2O3-SiO2 v0.2 - provenance and limits

Third slag binary and the opening brick of the CaO-Al2O3-SiO2 ternary campaign. MQMQA
liquid (Si+4, Al+3 / O-2; components SiO2 and AlO1.5) + cristobalite, corundum, and
mullite. Built 2026-08-26 from the gathered set (Rankin & Wright 1915; Robie & Hemingway
1995) plus the endmembers already shipped with the family. No value derives from any
prior assessment or commercial database.

## v0.2 (2026-09-30): refit to Bowen & Greig 1924

v0.1 was fitted to one number, the Rankin & Wright (1915) silica-side eutectic (1883 K, 13 wt%
Al2O3). That value belongs to the sillimanite picture Bowen & Greig (1924) overturned: they
measured the cristobalite + mullite eutectic at 1545 +- 5 C (1818 K) and 5.5 wt% Al2O3, and the
mullite liquidus from 7 to 50 wt%. v0.2 is fitted to their quench brackets
(`assessment/bowen_greig1924.csv`, read from the page images of the public-domain scan, Tables Ia
and Ib, pp. 243-244), each liquidus point scored only where the liquid is stable
(`assessment/assess.py`):

| Data | Measured | v0.2 |
|---|---|---|
| eutectic T, x_AlO1.5 | 1818 K, 0.064 | 1846 K, 0.064 |
| mullite liquidus, 7-50 wt% (5 points) | 1888-2073 K | within 31 K |
| cristobalite liquidus, 5 wt% | 1888 K | 1849 K |
| corundum liquidus, 70.6 wt% | 2185 K | mullite first at 2139 K |

Cost 131 -> 15.3. Their 5 wt% cristobalite point sits 70 K above an eutectic 0.5 wt% away,
likely read high from slow cristobalite solution in these viscous melts, and carries a 30 K
sigma. The corundum point is the disputed mullite melting (below): the model melts mullite
congruently, so mullite, not corundum, crystallizes first there.

Liquid excess, Q terms (p on SiO2, q on AlO1.5), J/mol:

    (0,0) 80191.65 - 23.25 T    (5,0) -1234.85 - 0.75 T    (0,1) -23050.36 - 2.08 T

Temperature parts carry a prior of 0 +- 15 J/K. No stable liquid demixing anywhere on the join
at 1700-2400 K (checked on the liquid alone). The terms live in `build_dat.ASSESSED_EXCESS`;
the CaO-Al2O3-SiO2 file reads them there.

Mullite (below) is unchanged: the Robie & Hemingway Cp equation it carries matches their
high-temperature table (`rh1995_mullite.csv`, bulletin p. 307, extracted by script) within 7 J
to 1800 K.

## Endmembers

- **SiO2** (cristobalite branch) and **AlO1.5** (corundum, per-cation unit): reused
  verbatim from the shipped CaO-SiO2 and CaO-Al2O3 systems.

## Mullite (Al6Si2O13, 3Al2O3.2SiO2)

Robie & Hemingway (1995): dHf = -6819.2 kJ/mol, S298 = 275.0 J/mol/K, Haas-Fisher Cp
with a T^-0.5 term (a 754.6, b -0.02943, c -3.454e6, d -6576). The d-term is carried
EXACTLY: the Gibbs function gains a 4d*sqrt(T) additional term (with -2d*sqrt(T0) and
-2d/sqrt(T0) folded into the constant and linear coefficients), written to the ChemSage
additional-terms slot as (coefficient, 0.5) - the same mechanism the olivine endmembers
use, now extended to stoichiometric blocks. A plain Maier-Kelley refit was tried and
rejected (19 J/mol/K Cp error at 298 K, integrating into real Gibbs error).

Consistency: formation from corundum + cristobalite gives dH_ox = +24.7 kJ/mol with
dS_ox = +35.4 J/mol/K - mullite is entropy-stabilized, oxide-stable above ~700 K, which
is the physically correct picture.

The Al2SiO5 polymorphs (kyanite, andalusite, sillimanite; R&H data are in the
workspace manifest) are deliberately absent: mullite is the stable compound on the
1-atm melting diagram.

## Mullite melting (reported, not fitted)

v0.2 melts mullite congruently at 2140 K, with the mullite + corundum eutectic at 2136 K and
x_AlO1.5 = 0.80. The literature is split: Bowen & Greig 1924 saw mullite break down to corundum
+ liquid at 1810 +- 10 C (2083 K); Aksay & Pask put it peritectic near 2101 K; Klug et al.
congruent near 2163 K. v0.2 sits between the congruent and peritectic readings. Rankin &
Wright's own Al-rich invariants assume sillimanite (62.9 wt%) and cannot be placed with mullite
(71.8 wt%); they are not used.

## Validation

- All three solids, including the sqrt-T mullite block, match pycalphad to machine
  precision at 1000 and 1900 K.
- The liquid converges onto pycalphad's sampled minimum (2.6-6.3 J/mol-atom at bin
  1e-4, sampling-limited), 2000 K.
- Full engine test suite passes.

Repro: `build_dat.py` (writes Al2O3-SiO2.dat with the assessed liquid; carries the sqrt-term
stoich writer), `assessment/assess.py` (v0.2 fit; `--fit` re-optimizes), `v01_fit.py`
(invariant report; its `--fit` is the superseded v0.1 fit).
