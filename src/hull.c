/* Lower convex hull for the multiphase equilibrium (see hull.h). The 2-D case is an
 * incremental (Quickhull) 3-D convex hull with the lower faces extracted; ported
 * faithfully from the browser implementation validated against scipy. */
#include "hull.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

/* ---- 1-D: monotone-chain lower hull over (x, g) ---- */

typedef struct { double x, g; int idx; } P1;

static int cmp_p1(const void *a, const void *b)
{
    const P1 *p = a, *q = b;
    if (p->x < q->x) return -1;
    if (p->x > q->x) return 1;
    return p->g < q->g ? -1 : (p->g > q->g ? 1 : 0);
}

int mqmqa_lower_hull_1d(const double *pts, int n, int *verts, int max_verts)
{
    if (n < 1) return -1;
    P1 *p = malloc((size_t)n * sizeof(P1));
    if (!p) return -1;
    for (int i = 0; i < n; ++i) { p[i].x = pts[2*i]; p[i].g = pts[2*i+1]; p[i].idx = i; }
    qsort(p, (size_t)n, sizeof(P1), cmp_p1);

    int *h = malloc((size_t)n * sizeof(int));
    if (!h) { free(p); return -1; }
    int m = 0;
    for (int i = 0; i < n; ++i) {
        while (m >= 2) {
            double x1 = p[h[m-2]].x, g1 = p[h[m-2]].g;
            double x2 = p[h[m-1]].x, g2 = p[h[m-1]].g;
            if ((x2 - x1) * (p[i].g - g1) - (g2 - g1) * (p[i].x - x1) <= 0.0) m--;
            else break;
        }
        h[m++] = i;
    }
    int rc = m;
    if (m > max_verts) rc = -1;
    else for (int i = 0; i < m; ++i) verts[i] = p[h[i]].idx;
    free(h); free(p);
    return rc;
}

/* ---- 2-D lower hull via incremental 3-D convex hull ---- */

typedef struct { double v[3]; } V3;
static V3 sub3(V3 a, V3 b){ V3 r={{a.v[0]-b.v[0], a.v[1]-b.v[1], a.v[2]-b.v[2]}}; return r; }
static V3 cross3(V3 a, V3 b){
    V3 r={{a.v[1]*b.v[2]-a.v[2]*b.v[1], a.v[2]*b.v[0]-a.v[0]*b.v[2], a.v[0]*b.v[1]-a.v[1]*b.v[0]}};
    return r;
}
static double dot3(V3 a, V3 b){ return a.v[0]*b.v[0]+a.v[1]*b.v[1]+a.v[2]*b.v[2]; }
static double len3(V3 a){ return sqrt(dot3(a,a)); }

typedef struct {
    int v[3];
    V3 nrm;
    double off;
    int *outside;   /* candidate points in front of this face */
    int nout, cap;
    int dead;
} Face;

typedef struct { Face *F; int nf, fcap; V3 IN; const V3 *P; } Hull;

static void face_push_out(Face *f, int p)
{
    if (f->nout == f->cap) {
        f->cap = f->cap ? f->cap * 2 : 8;
        f->outside = realloc(f->outside, (size_t)f->cap * sizeof(int));
    }
    f->outside[f->nout++] = p;
}

/* make a face (a,b,c) oriented so its normal points away from the interior h->IN;
 * appends it to h->F and returns its index */
static int add_face(Hull *h, int a, int b, int c)
{
    V3 nr = cross3(sub3(h->P[b], h->P[a]), sub3(h->P[c], h->P[a]));
    double of = dot3(nr, h->P[a]);
    if (dot3(nr, h->IN) - of > 0) {
        nr.v[0]=-nr.v[0]; nr.v[1]=-nr.v[1]; nr.v[2]=-nr.v[2]; of=-of;
        int t=b; b=c; c=t;
    }
    if (h->nf == h->fcap) {
        int nc = h->fcap * 2;
        h->F = realloc(h->F, (size_t)nc * sizeof(Face));
        memset(h->F + h->fcap, 0, (size_t)(nc - h->fcap) * sizeof(Face));
        h->fcap = nc;
    }
    Face *f = &h->F[h->nf];
    f->v[0]=a; f->v[1]=b; f->v[2]=c; f->nrm=nr; f->off=of;
    f->outside=NULL; f->nout=0; f->cap=0; f->dead=0;
    return h->nf++;
}

int mqmqa_lower_hull_2d(const double *pts, int n, int *facets, int max_facets)
{
    const double eps = 1e-9;
    if (n < 3) return -1;
    V3 *P = malloc((size_t)n * sizeof(V3));
    if (!P) return -1;
    for (int i = 0; i < n; ++i) { P[i].v[0]=pts[3*i]; P[i].v[1]=pts[3*i+1]; P[i].v[2]=pts[3*i+2]; }

    /* initial tetrahedron: four affinely independent points */
    int i0 = 0, i1 = -1, i2 = -1, i3 = -1;
    for (int i = 1; i < n; ++i) if (len3(sub3(P[i], P[i0])) > eps) { i1 = i; break; }
    if (i1 < 0) { free(P); return -1; }
    double bA = eps;
    for (int i = 0; i < n; ++i) {
        double a = len3(cross3(sub3(P[i], P[i0]), sub3(P[i], P[i1])));
        if (a > bA) { bA = a; i2 = i; }
    }
    if (i2 < 0) { free(P); return -1; }
    V3 n012 = cross3(sub3(P[i1], P[i0]), sub3(P[i2], P[i0]));
    double bV = eps;
    for (int i = 0; i < n; ++i) {
        double v = fabs(dot3(n012, sub3(P[i], P[i0])));
        if (v > bV) { bV = v; i3 = i; }
    }
    if (i3 < 0) { free(P); return -1; }   /* all coplanar: no volume, no lower facets here */

    Hull hull;
    hull.fcap = 16; hull.nf = 0; hull.P = P;
    hull.F = calloc((size_t)hull.fcap, sizeof(Face));
    for (int k = 0; k < 3; ++k) hull.IN.v[k] = (P[i0].v[k]+P[i1].v[k]+P[i2].v[k]+P[i3].v[k]) / 4.0;
    Hull *H = &hull;

    add_face(H,i0,i1,i2); add_face(H,i0,i1,i3); add_face(H,i0,i2,i3); add_face(H,i1,i2,i3);

    char *assigned = calloc((size_t)n, 1);
    assigned[i0]=assigned[i1]=assigned[i2]=assigned[i3]=1;
    for (int p = 0; p < n; ++p) {
        if (assigned[p]) continue;
        for (int k = 0; k < H->nf; ++k) {
            double d = dot3(H->F[k].nrm, P[p]) - H->F[k].off;
            if (d > eps * len3(H->F[k].nrm)) { face_push_out(&H->F[k], p); break; }
        }
    }

    long guard = 0;
    while (1) {
        if (++guard > 4000000) break;
        int fi = -1;
        for (int k = 0; k < H->nf; ++k) if (!H->F[k].dead && H->F[k].nout) { fi = k; break; }
        if (fi < 0) break;

        /* farthest outside point of this face */
        int far = H->F[fi].outside[0];
        double fd = (dot3(H->F[fi].nrm, P[far]) - H->F[fi].off) / len3(H->F[fi].nrm);
        for (int t = 0; t < H->F[fi].nout; ++t) {
            int p = H->F[fi].outside[t];
            double d = (dot3(H->F[fi].nrm, P[p]) - H->F[fi].off) / len3(H->F[fi].nrm);
            if (d > fd) { fd = d; far = p; }
        }

        /* visible faces from far; gather their edges and orphaned outside points */
        int *vis = malloc((size_t)H->nf * sizeof(int)); int nvis = 0;
        for (int k = 0; k < H->nf; ++k) if (!H->F[k].dead) {
            double d = dot3(H->F[k].nrm, P[far]) - H->F[k].off;
            if (d > eps * len3(H->F[k].nrm)) vis[nvis++] = k;
        }
        int *edges = malloc((size_t)nvis * 3 * 2 * sizeof(int)); int ne = 0;
        for (int t = 0; t < nvis; ++t) {
            int *v = H->F[vis[t]].v;
            int pr[3][2] = {{v[0],v[1]},{v[1],v[2]},{v[2],v[0]}};
            for (int e = 0; e < 3; ++e) { edges[2*ne]=pr[e][0]; edges[2*ne+1]=pr[e][1]; ne++; }
        }
        int *orph = malloc(sizeof(int)); int norph = 0, ocap = 1;
        for (int t = 0; t < nvis; ++t)
            for (int s = 0; s < H->F[vis[t]].nout; ++s) {
                int p = H->F[vis[t]].outside[s];
                if (p == far) continue;
                if (norph == ocap) { ocap*=2; orph = realloc(orph,(size_t)ocap*sizeof(int)); }
                orph[norph++] = p;
            }
        for (int t = 0; t < nvis; ++t) {
            free(H->F[vis[t]].outside); H->F[vis[t]].outside=NULL;
            H->F[vis[t]].nout=0; H->F[vis[t]].cap=0; H->F[vis[t]].dead=1;
        }

        /* new faces from each horizon edge (one that has no reverse) to far */
        int newstart = H->nf;
        for (int e = 0; e < ne; ++e) {
            int a = edges[2*e], b = edges[2*e+1];
            int shared = 0;
            for (int g = 0; g < ne; ++g) if (edges[2*g]==b && edges[2*g+1]==a) { shared = 1; break; }
            if (shared) continue;
            add_face(H, a, b, far);
        }
        assigned[far] = 1;
        for (int t = 0; t < norph; ++t) {
            int p = orph[t];
            if (assigned[p]) continue;
            for (int k = newstart; k < H->nf; ++k) {
                if (H->F[k].dead) continue;
                double d = dot3(H->F[k].nrm, P[p]) - H->F[k].off;
                if (d > eps * len3(H->F[k].nrm)) { face_push_out(&H->F[k], p); break; }
            }
        }
        free(vis); free(edges); free(orph);
    }

    /* collect lower faces: outward normal points down (n_z < 0) */
    int nlow = 0, rc;
    for (int k = 0; k < H->nf; ++k)
        if (!H->F[k].dead && H->F[k].nrm.v[2] < -eps * len3(H->F[k].nrm)) nlow++;
    if (nlow > max_facets) rc = -1;
    else {
        int w = 0;
        for (int k = 0; k < H->nf; ++k)
            if (!H->F[k].dead && H->F[k].nrm.v[2] < -eps * len3(H->F[k].nrm)) {
                facets[3*w]=H->F[k].v[0]; facets[3*w+1]=H->F[k].v[1]; facets[3*w+2]=H->F[k].v[2]; w++;
            }
        rc = nlow;
    }

    for (int k = 0; k < H->nf; ++k) free(H->F[k].outside);
    free(H->F); free(assigned); free(P);
    return rc;
}

/* ---- assemblage query: the facet under a bulk composition (see hull.h) ---- */
int mqmqa_hull_assemblage_2d(const double *pts, int n, const int *facets, int nf,
                             double qx, double qy, int *tri_out, double *w_out,
                             double *g_out)
{
    (void)n;
    const double tol = 1e-9;
    for (int f = 0; f < nf; ++f) {
        int a = facets[3*f], b = facets[3*f+1], c = facets[3*f+2];
        double ax = pts[3*a], ay = pts[3*a+1];
        double bx = pts[3*b], by = pts[3*b+1];
        double cx = pts[3*c], cy = pts[3*c+1];
        double det = (ax - cx) * (by - cy) - (bx - cx) * (ay - cy);
        if (fabs(det) < 1e-15) continue;
        double l1 = ((by - cy) * (qx - cx) + (cx - bx) * (qy - cy)) / det;
        double l2 = ((cy - ay) * (qx - cx) + (ax - cx) * (qy - cy)) / det;
        double l3 = 1.0 - l1 - l2;
        if (l1 >= -tol && l2 >= -tol && l3 >= -tol) {
            tri_out[0]=a; tri_out[1]=b; tri_out[2]=c;
            w_out[0]=l1; w_out[1]=l2; w_out[2]=l3;
            if (g_out) *g_out = l1*pts[3*a+2] + l2*pts[3*b+2] + l3*pts[3*c+2];
            return 1;
        }
    }
    return 0;
}
