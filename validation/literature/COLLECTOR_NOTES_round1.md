# Collector notes, round 1

Collected 2026-11-14 by the round 1 collector agent under RULES.md (commit 43822a8). This file
holds no measured values. The sealed file is `../sealed/literature_values_round1.csv`, SHA-256
`237cd910dc4c696bb1b021f50076e0f6c5a25b99a237ac3ea2c025a441e73ec9` (480 rows, 7 sources).
The collector's working copy is `../sealed/collector_working_copy_round1.csv` (identical bytes),
and the transcription files, page renders and downloaded papers are in
`../sealed/collector_round1_workfiles/`, kept out of the shared scratch folder because they carry
the values.

Every bibliographic record below was checked against Crossref on 2026-11-14 (authors in order,
title, journal, volume, pages, year).

## Sources used

| # | Reference | System | Quantity | Points | Where | Digitized |
|---|---|---|---|---|---|---|
| 1 | Y. Kang, D. Sichen, K. Morita, Activities of SiO2 in some CaO-Al2O3-SiO2(-10%MgO) melts with low SiO2 contents at 1873K, ISIJ Int. 47 (2007) 805-810, doi:10.2355/isijinternational.47.805 | CaO-Al2O3-SiO2 | a(SiO2), solid reference, 1873 K | 10 | Table 2 (ternary rows; the MgO-bearing rows are outside the systems) | no |
| 2 | K. Kume, K. Morita, T. Miki, N. Sano, Activity measurement of CaO-SiO2-AlO1.5-MgO slags equilibrated with molten silicon alloys, ISIJ Int. 40 (2000) 561-566, doi:10.2355/isijinternational.40.561 | CaO-SiO2; CaO-Al2O3-SiO2; CaO-MgO-SiO2 face; MgO-SiO2 | a(SiO2), a(CaO), a(AlO1.5), a(MgO), solid references, 1823 and 1873 K | 244 (CaO-SiO2 24, CaO-Al2O3-SiO2 141, CaO-MgO-SiO2 75, MgO-SiO2 4) | Tables 1, 2, 3 (Table 4 has Al2O3 and MgO together, outside the systems) | no |
| 3 | N. L. Bowen, J. F. Schairer, E. Posnjak, The system CaO-FeO-SiO2, Am. J. Sci. s5-26 (1933) 193-284, doi:10.2475/ajs.s5-26.153.193 | CaO-FeO-SiO2 face, iron crucibles | liquidus 85, temperature of beginning of melting 15, invariant temperatures 11, invariant liquid compositions 27, coexisting solid compositions 12 | 150 | Table I (a)-(g), pp199-202; Table II, p210 | no |
| 4 | J. B. Ferguson, H. E. Merwin, The ternary system CaO-MgO-SiO2, Am. J. Sci. s4-48 (1919) 81-123, doi:10.2475/ajs.s4-48.284.81 | CaO-MgO-SiO2 face | invariant temperatures 12, invariant liquid compositions 36 | 48 | text, pp99-103 (quench Tables III-XIII) | no |
| 5 | S. Ban-ya, Y. Iguchi, H. Honda, H. Ishizuka, Heats of formation of liquid FetO-SiO2 slags, Tetsu-to-Hagane 71 (1985) 846-852, doi:10.2355/tetsutohagane1955.71.7_846 | FeO-SiO2, iron vessel | enthalpy of mixing FetO(l) + SiO2(beta-cristobalite), 1693 K | 25 | Fig. 5 | yes, all 25 |
| 6 | X. Xu, G. Dehghani, J. Ning, P. Li, Basic properties of eutectic chloride salts NaCl-KCl-ZnCl2 and NaCl-KCl-MgCl2 as HTFs and thermal storage media measured using simultaneous DSC-TGA, Solar Energy 162 (2018) 431-441, doi:10.1016/j.solener.2018.01.067 | NaCl-KCl-MgCl2 | DSC melting onset (recorded as solidus_T) | 2 | Table 6, compositions Table 2 | no |
| 7 | X. Wang, J. Del Rincon, P. Li, Y. Zhao, J. Vidal, Thermophysical properties experimentally tested for NaCl-KCl-MgCl2 eutectic molten salt as a next-generation high-temperature heat transfer fluids in concentrated solar power systems, J. Sol. Energy Eng. 143 (2021) 041005, doi:10.1115/1.4049253 | NaCl-KCl-MgCl2 | DSC melting onset (recorded as solidus_T) | 1 | Table 2 | no |

Totals: 480 points from 7 sources, 25 digitized. By quantity: activities 254, liquidus 85,
solidus or melting onset 18, invariant temperatures 23, invariant liquid compositions 63,
coexisting solid compositions 12, enthalpies of mixing 25. Chloride points are 3; no LiCl-KCl,
NaCl-KCl or NaCl-MgCl2 point is in this round.

Points that need care when scoring (stated in the `notes` column too):

- Kume 2000: the a(SiO2) columns were derived in the companion paper K. Morita, K. Kume, N. Sano,
  ISIJ Int. 40 (2000) 554-560, doi:10.2355/isijinternational.40.554, and are tabulated in Kume.
  Rows at silica saturation carry an activity the authors set to unity. CaO activities on the
  CaO-free MgO-SiO2 rows (zero by composition) were not recorded. Compositions are mole
  fractions on the AlO1.5 basis where alumina is present.
- Bowen, Schairer and Posnjak 1933: liquid compositions are as analysed, with Fe2O3 listed
  separately (iron-saturated melts). One Table I(c) row sums to about 101 mass% as printed and
  was entered unchanged. Rows that sit on a boundary curve appear in two sub-tables with
  different primary phases, entered as printed. Invariant liquid compositions are rounded in
  the source. The binary invariants M, V, X and the CaFeSiO4 melting point lie on internal
  joins of the ternary; V, X and CaFeSiO4 come from the same authors' companion paper
  (Am. J. Sci. s5-25 (1933) 273-297, doi:10.2475/ajs.s5-25.148.273). Invariant J's temperature
  is marked uncertain by the authors.
- Ferguson and Merwin 1919: only the twelve quintuple points with a stated composition and
  temperature were taken.
- Invariant points: the invariant temperature row gives the assemblage and withholds the
  composition, and each oxide of the invariant liquid has its own row with the measured
  fraction in `value`, so the conditions file does not reveal measured compositions.
- Ban-ya 1985: compositions and enthalpies were both read off Fig. 5 (Hough circle centres
  calibrated on the plot frame, checked by overlay), in cal/mol converted at 4.184 J/cal, per
  mole of FetO + SiO2. Reference states are liquid FetO (with its Fe3+ at iron saturation) and
  solid beta-cristobalite. The paper's Table 2 holds smoothed values, not measurements, and was
  not taken.
- Xu 2018 and Wang 2021: values were read from the OSTI accepted manuscripts (OSTI 1538838,
  1866380). The DSC onset of a nominal eutectic mixture is recorded as `solidus_T`. Heat
  capacities and heats of fusion in these papers are not quantities RULES.md lists and were not
  taken.

## Sources excluded and why

- Xu 2018, salt #6 (KCl-MgCl2, 68/32 mol%): its melting onset equals the "Xu 2018" KCl-side
  eutectic the KCl-MgCl2 fit uses (kcl-mgcl2 PROVENANCE; the fitted point is most likely
  Xu et al., J. Sol. Energy Eng. 140 (2018), doi:10.1115/1.4040065, same group). Excluded. The
  two ternary salts from the same paper were kept; seal.py flags the source as "Xu 2018" and
  the code side should confirm the ternary rows are not in any fit.
- In USED_SOURCES or the provenance files: Rankin & Wright 1915; Shepherd, Rankin & Wright
  1909; Bowen & Greig 1924; Jerebtsov & Mikhailov 2001; Kay & Taylor 1960; Zaitsev et al. 1997;
  Stolyarova et al. 1991; Greig 1927; Abdul et al. 2023 (and the invariants it compiles, which
  the CaO-SiO2 fit uses); Bowen & Schairer 1932 and 1935; Bowen 1914; Bowen & Andersen 1914;
  Nafziger & Muan 1967; Schuhmann & Ensio 1951; Bodsworth 1959; Distin et al. 1971; Bjorkman
  1985; Perry & Fletcher 1993; Hersh & Kleppa 1965; Sangster & Pelton 1987; Janz 1992;
  Solomons 1958; Powers & Blalock 1953; INL 2011; Mohan et al. 2018; Villada et al. 2021 and
  Villada et al. 2022 (Front. Energy Res. 10, 809663, cited in nacl-mgcl2 PROVENANCE as
  "Wang et al. 2022"); Duemmler 2022.
- Ozturk & Fruehan 1987 (Metall. Trans. B 18, 746): USED_SOURCES lists "Fruehan 1987" (the
  comparison column of Zaitsev's Table 4). Excluded to be safe; also paywalled.
- Bowen, Schairer and Posnjak 1933, Table II entries on the CaO-SiO2 and FeO-SiO2 edges and the
  unary melting points: attributed in the table to Greig or to Bowen & Schairer 1932 (both
  used), or pure-component melting. Not taken.
- Ferguson and Merwin 1919: point 16 (temperature only estimated, location not determined) and
  point 12 (no values) are not measurements. The quench runs in Tables I-XXI are brackets, not
  stated liquidus temperatures, and were not converted; a later round could score them as
  brackets.
- Assessments and calculations, not measurements: Hidayat et al. 2017 (JPED and Calphad),
  Nekhoroshev et al. 2025, Wu, Eriksson, Pelton & Blander 1993, Mao 2005 thesis, Robelin &
  Chartrand 2011, Tan et al. 2024.
- Outside the systems: Chen et al. 2022 ISIJ Int. 62, 1341 (MnO and MgO in every slag); Ban-ya,
  Hino & Yuge 1985, Tetsu-to-Hagane 71, 853 (MnO); Ohta & Suito 1998 CaO-SiO2-Al2O3-MgO slags;
  Holmes & Mesmer 1978 (aqueous).
- Deferred: Ohta & Suito 1998 (Metall. Mater. Trans. B 29, 119-129,
  doi:10.1007/s11663-998-0014-1, held in the trove). Only two CaO-MgO-SiO2 slags are in the
  systems, each an average over several runs with spread compositions, and one slag's
  composition is published in a different article. Left for a round where that article is at
  hand.

## Paywalled or not yet read (round 2 candidates)

Fetch by full reference; those marked "verified" were checked on Crossref this session.

1. H. Ohta, H. Suito, Activities in CaO-SiO2-Al2O3 slags and deoxidation equilibria of Si and Al,
   Metall. Mater. Trans. B 27 (1996) 943, doi:10.1007/s11663-996-0008-9 (title and DOI from
   a reference list, not yet verified). CaO-Al2O3-SiO2 activities at 1873 K.
2. R. H. Rein, J. Chipman, Activities in the liquid solution SiO2-CaO-MgO-Al2O3 at 1600 C,
   Trans. Metall. Soc. AIME 233 (1965) 415-425 (no DOI). CaO-Al2O3-SiO2 and CaO-MgO-SiO2
   a(SiO2).
3. X. Wen, M. Shevchenko, E. Jak, Experimental study of "CuO0.5"-"FeO"-SiO2 and "FeO"-SiO2
   systems in equilibrium with metal at 1400-1680 C, J. Alloys Compd. 885 (2021) 160853,
   doi:10.1016/j.jallcom.2021.160853 (verified). FeO-SiO2 at iron saturation, EPMA phase
   compositions.
4. W. C. Allen, R. B. Snow, The orthosilicate-iron oxide portion of the system CaO-"FeO"-SiO2,
   J. Am. Ceram. Soc. 38 (1955), doi:10.1111/j.1151-2916.1955.tb14944.x (DOI from Crossref
   search; fields not yet verified). CaO-FeO-SiO2 at iron saturation.
5. J. Park, S. Sridhar, R. J. Fruehan, Metall. Mater. Trans. B 44 (2013) 13,
   doi:10.1007/s11663-012-9786-4 (from a reference list; not yet verified). CaO-Al2O3-SiO2
   a(SiO2).
6. J. D. Baird, J. Taylor, Trans. Faraday Soc. 54 (1958) 526, doi:10.1039/TF9585400526 (from a
   reference list; not yet verified). Silica activity in lime-silica melts.
7. R. A. Sharma, F. D. Richardson, The solubility of calcium sulphide and activities in
   lime-silica melts, J. Iron Steel Inst. 200 (1962) 373-379 (no DOI; pages unverified).
8. O. Karakaya, W. T. Thompson, Thermodynamic properties of MgCl2-NaCl melts from EMF,
   J. Electrochem. Soc. 133 (1986) 702, doi:10.1149/1.2108658 (title and DOI to verify).
   NaCl-MgCl2 activities.
9. G. Pan, J. Ding, Y. Yao, Z. Yuan, D.-J. Lee, Thermal performance of MgCl2-NaCl-KCl eutectic
   salt for the next generation concentrated solar power, Sol. Energy Mater. Sol. Cells 276
   (2024) 113091, doi:10.1016/j.solmat.2024.113091 (verified authors, journal, volume).
10. Z. Rong, J. Gui, Y. Wang, C. Lin, D. Zhang, F. Qiao, Thermophysical properties and pumping
    characteristics of near-eutectic NaCl-KCl-MgCl2 molten salts, Appl. Therm. Eng. 305 (2026)
    133027, doi:10.1016/j.applthermaleng.2026.133027 (verified authors, journal, volume).

Open but not taken in round 1 (bounded run): S.-W. Cho, H. Suito, ISIJ Int. 34 (1994) 177-185,
doi:10.2355/isijinternational.34.177 (CaO-Al2O3-SiO2, downloaded, not processed);
T. Fujisawa, H. Sakao, Tetsu-to-Hagane 63 (1977) 1504, doi:10.2355/tetsutohagane1955.63.9_1504
(CaO-Al2O3-SiO2 activities, in Japanese); Bowen, Schairer & Posnjak 1933, The system
Ca2SiO4-Fe2SiO4, doi:10.2475/ajs.s5-25.148.273; the Ferguson and Merwin quench brackets.
No open source turned up for FeO-MgO-SiO2 at iron saturation, LiCl-KCl, NaCl-KCl or
NaCl-MgCl2 that is not already used.

## Search log

1. Read RULES.md, README.md, template.csv, USED_SOURCES.txt, seal.py, and the PROVENANCE files
   for every oxide and chloride database in `data/` (text only, for the overlap check).
2. Local trove `Code/juno/literature` (folders Al2O3-SiO2, CaO-Al2O3, CaO-Al2O3-SiO2, CaO-SiO2,
   FeO-MgO-SiO2, FeO-SiO2, MgO-SiO2, oxide-slag, KCl-MgCl2, LiCl-KCl, NaCl-KCl, NaCl-MgCl2,
   _molten_salt, _fam_chlorides) and the ledger (PAPERS.tsv, PAYWALLED_SOURCES.tsv,
   OPEN_SOURCES.tsv). Found locally and used: Xu 2018 (OSTI 1538838), Wang 2021 (OSTI 1866380).
   Found and deferred or excluded: Ohta & Suito 1998, Chen 2022, Hidayat 2017, Nekhoroshev 2025,
   Jacobson 2015 and Copland 2011 (KEMS methods reports, no data in the systems), Stebbins &
   Carmichael 1984 (fayalite fusion, a pure compound).
3. Zotero and the OneDrive ASU folders were not searched; the trove and its ledger already
   index the relevant literature.
4. Reference lists of Chen 2022, Kume 2000 and Nekhoroshev 2025 gave the leads for Kang 2007,
   Kume 2000, Wen 2021, Allen & Snow 1955 and Ban-ya 1985.
5. Web: J-STAGE (open) for Kang 2007, Kume 2000, Cho & Suito 1994, Ban-ya 1985 (two papers);
   ajsonline.org (open archive) for Bowen, Schairer & Posnjak 1933 and Ferguson & Merwin 1919;
   Crossref API for every reference and for leads.
6. Transcription: tables read from page images at 4-5x zoom; composition sums checked (all within
   rounding except the one printed row noted above); Ban-ya Fig. 5 digitized and checked by
   overlay.
7. Built the CSV in the template's columns, sealed with `python seal.py round1_values.csv
   round1`, and moved the working copy into `../sealed/`.

## For the code side

- `phase_or_species` and `notes` are kept in `conditions_round1.csv`, as the template's example
  row does. For liquidus rows that column names the reported primary phase, so the phase-identity
  score in RULES.md is not blind to it. Decide before predicting whether to ignore that column.
- PROVENANCE_combined.md says the quaternary file carries no rankinite or other Ca-silicate line
  compounds beyond wollastonite and larnite, and several Bowen-Schairer-Posnjak and
  Ferguson-Merwin points name such phases. RULES.md already says every point is reported.
