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
compounds), a compound-energy-formalism Gibbs kernel, and equilibrium solving up to
full ternary isothermal sections by grid sampling plus lower convex hull. An open,
literature-only slag database family lives in `data/` (CaO-SiO2, MgO-SiO2, FeO-SiO2,
and the FeO-MgO-SiO2 ternary with olivine and orthopyroxene solid solutions), every
parameter traced to published measurements in the per-system provenance notes.
`python/mqmqa/dbbuild.py` turns a user's own measured data into a loadable `.dat`
(free up to four components). See `docs/DESIGN.md`.

## The browser app

`web/index.html` is the zero-install face of the engine: the C core compiled to
WebAssembly (`scripts/build_wasm.sh`, committed as `web/hephaestus.js`) with a live
melt calculator, the assessed FeO-MgO-SiO2 phase-diagram viewer, a live
isothermal-section solver, and a multicomponent eutectic builder. Everything runs in
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

MIT (see LICENSE). Model equations are public; this is an independent
implementation of them.
