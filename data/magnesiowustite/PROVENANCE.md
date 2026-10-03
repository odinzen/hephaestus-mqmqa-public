# Magnesiowustite (Fe,Mg)O provenance

The rock-salt solid solution between iron-saturated wustite and periclase. Wustite and periclase
are fully miscible at slag temperatures, so the FeO-MgO-SiO2 and CaO-FeO-MgO-SiO2 files carry
one (Fe,Mg)O phase, `MAGNESIOWUSTITE`, in place of the two pure oxides they held until
2026-09-30. Without it the iron of an MgO-rich bulk had nowhere to go but a small spurious
liquid.

`magnesiowustite.py` defines the phase and writes its ChemSage block; `assessment/assess.py`
fits it against `assessment/dataset.py`.

## Model

Per mole of (Fe,Mg)O, one metal site:

    G = y_Fe G(FeO) + y_Mg G(MgO) + RT (y_Fe ln y_Fe + y_Mg ln y_Mg) + y_Fe y_Mg [L0 + L1 (y_Fe - y_Mg)]

G(FeO) is the iron-saturated wustite of data/feo-sio2 and G(MgO) the periclase of
data/mgo-sio2, the solids those binaries are assessed on. L0 = 12965.2 J, L1 = 1158.7 J.

## Data and result

Nafziger & Muan 1967, Am. Mineral. 52, 1364-1385 (open access), Table 9: coexisting
magnesiowustite and olivine at 1200 degC, iron saturated, with the magnesiowustite FeO and MgO
activities (Hahn & Muan 1962, as they reproduce them). Read from the scan; the pure-FeO row is
left out. The shipped olivine (Robie-Hemingway endmembers, Wood & Kleppa 1981 excess) is held
fixed.

| Data | Result |
|---|---|
| 14 activities (sigma 0.05 in ln a) | within 1.5 sigma |
| 7 olivine partners (sigma 0.02) | within 1 sigma except 0.30 vs 0.38 at magnesiowustite 0.84 |

Total cost 9.43, weighted RMS 0.95. The engine's Gibbs energy of the phase matches pycalphad
on the same file to 1e-10 J.

## Limits

- One temperature (1473 K) and T-independent L0, L1.
- No ferric iron: the solution is iron saturated, as are the slags these files describe.
- Lime is kept a separate phase in the CaO-FeO-MgO-SiO2 file (CaO-MgO has a wide solvus).
