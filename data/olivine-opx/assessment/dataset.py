"""Measured data the two-site orthopyroxene is assessed against.

SITES: Saxena & Ghose 1971, Am. Mineral. 56, 532-559 (open access), Table 2: Mossbauer Fe
fractions on M1 and M2 of natural orthopyroxenes heated to equilibrium at 500-800 degC.
Read from the scan; every row satisfies (X_M1 + X_M2)/2 = X_bulk to the table's rounding.

TIELINES: Nafziger & Muan 1967, Am. Mineral. 52, 1364-1385 (open access), Table 5:
coexisting olivine (N_FeSi0.5O2) and pyroxene (N_FeSiO3) at 1200 degC, 1 atm, iron
saturated; by X-ray spacing or by the equilibrium gas composition.

BOHLEN: Bohlen, Essene & Boettcher 1980, Earth Planet. Sci. Lett. 47, 1-10 (open access at
hdl.handle.net/2027.42/23295): ferrosilite = fayalite + quartz reversed within 0.1 kbar.
At 1 bar the reaction 2 FeSiO3 -> Fe2SiO4 + SiO2 then has dG = -dV * P_eq, with
dV = 46.31 + 22.69 - 2 * 33.00 = 3.00 cm3 from the Robie-Hemingway 298 K volumes (thermal
expansion and compression, ignored, shift dV by about 10 %, inside sigma).

CALORIMETRY: Chatillon-Colinet, Newton, Perkins & Kleppa 1983, Geochim. Cosmochim. Acta
47, 1597 (in the trove): enthalpy of mixing of synthetic orthopyroxenes made at 1120 degC,
W_H = 950 cal per MSiO3, i.e. 2 * 950 * 4.184 * x(1-x) J per M2Si2O6 in the order state of
1393 K. The same paper measures the enthalpy of disordering of a natural En52.5 heated to
1150 degC: 0.85 kcal per MSiO3 lower solution enthalpy for a gain of about 0.25 in Fe on M1,
i.e. +7.1 kJ per M2Si2O6 between the 1423 K order state and one 0.25 more ordered.
"""
CAL = 4.184

# (T degC, X_bulk, X_Fe on M1, X_Fe on M2)
SITES = [
    (500, 0.181, 0.021, 0.341), (500, 0.381, 0.070, 0.692), (500, 0.455, 0.111, 0.799),
    (500, 0.500, 0.150, 0.850), (500, 0.580, 0.262, 0.897), (500, 0.620, 0.337, 0.902),
    (500, 0.720, 0.533, 0.907),
    (600, 0.181, 0.046, 0.316), (600, 0.381, 0.129, 0.632), (600, 0.455, 0.186, 0.726),
    (600, 0.500, 0.219, 0.781), (600, 0.580, 0.310, 0.849), (600, 0.620, 0.382, 0.857),
    (600, 0.720, 0.545, 0.895), (600, 0.760, 0.613, 0.905), (600, 0.860, 0.797, 0.922),
    (700, 0.181, 0.059, 0.303), (700, 0.381, 0.156, 0.605), (700, 0.455, 0.225, 0.685),
    (700, 0.580, 0.360, 0.800), (700, 0.620, 0.410, 0.829), (700, 0.860, 0.790, 0.929),
    (800, 0.181, 0.069, 0.293), (800, 0.381, 0.187, 0.575), (800, 0.455, 0.252, 0.657),
    (800, 0.500, 0.298, 0.701), (800, 0.620, 0.429, 0.811), (800, 0.720, 0.579, 0.860),
    (800, 0.860, 0.794, 0.926),
]
SIG_SITE = 0.015

T_TIE = 1473.15
# (X_Fe olivine, X_Fe pyroxene, method)
TIELINES = [(0.05, 0.05, "xray"), (0.11, 0.11, "xray"), (0.11, 0.11, "gas"),
            (0.15, 0.14, "gas"), (0.26, 0.22, "gas"), (0.30, 0.24, "gas"),
            (0.36, 0.29, "gas"), (0.43, 0.40, "xray"), (0.45, 0.40, "gas"),
            (0.49, 0.45, "gas"), (0.56, 0.52, "xray"), (0.62, 0.56, "xray")]
SIG_TIE = 0.02

# (T degC, P_eq kbar)
BOHLEN = [(700, 10.5), (750, 11.0), (800, 11.5), (850, 12.0), (900, 12.6), (950, 13.3),
          (1000, 14.1), (1050, 14.8)]
DV_BOHLEN = (46.31 + 22.69 - 2 * 33.00) * 0.1          # J/bar
SIG_BOHLEN = 300.0                                      # J per 2 FeSiO3

T_CAL = 1393.15
DH_MIX_HALF = 2 * 950.0 * CAL * 0.25                    # J per M2Si2O6 at x = 0.5
SIG_DH_MIX = 800.0

SIG_FS_SHIFT = 3000.0                                   # R&H dHf(ferrosilite) +- 3 kJ

X_DIS, T_DIS, DY_DIS = 0.475, 1423.15, 0.25             # En52.5 Fs47.5
DH_DIS = 2 * 850.0 * CAL                                # J per M2Si2O6
SIG_DH_DIS = 2500.0
