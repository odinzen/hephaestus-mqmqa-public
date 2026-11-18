# General equilibrium solver

Design note. Replaces the three-cation limit of `src/equilibrium.c` with a solver for any number
of elements and any mix of phases the engine models.

## Problem

At fixed temperature, pressure and bulk element amounts b, find the phases, their amounts and
compositions that minimize the total Gibbs energy. The element chemical potentials mu come out of
the same calculation.

## Method

Written from the textbook treatment of Gibbs energy minimization (Lukas, Fries and Sundman,
Computational Thermodynamics, Cambridge University Press, 2007, doi:10.1017/CBO9780511804137) and
the decomposition principle for linear programs (Dantzig and Wolfe, Operations Research 8 (1960)
101-111, doi:10.1287/opre.8.1.101). It generalizes the candidate-and-hull method the three-cation
solver already uses. No other program's solver source is read, so pycalphad and Thermochimica
remain independent checks of it.

1. **Candidates.** Every phase supplies points (x, g): x its element mole fractions, g its Gibbs
   energy per mole of atoms. A compound gives one point. A solution phase gives a grid over its
   internal variables (site fractions for the compound energy formalism, cation and anion fractions
   for the MQMQA, whose quadruplet distribution is relaxed at each point by the existing
   single-phase solver).
2. **Linear program.** Choose amounts n_k >= 0 of the candidate points with sum n_k x_k = b that
   minimize sum n_k g_k. The optimum is the lower convex hull of all candidates at b. Its dual
   values are the chemical potentials mu.
3. **Refinement.** For each phase, minimize its driving-force function g(x) - mu . x over its
   internal variables, starting from its best candidates. Any point below zero is added as a new
   candidate, and the linear program is solved again. This is column generation: it stops when no
   phase has a point below the hull, which is the equilibrium condition.
4. **Degenerate optima.** With fewer stable phases than elements, the linear program's basis
   holds columns at zero amount, and those fix its duals, one plane out of many that support the
   hull. A point below that plane need not lower the hull, and a point that would lower it may not
   lie below that plane. When a pass leaves the hull where it was, each phase is searched against
   two planes, the duals and the plane fitted tangent to the stable phases, and the loop ends only
   when the hull has not moved for two passes and nothing lies more than 1e-6 J/mol below the
   tangent plane (or after eight passes without a move).
5. **Result.** Candidates of one phase that remain in the solution and lie close in composition
   are merged into one composition set; those far apart are reported as separate sets (a
   miscibility gap). A column left at a negligible amount (below 1e-6) by a degenerate basis
   joins the nearest set of its phase instead of being reported on its own. Two copies of a
   phase count as one phase here. A ChemSage file lists a phase twice to give it room for a
   miscibility gap, and where none opens the copies have one energy and the linear program can
   split an amount between them at one composition (NobleMetals-Kaye's two HCPN at 2250 K). A
   shared name alone does not make a copy (FeMnCaS-1's two IONIC_LIQ differ by up to 48 kJ/mol),
   so two phases count as one only when their energies agree exactly at four fixed points.
6. **Certificate.** Every phase is searched once more against the final plane. The residual is
   the most negative driving force found, or the largest gap between the plane and a stable phase
   if that is worse (a plane passing under the stable phases has nothing below it either); at an
   equilibrium it is zero up to the solver's tolerance. When the plane is not unique, the fitted tangent plane can cut under a phase
   that the linear program's plane keeps above, so both are tried and the chemical potentials
   reported are those of the plane with the smaller violation. When the certificate finds a
   point more than 1e-6 J/mol below, that point becomes a candidate and the passes resume (at
   most twelve times, and at most 120 passes in all). The passes stop when one adds nothing below
   the plane it searched, and the certificate, searching from the final state, can still find
   something they missed: a strongly bound CsI gas at 1e-5 atm was once left 26 J/mol above its
   own minimum that way.
7. **Exact finish.** The passes end on sampled compositions. That fixes G to about 1e-9 of its
   value, but the chemical potentials are slopes and can hang on the last digits of a dilute
   constituent. The same CsI gas holds 4e-6 free Cs and I atoms, and a composition error of 3e-8
   there moved mu(Cs) - mu(I) by 70 J/mol. The equilibrium conditions are therefore solved
   directly by Newton steps, for every kind of stable set. A compound lies on the plane. A
   sublattice phase (the compound energy formalism with any number of sublattices, the one-lattice
   gas, RKMP and QKTO among them, and the SUBI ionic liquid) has, at its site fractions, the
   derivative of G - mu.N along each constituent equal to its sublattice's multiplier, each
   sublattice summing to one, and G = mu.N (G and the element amounts N per formula unit); the
   ideal part RT m ln y is differentiated exactly (m the sublattice's site number, P and Q in the
   ionic liquid), the rest by central differences. An MQMQA liquid's quadruplets are species, as
   Thermochimica's user manual treats SUBG and SUBQ (its eqs. 2, 3 and 6): each quadruplet's
   potential, from the model's exact gradient, lies on the plane. The amounts meet the bulk. Where
   an element is tied to the others by charge balance in every phase (oxygen in a fixed-valence
   oxide), the finish works in the passes' reduced space, that element's potential folded into the
   cations'.

   A constituent whose own fraction would fall below e^-690 (a quadruplet, e^-69, where smaller
   fractions underflow the gradient) is held at zero. A dilute constituent moves on its own, up to
   60 in log amount a step, so it does not hold back the others; a Newton step that fails its line
   search, or would move a log amount by more than a million, gives way to a damped least-squares
   (Levenberg-Marquardt) step. The tolerances are 1e-7 RT on each potential and 1e-15 on the
   balance; a Newton run that stalls is accepted at 1e-5 RT and 1e-12. The result is kept only if
   nothing lies below the new plane and G has not risen above the hull by more than the hull's own
   accuracy (1e-9 of the potentials' sizes, since the linear program meets each element's amount
   to 1e-9). The result's `exact` says whether it was kept.

   Independent checks. The 51 single-phase Thermochimica points where the tangent
   at the bulk can be computed directly agree to 1e-4 J/mol; all 314 sublattice-phase and
   ionic-liquid sets at the test points agree within 0.01 J/mol with their own internal
   equilibrium found from scratch in Python (a separate minimization from many starts and a root
   solve at the reported composition, the lowest state kept);
   every ideal gas meets mass action to 2e-14; the CuFeC-Kang liquid matches pycalphad's liquid at
   its composition. Limits. Below about 1e-15 free atoms no double-precision code resolves the
   potentials; a compound standing alone fixes only a sum of potentials and the reported split is
   one of many; a trace phase holding all of two elements (a NaCl melt at 1e-3 beside liquid Al)
   can leave the finish unconverged, reported as `exact` false with the sampled result.
8. **Candidates from the MQMQA liquid.** A sampled point counts only if the fixed-composition solve
   came within 1e-5 of its composition. In ClAlNa's metallic liquid it missed by 0.26 at a trace of
   Cl and returned the energy of another composition, 2 kJ/mol below the plane, which the hull took
   as a second liquid that does not exist (TestThermo63). A gross miss is moved onto the edge
   without its traces and solved as a subsystem; not every point is moved there, as columns exactly
   on an edge coincide with compounds and made the basis singular. The fixed-composition solve is
   also finished exactly (Newton on the quadruplets with the composition held) where its own check
   of the conditions fails by more than 1e-3 RT. On 7000 random compositions of the shipped liquids
   that finish lowered 69 energies (median 0.03 J/mol, at most 386 J/mol on CaO-Al2O3-SiO2 at
   1673 K); it was first used only inside this solver and is on everywhere, the web calculator
   included, since 16 November 2026 (Michael's decision).
9. **A bulk on a face of what the phases reach.** NaCl or NaAlCl4 at exactly their formulas, in a
   file whose only chlorine-rich species beyond the salts is a dummy, lies on the plane
   Cl = Na + 3 Al with every phase on or below it. States with free metal (Na vapour, the liquid's
   vacancy, the metals) then have zero amount, but their samples, carrying traces of everything,
   lie a hair off the plane, and bases mixing them with the salts were singular in exact arithmetic:
   the mass balance missed by 3e-5 or the linear program failed. Before sampling, a linear program
   finds the largest t with sum lambda_k e_k = b and every lambda_k >= t over the endmember
   compositions e_k of all phases (compounds, CEF endmembers, MQMQA pairs, SUBI endmembers). The
   bulk is on a face exactly when that t is zero, and the optimal duals w then satisfy w.e_k <= 0
   for every endmember with w.b = 0 (Gordan's alternative). Constituents leading strictly below
   that plane are held at zero as an absent element's are (in an MQMQA liquid, the ions whose
   every pair leads off it; the cut reaches the fixed-composition routines through
   `Phase.ion_off`), the test repeats until the bulk is inside what remains, and a cut that would
   leave the bulk out of reach is undone. A bulk inside the region is left exactly as before. On
   ClAlNa at 1200 K, NaAlCl4 then gives liquid and gas within 0.03 J of Thermochimica and NaCl
   liquid within 1e-10 J.
10. **An ionic liquid without its cations.** With only neutrals on the second sublattice a SUBI
   liquid has P = 0, so its cation sites vanish and it is the neutrals alone (pure Te in CsTe-2,
   pure C in an Fe-C liquid). Such a phase is kept when the bulk lacks every cation's element,
   with one cation as a placeholder holding no atoms and the anions and vacancy at zero.

Global first, then local: the hull cannot be trapped in a wrong assemblage the way a Newton step
from a poor start can, and refinement then takes the result to the true minimum. The phase
subproblems use quasi-Newton (BFGS) steps with finite-difference gradients (Nocedal and Wright,
Numerical Optimization, Springer, 2006, doi:10.1007/978-0-387-40065-5) over variables mapped so they
stay on their simplex. Each stable phase also adds the point at the weighted centre of its columns,
which settles degenerate optima, and the chemical potentials are finally fitted to the tangent of
every stable phase rather than taken from the linear program's duals.

## The MQMQA liquid inside it

Every liquid point is an internal equilibrium of the quadruplet distribution at fixed composition.
Checked against pycalphad's liquid-only result on one-liquid compositions, the engine's single-phase
solve agrees to 0.0005 J/mol for liquids with up to three cations (FeO-MgO-SiO2, CaO-Al2O3-SiO2), and
that path is unchanged. With four cations (CaO-FeO-MgO-SiO2) the strongly ordered states sit in
separate pockets near the edges of the feasible set, and the shipped single-start descent missed them
at 8 of 24 such compositions, by up to 6.1 kJ/mol. Larger liquids now start from a projected interior
point and descend from that point, one corner start per quadruplet and the lowest points of a
hit-and-run walk, each finished by Newton steps built on the exact gradients of the configurational
entropy and of the excess terms (`mqmqa_ideal_mixing_gradient`, `mqmqa_excess_gradient`; both are
checked against finite differences of the energies on every liquid the engine reads, in
`tests/test_energy_gradients.py`). The shipped careful descent runs once more from the lowest start
as a further candidate. All 24 compositions then agree with pycalphad, the largest difference
0.04 J/mol, at about 24 ms per four-cation liquid point against 1 ms for three cations.

That fixed-composition solve still fills the liquid's starting candidates, but refinement no longer
nests it. The driving force of an MQMQA phase is minimized directly over its quadruplet fractions,
G(X) - mu . n(X) with only sum X = 1, the composition left free
(`mqmqa_driving_force_minima`, `mqmqa_driving_force_db`). It uses the same starts and Newton steps
on the same exact gradients, with the linear term added, plus three starts per quadruplet where it
dominates (90, 99 and 99.9%): without them the silica-rich liquid of the miscibility gap, at 98.5%
Si on the cation sublattice, was never reached, and the engine put cristobalite out of a liquid that
is really two liquids 10 to 49 J/mol lower. A descent whose every step was an internal equilibrium
took about two minutes per four-oxide point; this takes 1 to 4 s.

The chemical potentials are fitted tangent to the stable phases. For an MQMQA phase the slopes come
exactly from its internal equilibrium, where every quadruplet present has dG/dX_q =
sum_e mu_e n_e(q) + lambda (`mqmqa_tangent_rows_db`, differences against the most abundant
quadruplet remove lambda). Central differences of the fixed-composition solve, used before, carried
its tolerance divided by the step and put the slopes kJ/mol off with four cations.

## Scope of the first version

- Phases: stoichiometric compounds, compound-energy-formalism solutions (any number of
  sublattices and constituents), MQMQA liquids (any numbers of cations and anions the energy
  routines accept), and the ChemSage ideal (IDMX) and Redlich-Kister-Muggianu (RKMP) solutions,
  read as one-lattice phases of species with binary, ternary (Muggianu's weights) and quaternary
  terms; a species takes its composition from its own record. SUBLM and RKMPM add the
  Inden-Hillert-Jarl magnetic term: the header holds -1/AFM (1 for BCC, 1/3 for FCC) and p,
  each species its Curie or Neel temperature and moment, and a magnetic interaction list
  precedes the excess list. pycalphad 0.11.2 leaves this term out of a ChemSage BCC phase
  (BCC Fe in Thermochimica's CuFeC-Kang file is higher there by exactly the term), so it is
  checked against the formula instead. A SUBL pair on one sublattice is ordered by name, as
  pycalphad orders it; where a file lists the pair in another order, an odd-order term takes
  the opposite sign from the file's order. Which order ChemSage means is left to the sealed
  Thermochimica comparison (recorded here before it is opened). A SUBL term may also mix three
  or four constituents on one sublattice (Muggianu's weights in file order for a three-parameter
  ternary) or a pair on each of two sublattices (a reciprocal term, one parameter), the other
  sublattices pinned. Dummy species (marked # in a
  ChemSage file) are never formed. An MQMQA ion takes its composition from its name when that
  is one atom of an element (Fe+2), as nothing when it is a vacancy, from the species table of a
  TDB, or else from the pair records, each the neutral unit of its two ions (Al2Cl6 with Cl
  known gives the Al2 dimer two Al); every pair is then checked against the result
  (`mqmqa_ph_ion_comps`). The element amounts per quadruplet are built from these
  compositions; for one-atom ions the arithmetic is exactly the earlier one.
- The ChemSage two-sublattice ionic liquid (SUBI), written from Sundman, Calphad 15 (1991) 109:
  (C)_P (A, Va, B)_Q with P = sum |v_A| y_A + Q y_Va and Q = sum v_C y_C, so a formula unit's
  element amounts move with composition (`mqmqa_ph_ionic_gibbs` returns them with its energy).
  A neutral's record holds v_C times its energy, so the records summed with the site fractions
  give Sundman's eq. 5; the reader checks that every cation's record of a neutral says the same.
  Each excess term is one of the sums of his eqs. 24 and 27, with the rule of pairs (y_Va with
  each cation fraction) where no anion multiplies the term, and eq. 37's order for a reciprocal
  series. Checked where the paper shows the model reduces to another: without anions it is the
  substitutional (RKMP) solution at x_C = y_Va y_C (eq. 19), with one charge per sublattice the
  SUBL phase of fixed sites, both to 1e-8 J; terms an anion multiplies agree with pycalphad's
  ionic liquid. On the two vacancy terms pycalphad differs from the paper by one factor y_Va
  (for (Fe+2)(Va,C) it gives x_Fe^2 x_C L where eq. 15 gives x_Fe x_C L). Refused: a term of
  two cations with Va and a neutral given three parameters (eqs. 34 and 37 both fit it), and a
  neutral-neutral term unless the phase has a single cation of charge 1 (how a file scales it
  for other cations is not known). A binary's odd orders take the file's order of the pair.
- ChemSage Kohler polynomial solutions (QKTO), written from Pelton, Calphad 12 (1988) 127: a
  term lists its species and the power of each, phi Y_A^i Y_B^j (eq. 7), and in more components
  takes Kohler's weights, s^2 (Y_A/s)^i (Y_B/s)^j with s = Y_A + Y_B, a ternary term s^3 and three
  ratios (eq. 12). Each species ends with its equivalents per particle and its group; only one
  equivalent and one group are read (the Toop form for two groups is refused, no file at hand
  showing how it is written). The term layout matches Kaye, Lewis and Thompson's printed bcc
  Mo-Pd equation (J. Nucl. Mater. 366 (2007) 8), and every QKTO phase of Thermochimica's files
  agrees with pycalphad's ChemSage reader to 1e-10 J inside the data's temperature range.
  Above a record's last temperature the last range is carried on and flagged (below).
- ChemSage SUBM (Pelton's two-sublattice equivalent-fraction model) is refused: the model is Pelton's (Calphad 12 (1988) 127), but how a ChemSage file records its excess terms is documented nowhere that may be read for this check: not in that paper, not in ChemApp's or Thermochimica's manuals, not in FactSage's public notes, and pycalphad does not read SUBM at all. The one file that uses it (ZrFeKClNaFOLi, a synthetic test) admits at least two readings of its records, which differ in whether a binary term's powers count from 0 or from 1, and the only source that would settle it is Thermochimica's code, which this check keeps closed.
- The linear program prices from a fresh inverse every pivot, uses Harris's ratio test with a
  minimum pivot, measures costs from the last pass's plane (so reduced costs are J-sized
  differences, not differences of 4e5 J/mol values), counts a pivot as progress only when the
  objective really drops, and keeps one column per point of a phase (two within 1e-9 made a nearly
  singular basis on which the simplex cycled).
- Conditions: T, P and bulk element amounts. P acts on the ideal gas of a ChemSage file (its first
  solution phase, when IDMX): each species gains R T ln(P / 1 bar), the data's own reference as
  FactSage and Thermochimica take it, so RT ln 1.01325 at 1 atm. (Before 15 November 2026 it was
  ln(P / 1 atm); running Thermochimica on pure H2 at 0.986923 atm showed its 1 bar reading.)
  pycalphad applies no pressure to such a gas, so this is checked against the mass-action law
  instead. Condensed phases carry no volume data. Fixed chemical potentials come next.
- Two more rules for reading a ChemSage file, fixed with Michael after the Thermochimica
  comparison. A mixing pair keeps the file's order: an odd-order term is (y_i - y_j)^n with i the
  constituent listed first (the sublattice reader sorted pairs by name, as pycalphad does, which
  flipped the sign of CuFeC-Kang's fcc Fe,Cu term). Above the end of a species' data the last
  range is carried on, as Thermochimica does (pycalphad 0.11.2 carries it on in TDB files and
  ChemSage one-lattice phases but takes zero in its MQMQA liquid), and the result lists every such species
  with where its data end (`Result.beyond_data`, `Database.beyond_data`); the reader took zero
  there before, which matched no code. A TDB function's last range was already carried on and is
  now flagged the same way.
- Phases can be suspended, as in the three-cation solver.
- Subsystems of a larger database. A solution phase holding an element the bulk lacks keeps
  those constituents at exactly zero (a gas of Na, NaCl and AlCl3 species with no Na present
  was otherwise given no candidate points and left out), and an MQMQA phase is computed
  without those ions (`el_keep` in `mqmqa_equilibrate_sub_db`, `mqmqa_driving_force_db`,
  `mqmqa_tangent_rows_db`): every quadruplet, pair and excess term naming them is dropped, which
  leaves the energy unchanged because their weight is zero. A phase with an empty sublattice is
  left out. The CaO-FeO-MgO-SiO2 file computed without CaO gives the FeO-MgO-SiO2 file's results
  to 0.001 J/mol. The fixed-composition solve (`mqmqa_equilibrate_db`, behind the web app's
  ternary calculator) now does the same for an element of the phase that is exactly zero; left in
  at zero amount it came out 1.0 to 2.6 kJ/mol high (pycalphad's subsystem liquid as reference),
  and the calculator named cristobalite + olivine on the FeO-SiO2 edge at 1473 K where liquid is
  stable. A target with every element present takes the earlier path unchanged. Short of zero,
  with four cations, the solve is still off by up to 1.1 kJ/mol once a component falls to
  1e-5. Inside the solver such values are only ever too high, so they cost candidates, never
  a wrong equilibrium.

## Checks

- pycalphad on the shipped alloy and slag databases (its solver is independent of this one).
  Where the two disagree the lower answer is checked with pycalphad's own energies, each set the
  engine reports re-evaluated by pycalphad at that set's composition. In CaO-FeO-MgO-SiO2 at
  1573 K (cations Ca 0.20, Fe 0.05, Mg 0.35, Si 0.40) pycalphad's all-phase result, olivine +
  wollastonite, lies 56 J/mol above liquid + olivine + clinopyroxene, whose pycalphad energies add
  up to the engine's total; at 1473 K (Ca 0.45, Fe 0.05, Mg 0.10, Si 0.40) it misses 3% liquid
  beside rankinite, olivine and wollastonite (0.48 J/mol).
- The three-cation solver where both apply.
- The sealed Thermochimica cases (`validation/thermochimica`), once the phase types they use are
  read.
- Planted cases with a known answer: two compounds and their tie line, an ideal solution, a
  symmetric miscibility gap.
