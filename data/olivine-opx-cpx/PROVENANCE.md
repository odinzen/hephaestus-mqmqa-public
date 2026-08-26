# Ca-Fe-Mg-Si silicate solid solutions (olivine + opx + cpx) provenance and limits

The three ferromagnesian silicate solid solutions of the Ca-Fe-Mg-Si-O system in one
ChemSage SUBL .dat, so their Fe-Mg partitioning can be computed. Built 2026-08-26.

    OLIVINE        (Mg,Fe)2 (Si)1 (O)4          forsterite / fayalite
    ORTHOPYROXENE  (Mg,Fe)2 (Si)2 (O)6          enstatite / ferrosilite
    CLINOPYROXENE  (Ca)1 (Mg,Fe)1 (Si)2 (O)6    diopside / hedenbergite

## Assembly (nothing refit)

Every endmember Gibbs energy and every excess is carried **verbatim** from the shipped
single-phase databases:

- **Olivine**: Robie-Hemingway forsterite/fayalite; Wood & Kleppa 1981 subregular excess
  (L0 = 12552, L1 = 4184 J/mol). From data/olivine.
- **Orthopyroxene**: Robie-Hemingway enstatite/ferrosilite (per M2Si2O6), including the
  assessed enstatite high-T Gibbs interval (break at the 1360 K ortho->proto transition);
  Chatillon-Colinet 1983 symmetric excess (L = 7949.6 J/mol). From data/olivine-opx.
- **Clinopyroxene**: Robie-Hemingway diopside/hedenbergite; the MLIP-triangulated (Fe,Mg)
  excess (L0 = -576, L1 = +3442 J/mol). From data/clinopyroxene.

The three combined phases reproduce their standalone databases **exactly** (0 J/mol-atom,
checked across the 1360 K enstatite break for opx). The assembly only lets the phases
coexist; it adds no new parameter.

## Validation

- **The C engine == pycalphad Model.GM to machine precision** (< 1.2e-10 J/mol-atom) on
  every phase in the combined file, x and T.
- **Fe-Mg exchange (K_D) among all three pairs** (data/olivine-opx-cpx/exchange.py). The
  equal-exchange-potential coexisting composition from the C CEF kernel equals pycalphad's
  own equilibrium() tie-line on the same file to machine precision (dX_Fe < 1e-4), at
  1000 K:

  | pair | K_D = (Fe/Mg)_A / (Fe/Mg)_B | note |
  |---|---|---|
  | olivine / orthopyroxene | 0.96 | near-ideal, consistent with the measured exchange (von Seckendorff & O'Neill 1993, K_D ~1) |
  | clinopyroxene / orthopyroxene | 0.33 | unfitted prediction (endmember-driven) |
  | clinopyroxene / olivine | 0.33 | unfitted prediction |

  The exchange potential per mixing site is (dG_formula/dX_Fe)/n_sites, n_sites = 2
  (olivine, opx) or 1 (cpx); at equilibrium it is equal in both phases.

## Known limits

- **The clinopyroxene K_D is an unfitted prediction** set by the Robie-Hemingway endmember
  thermochemistry (cpx strongly favours Mg relative to opx/ol; the measured cpx-opx D_FeMg
  is ~0.5-0.7, so the model over-predicts the Mg preference somewhat). It is not calibrated
  against measured cpx partitioning; that would be a future refinement with open exchange
  data. The ol-opx K_D is the calibrated, near-ideal case.
- **Solids only.** There is no silicate melt in this file, so it computes subsolidus phase
  relations and exchange, not melting. A Ca-Fe-Mg-Si oxide liquid (MQMQA) coexisting with
  these solids is the multiphase-equilibrium step beyond this assembly.
- **No pycalphad equilibrium across X(Ca) = 0.** For the Ca-free olivine-opx pair the
  equilibrium is run in the Ca-free subsystem; keeping the Ca dimension pinned at zero sits
  on a boundary where the global solver returns no phase (documented in exchange.py).

## Sources

The three single-phase PROVENANCE files (data/olivine, data/olivine-opx,
data/clinopyroxene) carry every citation; nothing new is introduced here. The measured
ol-opx cross-check is von Seckendorff & O'Neill (1993), Contrib. Mineral. Petrol.,
DOI 10.1007/BF00283228 (they report K_D ~ 1, near-ideal).

Repro: `build_dat.py` (writes Olivine-Opx-Cpx-CEF.dat from the three shipped databases),
`exchange.py` (the three pairwise K_D, engine vs pycalphad).
