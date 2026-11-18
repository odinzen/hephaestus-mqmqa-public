# Reproducing Table 3

**What this is:** the command behind each row of the manuscript's Table 3 (Validation), run from the
repository root after `bash scripts/build.sh`, in an environment with pycalphad, Cantera and scipy.
**Last updated:** 2026-11-16.

| Row | Command |
|---|---|
| Energy paths (MQMQA reference, ideal, excess; CEF; stoichiometric) | `pytest tests/test_reference_energy_vs_pycalphad.py tests/test_ideal_mixing_vs_pycalphad.py tests/test_excess_q_vs_pycalphad.py tests/test_coordination_vs_pycalphad.py tests/test_reciprocal_chi_vs_pycalphad.py tests/test_ternary_excess_vs_pycalphad.py` |
| ChemSage reader | `pytest tests/test_dat_reader_vs_pycalphad.py` |
| CEF kernel | `pytest tests/test_cef_vs_pycalphad.py` |
| Multiphase equilibrium (1560 K, four solver routes) | `pytest tests/test_ternary_combined_vs_pycalphad.py tests/test_multiphase_c_vs_pycalphad.py tests/test_self_contained_equilibrium_vs_pycalphad.py tests/test_tq_interface_vs_pycalphad.py` |
| General minimizer, blind against Thermochimica | `python validation/thermochimica/predict.py THERMOCHIMICA_DATA_DIR predictions.json`, then `python validation/thermochimica/compare.py SEALED_DIR` and `python validation/thermochimica/referee.py SEALED_DIR THERMOCHIMICA_DATA_DIR`; protocol and results in `validation/thermochimica/` (needs a Thermochimica build, see `PROTOCOL.md`) |
| WebAssembly build | open `web/index.html` from a local server, load each shipped database and compare with the values above (manual, per release) |
| TDB reader | `pytest tests/test_tdb_reader_vs_pycalphad.py tests/test_tdb_expressions.py tests/test_tdb_expressions_c.py` |
| TDB reader, SGTE collection | the commands in `validation/orchid/SOURCES.md` (needs a checkout of ORCHID's repository at the pinned commit); results in `validation/orchid/RESULTS.md` |
| TDB magnetic model | `pytest tests/test_fec_steel.py tests/test_tdb_sgte_dialect.py` |
| TDB scope guard | `pytest tests/test_tdb_reader_vs_pycalphad.py::test_out_of_subset_models_fail_loudly tests/test_tdb_sgte_dialect.py` |
| Gas phase | `pytest tests/test_gas_vs_cantera.py tests/test_gas_c_vs_cantera.py` |
| Gas-condensed coupling | `pytest tests/test_gas_condensed_vs_cantera.py` |
| Gas-slag coupling | `pytest tests/test_gas_slag_coupling.py` |
| Gas-flux coupling | `pytest tests/test_gas_flux.py` |

`pytest` with no arguments runs every row except the Thermochimica comparison, the SGTE collection
and the in-browser check.
