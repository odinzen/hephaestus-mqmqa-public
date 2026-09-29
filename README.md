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

## Provenance

The model is implemented from the published literature, with the one exception below:

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

No code, algorithms, or solver internals from any other implementation are used, except
for one term. In a SUBQ phase where both sublattices mix, the G-code Chi variables also
count the reciprocal quadruplets. The published equation (Paz Soldan Palma et al., Eq 9)
weights them 0.5; pycalphad's `ModelMQMQA._Chi_mix` weights them 1.0. The engine follows
pycalphad (`chi_quads` in `src/mqmqa.c`, adapted from that method), so its results
agree with pycalphad there. pycalphad is distributed under the MIT License:

    pycalphad, a Python library for the CALculation of PHAse Diagrams

    The MIT License (MIT)

    Copyright (c) 2014-2019 Richard Otis and Zi-Kui Liu
    Copyright (c) 2016-2019 Brandon Bocklund
    Copyright (c) 2016-2019 California Institute of Technology
    Copyright (c) 2018-2019 Materials Genome Foundation

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
    THE SOFTWARE.

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
ChemSage chemical-group override strings, and, in a phase whose other sublattice holds
more than one ion, an additional-constituent exponent r > 1 and chemical groups in a Q
term or a term with an additional constituent.

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

Each loaded database reports its own R and where it came from (`Database.gas_constant`,
`gas_constant_source`, `gas_constant_note`, the same on `XTDB`; `mqmqa_db_R*`,
`xtdb_R*`, `mqmqa_gas_R*` in C):

- read from file: a TDB `FUNCTION R` (which also replaces the built-in `R#`), an XTDB
  `TPfun R`, or the gas-constant line in the title of a `.dat` Hephaestus wrote;
- inferred from constants in the file: R is not stated, but the expressions use one
  gas-constant literal (8.314...) throughout. Literals that disagree are not guessed
  between; the convention applies and the note lists them. Comments never count;
- format convention, not stated in file: 8.3145 for `.dat`, `.tdb` and `.utdb`, 8.31451
  for `.xtdb`, 8.314462618 for the NASA gas data. A `.tdb` that uses `R#` without defining
  it keeps the built-in 8.31451 there, as it always has;
- user override: a forced mode is active; the database's own value is kept and shown.

Databases loaded together each keep their own value. When a file does not state R, the
user can declare which value it was assessed with (`declare_gas_constant("sgte")`,
`mqmqa_db_declare_R`); the source is then "declared by user". Saving a database records
its own R (stated, inferred, declared or convention, never a forced mode's) in every
format: `FUNCTION R` in `.tdb` and `.utdb`, a `TPfun R` in `.xtdb`, and a sentence in the
title line of a `.dat`, which has no field for it. A written file therefore reads back as
"read from file".

In the browser, the R control next to the temperature-unit toggle sets the mode (each
choice explains itself on hover) and recomputes what is on screen; after loading a
database a note gives its R and source, and offers the declaration when the file does
not state R.

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

## 3D phase space

`mqmqa.vis3d` (`src/vis3d.c`) turns a three-cation, single-anion system into meshes for 3D
views: `section` gives the phase regions of an isothermal section, `liquidus_surface` the
liquidus over the triangle with its primary-phase fields and eutectic valleys, and
`gibbs_surfaces` the Gibbs energies at one temperature relative to the equilibrium or to the
pure components. Each rests on a refined equilibrium hull (`vis3d.Hull`) whose phase
boundaries are located to a set tolerance (default 0.001 in cation fraction) independent of
the sampling seed. `surface_arrays` and `prism_arrays` give the VTK layout with numpy alone,
and `to_polydata` and `to_unstructured` build PyVista objects when PyVista is installed. The
mesh is for looking at; `liquidus_point`, `Hull.assemblage` and `Hull.gibbs` give the numbers.
Method and validation: `docs/VISUALIZATION_3D.md`, section 8.

## The browser app

`web/index.html` is the zero-install face of the engine: the C core compiled to
WebAssembly (`scripts/build_wasm.sh`, committed as `web/hephaestus.js`) with a live
melt calculator, binary and ternary phase-diagram solvers for any loaded .dat, .tdb,
or .utdb file (the steelmaking demo computes the real Fe-C diagram), Scheil
solidification, and a multicomponent eutectic builder. A separate card reads the open
XML `.xtdb` format (`src/xtdb.c`) and its third-generation models, an Einstein heat
capacity valid to 0 K and a two-state liquid, computing an `.xtdb` file's binary diagram
live; a third-generation Al-C database and a classic Pb-Sn assessment ship as examples. A
3D card draws a ternary's liquidus surface (height is temperature, one colour per primary
phase, the eutectic valleys as lines) with a movable temperature plane that shows the
exact isothermal section; it computes in Web Workers (`web/vis3d_worker.js`) with
Three.js bundled under `web/vendor/three` (MIT), and a click asks the engine for the
liquidus and equilibrium at that point. Everything runs in
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
clean-room implementation of them, apart from the one pycalphad-derived term credited
under Provenance. Releases up to and including v0.6.0 were published under
MIT (engine) and CC BY 4.0 (data), and those releases keep those terms.
