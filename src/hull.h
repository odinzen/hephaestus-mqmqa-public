#ifndef MQMQA_HULL_H
#define MQMQA_HULL_H

/* Lower convex hull of candidate (composition, Gibbs) points, the geometric core of
 * the multiphase equilibrium: the facet of the lower hull under a bulk composition
 * gives the coexisting phases and, by barycentric weights, their amounts. Ported
 * from the browser hull (validated against scipy to machine precision) so the C core
 * maps equilibria without a host layer. See docs/EQUILIBRIUM_ENGINE.md.
 */
#include "mqmqa.h"

#ifdef __cplusplus
extern "C" {
#endif

/* 1-D lower hull (binary join). pts is n*2 doubles laid out (x, g). Writes the
 * lower-hull vertex indices, left to right, to verts (capacity max_verts); returns
 * the count, or -1 on overflow/failure. Consecutive vertices are the tie-line edges. */
MQMQA_API int mqmqa_lower_hull_1d(const double *pts, int n, int *verts, int max_verts);

/* 2-D lower hull (ternary). pts is n*3 doubles laid out (x, y, g). Writes lower-hull
 * triangular facets as index triples to facets (capacity max_facets triples, i.e.
 * 3*max_facets ints); returns the facet count, or -1 on overflow/failure. */
MQMQA_API int mqmqa_lower_hull_2d(const double *pts, int n, int *facets, int max_facets);

/* Assemblage at a bulk composition. Given pts (n*3: x,y,g), the lower facets from
 * mqmqa_lower_hull_2d (nf index triples), and a query point (qx,qy): finds the facet
 * whose triangle in (x,y) contains the query, writes its three vertex indices to
 * tri_out[3] and their barycentric weights (the phase amounts by the lever rule) to
 * w_out[3], and the interpolated hull Gibbs energy to *g_out. Returns 1 if a facet
 * contains the query, 0 otherwise. */
MQMQA_API int mqmqa_hull_assemblage_2d(const double *pts, int n,
                                       const int *facets, int nf,
                                       double qx, double qy,
                                       int *tri_out, double *w_out, double *g_out);

#ifdef __cplusplus
}
#endif

#endif
