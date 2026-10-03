# Wet slag, aqueous (25 C): PHREEQC model of slag minerals in water

First version, 2026-10-02. Compared against Wells 1943, Nied 2016 and Stewart 2018 (below).

## Files

- `derive_logk.py` writes 25 C dissolution constants and `phreeqc_slag.dat` (phreeqc.dat plus our phases).
  - **Anhydrous slag minerals** come from the same Gibbs energies the Hephaestus builders ship (CaO-Al2O3, CaO-SiO2 silicates, olivine, clinopyroxene, spinel, CaO-Al2O3-SiO2).
  - **Hydrates** come from Cemdata18 (Lothenbach et al. 2019, doi:10.1016/j.cemconres.2018.04.018).
  - Each log K is built by an exchange cycle against portlandite, gibbsite, quartz and forsterite. The aqueous ions cancel, and so does any element-reference convention.
  - Portlandite and forsterite are copied into phreeqc.dat from wateq4f. Gibbsite is Cemdata18's (see Validation).
  - Anchor data are read from the Robie & Hemingway 1995 extracts in the assessment workspace. The Cemdata18 hydrates are anchored on Cemdata18's own portlandite, gibbsite and quartz.
  - The M-S-H phases are the exception: Cemdata18 has no Mg reference phase, so its published log KS0 values are converted directly.
- `extract_cemdata18.py` reads the Cemdata18 Gibbs energies (Tables 1 and 4) and log KS0 values (Table 2) from the accepted manuscript in the trove into `cemdata18_dfG.csv`, with PDF page and manuscript line. Nothing is retyped.
- `leach_demo.py` places 0.1 mol of each anhydrous mineral in 1 kg of water at 25 C. Room-temperature hydrates may precipitate, following Cemdata18's guidance; `--long-term` also admits the slow formers. C-S-H is Cemdata18's CSHQ ideal solid solution.

## Checks so far

- **CODATA water.** Checked against R&H lime + water = portlandite: 0.06 kJ.
- **Lime in water.** pH 12.46, Ca 20.4 mM. Measured portlandite saturation is pH about 12.45, Ca about 20 mM.
- **C3S and C2S hydration.** Portlandite + C-S-H with Ca/Si 1.62, against the measured 1.6-1.75 for C-S-H coexisting with portlandite.
- **wateq4f's own diopside and anorthite** differ from R&H-based values by +1.5 and -0.95 log units. That is an inconsistency inside the older database, not in ours.
- **Cemdata18 clinker phases against our solids**, log K by the same anchors:

  | Phase | Difference |
  |---|---|
  | lime | -0.35 |
  | C3S | -0.46 |
  | C2S | -0.99 |
  | C3A | +4.3 |
  | CA | -0.13 |
  | CA2 | +0.74 |

  With the Al anchor on Cemdata18's gibbsite, C3A is the outlier, about 25 kJ.

## Validation against measured data (validation/, tables extracted with page locators)

Wells, Clarke & McMurdie 1943 (21 C, `validate_wells1943.py`): saturation index of the identified solid at
each measured solution (0 = the model agrees it is at equilibrium).

| Solid | n | Mean SI | RMS |
|---|---|---|---|
| Gibbsite, Cemdata18 (the Al anchor) | 20 | -0.33 | 0.38 |
| Gibbsite, phreeqc.dat | 20 | -0.88 | 0.90 |
| C3AH6 (katoite) | 14 | -2.20 | 2.22 |
| C2AH7.5 / C4AH13 (metastable hexagonal hydrates) | 19 | -0.24 / -0.93 | 0.47 / 1.10 |

All derived phases now carry reaction enthalpies (van 't Hoff), by the same exchange cycle as their log K.

- **Aluminium anchor.** phreeqc.dat's gibbsite plus its Al(OH)4- constant overstate Al at high pH by about 0.6 log units. Aluminium is therefore anchored on Cemdata18's gibbsite.
- **Katoite: Cemdata18 and Wells 1943 disagree by about 2 log units.** Wells' katoite solutions have log IAP(3 Ca+2 + 2 Al(OH)4- + 4 OH-) = -22.6, against Cemdata18's log KS0 of -20.50 (Dilnesa 2014). That holds in Cemdata18's own species, before any of our conversions, and our database gives the same SI.
  - Likely cause: Wells approached katoite equilibrium by dissolution at 21 C, where katoite reacts very slowly.
  - An earlier version of this table showed -0.81. That came from 25 C log K used with 21 C aqueous constants, before the enthalpies were added.

Nied et al. 2016 (M-S-H, 20 C) and Stewart et al. 2018 (BOF slag leaching), `validate_msh_bof.py`:

- **Amorphous silica.** Our SI is within 0.06 of the authors' own at every point, after anchoring the hydrates' Si on amorphous silica (-2.71), not quartz.
- **Brucite.** Within 0.2-0.3 of the authors'.
- **M-S-H.** The solid solution comes out supersaturated by 0.1-1.3. Its log K is converted directly (no Mg anchor in Cemdata18) and has no temperature term.
- **BOF slag leachates.**
  - At day 14 (pH about 10.2) the sand leachates sit close to C-S-H saturation (SI -0.4 to -0.8).
  - Later, the open bottles take up CO2 and the pH falls to about 8.5, so the leachates become steadily undersaturated.
  - The C-S-H in equilibrium with them has Ca/Si 0.67, against 0.71 +- 0.15 (sand) and 0.73 +- 0.30 (gravel) measured by SEM-EDS. The blocks (1.15) do not match: a thicker, diffusion-limited rim.

## Known limits

- **Al anchor scope.** The Cemdata18-gibbsite Al anchor is right where Al(OH)4- dominates (pH above about 9). In acid solutions phreeqc.dat's own gibbsite is better.

- **CSH-II.** Cemdata18's older two-endmember C-S-H model, taken as ideal mixing per formula unit, does not coexist with portlandite above Ca/Si 0.9, so CSHQ is used.
- **Ca-silicate complexes.** phreeqc.dat lacks the Ca-silicate aqueous complexes Cemdata18 requires with its C-S-H models, so dissolved Si at high pH is likely too low.
- **No sulfate, carbonate or iron phases**, and no redox.
- **Equilibrium only.** Spinel, forsterite and the calcium aluminates react completely here; at 25 C they are slow, and CA forms metastable CAH10 and C2AH8 first.

## Next

Validate against measured data. The search ranked these first:

- **Lothenbach 2012:** calcium aluminate hydrates, 7-40 C.
- **Wells 1943 and Peppler 1954:** NBS, open.
- **Myers 2015:** C-(A-)S-H, 7-80 C.
- **Nied 2016 Table 5 and Bernard 2017:** M-S-H.
- **Stewart 2018:** BOF slag leaching, with an open data table.
