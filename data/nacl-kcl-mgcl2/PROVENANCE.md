# NaCl-KCl-MgCl2 v0.3 provenance and limits

The molten-salt CSP ternary (concentrated-solar / molten-salt-reactor heat-transfer
fluid), assembled from the three shipped binaries. Built 2026-08-26. v0.1 was the pure
Muggianu combination of the binary excesses; **v0.2 added one ternary MQMX term fitted to
the single open experimental ternary datum (Mohan et al. 2018's measured eutectic
melting), cutting the melting error from +46 K to +6 K; v0.3 adds the (Na,K)Cl halite
solid solution** so the NaCl-KCl edge is a continuous solution with its solvus rather than
two line compounds.

## Liquid (SUBQ, Na+1 / K+1 / Mg+2 / Cl-1)

Z = 6 for all three cations (MQM salt convention, via `Component.z_cat`); the shared-anion
coordination is charge-neutral per pair (Cl gets 6 in the Na and K pairs, 3 in the Mg
pair). The three shipped binary liquid excesses are carried **verbatim** and combined by
the writer's Muggianu extension, with no ternary term:

| binary | Delta_g / Cl (J/mol) | source |
|---|---|---|
| NaCl-KCl | -715.1 | NaCl-KCl v0.1 (Hersh-Kleppa dH_mix) |
| KCl-MgCl2 | -15895.0 - 88.5*chi_K | KCl-MgCl2 v0.1 |
| NaCl-MgCl2 | -4749.5 - 4732.3*chi_Na | NaCl-MgCl2 v0.1 |

**Ternary term (v0.2, fitted).** One MQMX additional-constituent term (Poschmann Eq.
25-26, single chemical group, r = 1) on the KCl-MgCl2 quadruplet with NaCl as the extra
cation: `Delta_g = -8500 J/mol` times the NaCl pair fraction. It is identically zero on
every binary edge (the extra-cation fraction vanishes there), so the three binaries are
untouched. Its magnitude was fit to the Mohan melting point below; the KCl-MgCl2 + NaCl
combination was chosen because it is strongly active at the MgCl2-rich eutectic.

## Solids

- **Halite (Na,K)Cl (CEF/SUBL, one mixing sublattice)** carries NaCl and KCl as its
  endmembers, with the regular excess W = 2R*768.15 = 12773.6 J/mol from NaCl-KCl v0.1
  (the evaluated solvus consolute). Below 768 K it unmixes into two halites, exactly the
  NaCl-KCl v0.1 solvus, now inside the ternary.
- **MgCl2 and the KCl-MgCl2 double salt KMgCl3**, stoichiometric (values identical to the
  binary databases).

The MgCl2-rich double salts that some assessments place on the KCl-MgCl2 / NaCl-MgCl2
edges beyond KMgCl3 (K2MgCl4, K3Mg2Cl7, NaMgCl3, Na2MgCl4) are not included, matching the
binary databases (their thermochemistry is not in open experimental data).

## Validation

- **The assembly is exact, ternary term included: the C engine and pycalphad agree on the
  liquid Gibbs energy to +/-0.000 J/mol-atom** at the Mohan composition, 700 K and 900 K.
  The Muggianu combination of three binaries (with the divalent-Mg pairs) and the ternary
  MQMX term are emitted by the writer and evaluated by the engine identically to pycalphad.
- **Ternary-eutectic melting: the model's liquidus at the Mohan eutectic composition is
  666 K vs the measured 660 K (387 degC), +6 K** (v0.1 without the ternary term gave
  706 K, +46 K). Mohan et al. 2018 located the eutectic with FactSage (24.5/20.5/55 wt%
  NaCl/KCl/MgCl2) and measured its melting by DSC at 387 degC; only the melting
  temperature is experimental (the composition is FactSage-derived, i.e. validation
  target). The ternary term's magnitude was fit to this one melting point; the residual
  +6 K is the model-versus-FactSage eutectic-composition mismatch (the model would melt at
  660 K at its own eutectic, which sits a few percent off the FactSage location). MgCl2 is
  the primary crystallizing solid just below the liquidus, as expected for the MgCl2-rich
  eutectic.
- **Eutectic-liquid heat capacity (not fitted): model 0.94 vs measured 1.18 J/g/K.** The
  SUBQ liquid Cp is inherited from the endmembers (the excess is temperature-independent),
  so it carries no configurational Cp; the ~20 percent shortfall is expected and bounds
  what a T-independent excess can do. The ternary term does not change it.
- **Halite solvus.** pycalphad equilibrium on the written file gives two coexisting
  halites below the 768 K consolute on the NaCl-KCl edge, reproducing the NaCl-KCl v0.1
  solvus, and the halite phase leaves the liquid and the MgCl2-rich eutectic untouched
  (the liquid GM check above still holds to machine precision).

## Known limits and the next steps

- **One ternary point.** Only Mohan's single melting temperature is available as open
  experimental ternary data, so exactly one ternary parameter is justified. If an open
  ternary liquidus surface is digitized, more terms (and their temperature dependence)
  could be fit; a b*T entropy on the ternary term would then also address the Cp shortfall.
- **MgCl2-rich double salts beyond KMgCl3** (K2MgCl4, K3Mg2Cl7, NaMgCl3, Na2MgCl4) are not
  modeled, matching the binary databases: their formation thermochemistry is not in open
  experimental data (the identities come only from FactSage assessments).
- **The eutectic composition is not independently located** here (the open literature's
  eutectic composition is FactSage-derived); v0.2 fits and reports the model melting at
  the measured composition, not a from-scratch ternary invariant search.

## Sources

- Mohan, Venkataraman, Coventry et al., *Assessment of a novel ternary eutectic chloride
  salt for next generation high-temperature sensible heat storage*, Energy Convers.
  Manag. 167 (2018) 156, DOI 10.1016/j.enconman.2018.04.100 (measured ternary-eutectic
  melting 387 degC and liquid Cp 1.18 J/g/K; composition FactSage-located, validation
  target only).
- The three binary databases (NaCl-KCl, KCl-MgCl2, NaCl-MgCl2 v0.1) supply every fitted
  parameter; see their PROVENANCE files.

Repro: `build_dat.py` (imports the three binaries and writes NaCl-KCl-MgCl2.dat),
`validate_ternary.py` (the three checks above), `liquidus_projection.py` (draws the
ternary liquidus surface from the model).
