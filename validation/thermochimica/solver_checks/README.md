# Independent checks of the solver's chemical potentials

Run on a predictions file before the comparison, never against sealed values. Each works from
the reported result and the phase's own energy, by a route that shares no code with the solver's
finish. Thermochimica's data folder is read from `THERMOCHIMICA_DATA`.

- `verify_sets.py`: every sublattice phase and ionic liquid, its internal equilibrium found from
  scratch at the reported composition (minimization from many starts, then a root solve of the
  equilibrium conditions, the lowest state kept); the potentials that come out against the
  reported ones. Not for a gas of almost one molecule, whose potentials hang on digits of the
  composition below double precision.
- `gas_check.py`: every phase whose energy is exactly ideal mixing, by mass action from the
  reported potentials (the species fractions must sum to one and give the reported composition).
- `pyc_liquid_check.py`: MQMQA liquids against pycalphad's liquid alone at the reported
  composition. pycalphad's MQMQA is the model Hephaestus's was translated from, so this checks
  the solve, not the model, and it does not read ClAlNa's Al2 and Va liquid the same way.

Results on the frozen predictions (15 November 2026): 314 sets within 0.01 J/mol, 8 ideal gas
sets to 2e-14, the CuFeC-Kang liquid to 1e-4 J/mol.
