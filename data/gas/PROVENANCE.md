# Reference gas thermochemistry

`nasa_gas.dat`, NASA 7-coefficient polynomials in CHEMKIN thermo format for the 16 species the
slag-gas card and the gas-phase engine use (CO, CO2, H2, H2O, O2, N2, CH4, H, O, OH, HO2, H2O2,
NO, NO2, C2H2, C2H4). Shipped as `web/nasa_gas.dat`.

Third-party data, not authored here. Every coefficient is the GRI-Mech 3.0 value as distributed
with Cantera (`gri30.yaml`): all 16 species agree to better than 1 part in 10^8 against Cantera
3.2.0.

- G. P. Smith, D. M. Golden, M. Frenklach, N. W. Moriarty, B. Eiteneer, M. Goldenberg,
  C. T. Bowman, R. K. Hanson, S. Song, W. C. Gardiner Jr., V. V. Lissianski, Z. Qin,
  GRI-Mech 3.0, http://combustion.berkeley.edu/gri-mech/

This file keeps the terms of its source and is not covered by `data/LICENSE`. Cite GRI-Mech 3.0
when you use it.

The gas tests (`tests/test_gas_vs_cantera.py`, `tests/test_gas_c_vs_cantera.py`,
`tests/test_gas_condensed_vs_cantera.py`) compare the engine against Cantera on the same species.
