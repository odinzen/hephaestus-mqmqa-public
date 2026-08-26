# Al2O3-SiO2 v0.1 — provenance and limits

Third slag binary and the opening brick of the CaO-Al2O3-SiO2 ternary campaign. MQMQA
liquid (Si+4, Al+3 / O-2; components SiO2 and AlO1.5) + cristobalite, corundum, and
mullite. Built 2026-08-26 from the gathered set (Rankin & Wright 1915; Robie & Hemingway
1995) plus the endmembers already shipped with the family. No value derives from any
prior assessment or commercial database.

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

## The compound-identity revision (why only one R&W invariant is used)

Rankin & Wright (1915) drew this binary with "sillimanite" (Al2SiO5, 62.9 wt% Al2O3)
as the compound; Bowen & Greig (1924) showed the stable compound is mullite (71.8 wt%).
R&W's Al-rich invariants (their congruent melting at 2089 K and their compound-corundum
eutectic at 64 wt%) are therefore topologically unusable with the modern compound - a
eutectic at 64 wt% cannot sit between mullite and corundum. Their silica-side eutectic
does not suffer from this and is the fitted target:

  cristobalite + compound eutectic: 1883.15 K, liquid 13 wt% Al2O3 (x_AlO1.5 = 0.1497).

## Liquid excess (fitted)

Delta_g(Si,Al)/O = 9317.3 + 33855.3*chi_Si^5   J/mol   (Q-code (0,0) + (5,0) terms)

Fitted 2026-08-26; the eutectic is reproduced exactly (1883.2 K, x = 0.150). The
silica-local chi_Si^5 form is the family's established silica-side lever; a global
positive term was tried and rejected (it drags the eutectic composition silica-ward
and overheats the mullite liquidus). Verified: no stable liquid demixing anywhere on
the join at 1900-2300 K.

## Predictions (reported, not fitted)

- Mullite melts CONGRUENTLY at 2291 K in this model; the mullite + corundum eutectic
  sits at 2239 K, x_AlO1.5 = 0.88. The literature is famously split - Aksay & Pask:
  peritectic ~2101 K; Klug: congruent ~2163 K. v0.1 lands on the congruent side,
  ~130 K above Klug; the Al-rich liquid is unconstrained by data here, and this is the
  known weak flank (a v0.2 would fit Al-rich liquidus data and/or melt-mixing
  enthalpies from an MLIP triangulation, the family method).

## Validation

- All three solids, including the sqrt-T mullite block, match pycalphad to machine
  precision at 1000 and 1900 K.
- The liquid converges onto pycalphad's sampled minimum (2.6-6.3 J/mol-atom at bin
  1e-4, sampling-limited), 2000 K.
- Full engine test suite passes.

Repro: `build_dat.py` (writes Al2O3-SiO2.dat; carries the sqrt-term stoich writer),
`v01_fit.py` (evaluates; `--fit` re-optimizes).
