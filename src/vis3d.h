#ifndef VIS3D_H
#define VIS3D_H

/* 3D phase-space views (docs/VISUALIZATION_3D.md). The mesh is for seeing; every
 * number a user reads comes from a fresh engine call, never from the mesh.
 *
 * Composition is the cation fractions (x1, x2, x3) of the liquid's three cations, in
 * the liquid's own cation order; Gibbs energies are per mole of cations, so every phase
 * sits on one lower hull (the basis of src/equilibrium.c). Single-anion systems only.
 *
 * Every function returns 0 on success and a negative code on failure, with the reason
 * in mqmqa_db_error(). Nothing approximate is returned on failure: a boundary that does
 * not converge within the requested passes is an error, not a coarser answer.
 */
#include <stdint.h>

#include "mqmqa.h"
#include "cs_dat.h"

#ifdef __cplusplus
extern "C" {
#endif

/* One mesh result lives in one arena allocation, so a request is one malloc and one
 * free and repeated requests do not fragment the heap. Every pointer below points
 * into that arena. */
typedef struct {
    int32_t n_vert;        /* vertices, each belonging to exactly one patch */
    int32_t n_tri;         /* triangles */
    int32_t n_patch;       /* phase-field patches */
    int32_t n_line_pts;    /* points in all polylines */
    int32_t n_line;        /* polylines */

    float    *pos;         /* n_vert * 3: Cartesian X, Y, z (z = T * z_per_kelvin) */
    double   *comp;        /* n_vert * 3: cation fractions x1, x2, x3 */
    double   *temp;        /* n_vert: temperature in K */
    float    *scalar;      /* n_vert: optional field, NULL when unused */
    uint32_t *tri;         /* n_tri * 3: vertex indices, grouped by patch */
    int32_t  *patch_start; /* n_patch + 1: first triangle of each patch, last = n_tri */
    int32_t  *patch_phase; /* n_patch: assemblage label index of each patch */
    float    *line_pos;    /* n_line_pts * 3 */
    int32_t  *line_start;  /* n_line + 1: first point of each polyline */

    int32_t  n_label;      /* assemblage labels, e.g. "LIQUID+OLIVINE" */
    char    (*label)[64];

    void     *arena;       /* the single allocation; free with vis3d_free */
} VisMesh;

typedef struct {
    int32_t  lattice_n;    /* triangular lattice subdivisions, (n+1)(n+2)/2 nodes */
    int32_t  n_temps;      /* isothermal sections in a stack (later steps) */
    double   t_lo, t_hi;   /* temperature window, K (later steps) */
    double   x_tol;        /* boundary location tolerance, cation mole fraction */
    double   t_tol;        /* liquidus bisection tolerance, K (later steps) */
    double   z_per_kelvin; /* display scale for temperature */
    uint32_t seed;         /* placement of the initial liquid samples; 0 = plain lattice */
    int32_t  max_refine;   /* cap on refinement passes near tangencies */
    double   z_per_joule;  /* display scale for a Gibbs energy (J per mole of cations) */
} VisOptions;

/* Defaults: lattice_n 60, x_tol 1e-3, z_per_kelvin 1e-3, seed 0, max_refine 16,
 * z_per_joule 1e-5. */
MQMQA_API void vis3d_default_options(VisOptions *opt);

/* Phase regions of the isothermal section at T, as flat patches at z = T * z_per_kelvin.
 * `phases` names the candidate phases (the MQMQA liquid, CEF solutions with one binary
 * mixing sublattice, stoichiometric compounds); NULL takes the first single-anion,
 * three-cation liquid and every other phase in the database. One patch per connected
 * phase field. The regions are the refined hull's own: a lattice triangle no phase
 * boundary crosses is kept whole, one a boundary crosses is clipped against the hull
 * facets, so boundary vertices are exact intersections rather than bisection results.
 * Seam vertices are duplicated per patch; boundaries come as two-point polylines.
 * Fields of zero width (a compound's point, a tie-line between two compounds, a line
 * solution's own segment) have no area and so no patch. */
MQMQA_API int vis3d_section(const mqmqa_db *db, const char *const *phases, int n_phases,
                            double T, const VisOptions *opt, VisMesh *out);

/* Liquidus surface T_liq(x1, x2, x3) over the triangle, z = T_liq * z_per_kelvin: one patch
 * per primary-phase field, labelled with the solid that crystallizes first, and the field
 * boundaries (the univariant valleys) as two-point polylines, their vertices duplicated
 * per patch. The liquidus of a composition is where the first solid's driving force
 * against the stable liquid (the single liquid, or both liquids where it has split)
 * reaches zero, found to t_tol; field boundaries are located to x_tol along lattice
 * edges. Reads lattice_n, n_temps (>= 3 temperature levels spanning t_lo..t_hi), t_lo,
 * t_hi, t_tol, x_tol, z_per_kelvin, and max_refine for the split-liquid hulls. A liquidus
 * outside [t_lo, t_hi] anywhere is an error (-7) naming the composition. */
MQMQA_API int vis3d_liquidus_surface(const mqmqa_db *db, const char *const *phases,
                                     int n_phases, const VisOptions *opt, VisMesh *out);
/* The liquidus temperature and primary phase (NUL-terminated, primary_len bytes) of one
 * bulk composition, as the surface computes it. */
MQMQA_API int vis3d_liquidus_point(const mqmqa_db *db, const char *const *phases, int n_phases,
                                   const VisOptions *opt, double x2, double x3, double *T,
                                   char *primary, int primary_len);

/* Gibbs energies at T per mole of cations, relative to the plane through the pure
 * components' equilibrium energies (relative = 0) or to the equilibrium itself (relative
 * = 1, so each value is the height above equilibrium; where the equilibrium is the single
 * liquid, that reference is the liquid's own exact energy). The liquid is a surface on the
 * lattice (patch labelled with its name), each CEF solution a curve along its line and
 * each compound a zero-length segment (polylines, in phase order), and the refined hull a
 * patch labelled "HULL". `scalar` holds the relative energy, z = scalar * z_per_joule,
 * `temp` is T. Computed in double; only the exported floats are rounded. */
MQMQA_API int vis3d_gibbs_surfaces(const mqmqa_db *db, const char *const *phases, int n_phases,
                                   double T, int relative, const VisOptions *opt, VisMesh *out);

/* Barycentric (x1, x2, x3) to Cartesian (X, Y): x1 at (0, 0), x2 at (1, 0), x3 at the
 * apex. The one place this transform lives. */
MQMQA_API void vis3d_bary_to_xy(double x2, double x3, double *X, double *Y);

MQMQA_API void vis3d_free(VisMesh *m);

/* Minimum Gibbs energy per mole of cations of the MQMQA liquid `phase` (three cations,
 * one anion) at T and cation fractions (x1, x2, x3), over its quadruplet fractions, which
 * go to X_out (may be NULL; mqmqa_num_quadruplets(3, 1) entries). NaN on failure. The
 * minimizer the hull samples the liquid with. */
MQMQA_API double vis3d_liquid_gibbs(const mqmqa_db *db, int phase, double T, double x2,
                                    double x3, double *X_out);

/* ---- The refined equilibrium hull at one temperature ----
 * The deterministic, tangency-refined candidate set that vis3d_section classifies,
 * exposed so the tie-line endpoints can be checked against an independent solver. */
typedef struct vis3d_hull vis3d_hull;

MQMQA_API vis3d_hull *vis3d_hull_build(const mqmqa_db *db, const char *const *phases,
                                       int n_phases, double T, const VisOptions *opt);
MQMQA_API void vis3d_hull_free(vis3d_hull *h);
/* Refinement passes run, and the largest tie-line endpoint shift (cation fraction) at
 * the fixed probe compositions in the last pass. */
MQMQA_API int vis3d_hull_passes(const vis3d_hull *h);
MQMQA_API double vis3d_hull_last_shift(const vis3d_hull *h);
MQMQA_API int vis3d_hull_num_points(const vis3d_hull *h);
/* Largest element-fraction error the single-phase liquid solver left in any sample. */
MQMQA_API double vis3d_hull_max_comp_err(const vis3d_hull *h);
/* Sample i: its cation fractions, Gibbs energy per mole of cations, and the liquid
 * solver's element-fraction error (0 for other phases); returns its phase index. The
 * lower-hull facets are index triples into the samples. For checks and diagnostics. */
MQMQA_API int vis3d_hull_point(const vis3d_hull *h, int i, double *x2, double *x3,
                               double *g, double *comp_err);
MQMQA_API int vis3d_hull_num_facets(const vis3d_hull *h);
MQMQA_API const int *vis3d_hull_facets(const vis3d_hull *h);
/* Phases taking part, in the order the assemblage query reports them. */
MQMQA_API int vis3d_hull_num_phases(const vis3d_hull *h);
MQMQA_API const char *vis3d_hull_phase_name(const vis3d_hull *h, int k);
/* The isothermal section of an already built hull, as vis3d_section computes it (only
 * lattice_n and z_per_kelvin are read from opt). */
MQMQA_API int vis3d_hull_section(const vis3d_hull *h, const VisOptions *opt, VisMesh *out);
/* Lower convex hull of n points (x, y, g) with every orientation decided exactly (points
 * rounded to a grid of 2^-24 in x and y and about 2^-38 of the g range); same layout and
 * return as mqmqa_lower_hull_2d, which can loop without end on degenerate input. */
MQMQA_API int vis3d_lower_hull(const double *pts, int n, int *facets, int max_facets);
/* Gibbs energy of the equilibrium (the hull) per mole of cations at bulk (x2, x3); NaN
 * outside the simplex. */
MQMQA_API double vis3d_hull_gibbs(const vis3d_hull *h, double x2, double x3);
/* Stable assemblage at bulk cation fractions (x2, x3): up to max_out coexisting phases,
 * each with its phase index (into vis3d_hull_phase_name), amount (cation fraction of the
 * whole) and cation composition (x2, x3). A solution phase on both ends of a miscibility
 * gap is reported twice. Returns the number of phases, 0 outside the simplex, <0 on error. */
MQMQA_API int vis3d_hull_assemblage(const vis3d_hull *h, double x2, double x3,
                                    int *phase_out, double *amt_out, double *comp_out,
                                    int max_out);

/* ---- For the browser: a heap-allocated mesh handle and scalar accessors, so the
 * page never lays out a C struct by hand. vis3d_section_js takes the phase names as
 * one comma-separated string (empty for all). */
MQMQA_API VisMesh *vis3d_mesh_new(void);
MQMQA_API void vis3d_mesh_delete(VisMesh *m);
MQMQA_API int vis3d_mesh_n_vert(const VisMesh *m);
MQMQA_API int vis3d_mesh_n_tri(const VisMesh *m);
MQMQA_API int vis3d_mesh_n_patch(const VisMesh *m);
MQMQA_API int vis3d_mesh_n_line(const VisMesh *m);
MQMQA_API int vis3d_mesh_n_line_pts(const VisMesh *m);
MQMQA_API int vis3d_mesh_n_label(const VisMesh *m);
MQMQA_API const float *vis3d_mesh_scalar(const VisMesh *m);
MQMQA_API const float *vis3d_mesh_pos(const VisMesh *m);
MQMQA_API const double *vis3d_mesh_comp(const VisMesh *m);
MQMQA_API const double *vis3d_mesh_temp(const VisMesh *m);
MQMQA_API const uint32_t *vis3d_mesh_tri(const VisMesh *m);
MQMQA_API const int32_t *vis3d_mesh_patch_start(const VisMesh *m);
MQMQA_API const int32_t *vis3d_mesh_patch_phase(const VisMesh *m);
MQMQA_API const float *vis3d_mesh_line_pos(const VisMesh *m);
MQMQA_API const int32_t *vis3d_mesh_line_start(const VisMesh *m);
MQMQA_API const char *vis3d_mesh_label(const VisMesh *m, int k);
MQMQA_API int vis3d_liquidus_surface_js(const mqmqa_db *db, const char *phase_list,
                                        int lattice_n, int n_temps, double t_lo, double t_hi,
                                        double x_tol, double t_tol, double z_per_kelvin,
                                        VisMesh *out);
MQMQA_API int vis3d_gibbs_surfaces_js(const mqmqa_db *db, const char *phase_list, double T,
                                      int relative, int lattice_n, double x_tol,
                                      double z_per_joule, VisMesh *out);
MQMQA_API vis3d_hull *vis3d_hull_build_js(const mqmqa_db *db, const char *phase_list, double T,
                                          double x_tol, uint32_t seed, int max_refine);
MQMQA_API int vis3d_liquidus_point_js(const mqmqa_db *db, const char *phase_list, double x2,
                                      double x3, int n_temps, double t_lo, double t_hi,
                                      double x_tol, double t_tol, double *T, char *primary,
                                      int primary_len);
MQMQA_API int vis3d_section_js(const mqmqa_db *db, const char *phase_list, double T,
                               int lattice_n, double x_tol, uint32_t seed, int max_refine,
                               double z_per_kelvin, VisMesh *out);

#ifdef __cplusplus
}
#endif

#endif
