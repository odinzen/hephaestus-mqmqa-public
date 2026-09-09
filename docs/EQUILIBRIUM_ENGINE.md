# C-core multiphase equilibrium and an OCASI-compatible interface

## Why

Today the C core evaluates phase Gibbs energies and equilibrates a single MQMQA
liquid; the real multiphase equilibrium (which phases coexist, in what amounts) lives
in the browser as a convex-hull sampling. Three separate goals collapse into one piece
of engine work:

1. **OCASI compatibility.** OpenCalphad's application interface (OCASI/TQ) is the
   de-facto way to embed a free CALPHAD engine. Mirroring its *interface* — not its
   GPL-v3 code — lets any OCASI-driven application use Hephaestus where OC cannot go:
   the browser, MIT-licensed and closed products, fast MQMQA.
2. **Mapping instead of sampling.** A proper conditions-driven equilibrium answers the
   standing critique that a sampled hull is coarser than a mapped diagram.
3. **Uncertainty bands.** Drawing an ESPEI posterior as a band means computing many
   real equilibria fast, in the browser — which needs the equilibrium in the core.

One capability, three payoffs: a conditions-driven multiphase equilibrium in C.

## Approach: robust-first, global before local

The equilibrium is found by **global minimization**, not a bare Newton step. Newton on
the Lagrangian is fast but traps in local minima and is exactly where this project's
earlier coupled solver failed twice. Instead, port the proven browser method:

1. **Candidate generation.** For each solution phase, sample its internal composition
   space and evaluate Gibbs per mole of atoms (the CEF `mqmqa_ph_cef_gibbs`, the MQMQA
   liquid `mqmqa_equilibrate`, the stoichiometric `mqmqa_db_stoich_gibbs`). Each sample
   is a point in (composition, G) space, tagged with its phase.
2. **Lower convex hull** over all candidate points (the routine already validated
   against scipy to machine precision, degenerate grids included). The hull facet under
   the overall composition gives the stable phase set; the barycentric weights give the
   amounts (the lever rule in n dimensions); the facet's supporting hyperplane gives the
   component chemical potentials.
3. **Optional local refinement (later stage).** A few Newton steps on the active set
   sharpen phase compositions from grid resolution to machine precision. This is polish
   on a correct answer, not the source of correctness.

This can never return a metastable assemblage the way an unrefined Newton can, which is
what makes it safe to expose through a general interface.

## Conditions model

Stage 1 supports the common case and grows outward:

- **Stage 1:** fix T, P, and overall composition (moles or mole fractions of the system
  components). Output: stable phases, their amounts and compositions, component chemical
  potentials, total Gibbs energy.
- **Later:** fix a component activity or chemical potential; fix a phase as stable
  (compute the condition that makes it so); suspend/enter phases.

## OCASI/TQ-compatible entry points (clean-room)

Implemented from the documented TQ interface semantics (a de-facto standard originating
in Thermo-Calc's TQ), **never by copying OpenCalphad's GPL headers or source**. Names
mirror OCASI so an application written against it can bind Hephaestus instead.

| TQ entry | Meaning | Backed by |
|---|---|---|
| `tqini` | initialise a workspace | new equilibrium context struct |
| `tqrfil` / `tqrpfil` | read a database (optionally select phases) | existing `.dat` / `.tdb` / `.utdb` readers (XTDB is roadmap S6) |
| `tqgcom` | get system components | `mqmqa_db_element` |
| `tqgnp` / `tqgpn` / `tqgpi` | number, name, index of phases | existing introspection |
| `tqgnsubl` / `tqgccf` | sublattices and constituents of a phase | existing CEF/MQMQA getters |
| `tqsetc` | set a condition (T, P, N, x) | conditions list on the context |
| `tqce` | compute equilibrium | the global hull minimiser above |
| `tqgetv` | get a state variable (phase amount, composition, potential, G) | equilibrium result |
| `tqphsts` | set phase status (entered / suspended / fixed) | phase mask on the context |
| `tqfree` | release the workspace | free the context |

The interface is thin: a stateful context holding the database, the conditions, the
phase mask, and the last result. Everything numeric routes to the existing evaluators
and the new minimiser.

## Validation

- The minimiser's equilibria are checked against **pycalphad** `equilibrium` on shared
  systems (the existing oracle), stable phase sets and Gibbs energies to tolerance.
- The same systems are cross-checked against **OpenCalphad** run as a separate program
  (use, not linkage — no GPL exposure), giving two independent reference engines: the
  strongest validation position in the field.
- The lower-hull primitive keeps its existing scipy parity test.

## Staging

- **S1** C multiphase equilibrium at fixed (T, P, x), reusing the current evaluators;
  validate against pycalphad.
- **S2** TQ-compatible C ABI over S1; unit tests through the ABI.
- **S3** WASM rebuild; the browser diagrams call the C equilibrium instead of the JS
  hull; verify parity in the app.
- **S4** conditions beyond composition (activity, fixed phase).
- **S5** optional Newton refinement for mapping-grade phase boundaries.
- **S6** XTDB reader as a file front-end; docs; paper update (the two-oracle validation
  story, the OCASI-compatible embedding claim).

## Licensing

Everything here is clean-room and MIT. OpenCalphad is read for its *interface shape and
its published model descriptions only*; no GPL code is copied or linked. XTDB is an open
documented format and is read directly.
