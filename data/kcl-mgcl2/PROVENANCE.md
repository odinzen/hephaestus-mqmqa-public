# KCl-MgCl2 v0.1 — provenance and limits

Third open salt system, the concentrated-solar-storage binary, and the family's first
with a DIVALENT cation. Liquid SUBQ (K+1, Mg+2 / Cl-1) + KCl, MgCl2, and the double
salt KMgCl3. Built 2026-08-26. No value derives from any prior assessment or
commercial database.

## Endmembers (TKV evaluation via the workspace Chlorides reference system)

| | dHf(298) kJ | S298 J/K | Tm K | dHfus kJ | solid Cp |
|---|---|---|---|---|---|
| KCl | -436.558 | 82.55 | 1044.0 | 26.317 | own MK fit to Barin (shared with the other salts) |
| MgCl2 | -644.796 | 89.537 | 987.0 | 43.095 | R&H Maier-Kelley model 298-987 K (76.9, 8.496e-3, -7.463e5) |

Coordination: Z = 6 for both cations (MQM salt convention; the writer's new
per-component z_cat override), anion Z per pair from charge neutrality
(q_cat/Z_cat = q_an/Z_an: Cl gets 6 in the K pair, 3 in the Mg pair).

## KMgCl3 and the liquid (co-fitted, four targets, four parameters)

Barin holds no K-Mg chloride sheets, so KMgCl3's formation enthalpy AND entropy from
the endmember chlorides are own-fitted together with two liquid excess terms:

  dHf_ox = -2859.3 J/mol, dS_ox = +26.2 J/mol/K (Cp Neumann-Kopp)
  Delta_g(K,Mg)/Cl = -15895.0 - 88.5*chi_K J/mol (Z = 6)

| target | measured | model |
|---|---|---|
| KMgCl3 congruent melting (Perry & Fletcher 1993) | 761.65 K | 761.9 K |
| KCl-side eutectic (Xu 2018) | 697.55 K, x(MgCl2) 0.375 | 697.2 K, 0.376 |
| eutectic fusion enthalpy (Xu 2018, 207 J/g) | 17.04 kJ/mol | 17.06 kJ/mol |

The fitted pair says KMgCl3 is ENTROPY-stabilized (near-zero formation enthalpy,
+26 J/K formation entropy) - the same pattern as mullite. The (dHf, dS) pair is
determined jointly by these targets; independent solution calorimetry of KMgCl3
would pin them separately and is the designated v0.2 refinement.

## Predictions (reported, not fitted)

- **Mg-side eutectic: 727.3 K at x(MgCl2) = 0.588.** (Published diagrams place it
  near ~710 K at x ~0.62 - a ~17 K unfitted miss, in line with the family's
  prediction quality; those data are not yet in the gathered set.)
- The narrow K2MgCl4 / K3Mg2Cl7 stability window near the KCl-side eutectic is NOT
  resolved in v0.1: Perry & Fletcher's 699.15 K K2MgCl4/K3Mg2Cl7 eutectic and Xu's
  697.55 K point are treated as one feature (they differ by 1.6 K across sources).
  Resolving the window needs those compounds' thermochemistry - v0.2+.

## Validation

- Liquid GM matches pycalphad's sampled minimum at tight-bin tolerance (0 to -10 J
  per mole of atoms, 900 K) - the first divalent-cation SUBQ liquid through this
  pipeline.
- pycalphad equilibrium reproduces the topology: KMgCl3 single-phase field at 720 K,
  liquid above the eutectic, KCl + KMgCl3 below.
- Full engine test suite passes.

Repro: `build_dat.py` (writes KCl-MgCl2.dat), `v01_fit.py` (evaluates; `--fit`
re-optimizes the three main parameters; the dS_ox co-fit is recorded in git history).
