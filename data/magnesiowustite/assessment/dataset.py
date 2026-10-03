"""Nafziger & Muan 1967, Am. Mineral. 52, 1364-1385 (open access), Table 9: coexisting
magnesiowustite and Mg-Fe olivine at 1200 degC, iron saturated, with the magnesiowustite FeO
and MgO activities (from Hahn & Muan 1962, which they reproduce). Read from the scan. The
pure-FeO row (a = 1 by definition) is left out.
"""
T = 1473.15
# (x_FeO magnesiowustite, a_FeO, a_MgO, x_Fe olivine)
TABLE9 = [(0.12, 0.27, 0.89, 0.06), (0.39, 0.61, 0.70, 0.12), (0.43, 0.64, 0.67, 0.12),
          (0.58, 0.73, 0.58, 0.15), (0.75, 0.83, 0.45, 0.22), (0.84, 0.88, 0.35, 0.38),
          (0.94, 0.95, 0.16, 0.54)]
SIG_LN_A = 0.05
SIG_X_OL = 0.02
