# Open CaO-SiO2 data inventory

Digitized, published experimental and reference data available for building an open
CaO-SiO2 (and, secondarily, CaO-Al2O3-SiO2) liquid-slag database. Each entry names the
primary source and its access status. Only open or public-domain sources are used to
build the database in this repository; paywalled entries are listed for completeness and
as future validation targets, never transcribed as parameters.

Source of the digitized tables: the assessment research workspace at
`odinzen_assessment_workspace/assessments/CaO-SiO2` and `.../CaO-Al2O3-SiO2`, which holds
per-table CSV mirrors with row-level provenance (paper, table, page). This inventory
summarizes what those tables contain and where each number comes from.

## CaO-SiO2 binary

### Pure-oxide liquid endmembers (open, used in v0.1)

| Quantity | CaO | SiO2 | Source | Access |
|---|---|---|---|---|
| dHf(298) from elements | -635.1 kJ/mol | -908.4 kJ/mol (cristobalite basis) | Robie & Hemingway 1995 | public domain (USGS) |
| S(298), third law | 38.1 J/mol/K | 43.4 J/mol/K | Robie & Hemingway 1995 | public domain |
| Cp(T) solid, Haas-Fisher | a=51.85, b=2.444e-3, c=-9.340e5 | a=72.75, b=1.300e-3, c=-4.132e6 (beta-cristobalite) | Robie & Hemingway 1995 | public domain |
| Fusion Tm | 3200 K (flagged high; JANAF estimate) | 1996 K | NIST-JANAF (Chase 1998) | open |
| Fusion dHfus | 79.5 kJ/mol (ESTIMATED = MgO) | 9.581 kJ/mol | NIST-JANAF | open |
| Liquid Cp | 62.760 J/mol/K | 85.772 J/mol/K | NIST-JANAF | open (refinement only) |

Cross-checks against Barin & Platzki (1995) agree to <0.2 percent but Barin is a
copyrighted compilation, so it is used only to confirm the open values, never as the
primary. Flags carried from the workspace: the CaO fusion point (3200 K) is high versus
modern reassessments (~2845-2900 K) and its dHfus is a JANAF estimate; the SiO2 solid Cp
uses only the beta-cristobalite branch extrapolated below 523 K.

### Experimental phase equilibria (Abdul et al. 2023, open CC-BY)

W. Abdul, C. Mawalala, A. Pisch, M. N. Bannerman, "CaO-SiO2 assessment using 3rd
generation CALPHAD models," Cement and Concrete Research 173 (2023) 107309,
DOI 10.1016/j.cemconres.2023.107309. Open access, CC-BY 4.0 (White Rose eprint 202703).

Digitized measured facts (Table 9, Section 6.1):
- Invariant reactions (salt mole fraction x = X(SiO2)): peritectic L+CaO -> C3S at 2423 K
  (x_L=0.27); eutectic L -> C3S + a-C2S at 2323 K (x_L=0.29); peritectic
  L+a-C2S -> rankinite at 1737 K (x_L=0.43); eutectic L -> rankinite + CS at 1733 K
  (x_L=0.44); eutectic L -> SiO2 + CS at 1709 K (x_L=0.61).
- Congruent melting: a-Ca2SiO4 at 2403 K; pseudowollastonite CaSiO3 at 1817 K.
- Rankinite incongruent (peritectic) melting by the authors' own DSC, 1737 +/- 5 K.
- Solid-state polymorphic transitions for C2S, C3S, and wollastonite/pseudowollastonite.
- New drop-calorimetry heat contents H(T)-H(298) for rankinite and (gamma, alpha')-C2S.
- Calorimetric formation enthalpies (Table A.2) and DFT 0 K energies (Table 6).

Note: Abdul et al. model the liquid with an ASSOCIATE solution model, not the modified
quasichemical model. The engine in this repository reads only SUBQ/SUBG (MQMQA) phases,
so the Abdul liquid parameters cannot be transcribed into an engine-readable file. Their
experimental invariants and calorimetry are, however, valid validation targets for an
MQMQA optimization.

### Silica-side liquid immiscibility (Greig 1927, public domain)

J. W. Greig, "Immiscibility in silicate melts; Part I," American Journal of Science,
ser. 5, 13 (73) (1927) 1-44. Pre-1929, public domain; open scan.
- Monotectic (cristobalite + liquid A + liquid B): 1698 degC = 1971 K.
- Silica-rich limb (liquid B): 99.4 wt% SiO2 at 1710 degC (Table V).
- Consolute (top of the two-liquid dome): 26.5 wt% CaO / 73.5 wt% SiO2, bracketed
  1710-1740 degC (~1998 K).

### Liquid activity (Kay & Taylor 1960; paywalled paper, digitized measurements)

D. A. R. Kay, J. Taylor, "Activities of silica in the lime + alumina + silica system,"
Transactions of the Faraday Society, 1960. Six a(SiO2) points near the binary edge
(0.6 wt% Al2O3), by the SiO2 + 3C = SiC + 2CO gas-equilibration method, ~1821 K,
reference state solid silica. Values fall from a(SiO2)=0.766 at 61.3 wt% SiO2 to 0.096
at 43.6 wt% SiO2, i.e. strong negative deviation from ideality. Held only as a validation
target for the future excess fit.

### Further primary liquid data (paywalled, NOT used; future validation targets)

Cataloged in the workspace but not open, so not transcribed: Stolyarova (1991) KEMS
a(CaO), a(SiO2), and dG at 1933 K (top pick for the liquid); Sharma & Richardson (1962)
a(CaO) via CaS solubility; Tewhey & Hess (1979) and Hudon, Jung & Baker (2004) silica-side
binodal.

## CaO-Al2O3-SiO2 ternary (secondary, for later increments)

Digitized in `.../CaO-Al2O3-SiO2`: Rankin & Wright (1915) phase equilibria (public
domain); Kay & Taylor (1960) a(SiO2); Zaitsev et al. (1997) and Ohta & Suito (1998)
activities (paywalled, digitized measurements). Not used in the CaO-SiO2 binary v0.1.

## What is deliberately excluded

No FactSage/FToxid parameters, no proprietary fitted TDB parameters, and none of the
workspace's own-derived or ESPEI-fit liquid interaction parameters are used. The
workspace's ESPEI attempt on this system is documented there as non-identifiable from the
boundary-filtered phase-diagram data alone; no liquid mixing parameters were committed
from it, and none are used here.
