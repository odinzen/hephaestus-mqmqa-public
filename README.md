# Hephaestus

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24210540.svg)](https://doi.org/10.5281/zenodo.24210540)

**Hephaestus** is an open-source Gibbs energy minimizer with the **Modified
Quasichemical Model in the Quadruplet Approximation (MQMQA)**, running in the browser,
with open databases for slags, molten salts, and alloys. You can also load your own
database (.dat, .tdb, .utdb or XTDB) and calculate with it in the browser. A C core does
the thermodynamics behind a thin Python wrapper and a WebAssembly build. The MQMQA
describes short-range ordering in ionic liquids (molten salts, oxide slags,
electrolytes), the physics behind FactSage's oxide/slag databases. 

Named for the god of the forge, it computes the thermodynamics of the melt.

The scientific model is MQMQA (a standard acronym); the engine that implements it is
Hephaestus. The library is currently imported as `mqmqa`.

## Use it now

Open **<https://odinzen.github.io/hephaestus-mqmqa-public/>** in any current browser. Nothing
to install and no account: press **Load the open slag database** (or the salt or alloy one),
then use **What is in my melt?** to type a composition and temperature and read which phases
are present and how much of each, or click any phase diagram to read the phases and their
amounts at that point. Files you load stay on your computer. A step-by-step guide for
non-programmers is `paper/Supplementary_S1_primer.md`.

To run the same page offline, serve the `web/` folder from any static web server, for
example `cd web && python -m http.server 8123`, then open <http://localhost:8123>.

## Getting help

Questions, wrong-looking results, or help with your own data: email **info@odinzen.io**.
Security reports: see `SECURITY.md`.

## For programmers

The C core has no dependencies. Build the shared library the Python package loads:

- Windows: `bash scripts/build.sh` (clang from the conda environment named in the script;
  override with `MQMQA_ENV` or `MQMQA_CLANG`).
- Linux / macOS: any C11 compiler, for example

      cc -O2 -std=c11 -fPIC -shared -Isrc -o python/mqmqa/libmqmqa.so src/*.c -lm

  (name the output `libmqmqa.dylib` on macOS).

Then `pip install -e python` and `import mqmqa`. The browser build is
`bash scripts/build_wasm.sh` (emscripten), which writes `web/hephaestus.js`. Run the tests
with `pytest` from the repository root in an environment that also has pycalphad and Cantera.

## Learning the model

[notebooks/LearnMQMQA](notebooks/LearnMQMQA/LearnMQMQA.ipynb) works through the MQMQA with the
shipped databases: what a slag database holds, how the short-range order forms along the
FeO-SiO2 join, what one excess parameter does, which solids crystallize as a slag cools, and the
same model written in TDB notation. The test suite runs it, so it always matches the engine.

## What is where

| Path | Contents |
|---|---|
| `src/` | the C engine: MQMQA and CEF Gibbs energies, file readers and writers, equilibrium, gas, 3D meshes |
| `python/mqmqa/` | the Python package over the C library, including the database builder (`dbbuild.py`) |
| `web/` | the browser app (`index.html`), its WebAssembly engine (`hephaestus.js`) and shipped databases |
| `data/` | the open databases, one folder per system, each with the fitting scripts and a `PROVENANCE.md` |
| `tests/` | the pytest suite, including the comparisons against pycalphad and Cantera |
| `scripts/` | build scripts (native, WebAssembly) and the script that syncs databases into `web/` |
| `docs/` | design notes and the unified `.utdb` format specification |
| `cef/` | the Python prototype of the compound-energy-formalism kernel |
| `paper/` | the JORS manuscript, its figures and the S1 primer |
| `notebooks/` | teaching notebooks, run by the test suite so they stay current |
| `validation/` | the sealed cross-checks against Thermochimica, published FactSage results and measured data, and the checks behind the ORCHID shelf (`validation/orchid/`) |
| `LICENSE`, `NOTICE` | the licence, and the third-party notices (pycalphad) |

## Scope and honest positioning

This is a lightweight, framework-independent MQMQA energy library, meant to be
embedded or called from other codes without pulling in a full CALPHAD stack.

It is not the first open MQMQA. pycalphad already ships one
(`pycalphad.models.model_mqmqa`, Paz Soldan Palma et al., Calphad 2023), and the
Hephaestus MQMQA energy is a translation of it into C. This library's value is being
small, dependency-light, callable from C or Python directly, and runnable in a web
browser. pycalphad is not a runtime dependency.

## Provenance

The MQMQA Gibbs energy in `src/mqmqa.c` (reference energy, configurational entropy,
excess terms, and the coordination-number recursion) is a translation into C of
pycalphad's `ModelMQMQA` (`pycalphad/models/model_mqmqa.py`). It was written with that
source open, method by method, and then checked against pycalphad on shared databases.
It follows pycalphad's choices where the papers leave room, including the AB/XX
coordination numbers, which pycalphad takes from Thermochimica. Following pycalphad was
deliberate, so that its users meet the same model, conventions and numbers here, and a
database moves between the two tools unchanged. Because the code was derived from
pycalphad, agreement with pycalphad confirms the translation; it is not an independent
check of the model.

Other parts consulted third-party source as follows:

- `src/cs_dat.c`, ChemSage .dat reader: the SUBQ/SUBG/SUBL block grammar follows
  pycalphad's `pycalphad/io/cs_dat.py`, which was read while writing it. The IDMX and RKMP(M)
  blocks (ideal and Redlich-Kister-Muggianu solutions) and the magnetic records of SUBLM and
  RKMPM were written from the data files themselves and the standard form of those models
  (the Inden-Hillert-Jarl magnetic term the TDB reader already used); no other program's
  source was read for them. The SUBI block (the two-sublattice ionic liquid) was written from
  Sundman, Calphad 15 (1991) 109-119 for the model and every excess term, and from the data
  files for the layout, as were FactSage 8's "= ... =" line annotations; no other program's
  source was read for it. pycalphad's ionic liquid was run as a program to compare against.
  The QKTO block (Kohler polynomial solutions) was written from Pelton, Calphad 12 (1988)
  127-142, eqs. 7 and 12, with the term layout confirmed against Kaye, Lewis and Thompson,
  J. Nucl. Mater. 366 (2007) 8-27; no other program's source was read for it. pycalphad's
  ChemSage reader was run as a program to compare against.
- `src/cs_dat.c`, TDB reader: pycalphad's `pycalphad/io/tdb.py` was read to match its
  handling of expressions. The Thermo-Calc dialect of the SGTE binary collection (abbreviated
  keywords, empty ",," temperature limits, the "*" constituent, BM/BMAG, type definitions
  declared after their phases, energy-bearing parameter types refused) was added on
  16 November 2026 from the files themselves and the Thermo-Calc conventions they rely on, and
  checked by running pycalphad as a program; no other program's source was read for it.
- `src/gem.c`, the general equilibrium solver: written from published methods, the
  hull-and-refinement scheme of Lukas, Fries and Sundman (Computational Thermodynamics, 2007),
  column generation (Dantzig and Wolfe, 1960), quasi-Newton steps (Nocedal and Wright, 2006),
  and linear-programming duality for a bulk on a face of the phases' compositions; no other
  equilibrium program's source was read for it. Thermochimica (BSD-3) was run as a program,
  its source unopened, for the blind comparison in `validation/thermochimica/`.
- `src/tq.c`: function signatures follow OpenCalphad's OCASI C binding (`octqc.h`,
  `liboctqisoc.F90`), which were read; no OpenCalphad model code was translated.
- `src/xtdb.c`: written from the published XTDB specification (Sundman's XTDB repository
  documents and example files).
- `python/mqmqa/utdb_xtdb.py`: written from the XTDB paper and the documentation in
  Sundman's XTDB repository (GPL-3.0, documents only); the magnetic model Ids follow the
  writer of pycalphad-xtdb (Odinzen, MIT). The MQMQA form it writes is our proposal
  (`docs/XTDB_MQMQA_PROPOSAL.md`).
- `validation/fig4_comparison/`: pycalphad is run as a program on the shipped FeO-MgO-SiO2
  file. Two pycalphad files, `pycalphad/core/calculate.py` and `pycalphad/core/workspace.py`,
  were opened on 16 November 2026 only to read the default sampling density of `equilibrium`
  (pdens 60); no code was taken from them.

The equations themselves are published in:

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

One known difference between the papers and pycalphad: in a SUBQ phase where both
sublattices mix, the G-code Chi variables also count the reciprocal quadruplets. The
published equation (Paz Soldan Palma et al., Eq 9) weights them 0.5; pycalphad's
`ModelMQMQA._Chi_mix` weights them 1.0, and the engine follows pycalphad (`chi_quads` in
`src/mqmqa.c`). pycalphad is distributed under the MIT License, whose notice is kept here
and in `NOTICE`:

    pycalphad, a Python library for the CALculation of PHAse Diagrams

    The MIT License (MIT)

    Copyright (c) 2014-2023 Richard Otis and Zi-Kui Liu
    Copyright (c) 2016-2023 Brandon Bocklund
    Copyright (c) 2016-2023 California Institute of Technology
    Copyright (c) 2018-2023 Materials Genome Foundation
    Copyright (c) 2020      David Walz

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
(any number of components). See `docs/DESIGN.md`.

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
read back as the same number.

`python/mqmqa/utdb_xtdb.py` is a separate converter between `.utdb` and `.xtdb` that
carries what the engine's own `.xtdb` writer refuses: the magnetic model, written as XTDB
defines it, and MQMQA liquids, written in a form proposed in `docs/XTDB_MQMQA_PROPOSAL.md`
because XTDB does not yet define their parameters. It works on the file text, so every
expression is kept as written:

```bash
python -m mqmqa.utdb_xtdb data/unified/FeC-FeOMgOSiO2.utdb steel.xtdb
python -m mqmqa.utdb_xtdb steel.xtdb steel.utdb
```

`python/mqmqa/dbbuild.py` is a different tool: it builds a
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

## Slag in water

`data/wet-slag/aqueous/` carries a PHREEQC database for slag minerals in water at 25 C
(`phreeqc_slag.dat`), for questions about stockpiled or reused slag and its leachate. The 16
anhydrous slag minerals get their dissolution constants from the same Gibbs energies the
high-temperature databases ship; hydrates and C-S-H come from Cemdata18. Run it with PHREEQC or
phreeqpython. `derive_logk.py` rebuilds it, and the folder README gives the comparisons with
measured solutions and the limits (no sulfate, carbonate, iron or redox; equilibrium only).

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

A second tab runs [Hermes](https://github.com/odinzen/hermes) 0.3.0 (MIT,
doi:10.5281/zenodo.23923573), which combines the free energies of competing
configurations into the free energy of the whole system (zentropy) and gives volume,
thermal expansion, entropy, heat capacity, bulk modulus, configuration probabilities and
the pressure-temperature phase diagram. It runs Hermes unchanged in Python in a Web Worker
(`web/hermes_worker.js`) on Pyodide, served from this site like everything else. The Python
runtime (about 40 MB) is not tracked in git; fetch it, and rebuild the Hermes wheel and the
Fe3Pt example in `web/hermes/`, with

    python scripts/build_hermes_web.py --hermes-repo <clone of odinzen/hermes>

Without it the rest of the page works and the Hermes tab says what is missing.

The hosted site is the `gh-pages` branch: the tracked contents of `web/` at the branch
root, no CI and no build step. GitHub Pages serves it once enabled (Settings -> Pages ->
Deploy from a branch -> `gh-pages`, `/ (root)`). After changing `web/` on `main`,
refresh the branch with:

    git push origin "$(git subtree split --prefix web main)":gh-pages

## Publication

A two-author **JORS** (Journal of Open Research Software) metapaper covers
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
thermodynamics it carries stay open. The MQMQA core is a C translation of pycalphad's
MIT-licensed model, credited under Provenance and in `NOTICE`. Releases up to and including v0.6.1 were published under
MIT (engine) and CC BY 4.0 (data), and those releases keep those terms.

Two pieces of third-party data keep their own terms. `data/gas/nasa_gas.dat` (and its copy
`web/nasa_gas.dat`) reproduces GRI-Mech 3.0 gas thermochemistry; see `data/gas/PROVENANCE.md`.
`data/wet-slag/aqueous/phreeqc_slag.dat` is built on the USGS PHREEQC databases `phreeqc.dat`
and `wateq4f`; only the slag phases appended to it are ours (see that folder's README).

`web/orchid/sgte-binary/` holds binary datasets of the SGTE collection, B. Hallstedt, "The SGTE
collection of binary datasets", Calphad 89 (2025) 102833, doi:10.1016/j.calphad.2025.102833,
published under CC BY 4.0 and redistributed unchanged as ORCHID distributes them
(orchid-project.org; R. Arróyave, J. Saal, D. Shin). They keep that licence; each file's header
names the original assessment, which work that uses it should cite. Every dataset the engine reads is included;
those that agree with pycalphad and whose parameters all trace to checked publications are marked
checked, and the rest carry "check before use" with what could not be traced.
`scripts/import_orchid.py` builds the shelf and `validation/orchid/` records the checks.
