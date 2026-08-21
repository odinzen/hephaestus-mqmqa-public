# mqmqa

A small, standalone implementation of the **Modified Quasichemical Model in the
Quadruplet Approximation (MQMQA)**: a C core with a thin Python wrapper. The MQMQA
describes short-range ordering in ionic liquids (molten salts, oxide slags,
electrolytes), the physics behind FactSage's oxide/slag databases.

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

Early scaffold. Nothing implemented yet. A C toolchain is being set up before any
C is written, so that every line is compiled and tested, not asserted.

## Publication

Intended as a single-author **JORS** (Journal of Open Research Software) metapaper covering
both the engine and the open slag database as one open-science contribution. See
`docs/DESIGN.md`.

## License

MIT (see LICENSE). Model equations are public; this is an independent
implementation of them.
