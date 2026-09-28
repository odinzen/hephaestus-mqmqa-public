# 3D phase-space visualization: red-team review and specification

Status: steps 1 and 2 of section 7 implemented (`src/vis3d.h`, `src/vis3d.c`,
`python/mqmqa/vis3d.py`, `tests/test_vis3d.py`); steps 3 to 7 not started. Section 8 records
where the implementation departs from this proposal and why. Target: the private `next-release`
line, then the public release. The proposal below builds on the engine's existing ternary path,
the C lower convex hull (`mqmqa_lower_hull_2d`) and the lever-rule assemblage lookup
(`mqmqa_hull_assemblage_2d`) in `src/hull.h`, fed with Gibbs-energy points sampled per phase.

## 1. Red-team findings

Each finding states the assumption in the original concept, what is actually true, and what the
design does about it.

### R1. The bottleneck is the equilibrium, not memory or transfer

Assumption: a 100 x 100 x 100 prism is a memory and serialization problem.

Reality: every grid node needs an equilibrium. One ternary section at one temperature already means
thousands of sampled liquid points plus a hull, and a 10^6-node volume means 10^6 assemblage
lookups on top of about 100 hull solves. Moving 10^6 float32 values (4 MB) costs milliseconds.
Computing them costs minutes to hours.

Design: do not compute a volume. The physics of a T-x1-x2 prism is a set of surfaces (liquidus,
solvus, univariant valleys), so compute surfaces directly.
- Stack of exact isothermal sections at N temperatures, each one hull solve (the engine's existing
  operation), classified into phase regions.
- Liquidus surface T_liq(x1, x2) on a triangular composition lattice, located per node by bisection
  in T between bracketing sections, refined only where needed.
- Cost scales with N sections plus lattice size (about 5,000 nodes at n = 100), not with n^3.

### R2. "Zero-copy to the GPU" does not exist, and heap views go stale

Assumption: share a HEAPF32 pointer with WebGL and avoid copies.

Reality, verified in `scripts/build_wasm.sh`:
- The module is built with `ALLOW_MEMORY_GROWTH=1`. When the WASM heap grows, every existing
  `HEAPF32`/`HEAPF64` view is detached and silently reads garbage. A cached pointer view is a latent
  bug.
- WebGL `bufferData` copies into GPU memory regardless, so one CPU-side copy is unavoidable anyway.

Design:
- Never cache a heap view. After each engine call, create a fresh typed-array view at the returned
  offset and `slice()` it into a JS-owned array. For 10^6 vertices this is a few milliseconds.
- The main-thread stall comes from the solve, so run the engine in a Web Worker. The module is built
  `MODULARIZE=1 SINGLE_FILE=1`, so a worker can instantiate it directly.
- Hand results to the main thread as transferable `ArrayBuffer`s (ownership moves, no copy).
- Do not use SharedArrayBuffer. It needs cross-origin isolation (COOP/COEP headers), which GitHub
  Pages cannot set without a service-worker workaround, and it buys nothing once the worker does the
  solving.

### R3. The engine is single-threaded by design

Verified this week (heap-corruption investigation): the engine keeps process-wide state (gas-constant
mode, loaded-database registry, message buffers are plain statics). It must never be called from two
threads at once.

Design: one engine instance per worker. Parallelism is several workers, each with its own module
instance and memory, splitting temperature levels between them. The same rule gives the HPC story:
many independent processes, not threads.

### R4. float32 destroys Gibbs-energy detail

Assumption: Float32 arrays straight from the solver.

Reality: molar Gibbs energies are around 10^5 to 10^6 J/mol. float32 carries about 7 significant
digits, so absolute resolution is about 0.1 to 1 J/mol at that magnitude, while the differences that
decide a common tangent are J-scale.

Design: the engine computes and differences in double, and exports only relative quantities for
rendering.
- G surfaces: export G minus the mechanical-mixture plane of the pure end members, or G minus the
  hull (the distance to equilibrium), per vertex, in double, then convert to float32.
- Positions in [0, 1] composition space and scaled temperature are safe in float32.

### R5. Sharp phase seams need explicit boundaries, not a finer grid

Assumption: triangulate a grid and let the renderer draw it.

Reality: any triangle whose vertices sit in two phase fields is interpolated across the boundary.
That smooths away the slope discontinuity at a eutectic valley and paints a false blend of two
fields. Refining the grid only narrows the smear.

Design:
- One mesh patch per phase field, never one mesh for the whole surface.
- Boundary vertices are computed by the engine, not interpolated from labels. Along each lattice
  edge whose two end nodes have different assemblages, bisect in composition until the assemblage
  change is located to a set tolerance (edge-crossing refinement, marching-triangles topology with
  exact root finding).
- Each boundary vertex is duplicated, one copy per adjacent patch, so normals are never averaged
  across the crease. The seam stays sharp in both Three.js and PyVista.
- Eutectic valleys and other univariant lines are exported as separate polylines and drawn as lines
  on top of the surfaces.

### R6. StructuredGrid is the wrong container for ternary data

Assumption: wrap the output in `pyvista.StructuredGrid`.

Reality: a StructuredGrid is a logically rectangular i x j x k lattice. A composition triangle is a
simplex. Forcing it into a rectangle either wastes half the nodes outside the triangle or distorts
the geometry.

Design:
- Composition surfaces (liquidus, G) as `pyvista.PolyData` triangles on a triangular lattice with
  (n + 1)(n + 2)/2 nodes.
- T-x1-x2 prisms as `pyvista.UnstructuredGrid` with wedge cells (VTK_WEDGE: triangle base x
  temperature layer).
- StructuredGrid (or ImageData) only for binary T-x planes, which are genuinely rectangular.

### R7. Sampled liquid points turn into bumps in 3D

Verified this week: the ternary liquid is represented by random samples of the quadruplet
fractions, and the liquidus at 1900 K moved between X_Fe = 0.337 and 0.451 across sampling seeds
(model-exact value 0.3696). In 2D that is a small shift of a boundary. In 3D it shows up as ridges
and dents that are sampling noise, not thermodynamics.

Design, prerequisites before any 3D surface is trusted:
- A fixed seed per request, so the same input always gives the same mesh.
- Local refinement of the liquid near each tangency, extending the existing `refine_liquid` step,
  until the boundary location changes by less than a set tolerance between refinements.
- A regression test comparing a 3D-derived boundary against the model-exact pycalphad value,
  like the olivine test added this week.

### R8. Coordinates: one transform, in one place

Design:
- The engine computes in mole fractions only.
- One C function maps barycentric to Cartesian at export: X = x2 + x3/2, Y = (sqrt(3)/2) x3.
  Python and JavaScript therefore receive identical geometry.
- Composition is also exported as a per-vertex attribute, so readouts never invert the transform.
- Temperature maps to Z by a user-set aspect factor (a 1000 K range against a unit triangle),
  stored with the mesh, not baked into the physics.

### R9. Short-range order is a color, not a shape

MQMQA quadruplet fractions and the SRO measure are per-composition scalars. Show them as a color
field on the liquid surface or a section, with a separate legend. Extra geometry adds clutter.

### R10. Keep the offline and air-gapped claims true

- Bundle the 3D library locally (Three.js is MIT, vtk.js is BSD; both compatible with AGPL-3.0).
  No CDN, so the page still makes no third-party requests and the CSP stays strict.
- WebGL can be disabled on locked-down machines. Fall back to the existing 2D diagrams with a clear
  message.

## 2. Architecture

```
            one engine instance per worker (engine is single-threaded)
+--------------------------- Web Worker / Python process ---------------------------+
|  loaded database (.dat/.tdb/.utdb/.xtdb)                                          |
|        |                                                                          |
|  sample phases per T (fixed seed) --> lower hull (mqmqa_lower_hull_2d)            |
|        |                                  |                                       |
|  refine liquid near tangencies <----------+   (repeat until boundary converges)   |
|        |                                                                          |
|  classify triangular lattice by assemblage (mqmqa_hull_assemblage_2d)             |
|        |                                                                          |
|  edge-crossing bisection -> exact boundary vertices, univariant polylines         |
|        |                                                                          |
|  liquidus bisection in T per lattice node (between bracketing sections)           |
|        |                                                                          |
|  export (double -> float32 only for positions and relative G):                    |
|    per-phase patches, duplicated seam vertices, polylines, attributes             |
+---------------------------------------|-------------------------------------------+
                                        | JS: fresh heap view + slice, postMessage
                                        |     with transferable ArrayBuffers
                                        | Python: cffi buffer -> numpy copy
                        +---------------+----------------+
                        v                                v
          Three.js BufferGeometry                 PyVista PolyData /
          (groups per phase, lines,               UnstructuredGrid (wedges),
           clipping planes, picking)              categorical phase scalars
                        |                                |
                        +----- exact on demand ----------+
                  picking or slicing calls the engine again at the exact
                  (x, T); the mesh is an overview, the numbers come from
                  the solver
```

Principle: the mesh is for seeing, the solver is for numbers. Any value a user reads (a temperature,
a composition, a phase amount) comes from a fresh engine call at that exact point, never from
interpolating the mesh.

## 3. User interaction

- **Isothermal plane:** dragging it shows a fast clipped preview. On release, the exact section at
  that temperature is computed and drawn in the plane. It must match the existing 2D isothermal
  section, which doubles as a consistency check.
- **Isopleth plane:** the same approach along a composition line.
- **Top view preset:** the liquidus surface seen from above is the liquidus projection. It must match
  the existing 2D projection.
- **Phase filter:** toggle each phase field's patch; the univariant lines stay visible.
- **Pick readout:** hover shows the composition and temperature under the cursor, and click runs the
  engine there for the assemblage, phase amounts and tie-line.
- **Isotherm contour lines** drawn on the liquidus surface.
- **Progressive refinement:** a coarse lattice first, refined while the page is idle. A visible
  status line shows the current refinement.
- **Clutter controls:** G surfaces show at most three phases at once, plus the hull.

## 4. C interface (proposed `src/vis3d.h`)

Every function returns 0 on success and a negative code on failure, with the message available
through the existing error path. The export list is generated from `MQMQA_API`, so the browser build
picks these up automatically.

```c
#ifndef VIS3D_H
#define VIS3D_H

#include <stdint.h>
#include "mqmqa.h"   /* MQMQA_API, mqmqa_db */

#ifdef __cplusplus
extern "C" {
#endif

/* One mesh result lives in one arena allocation, so a request is one malloc and one free and
 * repeated requests do not fragment the heap. All pointers below point into that arena. */
typedef struct {
    int32_t n_vert;        /* vertices, each belonging to exactly one patch */
    int32_t n_tri;         /* triangles */
    int32_t n_patch;       /* phase-field patches */
    int32_t n_line_pts;    /* points in all univariant polylines */
    int32_t n_line;        /* polylines */

    float    *pos;         /* n_vert * 3: Cartesian x, y, z (z = scaled T or relative G) */
    double   *comp;        /* n_vert * 3: mole fractions x1, x2, x3 (exact, for readouts) */
    double   *temp;        /* n_vert: temperature in K */
    float    *scalar;      /* n_vert: optional field (relative G, SRO measure), may be NULL */
    uint32_t *tri;         /* n_tri * 3: vertex indices, grouped by patch */
    int32_t  *patch_start; /* n_patch + 1: first triangle of each patch, last entry = n_tri */
    int32_t  *patch_phase; /* n_patch: phase-assemblage id of each patch (see labels) */
    float    *line_pos;    /* n_line_pts * 3 */
    int32_t  *line_start;  /* n_line + 1: first point of each polyline */

    int32_t  n_label;      /* assemblage labels, e.g. "LIQUID+OLIVINE" */
    char    (*label)[64];  /* n_label entries, NUL terminated (fits the engine's name limit) */

    void     *arena;       /* the single allocation; free with vis3d_free */
} VisMesh;

typedef struct {
    int32_t lattice_n;     /* triangular lattice subdivisions, (n+1)(n+2)/2 nodes */
    int32_t n_temps;       /* isothermal sections in the stack */
    double  t_lo, t_hi;    /* temperature window, K */
    double  x_tol;         /* boundary location tolerance in mole fraction */
    double  t_tol;         /* liquidus bisection tolerance, K */
    double  z_per_kelvin;  /* display scale for temperature */
    uint32_t seed;         /* fixed sampling seed: same input, same mesh */
    int32_t max_refine;    /* liquid refinement passes near tangencies */
} VisOptions;

/* Liquidus surface T_liq(x1, x2): one patch per primary-phase field, exact boundary vertices,
 * eutectic valleys and other univariant lines as polylines. */
MQMQA_API int vis3d_liquidus_surface(const mqmqa_db *db, const char *const *phases, int n_phases,
                                     const VisOptions *opt, VisMesh *out);

/* Phase regions of the exact isothermal section at T, as flat patches at z = T. */
MQMQA_API int vis3d_section(const mqmqa_db *db, const char *const *phases, int n_phases,
                            double T, const VisOptions *opt, VisMesh *out);

/* Gibbs-energy surfaces at T for the named phases, exported relative to the pure-end-member
 * plane (relative = 0) or to the hull (relative = 1), plus the hull facets as their own patch. */
MQMQA_API int vis3d_gibbs_surfaces(const mqmqa_db *db, const char *const *phases, int n_phases,
                                   double T, int relative, const VisOptions *opt, VisMesh *out);

/* Barycentric (x1, x2, x3) to Cartesian (X, Y), the one place this transform lives. */
MQMQA_API void vis3d_bary_to_xy(double x2, double x3, double *X, double *Y);

MQMQA_API void vis3d_free(VisMesh *m);

#ifdef __cplusplus
}
#endif

#endif
```

Field order and types are fixed, so JavaScript can read the struct at known offsets. The JS side
still goes through small accessor functions (`vis3d_mesh_n_vert`, `vis3d_mesh_pos`, ...) rather
than hard-coding offsets, so the struct can change without breaking the page.

## 5. Browser: worker and main thread (proposed)

Worker (`web/vis3d_worker.js`): owns the engine and does all solving.

```javascript
// One engine instance per worker: the engine is single-threaded by design.
importScripts('hephaestus.js');
let M = null, db = 0;

self.onmessage = async (ev) => {
  const { cmd, args } = ev.data;
  if (!M) M = await Hephaestus();
  if (cmd === 'load') {
    const n = M.lengthBytesUTF8(args.text) + 1, p = M._malloc(n);
    M.stringToUTF8(args.text, p, n);
    db = M._mqmqa_db_read_string(p);
    M._free(p);
    self.postMessage({ ok: db !== 0, error: db ? null : M.UTF8ToString(M._mqmqa_db_error()) });
    return;
  }
  if (cmd === 'liquidus') {
    const mesh = M._vis3d_mesh_new();
    const rc = M._vis3d_liquidus_surface_js(db, args.phaseList, args.latticeN, args.nTemps,
                                            args.tLo, args.tHi, args.seed, mesh);
    if (rc !== 0) {
      self.postMessage({ ok: false, error: M.UTF8ToString(M._mqmqa_db_error()) });
      M._vis3d_mesh_delete(mesh);
      return;
    }
    // Fresh views after the call: ALLOW_MEMORY_GROWTH may have replaced the heap buffer, so no
    // view created before the call is valid. slice() copies into worker-owned memory.
    const nv = M._vis3d_mesh_n_vert(mesh), nt = M._vis3d_mesh_n_tri(mesh);
    const np = M._vis3d_mesh_n_patch(mesh);
    const pos   = new Float32Array(M.HEAPF32.buffer, M._vis3d_mesh_pos(mesh), nv * 3).slice();
    const tri   = new Uint32Array(M.HEAPU32.buffer, M._vis3d_mesh_tri(mesh), nt * 3).slice();
    const start = new Int32Array(M.HEAP32.buffer, M._vis3d_mesh_patch_start(mesh), np + 1).slice();
    const phase = new Int32Array(M.HEAP32.buffer, M._vis3d_mesh_patch_phase(mesh), np).slice();
    const labels = [];
    for (let k = 0; k < M._vis3d_mesh_n_label(mesh); k++)
      labels.push(M.UTF8ToString(M._vis3d_mesh_label(mesh, k)));
    M._vis3d_mesh_delete(mesh);   // one arena, one free
    // Transfer, do not copy: ownership of the buffers moves to the main thread.
    self.postMessage({ ok: true, pos, tri, start, phase, labels },
                     [pos.buffer, tri.buffer, start.buffer, phase.buffer]);
  }
};
```

Main thread: builds the geometry. Three.js is bundled locally, with no CDN.

```javascript
import * as THREE from './vendor/three.module.js';

const worker = new Worker('./vis3d_worker.js');

function meshFromResult(r, palette) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(r.pos, 3));
  g.setIndex(new THREE.BufferAttribute(r.tri, 1));
  // One draw group per phase-field patch. Seam vertices are duplicated per patch in C, so
  // computeVertexNormals never averages across a phase boundary and the crease stays sharp.
  const materials = [];
  for (let p = 0; p < r.phase.length; p++) {
    const first = r.start[p] * 3, count = (r.start[p + 1] - r.start[p]) * 3;
    g.addGroup(first, count, p);
    materials.push(new THREE.MeshStandardMaterial({
      color: palette(r.labels[r.phase[p]]), side: THREE.DoubleSide,
      clippingPlanes: [isothermPlane], transparent: true, opacity: 0.92 }));
  }
  g.computeVertexNormals();
  return new THREE.Mesh(g, materials);
}

const isothermPlane = new THREE.Plane(new THREE.Vector3(0, 0, -1), 0);  // preview while dragging

function requestLiquidus(opts) {
  return new Promise((resolve, reject) => {
    worker.onmessage = (ev) => ev.data.ok ? resolve(ev.data) : reject(new Error(ev.data.error));
    worker.postMessage({ cmd: 'liquidus', args: opts });
  });
}
// On plane release: ask the worker for the exact section at that T (vis3d_section) and draw it.
// On click: ask the worker for the exact assemblage at the picked (x, T); never read numbers off
// the mesh.
```

The `_js` wrapper and the `vis3d_mesh_*` accessors are thin C functions that take plain scalars
and a handle, so the page never lays out a C struct by hand.

## 6. Python and PyVista (proposed)

```python
"""3D views of Hephaestus results. The mesh is for seeing; numbers come from the engine."""
import numpy as np
import pyvista as pv

from mqmqa import vis3d   # cffi binding over src/vis3d.h, copies arena arrays to numpy


def liquidus_polydata(db, phases, lattice_n=80, n_temps=40, t_lo=1400.0, t_hi=2400.0, seed=0):
    m = vis3d.liquidus_surface(db, phases, lattice_n=lattice_n, n_temps=n_temps,
                               t_lo=t_lo, t_hi=t_hi, seed=seed)
    # m.pos (nv, 3) float32, m.tri (nt, 3) uint32, m.patch_start (np+1,), m.patch_phase (np,)
    faces = np.hstack([np.full((len(m.tri), 1), 3, dtype=np.int64),
                       m.tri.astype(np.int64)]).ravel()
    surf = pv.PolyData(m.pos.astype(np.float64), faces)
    # Categorical phase-field id per triangle, so coloring never interpolates across a seam.
    field = np.empty(len(m.tri), dtype=np.int32)
    for p in range(len(m.patch_phase)):
        field[m.patch_start[p]:m.patch_start[p + 1]] = m.patch_phase[p]
    surf.cell_data["phase_field"] = field
    surf.point_data["T_K"] = m.temp
    surf.field_data["labels"] = np.array(m.labels)
    lines = pv.PolyData(m.line_pos.astype(np.float64))
    lines.lines = np.hstack([[e - s, *range(s, e)]
                             for s, e in zip(m.line_start[:-1], m.line_start[1:])])
    return surf, lines


def prism_unstructured(section_meshes, z_per_kelvin):
    """T-x1-x2 prism from a stack of exact sections: wedge cells between adjacent levels.
    Assumes each level is on the same triangular lattice (same topology, different labels)."""
    base = section_meshes[0]
    n_node = len(base.comp)
    pts = np.vstack([np.column_stack([s.pos[:, :2], np.full(n_node, s.T * z_per_kelvin)])
                     for s in section_meshes])
    cells, labels = [], []
    for k in range(len(section_meshes) - 1):
        lo, hi = k * n_node, (k + 1) * n_node
        for a, b, c in base.tri:
            cells.append([6, lo + a, lo + b, lo + c, hi + a, hi + b, hi + c])
        labels.extend(section_meshes[k].tri_phase)
    grid = pv.UnstructuredGrid(np.array(cells, dtype=np.int64).ravel(),
                               np.full(len(cells), pv.CellType.WEDGE, dtype=np.uint8), pts)
    grid.cell_data["phase_field"] = np.array(labels, dtype=np.int32)
    return grid


def show_liquidus(db, phases, **kw):
    surf, lines = liquidus_polydata(db, phases, **kw)
    pl = pv.Plotter()
    pl.add_mesh(surf, scalars="phase_field", categories=True, cmap="tab10",
                show_edges=False, smooth_shading=False)   # flat: never smear across fields
    pl.add_mesh(lines, color="black", line_width=3)      # eutectic valleys
    pl.add_mesh_clip_plane(surf, normal="z")              # isothermal preview
    pl.show_grid(xtitle="", ytitle="", ztitle="T (scaled)")
    pl.show()
```

The cffi binding copies each arena array into numpy (`np.frombuffer(...).copy()`) before
`vis3d_free`. Nothing in Python keeps a pointer into engine memory.

## 7. Implementation plan

1. **Deterministic, refined ternary liquid (R7).** Fixed seed, tangency refinement, and a
   regression test against the model-exact pycalphad boundary. Nothing 3D is trusted before this.
2. **`vis3d_section`.** Exact regions at one T with duplicated seam vertices, tested against the
   existing 2D isothermal section.
3. **`vis3d_liquidus_surface`.** Lattice classification, edge-crossing bisection, liquidus bisection
   in T, univariant polylines. Tested so that the top view reproduces the existing liquidus
   projection, and boundary locations converge as the lattice is refined.
4. **`vis3d_gibbs_surfaces`.** Relative G in double (R4). Tested so that the hull matches
   `mqmqa_lower_hull_2d` and tangent points match the section.
5. **Python binding and PyVista helpers.** Tests on mesh topology, and a check that no cell carries
   two phase labels.
6. **Browser.** Worker plus main thread, locally bundled Three.js, progressive refinement, pick
   readout from the engine, WebGL fallback. Measured and verified in the browser.
7. **Documentation.** Every view states which calculation produced it and at what resolution.

Acceptance for every step: the full suite passes; shipped databases are bit-identical (the 3D module
adds functions and changes no existing path); and every 3D view has a 2D counterpart it must agree
with.

## 8. Steps 1 and 2 as built

What testing found, and what changed from the proposal because of it.

- **The liquid needs its own minimizer.** The single-phase solver behind
  `mqmqa_equilibrate_db` (Nelder-Mead from one start) can stop with quadruplet fractions pinned at
  zero, 1 to 10 kJ/mol above the minimum (FeO-rich, low-silica liquid at 2000 K). A hull fed those
  values invents miscibility gaps. `vis3d.c` minimizes G per mole of cations itself: a start at the
  random-mixing distribution fitted exactly to the composition, then Levenberg-Marquardt steps in
  the constraint null space, scaled by the current fractions so no fraction reaches zero. The
  reference energy is linear in the fractions and is handled exactly; only mixing plus excess is
  differenced. Over 900 random FeO-MgO-SiO2 compositions from 1300 to 2400 K it is never more than
  6.5e-4 J above an SLSQP multi-start, and it matches pycalphad's liquid-only minimum to 1e-3 J.
- **The hull needs exact orientation tests.** Refinement puts many samples on one line in a nearly
  flat region; `mqmqa_lower_hull_2d` then loops without end. `vis3d_lower_hull` rounds points to an
  integer grid (2^-24 in composition, 2^-38 of the Gibbs range) and decides every orientation in
  128-bit integers.
- **Refinement and convergence.** Liquid samples start on a 1/40 lattice (the seed only moves the
  interior nodes). Around every hull vertex where two phases, or the two sides of a miscibility
  gap, meet, samples are added in all directions until the step is 1/160, then along the tie-line
  directions, halving the step each pass. The pass stops when the step is below `x_tol` and the
  tie-lines through 2145 fixed probe compositions move less than `x_tol` between passes; where
  they still move, the facet's same-phase edges are split. No convergence within `max_refine`
  passes is an error, never a coarser answer.
- **Miscibility gaps by energy, not distance.** Two liquid samples joined by a hull edge are one
  liquid or the two sides of a gap according to the liquid at the edge's midpoint: above the chord
  it is unstable, so the edge is a two-liquid tie-line. Edges shorter than 0.01 are taken as one
  liquid, so the last 0.01 of a gap before its critical point is not resolved.
- **The section is an overlay, not a bisection.** The phase regions are unions of hull facets, so
  their boundaries are known exactly. A lattice triangle no boundary crosses is kept whole; one a
  boundary crosses is clipped against the facets it overlaps. Bisection along lattice edges, as
  proposed in R5, missed fields narrower than the lattice (thin three-phase triangles, 9% of
  triangles mislabelled in CaO-Al2O3-SiO2 at 1673 K). Fields of zero width (a compound's point, a
  tie-line between two compounds) get no area.
- **Browser build.** `vis3d_*` joins the exported list in `scripts/build_wasm.sh`. The build does not
  export `HEAPF32`/`HEAPU32`; the worker of section 5 needs them added to
  `EXPORTED_RUNTIME_METHODS` (step 6).

Validation (`tests/test_vis3d.py`): the 1900 K olivine tie-line of R7 is within 1e-3 of
pycalphad (liquidus 0.3696, solidus 0.0803 on the join) for five seeds; seven further tie-lines
(olivine, periclase, two liquids, a three-phase triangle, orthopyroxene) from 1700 to 2000 K agree
within 1e-3; the section's fields equal the existing 2D lookup on the same candidates at every
point of a 50-step grid; field areas converge as the lattice goes from 30 to 120.
