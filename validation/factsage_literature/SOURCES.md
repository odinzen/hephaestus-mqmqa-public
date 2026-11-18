# Published FactSage MQMQA results: sources checked

Collected 2026-11-14 for the cross-check described in `../thermochimica/PROTOCOL.md`. This file
lists every paper looked at, whether it is usable, and why. It holds no FactSage result values;
those are sealed in `factsage_published.json` outside the repository (hash in `SEALED_HASHES.txt`).
Inputs and conditions for the usable cases are in `conditions.json`.

A source is usable only if it prints (a) every model parameter of the phases involved, or a
ChemSage file, and (b) numbers computed with FactSage under stated conditions. Bibliographic data
were checked against Crossref (journal articles), the arXiv and Zenodo APIs, or the OSTI record
(reports) on 2026-11-14.

The local trove came first. `juno/literature` holds no MQMQA paper with FactSage numbers (only
Wu, Eriksson, Pelton and Blander 1993 on FeO-MgO-SiO2 with the pair-approximation MQM). Zotero
has entries for MQM Parts I and IV, Poschmann et al. 2021 and Paz Soldan Palma et al. 2023, all
without attached PDFs.

## Usable

### 1. Ocadiz Flores et al. 2021, with the 2022 correction (case A)

- J.A. Ocadiz Flores, B.A.S. Rooijakkers, R.J.M. Konings, A.L. Smith, Thermodynamic description
  of the ACl-ThCl4 (A = Li, Na, K) systems, Thermo 1 (2021) 122-133.
  https://doi.org/10.3390/thermo1020009
- J.A. Ocadiz Flores, B.A.S. Rooijakkers, R.J.M. Konings, A.L. Smith, Correction: Ocadiz Flores
  et al. Thermodynamic description of the ACl-ThCl4 (A = Li, Na, K) systems. Thermo 2021, 1,
  122-133, Thermo 2 (2022) 394-400. https://doi.org/10.3390/thermo2040027
- Open access (CC BY 4.0). Read from the TU Delft repository copies, the 2021 one marked
  "Corrected: 8 November 2022".
- Parameters: yes. Table 2 (all end members and compounds, Cp form stated), Table 3 (cation
  coordination numbers), Equations (7)-(9) (liquid, in the chi variable). The correction replaced
  the liquid parameters and the compound enthalpies and entropies; only the corrected set is used.
- FactSage numbers: yes, FactSage 7.2. Correction Table 4 (same as Table 4 of the corrected 2021
  paper), invariant temperatures and liquid compositions in LiCl-, NaCl- and KCl-ThCl4.
- Also in the paper, not taken: Figures 4 and 5 (mixing enthalpy and entropy of the liquids at
  1100 K), which could be digitized later.

### 2. Paz Soldan Palma et al. 2026 (case B)

- J. Paz Soldan Palma, A.M. Mofrad, J. Schorne-Pinto, A. Padinhare Manissery, T.M. Besmann,
  Thermodynamic evaluation and modeling of the CeF3-LaF3-LiF-NaF system, J. Chem. Thermodyn.
  218 (2026) 107683. https://doi.org/10.1016/j.jct.2026.107683
- Read from the published version on OSTI (record 3367480).
- Parameters: yes for the four LiF/NaF-LaF3/CeF3 binaries. Table 1 (coordination numbers),
  Table 2 (end members and compounds), Table 3 (liquid and solid-solution terms). Not printed:
  the Cp functional form (columns a-d only, read as a + bT + cT^-2 + dT^2), the meaning of the
  chi subscript notation, and the LiF-NaF liquid and cubic parameters (taken from Schorne-Pinto et
  al.). The interpretations used are written into `conditions.json`.
- FactSage numbers: yes, FactSage 8.3. Table 4, rows labelled "Present work" (eutectic,
  peritectic and eutectoid temperatures and liquid compositions).
- Not usable from this paper: Table 5 (quaternary liquidus, needs LiF-NaF parameters).

### 3. Paz Soldan Palma et al., PyCalphad MQMQA paper, arXiv version (case C, digitized)

- J. Paz Soldan Palma, R. Gong, B.J. Bocklund, R. Otis, M. Poschmann, M. Piro, Y. Wang,
  T.G. Levitskaia, S. Hu, H. Kim, Z.-K. Liu, S.-L. Shang, Thermodynamic modeling with uncertainty
  quantification using the modified quasichemical model in quadruplet approximation:
  Implementation into PyCalphad and ESPEI, arXiv:2204.09111v2 (2022).
  https://arxiv.org/abs/2204.09111
- Journal version: J. Paz Soldan Palma, R. Gong, B.J. Bocklund, R. Otis, M. Poschmann, M. Piro,
  S. Shahbazi, T.G. Levitskaia, S. Hu, N.D. Smith, Y. Wang, H. Kim, Z.-K. Liu, S.-L. Shang,
  Calphad 83 (2023) 102618. https://doi.org/10.1016/j.calphad.2023.102618 (author list differs
  from the preprint).
- Data: Zenodo record https://doi.org/10.5281/zenodo.6471272 (CC BY 4.0), file
  `Supplement_Materials/pycalphad/Ocadiz_combined.dat`, the KF-NiF2 database of Ocadiz-Flores et
  al. 2018 in ChemSage format (liquid model SUBG).
- FactSage numbers: only in arXiv v2 Figure 3 (Gibbs energy, enthalpy and entropy of the KF-NiF2
  liquid at 1600 K, ten compositions each, FactSage shown as green triangles). Digitized. The
  LLNL accepted-manuscript copy on OSTI (record 2205714) replaced this figure with a Gibbs energy
  surface and has no FactSage comparison; the journal version was not checked.
- The supplement notebook holds Thermochimica values for this figure, not FactSage ones. A
  notebook cell reproduces PyCalphad's plotting helper (`eqplot`); it was seen while searching the
  notebook for data and is unrelated to the MQMQA model.

## Not usable, or not accessed

| Reference | Parameters | FactSage numbers | Status |
|---|---|---|---|
| M. Poschmann, P. Bajpai, B.W.N. Fitzpatrick, M.H.A. Piro, Recent developments for molten salt systems in Thermochimica, Calphad 75 (2021) 102341. https://doi.org/10.1016/j.calphad.2021.102341 | unknown | abstract says Thermochimica was benchmarked against FactSage | not accessed (ScienceDirect refused the accepted manuscript). Fetch. |
| A.D. Pelton, P. Chartrand, G. Eriksson, The modified quasi-chemical model: Part IV. Two-sublattice quadruplet approximation, Metall. Mater. Trans. A 32 (2001) 1409-1416. https://doi.org/10.1007/s11661-001-0230-7 | unknown | unknown | not accessed (closed). Fetch. |
| P. Chartrand, A.D. Pelton, The modified quasi-chemical model: Part III. Two sublattices, Metall. Mater. Trans. A 32 (2001) 1397-1407. https://doi.org/10.1007/s11661-001-0229-0 | unknown | unknown | not accessed (closed). Fetch. |
| P. Chartrand, A.D. Pelton, Thermodynamic evaluation and optimization of the LiF-NaF-KF-MgF2-CaF2 system using the modified quasi-chemical model, Metall. Mater. Trans. A 32 (2001) 1385-1396. https://doi.org/10.1007/s11661-001-0228-1 | likely | likely | not accessed (closed). Fetch. |
| A.D. Pelton, P. Chartrand, Thermodynamic evaluation and optimization of the LiCl-NaCl-KCl-RbCl-CsCl-MgCl2-CaCl2 system using the modified quasi-chemical model, Metall. Mater. Trans. A 32 (2001) 1361-1383. https://doi.org/10.1007/s11661-001-0227-2 | likely | likely | not accessed (closed). Fetch. |
| A.D. Pelton, P. Chartrand, The modified quasi-chemical model: Part II. Multicomponent solutions, Metall. Mater. Trans. A 32 (2001) 1355-1360. https://doi.org/10.1007/s11661-001-0226-3 | n/a | n/a | not accessed; one-sublattice model, outside MQMQA. |
| A.D. Pelton, S.A. Degterov, G. Eriksson, C. Robelin, Y. Dessureault, The modified quasichemical model I, Binary solutions, Metall. Mater. Trans. B 31 (2000) 651-659. https://doi.org/10.1007/s11663-000-0103-2 | n/a | n/a | not accessed; pair approximation, outside MQMQA. |
| G. Lambotte, P. Chartrand, Thermodynamic optimization of the (Na2O + SiO2 + NaF + SiF4) reciprocal system using the Modified Quasichemical Model in the Quadruplet Approximation, J. Chem. Thermodyn. 43 (2011) 1678-1699. https://doi.org/10.1016/j.jct.2011.05.038 | likely | likely | not accessed (closed). A true reciprocal case; fetch. |
| J.A. Ocadiz-Flores, E. Capelli, P.E. Raison, R.J.M. Konings, A.L. Smith, Thermodynamic assessment of the LiF-NiF2, NaF-NiF2 and KF-NiF2 systems, J. Chem. Thermodyn. 121 (2018) 17-26. https://doi.org/10.1016/j.jct.2018.01.023 | yes (as the Zenodo .dat) | probably (invariant table) | not accessed. Open access on ScienceDirect, which refused the download; the TU Delft repository serves an unrelated PDF under this record. Fetch. |
| J.C. Ard, J.A. Yingling, T.J. Johnson, J. Schorne-Pinto, M. Aziziha, C.M. Dixon, M.S. Christian, J.W. McMurray, T.M. Besmann, Development of the Molten Salt Thermal Properties Database - Thermochemical (MSTDB-TC), example applications, and LiCl-RbCl and UF3-UF4 system assessments, J. Nucl. Mater. 563 (2022) 153631. https://doi.org/10.1016/j.jnucmat.2022.153631 | unknown | unknown | not accessed (accepted manuscript refused). Fetch. |
| M. Aziziha, J. Schorne-Pinto, J.A. Yingling, C.M. Dixon, J.C. Ard, M.A.A. Aslani, A.M. Mofrad, T.M. Besmann, Thermodynamic assessment of lithium halide reciprocal salt systems for energy applications, J. Mol. Liq. 364 (2022) 119973. https://doi.org/10.1016/j.molliq.2022.119973 | Table 1 plus supplement (coordination numbers) | calculated eutectics in Tables 2-3, software not named | accepted manuscript read (OSTI 2423954). Not usable unless the journal version or supplement names FactSage. |
| C.M. Dixon, J. Schorne-Pinto, M. Aziziha, J.A. Yingling, R.E. Booth, T.M. Besmann, Thermodynamic modeling of CsF with LiF-NaF-KF for molten fluoride-fueled reactors, J. Mol. Liq. 406 (2024) 125056. https://doi.org/10.1016/j.molliq.2024.125056 | Table 1 plus supplement | calculated invariants in Tables 2-9, software not named | accepted manuscript read (OSTI 3028744; its author list omits R.E. Booth). Same gap as above. |
| J.A. Wilson et al. (16 authors), Thermodynamic properties of ZrCl4 with LiCl, NaCl, KCl, CsCl, MgCl2, and UCl3 for molten salt reactor applications, J. Mol. Liq. 437 (2025) 128578. https://doi.org/10.1016/j.molliq.2025.128578 | incomplete (mixed-pair coordination numbers taken from MSTDB-TC 4.0, not printed; ternary tables need MSTDB binaries) | FactSage 8.3, ternary eutectics in Tables 7-10 | not usable. |
| G.I.L. van Oudenaren, J.A. Ocadiz-Flores, A.L. Smith, Coupled structural-thermodynamic modelling of the molten salt system NaCl-UCl3, J. Mol. Liq. 342 (2021) 117470. https://doi.org/10.1016/j.molliq.2021.117470 | end members in Table 2; liquid parameters only in the supplement (not retrieved); multi-species uranium liquid | FactSage 7.0, figures | not usable from the main text. The supplement could make it usable. |
| T.M. Besmann, J. Schorne-Pinto, M. Aziziha, A.M. Mofrad, R.E. Booth, J.A. Yingling, J. Paz Soldan Palma, C.M. Dixon, J.A. Wilson, D. Hartanto, Applications of thermochemical modeling in molten salt reactors, Materials 17 (2024) 495. https://doi.org/10.3390/ma17020495 | no (refers to MSTDB-TC) | FactSage 8.2 speciation, Table 4 | not usable. |
| T.M. Besmann, J. Schorne-Pinto, Developing practical models of complex salts for molten salt reactors, Thermo 1 (2021) 168-178. https://doi.org/10.3390/thermo1020012 | unknown | unknown | not accessed (MDPI refused automated download). Fetch. |
| M. Piro, P. Bajpai, M. Poschmann, Development of a Gibbs energy minimiser for the MOOSE-based corrosion modelling app Yellowjacket and validation of MSTDB, report INL/RPT-22-69782 (2022). https://doi.org/10.2172/1963894 | no | relative differences from FactSage only (Figures 5 and 14) | not usable. |
| R. Gong, S. Shahbazi, Demonstrating PyCalphad, ESPEI, and MSTDB-TC for MSR applications, report ANL/NSE-24/64 (2024). https://doi.org/10.2172/2468788 | no (MSTDB-TC 2.0 not reproduced) | FactSage equilibrium runs | not usable. |
| S. Shahbazi, M. Bucknor, S. Thomas, A. Merwin, Q. Zhou, Thermochemical modeling in molten fluoride salts for radionuclide speciation, report ANL/KP-21/1 (2021). https://doi.org/10.2172/1812872 | no | no new calculations with parameters | not usable (literature review). |
| L. Hao, S. Sridar, W. Xiong, Thermodynamic description of molten salt systems: KCl-LiCl-NaCl and KCl-LiCl-NdCl3, J. Mol. Liq. 382 (2023) 121869. https://doi.org/10.1016/j.molliq.2023.121869 | n/a | n/a | out of scope (Thermo-Calc, ionic two-sublattice model). |
| N. Ury, B. Bocklund, E.E. Moore, A.P. Perron, Development of a Ca-K-Li-RE-Cl (RE = La, Ce, Pr, Nd) rare-earth molten salt database, Calphad 95 (2026) 103003. https://doi.org/10.1016/j.calphad.2026.103003 | n/a | n/a | out of scope (PyCalphad, not FactSage). |

## Counts

24 references checked (3 usable, 11 not accessed, 10 read and not usable or out of scope).
Usable cases: A (15 invariants, tabulated), B (8 invariants, tabulated), C (30 liquid property
points, digitized).

## Predictions (16 November 2026)

- Case C predicted by `predict.py` with the engine of 3f38162 from `data/Ocadiz_combined.dat`,
  downloaded from Zenodo record 10.5281/zenodo.6471272 on Michael's go (zip and file SHA-256 equal
  to those in conditions.json). The values stay sealed until cases A and B are predicted too, since
  one sealed file holds all three.
- Disclosure: earlier on 16 November the text of arXiv:2204.09111v2 (the case C source) was
  extracted to read its MQMQA equations, for an unrelated question (the ClAlNa liquid). Only the
  text was read; Figure 3, which holds the FactSage values, was not looked at, and no number from
  it entered the prediction.
- Cases A and B predicted on 17 November 2026 by `predict.py AB` with the engine of 754177c, from
  seven ChemSage files that `build_cases.py` writes from the transcribed tables in
  `conditions.json`, one per binary (`data/caseA_*.dat`, `data/caseB_*.dat`). The source papers
  were not opened for this step, so the transcription was not checked against them again; the
  FactSage values stay sealed. `check_cases.py` compares every species' Gibbs energy as the engine
  reads it with G = H - TS integrated numerically from the tables: 312 species-temperature checks,
  largest difference 8e-7 J/mol (a planted change of 0.01 J/K in one S298 shows as 10 J/mol at
  1000 K). Each invariant was found where a phase appears or vanishes on heating at a fixed bulk
  composition, and for each the phases just below and above were checked against the reaction the
  paper names. 22 of 23 are calculated; B08 (NaCeF4 = NaF + CeF3) is not found, NaCeF4 being stable
  down to 298.15 K where the tables start. The SUBQ zeta of the files (1.3774438) does not change
  the single-anion liquid (identical Gibbs energies with zeta 6).

## After unsealing (18 November 2026)

Scored once by `compare.py` (results in `RESULTS.md`). For the case B recheck, Paz Soldan Palma
et al. 2026 was downloaded again from OSTI on Michael's go (SHA-256 032696b6...) and filed in
Juno; Tables 1-3 match `conditions.json`.
