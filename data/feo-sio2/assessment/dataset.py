"""The measured FeO-SiO2 dataset the v0.4 liquid is assessed against.

Liquidus: Bowen & Schairer 1932, Am. J. Sci. 24, 177-213, Table 1 (p. 187), iron-saturated
melts quenched from an iron crucible under nitrogen, compositions in weight percent as
analysed. Their small Fe2O3 is counted as FeO (total iron), as they reduce their own
mixtures. Temperatures are the completion of melting (+-2 K near fayalite, +-5 K on the
wustite and silica sides). The model has one silica phase (cristobalite); the two points
Bowen & Schairer give with tridymite first are scored against it. Row ids follow the
assessment workspace (assessments/FeO-SiO2, pheq:bowen_schairer1932:*).

Monotectic: Bowen & Schairer 1932 Fig. 4 (p. 200) draw cristobalite + two liquids at 1690 degC
with conjugates at 42.8 and 3.0 wt% FeO (digitized, +-0.5 wt% and +-3 K read error). They did
not measure it (their iron crucibles melt above 1515 degC); the text (p. 201) takes it from
Greig 1927 (Am. J. Sci. 14, 479) by a short extrapolation from mixtures holding a little Fe2O3,
so it carries a wider sigma than their own liquidus.

Activities: data/feo-sio2/activities_feo_bjorkman1985_fig3.csv (measured symbols only).
"""
M = {"FeO": 71.844, "Fe2O3": 159.688, "SiO2": 60.083}


def x_sio2(feo, fe2o3, sio2):
    """Mole fraction SiO2 with total iron as FeO."""
    n_feo = feo / M["FeO"] + 2.0 * fe2o3 / M["Fe2O3"]
    n_si = sio2 / M["SiO2"]
    return n_si / (n_feo + n_si)


# (id suffix, T_K, sigma_K, wt% FeO, Fe2O3, SiO2, primary solid)
_B32 = [
    ("liquidus_1380C", 1653.15, 5.0, 88.44, 11.56, 0.00, "wustite"),
    ("liquidus_1315C", 1588.15, 5.0, 82.73, 9.00, 8.27, "wustite"),
    ("liquidus_1215C", 1488.15, 5.0, 75.19, 4.73, 20.08, "wustite"),
    ("liquidus_1193C", 1466.15, 2.0, 71.53, 3.32, 25.15, "fayalite"),
    ("liquidus_1202C", 1475.15, 2.0, 70.21, 2.50, 27.29, "fayalite"),
    ("congruent_fayalite_1205C", 1478.15, 2.0, 68.36, 2.25, 29.39, "fayalite"),
    ("liquidus_1203C", 1476.15, 2.0, 66.36, 2.21, 31.43, "fayalite"),
    ("liquidus_1187C", 1460.15, 2.0, 62.65, 1.39, 35.96, "fayalite"),
    ("liquidus_1260C", 1533.15, 2.0, 60.22, 1.32, 38.46, "silica"),     # tridymite
    ("liquidus_1365C", 1638.15, 2.0, 58.98, 1.31, 39.71, "silica"),     # tridymite
    ("liquidus_1455C", 1728.15, 5.0, 56.56, 1.15, 42.29, "silica"),     # cristobalite
    ("liquidus_1505C", 1778.15, 5.0, 55.21, 1.14, 43.49, "silica"),     # cristobalite
]
LIQUIDUS = [dict(id="pheq:bowen_schairer1932:" + i, T=T, sigT=s, x=x_sio2(a, b, c), solid=sol)
            for i, T, s, a, b, c, sol in _B32]

# cristobalite + L1 + L2; x_lo is the iron-rich liquid
MONOTECTIC = dict(id="pheq:bowen_schairer1932:fig4_monotectic_1690C", T=1963.15, sigT=10.0,
                  x_lo=x_sio2(42.8, 0.0, 57.2), x_hi=x_sio2(3.0, 0.0, 97.0), sigx=0.02)

# The fitted offset in ln a(FeO) of the sub-1644 K points: their reference is the supercooled
# iron-saturated melt, whose level no measurement fixes (assess.py fits it).
DLNA_LOW = 0.2427
