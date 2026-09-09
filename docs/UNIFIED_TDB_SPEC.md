# The unified TDB dialect (uTDB): MQMQA inside Thermo-Calc-style files

## The gap this closes

The CALPHAD world runs on two file dialects. ChemSage `.dat` (FactSage / ChemApp /
Thermochimica lineage) can hold MQMQA short-range-ordered liquids, compound energy
formalism (CEF) solids, and stoichiometric compounds together in one file. Thermo-Calc
`.tdb` (Thermo-Calc / OpenCalphad / pycalphad lineage) holds CEF and stoichiometric
phases but has no statements at all for MQMQA: no pair energies, no quadruplet
coordination numbers, no SNN excess codes. The divide is historical (two commercial
lineages, no standards body, no public TDB specification), not physical: the models
coexist in one Gibbs-energy calculation without difficulty, as the `.dat` side has
always demonstrated.

uTDB extends the TDB grammar with the missing statements. A uTDB file is an ordinary
TDB file whose MQMQA phases are declared with the `:Q` model-type suffix and
parameterized with the `MQ*` parameter types below. Everything else - ELEMENT, SPECIES,
FUNCTION, TYPE_DEFINITION, CEF PHASE/CONSTITUENT/PARAMETER, stoichiometric phases -
is unchanged TDB. One file can therefore hold an alloy, a slag, and a salt at once.

## Compatibility position, stated plainly

- Hephaestus reads uTDB natively (same reader, same engine, same accessors).
- Other TDB parsers do not know the `MQ*` statements. This is an open, documented
  extension, published so any implementation can adopt it; it is not secretly
  compatible with tools that have not adopted it. Files that must interoperate with
  unextended tools should ship the MQMQA content as a companion `.dat` (dbbuild
  writes both from one source).
- Extension: `.tdb` is accepted (statements are self-describing); `.utdb` is the
  recommended extension when a file uses `MQ*` statements, so intent is visible.

## Where this is heading: TDB to uTDB to XTDB

uTDB is a bridge, not a destination. The database formats run along one road:

- **`.tdb`** - the installed base (alloy CALPHAD, compound-energy-formalism solids); no
  MQMQA.
- **`.utdb`** - this extension: MQMQA carried inside TDB grammar, so one file can hold an
  alloy, a slag, a salt and a gas today, read by the same engine.
- **XTDB** - the community's XML successor to TDB (Sundman, Kattner, Hallstedt, van de Walle
  et al., *XTDB, an XML based format for Calphad databases*, Calphad 90 (2025) 102849), from
  the OpenCalphad and NIST circle. It is schema-validated, and its schema **already includes
  the MQMQA model**.

uTDB is the on-ramp from the installed base (extend the files you already have, in place); XTDB
is where the standard is going. Converting uTDB statements to XTDB elements is mechanical once
that schema settles.

**Status in this engine:** `.dat`, `.tdb`, and `.utdb` are read today. An **XTDB reader is a
roadmap item, not yet implemented** (see `docs/EQUILIBRIUM_ENGINE.md`, step S6). It is a clean,
self-contained piece of work: XTDB is an openly documented format, and every existing reader
already parses into the same in-memory database structure, so an XTDB front-end would parse the
XML into that same structure and the rest of the engine would work unchanged. Because XTDB's
schema carries MQMQA and this engine already models MQMQA, the reader is the one missing bridge
between the emerging standard and a working open engine. Implement it clean-room from the
published XTDB spec and schema (no GPL source), and validate it the way `.utdb` is validated -
round-trip and parity against the same system in `.dat`/`.utdb` form.

## Grammar

### Phase declaration

    PHASE <name>:Q  <code>  2  <a_cat>  <a_an> !
    CONSTITUENT <name>:Q : <cation>,<cation>,... : <anion>,... : !

`:Q` marks the MQMQA quadruplet model (SUBQ). Exactly two sublattices: cations then
anions. Constituents are species with charges declared via SPECIES (e.g. `LI+1`,
`CL-1`); the charge magnitudes feed the model. Site ratios are carried for form but
the quadruplet model derives its own amounts.

### Pair endmembers (MQMG equivalent)

    PARAMETER MQG(<phase>,<cat>:<an>;0)  <lowT>  <piecewise G(T)>; <T> N !

Gibbs energy of the pure cation-anion pair, per mole of salt formula, standard TDB
piecewise-polynomial syntax including FUNCTION references.

    PARAMETER MQZETA(<phase>,<cat>:<an>)   <lowT>  <zeta>; <T> N !
    PARAMETER MQSTOI(<phase>,<cat>:<an>)   <lowT>  <a> <b> <x> <y> <z>; <T> N !

`MQZETA` is the pair's zeta; `MQSTOI` the five-entry quadruplet stoichiometry row
(the ChemSage `stoichiometry_quadruplet`); constants, single interval.

### Coordination numbers (MQMZ equivalent)

    PARAMETER MQZ(<phase>,<catA>,<catB>:<anX>,<anY>)  <lowT>  <zA> <zB> <zX> <zY>; <T> N !

The four slot coordination numbers of the quadruplet (A,B / X,Y), constants.
Pure-pair rows use catA = catB and anX = anY.

### SNN excess (MQMX equivalent)

    PARAMETER MQX<c>(<phase>,<catA>,<catB>:<anX>,<anY>;<p>,<q>)  <lowT>  <L(T)>; <T> N !
    PARAMETER MQXT<c>(<phase>,<catA>,<catB>:<anX>,<anY>;<p>,<q>,<r>:<catT>)  ... !

`<c>` is the ChemSage excess code letter: `Q`, `G`, `B`, or `R`. `p`,`q` are the two
mixing exponents. The `MQXT` form carries a ternary term: exponent `r` and the
additional cation after the colon. `L(T)` uses the standard piecewise syntax on the
six-coefficient basis (1, T, T ln T, T^2, T^3, 1/T).

### Chemical groups

    PARAMETER MQGRP(<phase>,<species>)  <lowT>  <group>; <T> N !

Integer group id per constituent (cations and anions), for the group-dependent
excess interpolation.

### Ideal-gas phase (NASA polynomials)

A `:G` phase is an ideal-gas mixture whose species carry NASA 7-coefficient
polynomials, the combustion school's native thermochemistry (NASA CEA, Burcat,
GRI-Mech). The species may be declared inline or, preferably, resolved by name against
a companion NASA/CHEMKIN `thermo.dat`, so the gas keeps its standard, portable form.

    PHASE <name>:G  G  1  1.0 !
    CONSTITUENT <name>:G : <sp>,<sp>,... : !
    GAS_THERMO "<file>.dat"                                  ! external NASA cards

Gas species mix ideally and feel the pressure term, mu_i = G_i(T) + RT ln(x_i P / P0),
with the standard-state reference pressure P0 = 1 atm of the NASA polynomials. Ideal-gas
equilibrium at fixed temperature and pressure is solved by the element-potential
(RAND/CEA) method and validated against Cantera to machine precision. This phase makes
uTDB a four-model container, an alloy, a slag or salt, its stoichiometric solids, and a
gas, in one file. The reference gas thermochemistry ships as `data/gas/nasa_gas.dat`.

## Reference implementation and proof

The Hephaestus reader (`src/cs_dat.c`, TDB front-end) parses these statements into
the same internal database the `.dat` reader builds, so the engine, Python binding,
and WASM browser build behave identically for either container. The round-trip gates
(`tests/test_utdb_roundtrip.py`, `tests/test_utdb_recycling_roundtrip.py`,
`tests/test_utdb_steel_roundtrip.py`) assert that the three shipped unified files
(`web/AlZn-LiClKCl.utdb`; `web/AlZn-NaClKClMgCl2.utdb`, aluminum recycling with the
salt flux, its ternary excess term, and the halite CEF solution;
`web/FeC-FeOMgOSiO2.utdb`, steelmaking with the magnetic Fe-C steel and the
FeO-MgO-SiO2 slag) reproduce the `.dat` physics exactly: pair Gibbs, coordination rows, SNN excess, single-phase
equilibria, and stoichiometric solids agree at machine precision across temperature,
and the alloy phases match the reference `AlZn.tdb`. A `write_utdb` emitter in
dbbuild, so every dbbuild-built system ships in both containers automatically, is
the named next step.
