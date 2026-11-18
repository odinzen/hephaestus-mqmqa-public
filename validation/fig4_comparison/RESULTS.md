# Figure 4a against pycalphad and against Bowen and Schairer

Written 17 November 2026 for reply 2.2 of the JORS response letter (Reviewer 2 asked whether the
jagged isotherms of the submitted figure were real and whether other codes show them).

## What was compared, and what it can show

pycalphad 0.11.2 was run as a program on the shipped `data/feo-mgo-sio2/FeO-MgO-SiO2-combined.dat`,
the file Figure 4a is drawn from, at every node of the figure's grid (150 steps per side, 11,476
nodes). At each node it gives the liquidus temperature and the first solid to crystallize.

The MQMQA liquid energy in Hephaestus is a C translation of pycalphad's model
(`pycalphad/models/model_mqmqa.py`, see NOTICE). The two codes therefore evaluate the same Gibbs
energies (they agree to 0.001 J per mole of atoms wherever both reach the same state), and this
comparison cannot test the model or the database. It tests the step from energies to the figure,
that is, which solid appears first, at what temperature, where the isotherms run, and whether they
come out smooth. The test of the database is the comparison with measurements at the end.

The figure itself was first re-derived from the current engine (`compare_pycalphad.py export`),
and all 11,476 field cells match the shipped figure data.

## Primary phase

| | pycalphad as first run | pycalphad after recheck |
|---|---|---|
| nodes with the same first solid as Figure 4a | 11,438 | 11,470 |
| nodes that differ | 38 | 6 |
| largest distance of a differing node from a field boundary | 5.6 grid steps | 1 grid step |

The six nodes that still differ all sit on a field boundary, within the resolution of the grid
(one step is 0.67% of the side of the triangle).

## Liquidus temperature

pycalphad minus Hephaestus over all 11,476 nodes, after the recheck: mean +2.6 K, root mean square
8.2 K, median of the absolute difference 0.05 K. At 9,774 nodes the two agree within 1 K. The mean
and RMS are carried by the remaining 1,702 nodes, where pycalphad reads high, as follows.

**pycalphad misses the liquid.** pycalphad samples each phase at 60 points per degree of freedom
unless told otherwise. At that density it misses the lowest-energy liquid in places, keeps a
solid that should have melted, and reads the liquidus high, by up to 98 K. The 1,863 nodes that
disagreed by more than 1 K or in the phase were solved again at 2,000 points on a 5 K ladder
around both answers. Only 171 then agreed. A random 500 of the agreeing nodes were solved again
too, and 12 of them moved by more than 0.5 K or in phase.

**pycalphad's own energies decide.** At the midpoint temperature between the two answers one code
says a solid is present and the other says the melt is all liquid. Two tests settle which is
right, both from energies the codes share.

1. The driving force. From the lower of the two codes' liquid-only equilibria at that temperature
   (pycalphad sometimes misses the split into two liquids near the silica corner, by up to 192 J),
   is any state of the solid, with pycalphad's energy for it, below the liquid's tangent plane? If
   so, the temperature is below the liquidus.
2. The lowest state. Is the lowest state pycalphad finds with a solid present below the lowest
   liquid-only state either code finds?

The two tests agree at all 1,567 nodes where both apply and contradict each other at none. At the
other 134, pycalphad finds no state with a solid at all, and the driving force alone decides.
Checked by hand at forsterite, the driving force crosses zero at 2080 K, where the liquid and
olivine energies cross. Of the 1,704 nodes,

| finding | nodes | size |
|---|---|---|
| pycalphad high, the liquid is lower in energy (pycalphad wrong) | 1,590 | mean 19 K, up to 70 K |
| Hephaestus high, the liquid is lower in energy | 104 | mean 3.9 K, up to 9.2 K |
| Hephaestus low, a solid is lower in energy | 8 | up to 11.8 K, the others under 2.3 K |
| differ in phase only, on a boundary | 2 | |

The worst pycalphad case is forsterite, which pycalphad melts at 2151 K. At 2100 K and 2130 K
pycalphad itself reports solid olivine, yet its own liquid-only state is lower by 137 J and 349 J
per mole of atoms. The figure's 2080 K is right.

The 112 nodes where Hephaestus was off came from its point liquidus reader
(`vis3d.liquidus_point`), which the comparison used to give a temperature per node. They lie
where the liquid splits in two, along the silica-rich side of the MgO-SiO2 edge and along the
lower edge of the cristobalite field. Figure 4a does not use the point reader. Its fields come
from the liquidus surface and its isotherms from fixed-temperature hulls, and both are compared
directly below. The point reader has since been fixed (next section).

Hephaestus's general solver (`src/gem.c`) was also run as a referee. It sided with Hephaestus at
1,569 nodes and with pycalphad at 104, but at forsterite it returned liquid plus olivine at 2110 K,
77 J above the all-liquid state, and it found no equilibrium at fayalite (one node). The energy tests
above replace it as the arbiter. Inside the two-liquid gap the solver at its default sampling
(grid 6) can also stop 1 to 7 J above the minimum. It flags such a result as not exact, and a
coarser grid (3, then 2) finishes exactly at every temperature tried.

The solver has since been fixed (17 November 2026, `src/gem.c`). At a congruent melting point
the liquid and the solid share one composition, and a trace element carried by the liquid
alone left its chemical potential undetermined; against the plane that resulted, the search for
the liquid's lowest point missed the liquid at the bulk composition itself. The finished result
is now compared with each liquid at the bulk composition, and if the liquid is lower it enters
and the solve resumes. Forsterite at 2110 K and fayalite from 1480 to 1485 K now come out all
liquid, finished exactly, at the energy of the liquid-only state. A failed solve, or an
unfinished result holding a liquid, is tried again on grids 3 and 2 and the lowest kept, which
closes the 1 to 2 J misses beside the gap. Checks on the fixed solver: the 201 calculated
Thermochimica points come out bit for bit as before, the full test suite passes, and of 401
interior cells of the Figure 3 crystallization map (every cell on a field boundary and 60 at
random) one changes, by one 20 K step, its liquidus lying within 0.02 K of the grid temperature. On its CaO-free edge, where the
cells carry 1e-6 CaO, the old solver had the same fault (olivine and orthopyroxene 658 J above
the all-liquid state at 1970 K for one cell), and the edge cells' own liquidus temperatures drop;
the figure shows each edge cell's inner neighbor, so it does not change.

## The point reader, fixed

Where the liquid has split, the reader took the liquid's tangent plane from a convex hull and
interpolated the liquidus through three temperatures 25 K apart. The hull can miss the second
liquid, its vertex can sit off the edge of the gap by about 4 J near the silica corner, and the
interpolation fails at the kink where the bulk leaves the gap. The reader now takes the plane
from the general solver's liquid-only equilibrium, accepted only when the solver reports it
exact, and finds the temperature where the driving force of the first solid crosses zero. Where
the solver gives no exact answer the reader keeps the old path. Figure 4a's fields and isotherms
are untouched (`export`, all 11,476 field cells unchanged).

The whole grid was read again (`reader`, 78 min). No node failed and no first solid changed.
174 nodes moved by more than 1 K (mean 3.6 K lower, at most 11.7 K). Every node that moved, or
that differs from pycalphad by more than 1 K, 1,884 in all, was checked with the energies of both
codes 0.3 K either side (`verify`). At all 1,884 a solid is stable below the new temperature and
the melt is all liquid above it.

| | old point reader | fixed point reader |
|---|---|---|
| nodes within 1 K of pycalphad | 9,774 | 9,820 |
| nodes where the energy tests show Hephaestus wrong | 112 | 0 |
| nodes where pycalphad reads more than 1 K below Hephaestus | 104 | 0 |
| at the 112 nodes, Hephaestus minus the energy-settled liquidus | mean +3.5 K, up to 11.8 K | mean -0.35 K, up to 2.7 K |

The last row compares with pycalphad's answer at those nodes, which is itself read from a 5 K
ladder; the fixed reader is checked to 0.3 K directly. Every remaining difference of more than
1 K is pycalphad reading high where it misses the liquid.

## Isotherms and smoothness

Distance, in grid steps, from each code's unsmoothed isotherm to the isotherm drawn in Figure 4a
(no isotherm at 1473 K falls inside the triangle).

| isotherm | pycalphad, mean (largest) | energy-settled liquidus, mean (largest) |
|---|---|---|
| 1573 K | 0.44 (1.8) | 0.43 (1.8) |
| 1673 K | 0.41 (1.6) | 0.40 (1.5) |
| 1773 K | 0.39 (1.7) | 0.38 (1.7) |
| 1873 K | 0.39 (1.4) | 0.39 (1.4) |
| 1973 K | 32 (77) | 0.45 (1.5) |

At 1973 K pycalphad's missed liquid in the cristobalite field puts its liquidus above 1973 K over
a band where the true liquidus is near 1940 K, which draws a false closed isotherm there (white
dashes in the silica field of panel a). The energy-settled liquidus has no such loop and runs
within half a grid step of the figure.

Smoothness is measured as the root mean square change of direction between steps of one grid
spacing along each isotherm. A staircase turns sharply at every step and a smooth curve turns
little.

| isotherm | pycalphad raw | Hephaestus raw | Figure 4a as drawn | pycalphad cut into 10 K steps |
|---|---|---|---|---|
| 1573 K | 12.2 deg | 12.2 deg | 9.6 deg | 36.0 deg |
| 1673 K | 11.3 deg | 11.4 deg | 8.5 deg | 19.1 deg |
| 1773 K | 13.6 deg | 13.6 deg | 9.3 deg | 30.5 deg |
| 1873 K | 9.6 deg | 9.6 deg | 10.4 deg | 27.4 deg |
| 1973 K | 43.0 deg (false loop) | 11.1 deg | 9.8 deg | 33.0 deg |

Both codes give equally smooth isotherms. Storing the liquidus in 10 K steps, as the scan behind
the submitted figure did, brings the staircase back, so the jagged edges were a numerical artifact
of that scan, not a feature of the system.

## Measured liquidus (Bowen and Schairer 1935)

The 38 points of Table I (`data/feo-mgo-sio2/bs1935_table1.csv`, read from the repository, scored
with the field grouping of `bs1935_liquidus.py`), calculated minus measured.

| field | points | mean | mean absolute | RMS | worst |
|---|---|---|---|---|---|
| olivine | 23 | +5.6 K | 21.2 K | 26.6 K | 68 K |
| pyroxene | 8 | +18.8 K | 18.8 K | 19.5 K | 27 K |
| silica | 7 | +6.0 K | 11.3 K | 14.6 K | 28 K |

Primary phase as measured, 29 of 37. Hephaestus, pycalphad at both densities and the general
solver give the same first solid at all 38 points and liquidus temperatures within 0.2 K of each
other, so these are the manuscript's figures (olivine within a mean 21 K of 23 points, pyroxene
19 K, silica 11 K, 29 of 37) and none of them changes.

## Against a FactSage-lineage assessment (Wu et al. 1993)

Wu, Eriksson, Pelton and Blander, ISIJ Int. 33 (1993) 26-35, assessed this system with the
modified quasichemical model in its pair form, a different database from ours. Their text
states the calculated ternary peritectic and their Table 3 the olivine solidus along the
Mg2SiO4-Fe2SiO4 join, each beside Bowen and Schairer's measurement. This comparison does test
our database, unlike the pycalphad one. `factsage_wu1993.py` finds our peritectic as the liquid
composition and temperature at which olivine, orthopyroxene and silica all have zero driving
force (`factsage_wu1993.json`). Figure 4a puts the meeting point of its three fields in the
same place, within one grid step. Our database has no tridymite, so its silica is
cristobalite.

| peritectic L + olivine + pyroxene + silica | T | liquid, wt% MgO / FeO / SiO2 | olivine, wt% Fe2SiO4 | pyroxene, wt% FeSiO3 |
|---|---|---|---|---|
| measured (Bowen and Schairer, as quoted by Wu et al.) | 1579 K | 9 / 46 / 45 | 68 | 62 |
| Wu et al. 1993 | 1583 K | 10.5 / 45 / 44.5 | 61 | 50 |
| this database | 1506 K | 3.8 / 56.2 / 40.0 | 79 | 65 |

Olivine solidus on the join, wt% Fe2SiO4 at each temperature, and our solidus temperature at
the measured composition minus the measured temperature.

| T | measured | Wu et al. | this database | our solidus at the measured composition |
|---|---|---|---|---|
| 1768 K | 41 | 40.5 | 37.4 | 49 K low |
| 1738 K | 45 | 45 | 39.6 | 75 K low |
| 1713 K | 47.5 | 49 | 41.4 | 71 K low |
| 1683 K | 54 | 54 | 43.6 | 72 K low |
| 1591 K | 70 | 71.5 | 59.0 | 38 K low |
| 1549 K | 80 | 81 | 71.5 | 24 K low |

Wu et al. reproduce the peritectic within 4 K and the solidus within 1.5 wt% Fe2SiO4. Ours places the peritectic
73 K low and toward FeO, so the pyroxene field reaches further toward FeO than measured, and
melts olivine 24 to 75 K early on the join. Table 2 of the manuscript gives the solidus as
36 to 42 K low against Nafziger and Muan; against Bowen and Schairer the gap is larger in
mid-join. Neither offset is stated in the manuscript yet.

## Files

- `compare_pycalphad.py` produces everything here. `run` (the full grid, 14.6 h on 14 processes),
  `recheck` (2.6 h), `energy` and `driving` (about 4 min each), `reader` (78 min) and `verify`
  (15 min) for the fixed point reader, `export` and `report`.
- `liquidus.npz`, `liquidus_pdens2000.npz`, `energy_check.npz`, `driving_force.npz`,
  `liquidus_reader_fixed.npz` and `reader_verified.npz` hold the raw results, so `report` reruns
  in a minute.
- `factsage_wu1993.py` and `factsage_wu1993.json`, the comparison with Wu et al. 1993.
- `results.json` holds every number above.
- `fig4a_vs_pycalphad.png`. (a) Figure 4a's fields (tinted) and isotherms (black), pycalphad's
  unsmoothed isotherms after the recheck (white dashes), nodes where the first solid differs (red)
  and the measured points of Bowen and Schairer. (b) pycalphad minus Hephaestus liquidus at each
  node from the fixed point reader, with the 112 nodes where the old reader was off by over 1 K
  (black).

pycalphad's `core/calculate.py` and `core/workspace.py` were opened on 16 November 2026 only to read
the default sampling density of `equilibrium`; no code was taken from them (NOTICE, README).
