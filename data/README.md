# Open oxide-slag database (Hephaestus data)

An open, citable thermodynamic database for oxide slags in the ChemSage `.dat` format
that the Hephaestus MQMQA engine reads. The first system is the CaO-SiO2 liquid slag.

This database is the open-data counterpart to the engine: no free MQMQA oxide-slag
database exists, so every commercial workflow depends on closed sources. The goal here is
a database whose every parameter is traceable to a published, openly available source.

## License

The data in this directory (the `.dat` databases and the derived tables) are licensed
under Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0); see
`LICENSE`. The engine is code and carries AGPL-3.0-only; this is data, and CC BY-SA is the
instrument for a citable dataset that must stay open. Attribution is met by citing this
repository and the primary sources listed in each system's `PROVENANCE.md`. Any adapted
version that is shared, including one converted to another file format, must be shared
under CC BY-SA 4.0 with the same credits and without technical measures that restrict it.
Releases up to and including v0.6.1 were published under CC BY 4.0 and keep those terms.

## Shipped databases

Every database the calculator ships is listed in `databases.toml`, and each one's source lives
here under `data/<system>/` with its `PROVENANCE.md`. The copies in `web/` are generated from
these sources by `scripts/sync_databases.py`, which also generates the calculator's load
buttons; never edit a database in `web/` directly. To add one, put its source in its system
folder, add an entry to `databases.toml`, and run the sync. Store one format per database
(`.dat` for slags and salts, `.tdb` for alloys, `.utdb` only for an alloy and a melt together,
`.xtdb` for third-generation data); the calculator converts to the others on demand.

## Scope and status

Each folder's `PROVENANCE.md` is the authority for its sources, fitted values and limits; this
list only says what ships and how settled it is (2026-10-07).

Oxide slags (MQMQA liquids, Fe2+ only):

- `cao-sio2/` - CaO-SiO2 liquid, v0.4, assessed on Robie-Hemingway calcium silicates.
- `mgo-sio2/` - MgO-SiO2 liquid, three-way fit N1 (with the two ternary faces below).
- `feo-sio2/` - FeO-SiO2 liquid, v0.4, iron-saturated wustite as the FeO solid.
- `al2o3-sio2/` - Al2O3-SiO2 with mullite, v0.2 (Bowen & Greig 1924).
- `cao-al2o3/` - CaO-Al2O3 v0.2, dry (no Ca12Al14O33), with the CaAl4O7 and Ca3Al2O6
  formation enthalpies shifted by the assessment; the measured values stay in `MEASURED`.
- `cao-al2o3-sio2/` - the CaO-Al2O3-SiO2 ternary v0.3 with gehlenite and anorthite, three
  ternary terms on the shipped binaries.
- `feo-mgo-sio2/` - the ternary liquid with olivine, two-site orthopyroxene,
  magnesiowustite and cristobalite (`FeO-MgO-SiO2-combined.dat`).
- `cao-feo-mgo-sio2/` - the quaternary slag, with clinopyroxene and the calcium silicates.

Solid solutions (CEF): `olivine/`, `olivine-opx/`, `olivine-opx-cpx/`, `clinopyroxene/`,
`magnesiowustite/`, `spinel/`; `solidsolutions/` holds the MLIP and SQS mixing-energy checks.

Molten salts: `licl-kcl/`, `nacl-kcl/`, `kcl-mgcl2/`, `nacl-mgcl2/`, `nacl-kcl-mgcl2/`.

Other: `wet-slag/` (aqueous PhreeqC database for slag minerals at 298 K), `gas/` (NASA
polynomials), `al-zn/` and `fe-c/` (alloy TDBs), `unified/` (.utdb demonstrations), `xtdb/`
and `xtdb-alc/` (XTDB examples and the reference prototype).

## Reproducing and validating

From the repository root, with the engine built:

```
PYTHONPATH=python python data/cao-sio2/build_dat.py      # regenerate the .dat
PYTHONPATH=python python data/cao-sio2/validate.py       # load + check vs published data
```

The validation script reports the load, the endmember round-trip against an independent
H - T*S evaluation of the open Robie-Hemingway/JANAF data, the reproduction of the
published fusion points (dG_fus -> 0 at Tm(SiO2)=1996 K and Tm(CaO)=3200 K), and the
pure-oxide-limit reduction. See `PROVENANCE.md` for the citation behind each number.

## Before an assessment ships

Three checks, for every assessment that goes public:

1. **One Gibbs function per phase.** A fitting script never carries its own copy or correction of
   a phase's energy. A correction (polymorph shift, heat-capacity fix, enthalpy shift) lives in the
   module the builder writes from, and the fit imports it.
2. **The fitting code matches the shipped file.** `tests/test_fit_tools_match_shipped.py` compares
   each binary's fitting solids with the shipped files at 800-2200 K; a new assessment adds its
   solids there. From 2026-08-22 to 2026-09-29 the MgO-SiO2 and CaO-SiO2 fitting code made pure
   cristobalite 2.3 kJ more stable than any shipped file, and every fit in that window was made
   against it.
3. **Quoted numbers come from the shipped file.** Every invariant, liquidus or activity quoted in a
   `PROVENANCE.md`, a table or a paper is recomputed from the written file with all its phases, and
   only stable equilibria count.
