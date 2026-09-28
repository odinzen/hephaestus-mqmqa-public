# Hephaestus

**Hephaestus** is an open-source, high-performance thermodynamic engine for ionic liquids, alloys, and coupled gas phases. Its C core provides a pure, unconstrained implementation of the **Modified Quasichemical Model in the Quadruplet Approximation (MQMQA)** to capture short-range ordering in molten salts, metallurgical slags, and electrolytes.  

## Core capabilities

**Universal CALPHAD Interoperability** includes lossless native readers and writers for ChemSage (.dat), Thermo-Calc (.tdb), .utdb, and XTDB formats.   

**Run-Anywhere Architecture** as a C core, a Python module (import mqmqa), or compiled to WebAssembly (WASM) for client-side execution in a browser.   

**Coupled Multi-Phase Solver** computes equilibrium across ionic melts, alloy solids, and an ideal gas phase coupled at a shared oxygen potential.   

**HPC and Cluster Ready** offers and engine free of commercial floating-license restrictions, enabling parallel scaling across thousands of cores for high-throughput screening and uncertainty quantification.

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

No code, algorithms, or solver internals from any other implementation are used.

## Validation

Every energy contribution (reference, ideal mixing, excess) is checked against
pycalphad's MQMQA on shared parameters to tight tolerance, and against published
values for the classical systems (CaO-SiO2 silicate slag; the KF-NiF2 reciprocal
salt from the 2023 pycalphad paper). Nothing is claimed working until it matches.

## Status

The C core is complete and validated to machine precision against pycalphad: the full
MQMQA energy path (reference, ideal mixing, excess, recursive coordination numbers), a
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

Hephaestus is released under copyleft terms:

* **Engine & Code** [GNU Affero General Public License v3.0 (AGPL-3.0)](https://www.gnu.org/licenses/agpl-3.0)
* **Databases & Assessments** [Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/)

Anyone may use, teach with, extend, or build consulting work on this software, provided all distributed or hosted versions remain open-source and credited under the same terms. Model equations are public domain; this codebase is an independent clean-room implementation.
