# Contributing to Hephaestus

Thanks for your interest. Hephaestus is a small C engine for the Modified Quasichemical Model
(MQMQA) with a Python wrapper and an in-browser WebAssembly build, plus an open database of
assessed systems. Code is MIT; the `data/` directory is CC BY 4.0.

## The one rule that matters most: don't decide the science on software grounds

This project has two kinds of authority. **Code** — architecture, the browser app, tooling,
tests, refactors — is open to contribution in the usual way. **Science** — the thermodynamic
models, the assessed parameters under `data/`, the validation tolerances, and any computed
result — belongs to the maintainer.

So: if a change would **alter a validated number, touch a physics assumption or a load-bearing
constant, change a validation tolerance, or hinge on a thermodynamic judgment** (for example,
loosening a tolerance to make a pycalphad or Cantera comparison pass, or editing a fitted
parameter), **stop and raise it with the maintainer first** — in an issue or a short write-up,
not silently in a pull request. A code contributor is not expected to adjudicate whether a
numerical shift is an acceptable change or a regression; only the maintainer can.

This is rare in practice — tooling, UX, and refactors almost never touch the science — but it is
the one thing to escalate rather than settle in a commit. When in doubt, ask.

Concretely, treat these as science, not code:
- Anything under `data/` (assessed parameters and their `PROVENANCE.md`) — read-only unless the
  maintainer directs a change.
- Load-bearing constants in `src/` (for example the CALPHAD gas constant `R = 8.3145`, the
  per-mole-atom normalization, coordination numbers, NASA polynomial coefficients).
- The numbers and tolerances in `tests/` that compare against pycalphad or Cantera.

## How the project is validated

Every energy path and equilibrium is checked against **pycalphad** (condensed phases) and
**Cantera** (gas), used as independent truth oracles, never as runtime dependencies. A change to
the engine should keep those comparisons passing at their existing tolerances. See the tests in
`tests/` for the pattern.

## Building and running

- Native library: `bash scripts/build.sh` builds `python/mqmqa/mqmqa.dll` (clang is required).
- Tests: `pytest` from the repo root, in an environment with pycalphad, Cantera, and scipy.
- Browser engine: `bash scripts/build_wasm.sh` builds `web/hephaestus.js` (emscripten). Rebuild
  and re-commit it whenever `src/` changes, or the browser app diverges from the library.
- Serve the app locally: `python -m http.server -d web`, then open `index.html`.

## Provenance and licensing boundary

Hephaestus is a clean-room implementation of published model equations (Pelton et al. 2001;
Poschmann et al. 2021). Do not copy code, algorithms, or solver internals from any other
implementation. The database is assembled only from published experimental data with per-value
provenance. Contributions must respect the same boundary.

## Getting in touch

Open an issue on GitHub for bugs, questions, or a proposed change. For a new database system or
a substantial contribution, describe it first so we can agree on scope and provenance before you
invest the work.
