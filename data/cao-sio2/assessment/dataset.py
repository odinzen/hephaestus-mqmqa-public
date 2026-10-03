"""The measured CaO-SiO2 dataset the v0.4 liquid is assessed against.

Invariants: Abdul et al. 2023, Cement and Concrete Research 174, 107039 (CC BY), Table 9
(experimental values they collect; liquid compositions in mole fraction SiO2), and their
own DSC for the rankinite peritectic (section 6.1, 1737 +- 5 K). Each invariant enters as
the liquidus of every solid it involves, at the tabulated liquid composition. Those
compositions come from the classic diagrams, so sigma covers a composition error of about
0.01 on the local liquidus slope as well as the temperature error: 10 K near the
well-measured calcium metasilicate invariants, 20 K for C2S melting, and 40 K for the two
lime-rich invariants above 2300 K, where the liquidus runs at thousands of K per unit x. The silica at the CS-SiO2 eutectic is tridymite; the model's one
silica phase (cristobalite) is scored in its place.

Two liquids: Greig 1927, Am. J. Sci. 13, 1-44 (public domain), Table III (cristobalite +
two liquids at 1971 K, silica-rich liquid 99.4 wt% SiO2) and Table IV (consolute bracketed
1983-2013 K at 73.5 wt% SiO2).

Activities are data/cao-sio2/fit_excess.py (Kay & Taylor 1960; Stolyarova 1991).
Row ids follow the assessment workspace (assessments/CaO-SiO2).
"""
M_CAO, M_SIO2 = 56.077, 60.083


def x_wt(sio2):
    n = sio2 / M_SIO2
    return n / (n + (100.0 - sio2) / M_CAO)


# (id, T_K, sigma_K, x_SiO2 of the liquid, solids on whose liquidus it lies)
_INV = [
    ("pheq:abdul2023:mp_cycloCS", 1817.0, 5.0, 0.5, ("CS(pseudowoll)",)),
    ("pheq:abdul2023:mp_aC2S", 2403.0, 20.0, 1.0 / 3.0, ("C2S",)),
    ("pheq:abdul2023:inv_L_C3S2_CS", 1733.0, 10.0, 0.44, ("C3S2(rankinite)", "CS(pseudowoll)")),
    ("pheq:abdul2023:mp_rankinite_DSC", 1737.0, 10.0, 0.43, ("C2S", "C3S2(rankinite)")),
    ("pheq:abdul2023:inv_L_SiO2_CS", 1709.0, 15.0, 0.61, ("CS(pseudowoll)", "SiO2(cristobalite)")),
    ("pheq:abdul2023:inv_L_C3S_aC2S", 2323.0, 40.0, 0.29, ("C3S", "C2S")),
    ("pheq:abdul2023:inv_L_CaO_C3S", 2423.0, 40.0, 0.27, ("CaO(lime)", "C3S")),
]
INVARIANTS = [dict(id=i, T=T, sigT=s, x=x, solids=sol) for i, T, s, x, sol in _INV]

MONOTECTIC = dict(id="pheq:greig1927:monotectic_LA_LB_cristobalite", T=1971.15, sigT=10.0,
                  x_hi=x_wt(99.4), sigx=0.01)
CONSOLUTE = dict(id="pheq:greig1927:consolute_two_liquids", T=1998.15, sigT=15.0,
                 x=x_wt(73.5), sigx=0.03)
