# FeO-SiO2-liquid.dat provenance

Open FeO-SiO2 liquid-slag MQMQA database, **v0.1 (ideal endmembers)**. The Fe-side
counterpart of `data/mgo-sio2`, and the second binary the FeO-MgO-SiO2 ternary slag needs
(for the olivine + orthopyroxene + liquid diagram). **Iron-saturated**: all iron is Fe2+ /
FeO, no Fe3+ - matching the iron-crucible conditions of Bowen & Schairer's phase-equilibrium
work, and avoiding redox for now.

Built by `build_dat.py`; validated by `validate.py`. Run:

    C:/Users/busta/miniforge3/envs/calphad/python.exe data/feo-sio2/validate.py

## Pure-oxide liquid endmembers (open)

| Quantity | FeO | SiO2 | Source | Access |
|---|---|---|---|---|
| dHf(298) from elements | -272.044 kJ/mol | -908.4 kJ/mol (cristobalite) | NIST-JANAF (Chase 1998) / R&H 1995 | open |
| S(298), third law | 60.752 J/mol/K | 43.4 J/mol/K | NIST-JANAF / R&H 1995 | open |
| Cp(T) solid, Haas-Fisher a,b,c | 50.663, 8.711e-3, -3.134e5 | 72.75, 1.300e-3, -4.132e6 | fit to JANAF FeO(cr) 298-1500 K (max resid 0.35) / R&H | open |
| Fusion Tm | 1650 K | 1996 K | NIST-JANAF | open |
| Fusion dHfus | 24.058 kJ/mol | 9.581 kJ/mol | NIST-JANAF | open |

The FeO numbers are the NIST-JANAF (Chase 1998) critically-evaluated values for stoichiometric
FeO, already digitized in the assessment workspace
(`assessments/FeO-SiO2/data_tables/paper_nist_janaf__table_JANAF_web_table_Fe-020.csv`); the
Haas-Fisher Cp is a least-squares fit to the six tabulated FeO(crystal) Cp points (298-1500 K).
SiO2 is identical to `data/mgo-sio2` (Robie-Hemingway solid, JANAF fusion). Both endmember Gibbs
energies read back by the engine match a direct H - T*S evaluation to ~1e-7 J/mol, and both
reproduce their fusion temperatures exactly (dG_fus = 0 at Tm).

## What v0.1 is NOT (yet)

The interior mixing is **ideal** (excess MQMQA parameters are zero). An ideal FeO-SiO2 liquid
does not reproduce the measured fayalite congruent melting (1478 K / 1205 C, Bowen & Schairer
1932, digitized in the trove) or the FeO-SiO2 activities; those are set by the ordering energy
around the orthosilicate composition, exactly as in CaO-SiO2 / MgO-SiO2. The excess is the next
increment.

## Roadmap: the excess fit (data needed)

The FeO-SiO2 liquid excess can be fitted the same way as MgO-SiO2 (v0.2 method): the congruent
melting of fayalite fixes the entropy term, and an enthalpy-of-mixing anchor fixes the depth.
The enthalpy anchor can come from **MLIP melt-mixing MD** (env `mlip-screen`, no literature
needed, bias-corrected against calorimetry as in MgO-SiO2), or from measured **FeO-SiO2 melt
activities**:

- **Schuhmann & Ensio 1951**, "Thermodynamics of Iron-Silicate Slags: Slags Saturated with
  Gamma Iron," JOM 3:401. DOI 10.1007/BF03397323 - iron-saturated a(FeO), a(SiO2). The classic
  measured activity dataset (paywalled; abstract-level values may suffice for a cross-check).
- **Michal & Schuhmann 1952** (silica-saturated companion), JOM 4:723. DOI 10.1007/BF03398131.

Validation targets already in the trove: Bowen & Schairer 1932 FeO-SiO2 phase diagram
(fayalite congruent melting 1478 K; wustite / silica liquidus; eutectics), digitized in
`assessments/FeO-SiO2/data_tables/paper_bowen_schairer1932__table_1__pheq.csv`.

## What is deliberately excluded

No FactSage/FToxid or optimized-TDB parameters. Bjorkman 1985 and the Shishin/Jak
FeO-Fe2O3-SiO2 assessments are validation targets only, never a parameter source. The FeO
endmember is a JANAF single-substance evaluated value (allowed as an input).
