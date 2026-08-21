# Design and paper plan

Target: a single **JORS** (Journal of Open Research Software) metapaper, single author,
presenting **both** the open MQMQA engine and the first open oxide-slag database. The
build maps onto the JORS section structure so "done" is well defined.

## The contribution

A free, dependency-light, browser-runnable Modified Quasichemical Model (quadruplet
approximation) engine, plus an openly-licensed oxide-slag database it runs. Together they
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

Seed the open oxide-slag database from `odinzen_assessment_workspace/assessments/` (digitized
literature: CaO-SiO2 first, the classic Pelton-Blander MQM system, then the CaO-Al2O3-SiO2
ternary). CC-BY-4.0. Grows as the work matures. The engine also runs the free MSTDB-TC salt
database unchanged, giving an immediate demo without any assessment work.

## Availability and archiving (JORS requires this)

- Engine MIT, database CC-BY-4.0.
- Public GitHub repo, tagged release archived to Zenodo for a citable DOI.
- Versioned; dependencies documented; tests runnable.

## Boundaries

Clean-room from the papers only. No reuse or mention of the Odinzen Rust kernel. No FactSage
code, database, or trademark; only open data. Nothing of Michael's existing proprietary work
is released.

## Status

Walking skeleton verified (C -> clang/mingw DLL -> cffi -> Python). Next: reference-energy
term in C, validated against pycalphad on a concrete slag sub-case.
