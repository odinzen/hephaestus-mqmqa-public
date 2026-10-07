# CaO-FeO-MgO-SiO2 oxide liquid (Ca-Fe-Mg-Si slag melt) provenance and limits

The four-oxide silicate melt of the steel-slag / basalt family: a single MQMQA (SUBQ)
liquid over Ca, Fe, Mg, Si and O. It is the melt that crystallizes the ferromagnesian
silicates (olivine, orthopyroxene, clinopyroxene, data/olivine-opx-cpx). Built 2026-08-26.
Each ternary face is its shipped ternary or binary-derived face, and in every binary limit the melt
reduces to the shipped binary exactly. Nothing quaternary is fitted.

## Liquid (SUBQ; Ca+2 / Fe+2 / Mg+2 / Si+4 / O)

Endmembers and excesses are read from the shipped builders (single source of truth):

| Edge or term | Source |
|---|---|
| CaO-SiO2 | CaO-SiO2 v0.4, five silica-weighted terms (data/cao-sio2) |
| FeO-SiO2 | FeO-SiO2 v0.4, four terms plus the FeO(l) interval below 1650 K (data/feo-sio2) |
| MgO-SiO2 | the three-way fit N1, with the MgO(l) heat-capacity excess and the explicit Mg-Si ordering row (data/mgo-sio2) |
| FeO-MgO, Fe-Si with Mg, Mg-Si with Fe | data/feo-mgo-sio2 (`TERNARY_EXCESS`) |
| CaO-MgO 11522.6 J, Ca-Si with Mg 3249.8 J, Mg-Si with Ca -3864.9 J | `build_dat.CMS_TERNARY` |
| CaO-FeO | **ideal** (no term) |

The CaO-MgO-SiO2 terms were fitted on 2026-10-05 together with the MgO-SiO2 liquid and the
FeO-MgO-SiO2 terms (`data/mgo-sio2/assessment/joint3.py`), against 40 liquidus points of Bowen
(1914): cost 22.35, 36 of 40 primary phases as measured; forsterite field 8 K, pyroxene 16 K and
silica 17 K mean absolute miss; diopside liquidus 1665 K at Bowen's forsterite-pyroxene point
against 1664 K measured (`assessment/assess.py` reports the face). Pure diopside melts
congruently at 1673 K in the combined file (liquid against the clinopyroxene endmember; measured
1664-1670 K), inside the window `tests/test_cao_feo_mgo_sio2_combined.py` checks.

**Chemical groups: Ca, Fe and Mg in group 1, Si in group 2**, the layout of the FeO-MgO-SiO2
liquid, so its Ca-free face is that shipped liquid exactly. There is no CaO(l) correction since
2026-09-29: v0.2 shifted CaO(l) so diopside melted at 1670 K, and the CaO-MgO-SiO2 terms now
carry that interaction instead.

## Validation

- **Reduction to the shipped files.** Each binary edge equals its shipped binary, and the Ca-free
  face equals the shipped FeO-MgO-SiO2 liquid (`tests/test_cao_feo_mgo_sio2_liquid.py`,
  `tests/test_mgsi_ordering_consistency.py`).
- **pycalphad reads the quaternary** and is the reference for its multicomponent equilibria. The
  primary phase used in the tests is the highest single-solid saturation temperature; a solid
  counts only if it lowers the Gibbs energy below the liquid alone, because pycalphad's full-phase
  equilibrium can miss the liquid at these compositions.

## Known limits

- **CaO-FeO is ideal**, and the CaO-FeO-SiO2 face has no ternary term. With Si in its own
  group that face carries a two-liquid region between an FeO-rich basic liquid and a lime
  silicate liquid (about 100 nodes on a 1/40 grid at 1700 K, liquid only) that no measurement
  supports. With all four cations in group 1 that face is clean, but the FeO-MgO-SiO2 and
  CaO-MgO-SiO2 faces grow spurious gaps instead. The engine takes no per-ternary group
  overrides, so a CaO-FeO-SiO2 term is the fix.
- **The interior is a prediction.** No quaternary term; the ternary terms come from the
  CaO-MgO-SiO2 and FeO-MgO-SiO2 faces only.
- **Inherited from the binaries:** forsterite melts 83 K low and the MgO-SiO2 dome sits high
  (data/mgo-sio2).
- **Liquid only.** This file has no solid phases; `build_combined_dat.py` adds them
  (PROVENANCE_combined.md).

## Sources

The four binary PROVENANCE files (data/cao-sio2, data/feo-sio2, data/mgo-sio2, and the
data/feo-mgo-sio2 ternary) carry every citation and fitted parameter; nothing new is
introduced here.

Repro: `build_dat.py` (writes CaO-FeO-MgO-SiO2-liquid.dat from the shipped binaries),
`validate.py` (binary-limit reductions + the pycalphad comparison).
