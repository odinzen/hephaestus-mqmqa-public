# NaCl-KCl v0.1 — provenance and limits

Second open salt system, and the family's first with a SOLID SOLUTION: a minimum-type
liquidus over the continuous (Na,K)Cl halite solution with a low-temperature solvus.
Built 2026-08-26. No value derives from any prior assessment or commercial database;
the Sangster & Pelton (1987) evaluation is used only for one fitted feature (the solvus
consolute temperature) and one pure validation target (the liquidus minimum).

## Endmembers (per mole salt; TKV evaluation via the workspace Chlorides reference system)

| | dHf(298) kJ | S298 J/K | Tm K | dHfus kJ | solid Cp (own Maier-Kelley fit to Barin points) |
|---|---|---|---|---|---|
| NaCl | -411.412 | 72.132 | 1074.15 | 28.200 | a 41.1961, b 2.280119e-2, c +2.46588e5 (298-1000 K, max resid 0.63) |
| KCl | -436.558 | 82.55 | 1044.0 | 26.317 | a 40.5254, b 2.498808e-2, c +2.9839e5 (same endmember as LiCl-KCl) |

## Liquid (SUBQ, Na+1/K+1/Cl-1, Z = 6 salt convention)

One Q-code term, enthalpy only, fitted to the measured Hersh & Kleppa (1965) mixing
enthalpy: L = -715.1 J/mol reproduces dH_mix(x = 0.5, 1083 K) = -547 J/mol exactly.
(H&K's interaction parameter -2050 J/mol is held in the workspace as the companion
record; the model's small negative L is consistent with it.)

## Halite (Na,K)Cl (CEF, one mixing site)

Regular-solution excess W = 2R*768.15 = 12773.6 J/mol, i.e. the solvus consolute is
built in from the evaluated 768.15 K (T_c = W/2R for one ideally-mixing site).
Verified numerically: the model's consolute reproduces 768.1 K, and pycalphad
equilibrium at 700 K gives two coexisting halites at site fractions 0.251/0.749
(the symmetric solvus).

## Validation

- **Liquidus minimum (not fitted): predicted 913.6 K at x_KCl = 0.530 vs the
  evaluated 931.15 K** — a 17.6 K prediction miss with nothing in the liquidus
  fitted; endmember fusion data quality sets this scale.
- Halite endmembers match the analytic solid Gibbs to machine precision in the
  engine; pycalphad reads the same file and reproduces the full topology
  (liquid above the minimum, halite below, the melting lens, the two-halite solvus).
- The browser's binary diagram card renders the system with the new
  solid-solution support (CEF phases on the join are sampled into the hull).

## Known limits

- v0.1 carries the H&K point and the consolute; the liquidus/solidus SHAPE between
  the endmember meltings is a prediction (17.6 K low at the minimum). Fitting the
  measured liquidus would be the v0.2 refinement.
- The solvus is symmetric by construction (one regular parameter); the measured
  solvus is slightly asymmetric.
- In the browser card the solvus region renders as undifferentiated subsolidus
  shading (the two-halite field is not visually separated from single-phase halite).

Repro: `build_dat.py` (writes NaCl-KCl.dat: SUBQ liquid + SUBL halite),
`v01_fit.py` (evaluates; `--fit` re-derives L from the H&K point).
