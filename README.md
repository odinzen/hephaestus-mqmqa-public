# Hephaestus

**Hephaestus** is a small, standalone engine for the **Modified Quasichemical Model in
the Quadruplet Approximation (MQMQA)**: a C core with a thin Python wrapper. The MQMQA
describes short-range ordering in ionic liquids (molten salts, oxide slags,
electrolytes), the physics behind FactSage's oxide/slag databases. Named for the god of
the forge, it computes the thermodynamics of the melt.

The scientific model is MQMQA (a standard acronym); the engine that implements it is
Hephaestus. The library is currently imported as `mqmqa`.

## Scope and honest positioning

This is a lightweight, framework-independent MQMQA energy library, meant to be
embedded or called from other codes without pulling in a full CALPHAD stack.

It is not the first open MQMQA. pycalphad already ships one
(`pycalphad.models.model_mqmqa`, Paz Soldan Palma et al., Calphad 2023). This
library's value is being small, dependency-light, and callable from C or Python
directly. pycalphad is used here as the validation oracle, not as a dependency.

## Provenance (clean-room)

The model is implemented from the published literature only:

- Pelton, Chartrand, Eriksson, "The Modified Quasi-chemical Model: Part IV.
  Two-Sublattice Quadruplet Approximation," Metall. Mater. Trans. A 32 (2001)
  1409, doi:10.1007/s11661-001-0230-7.
- Poschmann, Bajpai, Fitzpatrick, Piro, "Recent developments for molten salt
  systems in Thermochimica," Calphad 75 (2021) 102341,
  doi:10.1016/j.calphad.2021.102341.
- Paz Soldan Palma et al., "Thermodynamic modeling with uncertainty quantification
  using the modified quasichemical model in quadruplet approximation: Implementation
  into PyCalphad and ESPEI," arXiv:2204.09111, Eqs 8-10 (the chemical-group excess
  interpolation of Pelton et al., restated).

No code, algorithms, or solver internals from any other implementation are used.

## Validation

Every energy contribution (reference, ideal mixing, excess) is checked against
pycalphad's MQMQA on shared parameters to tight tolerance, and against published
values for the classical systems (CaO-SiO2 silicate slag; the KF-NiF2 reciprocal
salt from the 2023 pycalphad paper). Nothing is claimed working until it matches.

## Status

The C core is complete and validated to machine precision against pycalphad: the full
MQMQA energy path (reference, ideal mixing, excess with its chemical-group interpolation
and additional-constituent terms of any order, recursive coordination numbers), a
ChemSage `.dat` reader (SUBQ/SUBG liquids, SUBL solid solutions, stoichiometric
compounds), a Thermo-Calc `.tdb` reader (CEF phases with vacancies, any-order
Redlich-Kister, and the Inden magnetic model real steel files require), the openly
specified `.utdb` unified dialect (MQMQA statements inside TDB grammar; spec in
`docs/UNIFIED_TDB_SPEC.md`, with shipped aluminum-recycling and steelmaking
demonstrations), a compound-energy-formalism Gibbs kernel, and equilibrium solving up to
full ternary isothermal sections by grid sampling plus lower convex hull. An open,
literature-only database family lives in `data/`: the slags (CaO-SiO2, MgO-SiO2,
FeO-SiO2, and the FeO-MgO-SiO2 ternary with olivine and orthopyroxene solid
solutions) and a chloride molten-salt family (LiCl-KCl through the NaCl-KCl-MgCl2
ternary with its halite solid solution), every parameter traced to published
measurements in the per-system provenance notes.
`python/mqmqa/dbbuild.py` turns a user's own measured data into a loadable `.dat`
(free up to four components). See `docs/DESIGN.md`.

An MQMQA excess term the engine does not evaluate is refused with a message naming the
phase (`Database.excess_unsupported`, `UnsupportedModelError`, a note in the browser),
never computed as something else: the B and R excess codes, reciprocal mixing,
ChemSage chemical-group override strings, and chemical groups or an
additional-constituent exponent r > 1 in a phase whose other sublattice holds more than
one ion.

## Gas constant

Three values of R are in use, each matching the data it came with: 8.3145 (the CALPHAD
convention of Thermo-Calc, pycalphad and OpenCalphad, and of this engine's ChemSage and
TDB databases), 8.31451 (the SGTE unary data and XTDB), and 8.314462618 (exact SI, CODATA
2018, used by the NASA and Cantera gas data). One engine-wide setting governs every
calculation (`mqmqa.set_gas_constant`, `mqmqa_set_gas_constant` in C):

- `"as_assessed"` (default): each database uses the value its data was built with.
- `"calphad"`, `"sgte"`, `"si"`: force 8.3145, 8.31451 or 8.314462618 everywhere, the gas
  phase included. A TDB file's `R#` references follow the forced value too.

The setting affects calculations only. Building a database (`dbbuild`) and writing one
never depend on it.

## Converting databases

Any database Hephaestus has loaded can be saved in another format. In Python,
`Database.write_tdb`, `write_utdb`, `write_dat`, and `write_xtdb` return the file text
and write it when given a path, and an `.xtdb` file read with `mqmqa.XTDB` has
`write_xtdb`, `write_tdb`, `write_utdb`, and `write_dat`. In C they are
`mqmqa_db_write_*` (`src/db_write.c`) and `xtdb_write_*` (`src/xtdb.c`), exported to the
WebAssembly build like the readers.

- `.tdb` holds CEF solutions (with the Inden magnetic model) and stoichiometric compounds.
- `.utdb` adds MQMQA SUBQ liquids as the statements of `docs/UNIFIED_TDB_SPEC.md`.
- `.dat` (plain-text ChemSage) holds SUBQ and SUBG liquids, SUBL solutions, and compounds.
- `.xtdb` holds what the XTDB engine evaluates: CEF phases with one binary mixing
  sublattice, compounds, and, from an `.xtdb` source, the third-generation Einstein and
  two-state liquid models.

A model the target format cannot represent is refused with an error that names the model
and a format that can hold it, and no file is written: an MQMQA liquid in plain `.tdb` or
`.xtdb`, a SUBG liquid in `.utdb`, the magnetic model in `.dat` or `.xtdb`, an Einstein
or two-state term in `.tdb` or `.dat`. A source the reader had to skip
part of (a ChemSage magnetic record, a TDB parameter type the engine does not read) is
refused too, since the copy would silently lack it. Functions in a TDB source are written
expanded, one polynomial per temperature interval, with every coefficient printed to
read back as the same number. `python/mqmqa/dbbuild.py` is a different tool: it builds a
new `.dat` from a user's measured data, while the writers re-serialize a database that
is already loaded.

Convert only data you have the rights to use. Converting a database does not change its
license; the license of the source data applies. Every written file records this in its
header, with the source file name and the Hephaestus version. Hephaestus reads plain-text
files only and contains no decryption code, so an encrypted database cannot be opened or
converted.

## The browser app

`web/index.html` is the zero-install face of the engine: the C core compiled to
WebAssembly (`scripts/build_wasm.sh`, committed as `web/hephaestus.js`) with a live
melt calculator, binary and ternary phase-diagram solvers for any loaded .dat, .tdb,
or .utdb file (the steelmaking demo computes the real Fe-C diagram), Scheil
solidification, and a multicomponent eutectic builder. A separate card reads the open
XML `.xtdb` format (`src/xtdb.c`) and its third-generation models, an Einstein heat
capacity valid to 0 K and a two-state liquid, computing an `.xtdb` file's binary diagram
live; a third-generation Al-C database and a classic Pb-Sn assessment ship as examples. Everything runs in
the page: a loaded database never leaves the visitor's machine, the CSP blocks every
third-party request, and the fonts are self-hosted. Serve it from any static host, or
locally:

    cd web && python -m http.server 8123

The hosted site is the `gh-pages` branch: the tracked contents of `web/` at the branch
root, no CI and no build step. GitHub Pages serves it once enabled (Settings -> Pages ->
Deploy from a branch -> `gh-pages`, `/ (root)`). After changing `web/` on `main`,
refresh the branch with:

    git push origin "$(git subtree split --prefix web main)":gh-pages

## Publication

Intended as a single-author **JORS** (Journal of Open Research Software) metapaper covering
both the engine and the open slag database as one open-science contribution. See
`docs/DESIGN.md`.

## License

Copyright (C) 2026 Michael E. Bustamante (Odinzen LLC).

The engine is licensed under the GNU Affero General Public License, version 3 only
(AGPL-3.0-only; see `LICENSE`). The open databases under `data/` and the example databases
under `web/` are licensed under Creative Commons Attribution-ShareAlike 4.0 International
(CC BY-SA 4.0; see `data/LICENSE`). Anyone may use, study, teach with, extend, and build
consulting work on either. Any modified version that is distributed, or offered to users
over a network, must carry the same license and keep the credits, so the engine and the
thermodynamics it carries stay open. Model equations are public; this is an independent,
clean-room implementation of them. Releases up to and including v0.6.0 were published under
MIT (engine) and CC BY 4.0 (data), and those releases keep those terms.
