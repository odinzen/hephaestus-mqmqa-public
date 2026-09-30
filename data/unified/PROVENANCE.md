# Unified-dialect (.utdb) demonstration databases

Each file holds an alloy and a melt in ONE database: ordinary Thermo-Calc-style TDB for the
alloy plus the MQMQA melt carried by the uTDB extension statements (:Q phase, MQG / MQZETA /
MQSTOI / MQZ / MQX; see `docs/UNIFIED_TDB_SPEC.md`). Licensed CC BY-SA 4.0.

The files are authored, not generated, because each carries its own explanatory header. Their
halves must not drift from the source databases, and the round-trip tests enforce that at
machine precision.

| File | Alloy half | Melt half | Round-trip test |
|---|---|---|---|
| `AlZn-LiClKCl.utdb` | `../al-zn/AlZn.tdb` (an Mey 1993 on Dinsdale) | `../licl-kcl/LiCl-KCl.dat` | `tests/test_utdb_roundtrip.py` |
| `AlZn-NaClKClMgCl2.utdb` | `../al-zn/AlZn.tdb` | `../nacl-kcl-mgcl2/NaCl-KCl-MgCl2.dat` (aluminum recycling salt flux) | `tests/test_utdb_recycling_roundtrip.py` |
| `FeC-FeOMgOSiO2.utdb` | `../fe-c/FeC.tdb` (Gustafson 1985 on Dinsdale, magnetic BCC/FCC) | `../feo-mgo-sio2/FeO-MgO-SiO2-combined.dat` (steelmaking slag) | `tests/test_utdb_steel_roundtrip.py` |

If either half changes, update the .utdb to match and rerun its round-trip test.
