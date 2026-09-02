# Hephaestus: an open-source engine and database for the thermodynamics and phase diagrams of molten oxide slags

Michael E. Bustamante

Odinzen LLC, Houston, TX, United States

Corresponding author: michaelbusta@odinzen.io

ORCID: 0009-0009-9001-8151

**Abstract**

The Modified Quasichemical Model in the Quadruplet Approximation (MQMQA) is the standard thermodynamic description of short-range-ordered ionic melts, and it underpins the commercial databases used throughout pyrometallurgy. Open implementations exist inside larger frameworks, but no free oxide slag database exists at all, so every practical slag calculation still depends on closed data. Hephaestus addresses the model and the data together. The engine is a small dependency-free C core with a Python interface and a WebAssembly build, so the same code runs embedded, scripted, or in a browser with nothing installed. It reads ChemSage-format files directly, covering MQMQA liquids, compound energy formalism solid solutions, and stoichiometric compounds, and it calculates phase equilibria up to full ternary isothermal sections and liquidus projections. Every energy path is validated to machine precision against pycalphad. The companion database covers the CaO-SiO~2~, MgO-SiO~2~, and FeO-SiO~2~ liquids and the FeO-MgO-SiO~2~ ternary with olivine and orthopyroxene solid solutions, assembled solely from published measurements with per-value provenance and documented limits. The code is MIT licensed and the database is CC BY 4.0.

**Keywords:** CALPHAD; molten slag; modified quasichemical model; thermodynamic database; phase diagram; WebAssembly; oxide melts; open data

## (1) Overview

### Introduction

Molten oxide slags and molten salts are dominated by short-range ordering, which the Modified Quasichemical Model in the Quadruplet Approximation describes through the distribution of cation-anion quadruplets [1]. The quadruplet formalism is the current form of the modified quasichemical family, which grew from the pair-approximation treatment of binary liquids [2] and its application to silicate slags [3]. The model is published in full, and it is the basis of the oxide and salt databases in FactSage, the software that carries most industrial slag work [4]; databases of this kind are embedded in everyday steelmaking practice, from slag design through virtual process simulation [5,6]. What separates a published model from a usable calculation is an implementation and a parameter set. On the implementation side the situation has improved. OpenCalphad brought a free general equilibrium code [7]; pycalphad, itself published in this journal [8], gained an MQMQA model with uncertainty quantification [9] and a companion parameter-fitting framework [10]; Thermochimica calculates MQMQA molten salts inside a nuclear fuel framework [11]. Both MQMQA implementations live inside larger frameworks with correspondingly large dependency stacks. On the data side the situation has not improved at all. The community has argued for years that phase-based data need open infrastructure [12], yet there is no free MQMQA oxide slag database. A student, a startup, or a plant engineer who wants to calculate a slag equilibrium with open tools has the model, possibly an implementation, and no parameters to run through it.

Hephaestus is a deliberate response to that gap, and it treats the engine and the data as one contribution because neither is useful alone. The engine is small on purpose. Its core is plain C with no dependencies, which makes it easy to embed and lets the identical code compile to WebAssembly, so the full calculator runs in a web browser with nothing installed and no data leaving the user's machine. The database is open on purpose. Every parameter in it derives from published measurements, each value carries its provenance down to table and page, and the known shortcomings are documented next to the numbers they affect. The present work describes both, their validation against pycalphad and against measured phase equilibria, and the ways they can be reused.

### Implementation and architecture

Hephaestus is layered (Figure 1). A C core holds all thermodynamics. A thin Python package binds it through the cffi ABI interface, so importing it requires a prebuilt shared library and no compiler. An emscripten build compiles the same C into a single WebAssembly file behind a browser application. Nothing in the chain duplicates a formula, so a fix in the core reaches every layer.

![Figure 1: Architecture of Hephaestus. A single dependency-free C core reads ChemSage-format files and computes all thermodynamics; the same core is used as a native library, from Python through cffi, and compiled to WebAssembly behind the browser application. dbbuild writes new ChemSage files from measured data, and every energy path is validated against pycalphad.](figures/fig1_architecture.png){width=6.3in}

The core implements the MQMQA Gibbs energy of Pelton, Chartrand and Eriksson [1]: the pair reference energy, the configurational entropy of the quadruplet distribution, and the excess energy with composition-dependent interaction terms, together with the recursive coordination-number rules, including reciprocal quadruplets. Solid solutions use the compound energy formalism [13], with sublattice site fractions, per-sublattice ideal entropy, and Redlich-Kister excess terms; the Gibbs energy is normalized per mole of real atoms, so vacancy-bearing phases come out on the same basis pycalphad uses. A reader for the ChemSage data format loads MQMQA liquids (SUBQ and SUBG blocks), compound energy formalism phases (SUBL, including the magnetic variant), and stoichiometric compounds, with multi-interval Gibbs functions and the additional-term forms such as T^0.5^ and ln T. The format has no public specification, so the reader's grammar was written against the format as handled by pycalphad's open-source parser and proven by loading pycalphad's own test databases.

Equilibrium is calculated at two levels. The core minimizes the liquid Gibbs energy over quadruplet fractions under element balance. The Python layer adds an exact one-dimensional solve for common-anion binary liquids, where mass balance pins the quadruplet distribution to a single degree of freedom, and a multiphase construction by dense sampling and the lower convex hull, the same global method pycalphad uses. For a binary the hull yields tie-lines with a test that separates true two-phase edges from adjacent samples of one continuous curve. For a ternary the hull runs over the cation simplex, and each facet is a tie-triangle or tie-line read directly with the lever rule. On top of this sit isothermal sections and liquidus projections for the full FeO-MgO-SiO~2~ system.

The Python package also contains dbbuild, a declarative route from measured data to a loadable database. A user describes components with sourced endmember thermodynamics and fitted binary excess terms, and dbbuild writes a valid ChemSage file; a fitting routine obtains the excess parameters from measured component activities using the engine itself as the forward model. The builder covers single-anion oxide systems of two to four components, and multicomponent liquids are assembled from their binaries in the usual way.

The browser application, hosted at https://odinzen.github.io/hephaestus-mqmqa-public/, exposes five tools: a calculator over any loaded ChemSage file (a user can hold up to three uploaded files per session and switch between them), a binary join phase-diagram tool with tap-to-read point comparison, a viewer for the assessed FeO-MgO-SiO~2~ diagrams, a live isothermal-section solver that calculates the full phase assemblage at a chosen temperature in about a second, for the shipped ternaries or for any loaded three-cation file (Figure 2), and an interactive eutectic builder whose component names, melting points, and fusion enthalpies pre-fill from the loaded database. Everything runs client side. The page holds a strict content security policy, escapes all file-derived strings, makes no third-party requests, and never transmits a loaded file, which matters to industrial users whose compositions are confidential.

![Figure 2: The live solver in the browser application. The user loads the shipped database, picks a temperature, and presses Compute; the WebAssembly engine then solves the full FeO-MgO-SiO~2~ phase assemblage client side (here 1023 composition samples and 512 tie-facets in under half a second) and reports the composition and stable phases under the cursor on hover.](figures/fig2_browser_app.png){width=5.2in}

The database is the second half of the contribution. Endmember oxide thermodynamics come from open compilations, chiefly Robie and Hemingway [14] and the NIST-JANAF tables [15]. Liquid excess parameters are fitted to published measurements: Knudsen-effusion and gas-slag equilibrium activities for CaO-SiO~2~ [16,17], the measured iron-saturated activities collected by Björkman for FeO-SiO~2~ [18], and the melting and immiscibility constraints of the classical phase diagram studies [19-21]. Solution-calorimetric compound enthalpies [22] anchor the solids. Where published calorimetry cannot constrain a liquid, melt-mixing enthalpies from machine-learned interatomic potentials [23,24] serve as auxiliary anchors after bias correction against measured formation enthalpies; each such use is recorded in the provenance files. The olivine and orthopyroxene solid solutions take their endmembers from Robie and Hemingway [14] and their mixing parameters from solution calorimetry [25]. The assembled ternary reproduces the topology of the measured MgO-FeO-SiO~2~ liquidus surface [19], with the olivine field quantitative and the known offsets stated. No parameter is taken from any prior assessment or commercial database; published assessments of these systems [26] are used only as method literature. Each system folder carries a provenance file that names every source, every modeling judgment, and every known limit. The largest limit is stated plainly: the CaO-SiO~2~ and MgO-SiO~2~ silica-rich miscibility gaps sit at the right compositions but too high in temperature, a documented consequence of the single-common-anion excess form. Figure 3 shows the assembled ternary as the engine calculates it from the shipped database files, in the two views the application offers; Table 1 summarizes each fitted liquid, the data behind it, and what it reproduces. The code is MIT licensed at the repository root and the database directory carries its own CC BY 4.0 license.

![Figure 3: The assessed FeO-MgO-SiO~2~ system calculated from the shipped database files. (a) Liquidus projection: primary crystallizing phase fields, with liquidus isotherms labeled in °C. (b) Isothermal section at 1600 °C: stable phase assemblages, shaded by the number of solid phases present. Phase labels: L liquid, Crs cristobalite, Ol olivine, Opx orthopyroxene, Per periclase, Wus wustite.](figures/fig3_ternary.png){width=6.5in}

| System | Fitted liquid excess (J/mol) | Fitted to | Reproduces; known limit |
|---|---|---|---|
| CaO-SiO~2~ | (-189764 + 15.71 T) + 57171 χ~Ca~ | silica activities [16,17]; bias-corrected melt-mixing enthalpies [23,24]; endmember and compound melting | mixing enthalpy near -58 kJ/mol at the metasilicate; silica-rich miscibility gap at the right composition but high in temperature |
| MgO-SiO~2~ | five terms in the equivalent fraction Y~SiO2~, each a + b T | measured invariants and immiscibility data [20,21] from five studies, the measured consolute, and solution calorimetry [22] | all four invariants within about 40 °C; calorimetry matched; stable two-liquid field about 340 °C high |
| FeO-SiO~2~ | -42839 + 17.83 T | 23 iron-saturated activities across two isotherms [18] | RMS ln a = 0.067; fayalite congruent melting within a few degrees |
| FeO-MgO-SiO~2~ | binaries combined; no ternary term | assembled from the binaries with olivine and orthopyroxene solutions [14,25] | measured liquidus-surface topology [19]; stable phase sets match pycalphad at 15 of 16 points |

Table 1: The assessed liquids. Full source lists, modeling judgments, and limits are in each system's provenance file in the repository.

### Anatomy of a database file

Because the database is half the contribution, it is worth stating plainly what such a file is. A ChemSage-format database is a self-contained plain-text file; the fitted binaries here are 41 to 59 lines, and the combined ternary with two solid solutions is 123. Those lines hold everything the calculation needs. The file opens with the elements and their masses. Each liquid carries its endmember Gibbs-energy functions as interval-wise polynomial coefficients, its cation charges and chemical groups, its quadruplet coordination numbers, and its excess terms with their composition exponents. Each solid solution lists its sublattice constituents, site ratios, and interaction terms, and each stoichiometric compound is a single line of coefficients. Nothing is opaque: every parameter that enters a calculated diagram can be read directly from the file.

The brevity of the file is inverted in the effort behind it. Building one from scratch, as done for each system here, starts with locating and triaging the primary literature, then extracting measurements with per-value provenance, including digitization from sixty-year-old figures. Endmember functions are assembled from evaluated compilations, the model structure is chosen, and the excess is fitted with the engine as the forward model. The result is validated against an independent implementation and against measurements withheld from the fit, and the limits are written down. The steps that resist automation are judgments: conflicting data sets must be arbitrated, reference states reconciled, and model-form limits recognized rather than papered over with additional terms. dbbuild automates the mechanical part of this pipeline; the judgment does not compress.

That asymmetry is the economics of the field in miniature: implementations of the published models are increasingly available, but each fitted parameter condenses dozens of measurements and decisions. Parameter sets rather than codes are therefore the scarce commodity, and an openly licensed, provenance-tracked database is the part of this contribution that cannot be regenerated from the paper alone.

### Quality control

pycalphad is the validation oracle throughout, on the principle that nothing is claimed working until it matches an independent implementation; Table 2 lists the checks. The test suite, 40 tests run with pytest, checks every energy contribution against pycalphad on shared parameters to machine precision, near 10^-10^ J per mole of atoms. The reader is tested by loading pycalphad's open test databases and reproducing their energies with no pycalphad at runtime. The compound energy formalism kernel matches pycalphad on a real multicomponent industrial file with charged species, vacancies, and logarithmic temperature terms. The multiphase construction is tested end to end: a combined file holding the MQMQA liquid, both solid solutions, and three stoichiometric oxides runs through pycalphad's own equilibrium calculation. The stable phase sets agree at 15 of 16 probe points, with Gibbs energies within about 10 J per mole of atoms; the one disagreement is a facet-resolution sliver at a field boundary. The WebAssembly build is validated in the browser against the same oracle values to machine precision.

| Check | Scope | Agreement |
|---|---|---|
| Energy paths (MQMQA reference, ideal, excess; CEF; stoichiometric) | shared parameter sets, every phase model | ~10^-10^ J per mole of atoms |
| ChemSage reader | pycalphad's open test databases, no pycalphad at runtime | energies reproduced to machine precision |
| CEF kernel | multicomponent industrial file with charges, vacancies, ln T terms | machine precision |
| Multiphase equilibrium | liquid + two solid solutions + three oxides, 16 probe points | phase sets at 15 of 16; Gibbs energies within ~10 J per mole of atoms |
| WebAssembly build | in-browser against the same oracle values | machine precision |

Table 2: Validation against the independent oracle. Every check runs in the pytest suite except the in-browser one, which is exercised manually per release.

The database is tested against measurements rather than against other software. Endmember fusion points reproduce their sources exactly. The fitted FeO-SiO~2~ liquid reproduces 23 measured activity points with a root-mean-square deviation of 0.067 in ln a [18], and the fitting route itself is regression-tested by re-deriving those published parameters from the raw data. Congruent melting of fayalite and forsterite lands within a few degrees of measurement, assessed MgO-SiO~2~ invariants sit within about 40 °C, and the ternary liquidus projection reproduces the measured field topology [19]. The suite runs on Windows 11 under CPython 3.11 and 3.12; the browser application is exercised in Chromium- and Gecko-based browsers. A user can confirm a working installation by running pytest against the bundled test databases, or with no installation at all by opening the web application and loading the shipped ternary database.

## (2) Availability

### Operating system

Platform independent. The core builds with any C99 compiler; development and testing used Windows 11. The browser application runs in any current browser with WebAssembly support.

### Programming language

C (core), Python 3.11 or later (interface and fitting tools), JavaScript (browser application).

### Additional system requirements

None of note. The engine and database together are a few megabytes.

### Dependencies

Python interface: cffi, NumPy, SciPy. Validation suite additionally requires pycalphad. WebAssembly build requires emscripten. The C core and the browser application have no dependencies.

### List of contributors

Michael E. Bustamante (design, implementation, validation, data curation).

### Software location

**Archive**

- Name: GitHub Releases (release archive of the code repository)
- Persistent identifier: https://github.com/odinzen/hephaestus-mqmqa-public/releases/tag/v0.2.0
- Licence: MIT (code), CC BY 4.0 (database)
- Publisher: Michael E. Bustamante
- Version published: v0.2.0
- Date published: 2026-09-02

**Code repository**

- Name: GitHub
- Identifier: https://github.com/odinzen/hephaestus-mqmqa-public
- Licence: MIT (code), CC BY 4.0 (database, under data/)
- Date published: 2026-09-02

### Language

English.

## (3) Reuse potential

The nearest reuse is interoperation. Hephaestus reads the same ChemSage format pycalphad reads, and files written by dbbuild load in both, which the tests enforce. A group already working in pycalphad can treat the database as input data and ignore the engine. A group that needs a small embeddable solver can take the C core, two source directories with no dependencies, and call it from C, Python, or anything with a C foreign-function interface.

The browser application makes the lowest barrier the default. A lecture on slag thermodynamics, a plant metallurgist screening a composition, or a reviewer checking a claimed equilibrium can load the database and calculate in seconds, with confidential inputs never leaving the machine. The same property makes it a practical template for other groups who want to publish a model as a zero-install tool.

The database is a starting point rather than an endpoint, and the file format rewards growth: new components, new phases, and refits against new measurements accumulate in the same database. A system is therefore extended release by release rather than rebuilt, and archived versions keep results calculated against earlier releases reproducible. Because every value carries its source and every judgment is written down, another assessor can reweight the data, swap an endmember, or extend a system without reverse-engineering anything; dbbuild turns a table of measured activities into a loadable file in a few lines. The in-browser multiphase hull already covers any loaded three-cation file, so a new system becomes a browser phase diagram the moment its file loads; natural extensions are further oxide systems and the remaining ChemSage solution models. Contributions and issues are handled through the GitHub repository.

## Data availability

The engine, the database, the browser application, and the validation suite are openly available in the code repository listed above; the version described here is archived as release v0.2.0. The database files and their provenance records are in the repository's data directory under CC BY 4.0.

## Acknowledgements

During the development of this software the author used Claude Code (Anthropic) to assist with implementation, validation scripting, and manuscript preparation. This assistance was agentic, not autonomous: it operated under author direction and supervision at every step and was never a closed loop that produced or accepted results without review. Every parameter was traced by the author to its primary source before entering the database, and every reference was verified against its registry record. The author reviewed and approved all output and takes full responsibility for this article.

## Funding statement

The development of this software received no external funding.

## Competing interests

The author founded Odinzen LLC, which provides commercial thermodynamic modeling services, and declares this as a competing interest. The software and database published here are released in full under open licenses, and no proprietary Odinzen assets are included.

## References

[1] Pelton AD, Chartrand P, Eriksson G. The modified quasi-chemical model: Part IV. Two-sublattice quadruplet approximation. Metall Mater Trans A. 2001 Jun;32(6):1409–16. doi:10.1007/s11661-001-0230-7

[2] Pelton AD, Degterov SA, Eriksson G, Robelin C, Dessureault Y. The modified quasichemical model I—Binary solutions. Metall Mater Trans B. 2000 Aug;31(4):651–9. doi:10.1007/s11663-000-0103-2

[3] Pelton AD, Blander M. Thermodynamic analysis of ordered liquid solutions by a modified quasichemical approach—Application to silicate slags. Metall Trans B. 1986 Dec;17(4):805–15. doi:10.1007/BF02657144

[4] Bale CW, Bélisle E, Chartrand P, Decterov SA, Eriksson G, Gheribi AE, et al. FactSage thermochemical software and databases, 2010–2016. Calphad. 2016 Sep;54:35–53. doi:10.1016/j.calphad.2016.05.002

[5] Jung IH. Overview of the applications of thermodynamic databases to steelmaking processes. Calphad. 2010 Sep;34(3):332–62. doi:10.1016/j.calphad.2010.06.003

[6] Jung IH, Van Ende MA. Computational Thermodynamic Calculations: FactSage from CALPHAD Thermodynamic Database to Virtual Process Simulation. Metall Mater Trans B. 2020 Oct;51(5):1851–74. doi:10.1007/s11663-020-01908-7

[7] Sundman B, Kattner UR, Palumbo M, Fries SG. OpenCalphad - a free thermodynamic software. Integr Mater Manuf Innov. 2015 Dec;4(1):1–15. doi:10.1186/s40192-014-0029-1

[8] Otis R, Liu ZK. pycalphad: CALPHAD-based Computational Thermodynamics in Python. JORS. 2017 Jan 9;5(1):1. doi:10.5334/jors.140

[9] Paz Soldan Palma J, Gong R, Bocklund BJ, Otis R, Poschmann M, Piro M, et al. Thermodynamic modeling with uncertainty quantification using the modified quasichemical model in quadruplet approximation: Implementation into PyCalphad and ESPEI. Calphad. 2023 Dec;83:102618. doi:10.1016/j.calphad.2023.102618

[10] Bocklund B, Otis R, Egorov A, Obaied A, Roslyakova I, Liu ZK. ESPEI for efficient thermodynamic database development, modification, and uncertainty quantification: application to Cu–Mg. MRS Communications. 2019 Jun;9(2):618–27. doi:10.1557/mrc.2019.59

[11] Poschmann M, Bajpai P, Fitzpatrick BWN, Piro MHA. Recent developments for molten salt systems in Thermochimica. Calphad. 2021 Dec;75:102341. doi:10.1016/j.calphad.2021.102341

[12] Campbell CE, Kattner UR, Liu ZK. The development of phase-based property data using the CALPHAD method and infrastructure needs. Integr Mater Manuf Innov. 2014 Dec;3(1):158–80. doi:10.1186/2193-9772-3-12

[13] Hillert M. The compound energy formalism. Journal of Alloys and Compounds. 2001 May;320(2):161–76. doi:10.1016/S0925-8388(00)01481-X

[14] Robie RA, Hemingway BS. Thermodynamic properties of minerals and related substances at 298.15 K and 1 bar (10^5^ pascals) pressure and at higher temperatures. U.S. Geological Survey Bulletin 2131. Washington: U.S. Government Printing Office; 1995.

[15] Chase MW Jr. NIST-JANAF Thermochemical Tables, 4th edition. Journal of Physical and Chemical Reference Data, Monograph 9. Woodbury, NY: American Institute of Physics; 1998.

[16] Kay DAR, Taylor J. Activities of silica in the lime + alumina + silica system. Trans Faraday Soc. 1960;56:1372. doi:10.1039/tf9605601372

[17] Stolyarova VL, Shornikov SI, Ivanov GG, Shultz MM. High Temperature Mass Spectrometric Study of Thermodynamic Properties of the CaO-SiO2 System. J Electrochem Soc. 1991 Dec 1;138(12):3710–4. doi:10.1149/1.2085485

[18] Björkman B. An assessment of the system Fe-O-SiO2 using a structure based model for the liquid silicate. Calphad. 1985 Jul;9(3):271–82. doi:10.1016/0364-5916(85)90012-4

[19] Bowen NL, Schairer JF. The system MgO-FeO-SiO2. American Journal of Science. 1935 Feb 1;s5-29(170):151–217. doi:10.2475/ajs.s5-29.170.151

[20] Greig JW. Immiscibility in silicate melts; Part I. American Journal of Science. 1927 Jan 1;s5-13(73):1–44. doi:10.2475/ajs.s5-13.73.1

[21] Greig JW. Immiscibility in silicate melts; Part II. American Journal of Science. 1927 Feb 1;s5-13(74):133–54. doi:10.2475/ajs.s5-13.74.133

[22] Charlu TV, Newton RC, Kleppa OJ. Enthalpies of formation at 970 K of compounds in the system MgO-Al2O3-SiO2 from high temperature solution calorimetry. Geochimica et Cosmochimica Acta. 1975 Nov;39(11):1487–97. doi:10.1016/0016-7037(75)90150-7

[23] Yang H, Hu C, Zhou Y, Liu X, Shi Y, Li J, et al. MatterSim: A Deep Learning Atomistic Model Across Elements, Temperatures and Pressures. arXiv; 2024. doi:10.48550/ARXIV.2405.04967

[24] Neumann M, Gin J, Rhodes B, Bennett S, Li Z, Choubisa H, et al. Orb: A Fast, Scalable Neural Network Potential. arXiv; 2024. doi:10.48550/ARXIV.2410.22570

[25] Wood BJ, Kleppa OJ. Thermochemistry of forsterite-fayalite olivine solutions. Geochimica et Cosmochimica Acta. 1981 Apr;45(4):529–34. doi:10.1016/0016-7037(81)90185-X

[26] Wu P, Eriksson G, Pelton AD, Blander M. Prediction of the Thermodynamic Properties and Phase Diagrams of Silicate Systems-Evaluation of the FeO-MgO-SiO2 System. ISIJ International. 1993;33(1):26–35. doi:10.2355/isijinternational.33.26
