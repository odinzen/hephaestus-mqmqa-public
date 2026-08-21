# Design and paper plan

Target: a single **JORS** (Journal of Open Research Software) metapaper, single author,
presenting **both** the open MQMQA engine and the first open oxide-slag database. The
build maps onto the JORS section structure so "done" is well defined.

## The contribution

A free, dependency-light, browser-runnable Modified Quasichemical Model (quadruplet
approximation) engine, **Hephaestus**, plus an openly-licensed oxide-slag database it runs. Together they
are a complete open path for slag/salt thermodynamics that today requires commercial
software. The reuse hook is zero-install, in-browser access (WASM) and thin language
bindings.

## Architecture

- **C core** (`src/`): MQMQA Gibbs energy of one mole of quadruplets as a function of the
  quadruplet fractions, plus the equilibrium solve (minimise G at fixed composition).
- **Python binding** (`python/mqmqa/`, cffi ABI): load the prebuilt library, no compiler at
  import.
- **WASM build** (later): same C compiled with emscripten for the browser calculator.
- **ChemSage `.dat` reader**: ingest existing open databases (MSTDB-TC salts on day one),
  not a new format. Interop over novelty.

## The model (implemented clean-room from the papers)

Sources: Pelton, Chartrand, Eriksson 2001 (MMTA 32:1409); Poschmann 2021 (Calphad 75:102341).
G = G_reference + G_ideal_mixing (the quadruplet configurational entropy) + G_excess.
Two sublattices (cations / anions), quadruplets (i,j / k,l), coordination numbers Z and the
zeta (quadruplets-per-pair) terms, SUBQ and SUBG variants. Build term by term.

## Quality control (the JORS QC section)

1. **Energy terms vs pycalphad.** For identical parameters and quadruplet fractions, each C
   contribution (reference, ideal-mix, excess) must match `pycalphad.models.model_mqmqa` to
   tight tolerance. pycalphad is the oracle (already runs the Shishin Fe-Sb-S-O slag `.dat`
   here, GM ~ -241 kJ/mol-quad at 1873 K).
2. **Equilibrium vs Thermochimica** and against published invariants where available.
3. **Database vs experiment.** The seed slag database must reproduce known CaO-SiO2 and
   CaO-Al2O3-SiO2 phase equilibria (Rankin & Wright 1915, Kay-Taylor 1960, Zaitsev 1997).

## The database

Seed the open oxide-slag database from our own digitized literature assessments (CaO-SiO2
first, the classic Pelton-Blander MQM system, then the CaO-Al2O3-SiO2 ternary). CC-BY-4.0.
Grows as the work matures. The engine also runs the free MSTDB-TC salt database unchanged,
giving an immediate demo without any assessment work.

## Availability and archiving (JORS requires this)

- One repository, two licenses: the engine code is MIT (root `LICENSE`); the open slag
  database lives under `data/` with its own CC-BY-4.0 license.
- Public GitHub repo, tagged release archived to Zenodo for a citable DOI.
- Versioned; dependencies documented; tests runnable.

## Boundaries

Clean-room from the published papers only; no proprietary code is reused. The open slag
database is assembled solely from published experimental literature (digitized phase
diagrams and calorimetry); no closed, optimized, or otherwise proprietary database
parameters go into it. No FactSage code, database, or trademark; only open data.

## Status

Energy path complete and validated to machine precision against pycalphad: reference,
ideal-mixing, and excess (Q code any exponents; G code zero exponents), plus coordination
numbers Z (recursive, including reciprocal quadruplets).

ChemSage `.dat` reader done (`src/cs_dat.c`): parses the header, SUBQ/SUBG phases (pairs,
charges, chemical groups, MQMZ coordinations, MQMX excess), and stoichiometric compounds,
into an in-memory database with no pycalphad. Validated by loading the reader's own data
into the energy routines and reproducing pycalphad's reference/ideal/excess on the Shishin
Fe-Sb-S-O slag (SUBQ, reciprocal), a Cu-Ni SUBG salt, and the KF-NiF2 SUBG salt. Reads the
open MQMQA `.dat` files in pycalphad's test set (KF-NiF2, Ocadiz-Flores, tern-tests).

Next, in order: (1) excess-model follow-ons the reader unlocks (nonzero-exponent G via
Chi_mix, Bragg-Williams B/H, reciprocal R); (2) the equilibrium solver (minimise G over
quadruplet fractions at fixed composition); (3) WASM build and the browser calculator.
Databases containing non-MQMQA solution phases (QKTO, SUBL) are not yet read.
