/* 3D phase-space views, steps 1 and 2 of docs/VISUALIZATION_3D.md: a deterministic,
 * tangency-refined equilibrium hull at one temperature, and the exact phase regions of
 * that isothermal section as mesh patches.
 *
 * The section is the hull's own regions laid over a triangular lattice (see the overlay
 * below), so its boundaries are exact intersections, not searched for.
 *
 * The hull. Candidates are the liquid (a triangular lattice of single-phase minima, from
 * the minimizer below), each CEF solution along its composition line, and the
 * stoichiometric compounds, all per mole of cations. Where the lower hull joins two
 * different phases (or the two sides of a miscibility gap) the sampling decides where
 * the boundary lands, so the samples next to every such tangency are refined pass by
 * pass, halving the step, until the step is below x_tol and the tie-lines through a
 * fixed set of probe compositions move less than x_tol between passes. The seed only
 * moves the interior lattice nodes, so the converged boundary must not depend on it;
 * the tests hold it to that.
 *
 * The lower hull here is its own implementation rather than mqmqa_lower_hull_2d: the
 * refinement puts many samples on one line in a nearly flat region, and a hull built on
 * floating-point orientation tests can fail to terminate on such input. This one rounds
 * the points to an integer grid (composition to 2^-24, Gibbs energy to 2^-38 of its
 * range) and decides every orientation exactly in 128-bit integers.
 */
#include "vis3d.h"
#include "cs_dat_priv.h"   /* NAME_MAX, mqmqa_db_set_error */

#include <ctype.h>
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define LIQ_LATTICE 40        /* initial liquid lattice; accuracy comes from refinement */
#define CEF_SAMPLES 80        /* initial samples along each CEF line */
#define MAX_POINTS 400000     /* refuse rather than run away */
#define W_MIN 1e-6            /* lever weight below which a vertex is not a phase */
#define LABEL_LEN 64
#define PROBE_N 64            /* fixed bulk compositions whose tie-lines must settle */
#define H_ISO (1.0 / 160.0)   /* refine all round down to this step, then along tie-lines */

/* ------------------------------------------------------------------ small helpers */

static void el_of(const char *name, char *out)
{
    int j = 0;
    for (const char *p = name; *p && j < NAME_MAX - 1 && isalpha((unsigned char)*p); ++p)
        out[j++] = (char)toupper((unsigned char)*p);
    out[j] = '\0';
    if (j == 0) { strncpy(out, name, NAME_MAX - 1); out[NAME_MAX - 1] = '\0'; }
}

static int grow(void **p, int *cap, int need, size_t elem)
{
    if (need <= *cap) return 0;
    int nc = *cap ? *cap : 64;
    while (nc < need) nc *= 2;
    void *q = realloc(*p, (size_t)nc * elem);
    if (!q) return -1;
    *p = q; *cap = nc;
    return 0;
}

/* splitmix64: a fixed, documented generator, so a seed means the same thing on every
 * platform and in the browser */
static uint64_t mix_next(uint64_t *s)
{
    uint64_t z = (*s += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}
static double mix_unit(uint64_t *s) { return (double)(mix_next(s) >> 11) * (1.0 / 9007199254740992.0); }

void vis3d_bary_to_xy(double x2, double x3, double *X, double *Y)
{
    *X = x2 + 0.5 * x3;
    *Y = 0.86602540378443864676 * x3;
}

void vis3d_default_options(VisOptions *opt)
{
    memset(opt, 0, sizeof *opt);
    opt->lattice_n = 60;
    opt->n_temps = 0;
    opt->t_lo = opt->t_hi = 0.0;
    opt->x_tol = 1e-3;
    opt->t_tol = 1.0;
    opt->z_per_kelvin = 1e-3;
    opt->seed = 0;
    opt->max_refine = 16;
}

/* ------------------------------------------------------- exact 128-bit orientation */

typedef struct { uint64_t hi, lo; } I128;

static I128 i128_from_u(uint64_t a, uint64_t b)   /* a * b, unsigned */
{
    uint64_t a0 = a & 0xFFFFFFFFu, a1 = a >> 32, b0 = b & 0xFFFFFFFFu, b1 = b >> 32;
    uint64_t p00 = a0 * b0, p01 = a0 * b1, p10 = a1 * b0, p11 = a1 * b1;
    uint64_t mid = (p00 >> 32) + (p01 & 0xFFFFFFFFu) + (p10 & 0xFFFFFFFFu);
    I128 r;
    r.lo = (mid << 32) | (p00 & 0xFFFFFFFFu);
    r.hi = p11 + (p01 >> 32) + (p10 >> 32) + (mid >> 32);
    return r;
}
static I128 i128_neg(I128 a)
{
    I128 r; r.lo = ~a.lo + 1; r.hi = ~a.hi + (r.lo == 0);
    return r;
}
static I128 i128_mul(int64_t a, int64_t b)
{
    int neg = (a < 0) != (b < 0);
    uint64_t ua = a < 0 ? (uint64_t)0 - (uint64_t)a : (uint64_t)a;
    uint64_t ub = b < 0 ? (uint64_t)0 - (uint64_t)b : (uint64_t)b;
    I128 r = i128_from_u(ua, ub);
    return neg ? i128_neg(r) : r;
}
static I128 i128_add(I128 a, I128 b)
{
    I128 r; r.lo = a.lo + b.lo; r.hi = a.hi + b.hi + (r.lo < a.lo);
    return r;
}
static int i128_sign(I128 a)
{
    if ((int64_t)a.hi < 0) return -1;
    return (a.hi | a.lo) ? 1 : 0;
}

typedef struct { int64_t x, y, z; } Q3;

/* sign of det[b-a, c-a, d-a]; the xy minors stay below 2^51 and z differences below
 * 2^39, so every product and the sum fit in 128 bits */
static int orient3(const Q3 *a, const Q3 *b, const Q3 *c, const Q3 *d)
{
    int64_t bx = b->x - a->x, by = b->y - a->y, bz = b->z - a->z;
    int64_t cx = c->x - a->x, cy = c->y - a->y, cz = c->z - a->z;
    int64_t dx = d->x - a->x, dy = d->y - a->y, dz = d->z - a->z;
    I128 s = i128_mul(bz, cx * dy - cy * dx);
    s = i128_add(s, i128_mul(cz, dx * by - dy * bx));
    s = i128_add(s, i128_mul(dz, bx * cy - by * cx));
    return i128_sign(s);
}

/* --------------------------------------------------------------- exact lower hull */

typedef struct {
    int v[3];       /* counter-clockwise seen from outside */
    int nb[3];      /* face across edge (v[i], v[i+1]) */
    int *out; int nout, cap;
    int dead, mark;
} HFace;

typedef struct {
    const Q3 *Q; const double *P;
    HFace *F; int nf, fcap;
    int err;
} HCtx;

static int hc_new_face(HCtx *h, int a, int b, int c)
{
    if (grow((void **)&h->F, &h->fcap, h->nf + 1, sizeof(HFace))) { h->err = 1; return -1; }
    HFace *f = &h->F[h->nf];
    memset(f, 0, sizeof *f);
    f->v[0] = a; f->v[1] = b; f->v[2] = c;
    f->nb[0] = f->nb[1] = f->nb[2] = -1;
    return h->nf++;
}
static void hc_push(HCtx *h, int fi, int p)
{
    HFace *f = &h->F[fi];
    if (grow((void **)&f->out, &f->cap, f->nout + 1, sizeof(int))) { h->err = 1; return; }
    f->out[f->nout++] = p;
}
static int hc_above(const HCtx *h, int fi, int p)
{
    const HFace *f = &h->F[fi];
    return orient3(&h->Q[f->v[0]], &h->Q[f->v[1]], &h->Q[f->v[2]], &h->Q[p]) > 0;
}
/* approximate height of p over face fi, only to pick the farthest point */
static double hc_dist(const HCtx *h, int fi, int p)
{
    const HFace *f = &h->F[fi];
    const double *a = h->P + 3*f->v[0], *b = h->P + 3*f->v[1], *c = h->P + 3*f->v[2];
    const double *q = h->P + 3*p;
    double u[3] = {b[0]-a[0], b[1]-a[1], b[2]-a[2]}, w[3] = {c[0]-a[0], c[1]-a[1], c[2]-a[2]};
    double n[3] = {u[1]*w[2]-u[2]*w[1], u[2]*w[0]-u[0]*w[2], u[0]*w[1]-u[1]*w[0]};
    double nn = sqrt(n[0]*n[0]+n[1]*n[1]+n[2]*n[2]);
    if (!(nn > 0)) return 0.0;
    return (n[0]*(q[0]-a[0]) + n[1]*(q[1]-a[1]) + n[2]*(q[2]-a[2])) / nn;
}
static int edge_slot(const HFace *f, int a, int b)
{
    for (int i = 0; i < 3; ++i) if (f->v[i] == a && f->v[(i+1)%3] == b) return i;
    return -1;
}

/* Lower hull of n points (x, y, g), g already relative. The points are snapped in place
 * to the integer grid the orientation tests use, so a later point location sees exactly
 * the geometry the hull was built on. Writes a malloc'd array of facet index triples to
 * *facets_out; returns the facet count, or -1 on failure (all points coplanar, out of
 * memory). */
static int exact_lower_hull(double *P, int n, int **facets_out)
{
    *facets_out = NULL;
    if (n < 4) return -1;
    double gmax = 0.0;
    for (int i = 0; i < n; ++i) if (fabs(P[3*i+2]) > gmax) gmax = fabs(P[3*i+2]);
    double gstep = gmax > 0 ? gmax / 274877906944.0 : 1.0;   /* 2^38 steps over the range */
    Q3 *Q = malloc((size_t)n * sizeof(Q3));
    if (!Q) return -1;
    for (int i = 0; i < n; ++i) {
        Q[i].x = (int64_t)llround(P[3*i] * 16777216.0);
        Q[i].y = (int64_t)llround(P[3*i+1] * 16777216.0);
        Q[i].z = (int64_t)llround(P[3*i+2] / gstep);
        P[3*i] = (double)Q[i].x / 16777216.0;
        P[3*i+1] = (double)Q[i].y / 16777216.0;
        P[3*i+2] = (double)Q[i].z * gstep;
    }

    /* initial tetrahedron from exactly non-degenerate points */
    int i0 = 0, i1 = -1, i2 = -1, i3 = -1;
    for (int i = 1; i < n && i1 < 0; ++i)
        if (Q[i].x != Q[i0].x || Q[i].y != Q[i0].y || Q[i].z != Q[i0].z) i1 = i;
    for (int i = 1; i < n && i1 >= 0 && i2 < 0; ++i) {
        int64_t ux = Q[i1].x-Q[i0].x, uy = Q[i1].y-Q[i0].y, uz = Q[i1].z-Q[i0].z;
        int64_t vx = Q[i].x-Q[i0].x, vy = Q[i].y-Q[i0].y, vz = Q[i].z-Q[i0].z;
        /* collinear iff every 2x2 minor of [u v] vanishes; x,y minors fit in int64 and
         * the z minors are checked in 128 bits */
        int nz = (ux*vy - uy*vx) != 0;
        if (!nz) {
            I128 m1 = i128_add(i128_mul(uy, vz), i128_neg(i128_mul(uz, vy)));
            I128 m2 = i128_add(i128_mul(uz, vx), i128_neg(i128_mul(ux, vz)));
            nz = i128_sign(m1) != 0 || i128_sign(m2) != 0;
        }
        if (nz) i2 = i;
    }
    for (int i = 1; i < n && i2 >= 0 && i3 < 0; ++i)
        if (orient3(&Q[i0], &Q[i1], &Q[i2], &Q[i]) != 0) i3 = i;
    if (i3 < 0) { free(Q); return -1; }

    HCtx h = {0};
    h.Q = Q; h.P = P;
    int tv[4] = {i0, i1, i2, i3};
    int tf[4][3] = {{0,1,2},{0,3,1},{1,3,2},{0,2,3}};
    for (int k = 0; k < 4; ++k) {
        int a = tv[tf[k][0]], b = tv[tf[k][1]], c = tv[tf[k][2]], d = tv[6 - tf[k][0] - tf[k][1] - tf[k][2]];
        if (orient3(&Q[a], &Q[b], &Q[c], &Q[d]) > 0) { int t = b; b = c; c = t; }
        hc_new_face(&h, a, b, c);
    }
    /* neighbours of the tetrahedron: match reversed edges */
    for (int f = 0; f < 4; ++f)
        for (int e = 0; e < 3; ++e) {
            int a = h.F[f].v[e], b = h.F[f].v[(e+1)%3];
            for (int g = 0; g < 4; ++g)
                if (g != f && edge_slot(&h.F[g], b, a) >= 0) { h.F[f].nb[e] = g; break; }
        }
    for (int p = 0; p < n; ++p) {
        if (p == i0 || p == i1 || p == i2 || p == i3) continue;
        for (int f = 0; f < 4; ++f)
            if (hc_above(&h, f, p)) { hc_push(&h, f, p); break; }
    }

    int *stack = NULL, scap = 0, *vis = NULL, vcap = 0, *horiz = NULL, hcap = 0;
    int *newf = NULL, nfcap = 0, *orph = NULL, ocap = 0;
    int *start_of = malloc((size_t)n * sizeof(int));
    if (!start_of) h.err = 1;
    else for (int i = 0; i < n; ++i) start_of[i] = -1;
    int mark = 0;

    for (int cur = 0; !h.err && cur < h.nf; ++cur) {
        while (!h.err && !h.F[cur].dead && h.F[cur].nout > 0) {
            HFace *f = &h.F[cur];
            int far = f->out[0]; double fd = hc_dist(&h, cur, far);
            for (int t = 1; t < f->nout; ++t) {
                double d = hc_dist(&h, cur, f->out[t]);
                if (d > fd) { fd = d; far = f->out[t]; }
            }
            /* visible region: connected faces the point is strictly above */
            ++mark;
            int nvis = 0, ns = 0;
            if (grow((void **)&stack, &scap, 1, sizeof(int))) { h.err = 1; break; }
            stack[ns++] = cur; h.F[cur].mark = mark;
            while (ns > 0) {
                int g = stack[--ns];
                if (grow((void **)&vis, &vcap, nvis + 1, sizeof(int))) { h.err = 1; break; }
                vis[nvis++] = g;
                for (int e = 0; e < 3; ++e) {
                    int q = h.F[g].nb[e];
                    if (q < 0 || h.F[q].mark == mark) continue;
                    if (hc_above(&h, q, far)) {
                        h.F[q].mark = mark;
                        if (grow((void **)&stack, &scap, ns + 1, sizeof(int))) { h.err = 1; break; }
                        stack[ns++] = q;
                    }
                }
            }
            if (h.err) break;
            /* horizon: edges of visible faces whose neighbour is not visible */
            int nh = 0;
            for (int t = 0; t < nvis; ++t) {
                HFace *g = &h.F[vis[t]];
                for (int e = 0; e < 3; ++e) {
                    int q = g->nb[e];
                    if (q >= 0 && h.F[q].mark == mark) continue;
                    if (grow((void **)&horiz, &hcap, 3*(nh + 1), sizeof(int))) { h.err = 1; break; }
                    horiz[3*nh] = g->v[e]; horiz[3*nh+1] = g->v[(e+1)%3]; horiz[3*nh+2] = q;
                    nh++;
                }
            }
            if (h.err || nh < 3) { h.err = 1; break; }
            /* new faces (u, v, far), linked across the horizon and to each other */
            if (grow((void **)&newf, &nfcap, nh, sizeof(int))) { h.err = 1; break; }
            for (int t = 0; t < nh; ++t) {
                int u = horiz[3*t], v = horiz[3*t+1], q = horiz[3*t+2];
                int nf_ = hc_new_face(&h, u, v, far);
                if (nf_ < 0) break;
                newf[t] = nf_;
                h.F[nf_].nb[0] = q;
                if (q >= 0) { int s = edge_slot(&h.F[q], v, u); if (s >= 0) h.F[q].nb[s] = nf_; }
                start_of[u] = nf_;
            }
            if (h.err) break;
            for (int t = 0; t < nh; ++t) {
                HFace *g = &h.F[newf[t]];
                g->nb[1] = start_of[g->v[1]];   /* edge (v, far) borders the face starting at v */
                for (int s = 0; s < nh; ++s)     /* edge (far, u) borders the face ending at u */
                    if (h.F[newf[s]].v[1] == g->v[0]) { g->nb[2] = newf[s]; break; }
            }
            for (int t = 0; t < nh; ++t) start_of[horiz[3*t]] = -1;
            /* hand the visible faces' points to the new faces; the rest are inside */
            int no = 0;
            for (int t = 0; t < nvis; ++t) {
                HFace *g = &h.F[vis[t]];
                for (int s = 0; s < g->nout; ++s) {
                    if (g->out[s] == far) continue;
                    if (grow((void **)&orph, &ocap, no + 1, sizeof(int))) { h.err = 1; break; }
                    orph[no++] = g->out[s];
                }
                free(g->out); g->out = NULL; g->nout = g->cap = 0; g->dead = 1;
            }
            for (int s = 0; s < no && !h.err; ++s)
                for (int t = 0; t < nh; ++t)
                    if (hc_above(&h, newf[t], orph[s])) { hc_push(&h, newf[t], orph[s]); break; }
        }
    }

    int nlow = -1;
    if (!h.err) {
        int *out = NULL, ocap2 = 0;
        nlow = 0;
        for (int f = 0; f < h.nf; ++f) {
            HFace *g = &h.F[f];
            if (g->dead) continue;
            const Q3 *a = &Q[g->v[0]], *b = &Q[g->v[1]], *c = &Q[g->v[2]];
            int64_t nz = (b->x - a->x) * (c->y - a->y) - (b->y - a->y) * (c->x - a->x);
            if (nz >= 0) continue;          /* outward normal points down: lower facet */
            if (grow((void **)&out, &ocap2, 3*(nlow + 1), sizeof(int))) { nlow = -1; break; }
            out[3*nlow] = g->v[0]; out[3*nlow+1] = g->v[1]; out[3*nlow+2] = g->v[2];
            nlow++;
        }
        if (nlow < 0) free(out); else *facets_out = out;
    }
    for (int f = 0; f < h.nf; ++f) free(h.F[f].out);
    free(h.F); free(Q); free(stack); free(vis); free(horiz); free(newf); free(orph); free(start_of);
    return nlow;
}

/* ------------------------------------------------------------------ the system */

enum { SLOT_LIQ = 0, SLOT_CEF = 1, SLOT_STOICH = 2 };

typedef struct {
    int kind;                  /* SLOT_* */
    int index;                 /* db phase index, or stoich index */
    char name[NAME_MAX];
    /* CEF line: Y template, mixing flat offset, cation moles per unit y */
    int nsub, ncon, mix0;      /* mix0: flat index of the first mixing constituent */
    double *Y;
    double p0[2], p1[2];       /* (x2, x3) at y = 0 and y = 1 */
    double cat_mol;            /* cations per formula (constant along the line) */
    double line_len;
    double gap;                /* same-phase separation that means a miscibility gap */
} Slot;

/* ----------------------------------------------------- single-phase liquid minimum */

/* The MQMQA liquid at fixed T, assembled once from the database so each composition is
 * one minimization rather than a rebuild. The minimizer is its own: the Nelder-Mead
 * solve behind mqmqa_equilibrate_db can stop with quadruplet fractions pinned at zero,
 * several kJ above the minimum (FeO-rich, low-silica liquid at 2000 K), and a hull fed
 * those values invents miscibility gaps. Here the start is the random-mixing
 * distribution fitted exactly to the composition, strictly inside the feasible set,
 * and damped Newton steps in the constraint null space never let a fraction reach zero.
 * The objective is G per mole of cations, the quantity the hull compares. */
typedef struct {
    double T, R_own;
    int ncat, nq, np, nx, soln;
    int *qca, *qcb, *qax, *qay;
    double *Za, *Zb, *Zx, *Zy, *Ztab, *zeta;
    int *pc, *pa; double *pG, *pst;
    int *xm, *xc, *xA, *xB, *xX, *xY, *xac, *cgrp, *agrp;
    double *xpp, *xqp, *xL, *xr;
    double *ccat;              /* ccat[q*ncat + i]: moles of cation i per quadruplet q */
    double *rq, *cq;           /* reference energy and cations of each pure quadruplet */
    double *X, *Xt;            /* scratch */
} LiqModel;

static void liqm_free(LiqModel *m)
{
    void *p[] = {m->qca, m->qcb, m->qax, m->qay, m->Za, m->Zb, m->Zx, m->Zy, m->Ztab, m->zeta,
                 m->pc, m->pa, m->pG, m->pst, m->xm, m->xc, m->xA, m->xB, m->xX, m->xY,
                 m->xac, m->cgrp, m->agrp, m->xpp, m->xqp, m->xL, m->xr, m->ccat, m->rq, m->cq,
                 m->X, m->Xt};
    for (size_t k = 0; k < sizeof p / sizeof p[0]; ++k) free(p[k]);
    memset(m, 0, sizeof *m);
}

static int liqm_build(LiqModel *m, const mqmqa_db *db, int p, double T)
{
    memset(m, 0, sizeof *m);
    int ncat = mqmqa_ph_num_cations(db, p), nan_ = mqmqa_ph_num_anions(db, p);
    m->T = T; m->R_own = mqmqa_db_R_own(db); m->ncat = ncat;
    m->soln = mqmqa_db_phase_is_subq(db, p);
    int nq = m->nq = mqmqa_num_quadruplets(ncat, nan_);
    double q_cat[8], q_an[8];
    if (ncat > 8 || nan_ > 8) return -1;
    for (int i = 0; i < ncat; ++i) q_cat[i] = mqmqa_ph_cation_charge(db, p, i);
    for (int k = 0; k < nan_; ++k) q_an[k] = mqmqa_ph_anion_charge(db, p, k);
    m->qca = malloc((size_t)nq * sizeof(int)); m->qcb = malloc((size_t)nq * sizeof(int));
    m->qax = malloc((size_t)nq * sizeof(int)); m->qay = malloc((size_t)nq * sizeof(int));
    m->Za = malloc((size_t)nq * sizeof(double)); m->Zb = malloc((size_t)nq * sizeof(double));
    m->Zx = malloc((size_t)nq * sizeof(double)); m->Zy = malloc((size_t)nq * sizeof(double));
    m->ccat = calloc((size_t)nq * ncat, sizeof(double));
    m->X = malloc((size_t)nq * sizeof(double)); m->Xt = malloc((size_t)nq * sizeof(double));
    if (!m->qca || !m->qcb || !m->qax || !m->qay || !m->Za || !m->Zb || !m->Zx || !m->Zy ||
        !m->ccat || !m->X || !m->Xt) return -1;
    mqmqa_enumerate_quadruplets(ncat, nan_, m->qca, m->qcb, m->qax, m->qay);

    int nmz = mqmqa_ph_num_mqmz(db, p);
    int *mzA = malloc((size_t)(nmz + 1) * sizeof(int)), *mzB = malloc((size_t)(nmz + 1) * sizeof(int));
    int *mzX = malloc((size_t)(nmz + 1) * sizeof(int)), *mzY = malloc((size_t)(nmz + 1) * sizeof(int));
    double *mzZ = malloc((size_t)(nmz + 1) * 4 * sizeof(double));
    if (!mzA || !mzB || !mzX || !mzY || !mzZ) { free(mzA); free(mzB); free(mzX); free(mzY); free(mzZ); return -1; }
    mqmqa_ph_mqmz(db, p, mzA, mzB, mzX, mzY, mzZ);
#define ZC(is_cat, sp, A, B, X, Y) \
    mqmqa_coordination((is_cat), (sp), (A), (B), (X), (Y), ncat, nan_, q_cat, q_an, nmz, mzA, mzB, mzX, mzY, mzZ)
    for (int q = 0; q < nq; ++q) {
        int a = m->qca[q], b = m->qcb[q], x = m->qax[q], y = m->qay[q];
        m->Za[q] = ZC(1, a, a, b, x, y); m->Zb[q] = ZC(1, b, a, b, x, y);
        m->Zx[q] = ZC(0, x, a, b, x, y); m->Zy[q] = ZC(0, y, a, b, x, y);
        m->ccat[(size_t)q * ncat + a] += 1.0 / m->Za[q];
        m->ccat[(size_t)q * ncat + b] += 1.0 / m->Zb[q];
    }
    int np_ = m->np = mqmqa_ph_num_pairs(db, p);
    m->pc = malloc((size_t)(np_ + 1) * sizeof(int)); m->pa = malloc((size_t)(np_ + 1) * sizeof(int));
    m->pG = malloc((size_t)(np_ + 1) * sizeof(double)); m->pst = malloc((size_t)(np_ + 1) * sizeof(double));
    double *pz = malloc((size_t)(np_ + 1) * sizeof(double));
    m->Ztab = malloc((size_t)(np_ + 1) * nq * sizeof(double));
    m->zeta = calloc((size_t)ncat * nan_, sizeof(double));
    int ok = m->pc && m->pa && m->pG && m->pst && pz && m->Ztab && m->zeta;
    if (ok) {
        mqmqa_ph_pair_indices(db, p, m->pc, m->pa);
        mqmqa_ph_pair_gibbs(db, p, T, m->pG);
        mqmqa_ph_pair_stoich(db, p, m->pst);
        mqmqa_ph_pair_zeta(db, p, pz);
        for (int i = 0; i < np_; ++i) {
            for (int q = 0; q < nq; ++q)
                m->Ztab[i * nq + q] = (m->pc[i] == m->qca[q] || m->pc[i] == m->qcb[q])
                    ? ZC(1, m->pc[i], m->qca[q], m->qcb[q], m->qax[q], m->qay[q]) : 1.0;
            m->zeta[m->pc[i] * nan_ + m->pa[i]] = pz[i];
        }
    }
#undef ZC
    free(pz); free(mzA); free(mzB); free(mzX); free(mzY); free(mzZ);
    if (!ok) return -1;

    int nx = m->nx = mqmqa_ph_num_mqmx(db, p);
    size_t ni = (size_t)(nx + 1) * sizeof(int), nd = (size_t)(nx + 1) * sizeof(double);
    m->xm = malloc(ni); m->xc = malloc(ni); m->xA = malloc(ni); m->xB = malloc(ni);
    m->xX = malloc(ni); m->xY = malloc(ni); m->xac = malloc(ni);
    int *xp = malloc(ni), *xq = malloc(ni);
    m->xpp = malloc(nd); m->xqp = malloc(nd); m->xL = malloc(nd); m->xr = malloc(nd);
    m->cgrp = malloc((size_t)ncat * sizeof(int)); m->agrp = malloc((size_t)nan_ * sizeof(int));
    ok = m->xm && m->xc && m->xA && m->xB && m->xX && m->xY && m->xac && xp && xq &&
         m->xpp && m->xqp && m->xL && m->xr && m->cgrp && m->agrp;
    if (ok) {
        mqmqa_ph_mqmx(db, p, m->xm, m->xc, m->xA, m->xB, m->xX, m->xY, xp, xq);
        mqmqa_ph_mqmx_L(db, p, T, m->xL);
        mqmqa_ph_mqmx_ternary(db, p, m->xr, m->xac);
        for (int i = 0; i < nx; ++i) { m->xpp[i] = xp[i]; m->xqp[i] = xq[i]; }
        for (int i = 0; i < ncat; ++i) m->cgrp[i] = mqmqa_ph_cation_group(db, p, i);
        for (int k = 0; k < nan_; ++k) m->agrp[k] = mqmqa_ph_anion_group(db, p, k);
    }
    free(xp); free(xq);
    if (!ok) return -1;
    /* R and n are linear in X: their coefficients are their values at each pure quad */
    m->rq = malloc((size_t)nq * sizeof(double)); m->cq = malloc((size_t)nq * sizeof(double));
    if (!m->rq || !m->cq) return -1;
    for (int q = 0; q < nq; ++q) {
        for (int r = 0; r < nq; ++r) m->X[r] = r == q;
        m->rq[q] = mqmqa_reference_energy(nq, m->qca, m->qcb, m->qax, m->qay, m->X,
                                          m->np, m->pc, m->pa, m->pG, m->pst, m->Ztab);
        m->cq[q] = 0.0;
        for (int i = 0; i < ncat; ++i) m->cq[q] += m->ccat[(size_t)q * ncat + i];
    }
    return 0;
}

/* the same three terms, in the same order, as the existing solver's objective */
static double liqm_gpq(const LiqModel *m, const double *X)
{
    int nan_ = 1;
    return mqmqa_reference_energy(m->nq, m->qca, m->qcb, m->qax, m->qay, X,
                                  m->np, m->pc, m->pa, m->pG, m->pst, m->Ztab)
         + mqmqa_ideal_mixing_energy(m->T, m->ncat, nan_, m->nq, m->qca, m->qcb, m->qax, m->qay,
                                     X, m->Za, m->Zb, m->Zx, m->Zy, m->zeta, m->soln, m->R_own)
         + mqmqa_excess_energy(m->ncat, nan_, m->nq, m->qca, m->qcb, m->qax, m->qay, X,
                               m->Za, m->Zb, m->Zx, m->Zy, m->soln, m->nx, m->xm, m->xc,
                               m->xA, m->xB, m->xX, m->xY, m->xpp, m->xqp, m->xL,
                               m->xr, m->xac, m->cgrp, m->agrp);
}

/* the mixing and excess share of G per mole of cations */
static double liqm_mix(const LiqModel *m, const double *X)
{
    int nan_ = 1;
    double nc = 0.0;
    for (int q = 0; q < m->nq; ++q) nc += X[q] * m->cq[q];
    return (mqmqa_ideal_mixing_energy(m->T, m->ncat, nan_, m->nq, m->qca, m->qcb, m->qax, m->qay,
                                      X, m->Za, m->Zb, m->Zx, m->Zy, m->zeta, m->soln, m->R_own)
          + mqmqa_excess_energy(m->ncat, nan_, m->nq, m->qca, m->qcb, m->qax, m->qay, X,
                                m->Za, m->Zb, m->Zx, m->Zy, m->soln, m->nx, m->xm, m->xc,
                                m->xA, m->xB, m->xX, m->xY, m->xpp, m->xqp, m->xL,
                                m->xr, m->xac, m->cgrp, m->agrp)) / nc;
}

static double liqm_gcat(const LiqModel *m, const double *X)
{
    double nc = 0.0;
    for (int q = 0; q < m->nq; ++q)
        for (int i = 0; i < m->ncat; ++i) nc += X[q] * m->ccat[(size_t)q * m->ncat + i];
    return liqm_gpq(m, X) / nc;
}

/* Solve the small dense system A x = b (n <= 8) by Gaussian elimination with partial
 * pivoting; returns -1 when singular. A and b are overwritten. */
static int small_solve(double *A, double *b, int n)
{
    for (int c = 0; c < n; ++c) {
        int piv = c;
        for (int r = c + 1; r < n; ++r) if (fabs(A[r*n+c]) > fabs(A[piv*n+c])) piv = r;
        if (!(fabs(A[piv*n+c]) > 1e-300)) return -1;
        if (piv != c) {
            for (int k = 0; k < n; ++k) { double t = A[c*n+k]; A[c*n+k] = A[piv*n+k]; A[piv*n+k] = t; }
            double t = b[c]; b[c] = b[piv]; b[piv] = t;
        }
        for (int r = c + 1; r < n; ++r) {
            double f = A[r*n+c] / A[c*n+c];
            for (int k = c; k < n; ++k) A[r*n+k] -= f * A[c*n+k];
            b[r] -= f * b[c];
        }
    }
    for (int c = n - 1; c >= 0; --c) {
        double s = b[c];
        for (int k = c + 1; k < n; ++k) s -= A[c*n+k] * b[k];
        b[c] = s / A[c*n+c];
    }
    return 0;
}

/* Minimum G per mole of cations at cation fractions x[0..ncat-1] (single anion). Writes
 * the largest cation-fraction error of the result to *err. NaN if it does not converge. */
static double liqm_minimize(LiqModel *m, const double *x, double *err)
{
    enum { MAXQ = 16, MAXK = 16 };
    int nq = m->nq, ncat = m->ncat;
    if (nq > MAXQ || ncat > 8) return NAN;
    /* variables: quadruplets whose cations are all present */
    int var[MAXQ], nv = 0;
    for (int q = 0; q < nq; ++q)
        if (x[m->qca[q]] > 0 && x[m->qcb[q]] > 0) var[nv++] = q;
    int pres[8], npres = 0;
    for (int i = 0; i < ncat; ++i) if (x[i] > 0) pres[npres++] = i;
    if (npres == 0) return NAN;

    /* random-mixing start: X_ab proportional to (2 - d_ab) u_a u_b, with u fitted so the
     * cation fractions come out exactly x (a proportional-fitting iteration) */
    double u[8];
    for (int i = 0; i < ncat; ++i) u[i] = x[i] > 0 ? x[i] : 0.0;
    double *X = m->X;
    for (int it = 0; it < 500; ++it) {
        for (int q = 0; q < nq; ++q) X[q] = 0.0;
        for (int t = 0; t < nv; ++t) {
            int q = var[t], a = m->qca[q], b = m->qcb[q];
            X[q] = (a == b ? 1.0 : 2.0) * u[a] * u[b];
        }
        double n[8] = {0}, tot = 0.0;
        for (int t = 0; t < nv; ++t)
            for (int i = 0; i < ncat; ++i) n[i] += X[var[t]] * m->ccat[(size_t)var[t] * ncat + i];
        for (int i = 0; i < ncat; ++i) tot += n[i];
        double worst = 0.0;
        for (int k = 0; k < npres; ++k) {
            int i = pres[k];
            double r = x[i] / (n[i] / tot);
            if (fabs(r - 1.0) > worst) worst = fabs(r - 1.0);
            u[i] *= sqrt(r);
        }
        if (worst < 1e-15) break;
    }
    double s = 0.0;
    for (int t = 0; t < nv; ++t) s += X[var[t]];
    for (int t = 0; t < nv; ++t) X[var[t]] /= s;

    /* Constraint rows over the variables: all but one present cation, plus the
     * normalization. Each Newton step works in fractions scaled by their current values
     * (dX_q = X_q dY_q), the affine scaling of interior-point methods: a step of a given
     * size moves every fraction by the same relative amount, so a dilute component is
     * resolved as well as a major one. */
    int mrows = npres;
    double Crow[8][MAXQ];
    for (int r = 0; r < npres - 1; ++r) {
        int i = pres[r];
        for (int t = 0; t < nv; ++t) {
            int q = var[t];
            double cq = 0.0;
            for (int c = 0; c < ncat; ++c) cq += m->ccat[(size_t)q * ncat + c];
            Crow[r][t] = m->ccat[(size_t)q * ncat + i] - x[i] * cq;
        }
    }
    for (int t = 0; t < nv; ++t) Crow[mrows - 1][t] = 1.0;

    /* f = R(X)/n(X) + M(X)/n(X): the reference energy R and the cation count n are
     * linear in X, so their share of the gradient, the Hessian and every step's change
     * is computed exactly; only the mixing-plus-excess share M/n is differenced. That
     * keeps the ~1e6 J reference energy out of the rounding. */
    double fn = liqm_mix(m, X);
    if (!isfinite(fn)) return NAN;
    double *Xt = m->Xt;
    for (int q = 0; q < nq; ++q) Xt[q] = X[q];
    const double hs = 1e-5;          /* relative probe step */
    const double GTOL = 1e-3;        /* J per unit relative change */
    const double GSTALL = 1.0;
    double lam = 0.0, gain[10] = {0};   /* energy bought by each of the last ten steps */
    int converged = 0;
    for (int iter = 0; iter < 500; ++iter) {
        /* orthonormal basis of the scaled rows, then of their complement (the null space) */
        double B[MAXQ][MAXQ]; int nb = 0;
        for (int r = 0; r < mrows; ++r) {
            double v[MAXQ];
            for (int t = 0; t < nv; ++t) v[t] = Crow[r][t] * X[var[t]];
            for (int pass = 0; pass < 2; ++pass)
                for (int b = 0; b < nb; ++b) {
                    double d = 0; for (int t = 0; t < nv; ++t) d += v[t] * B[b][t];
                    for (int t = 0; t < nv; ++t) v[t] -= d * B[b][t];
                }
            double nn = 0; for (int t = 0; t < nv; ++t) nn += v[t] * v[t];
            nn = sqrt(nn);
            if (nn < 1e-14) continue;
            for (int t = 0; t < nv; ++t) B[nb][t] = v[t] / nn;
            nb++;
        }
        int nrow = nb;
        for (int e = 0; e < nv && nb < nv; ++e) {
            double v[MAXQ] = {0};
            v[e] = 1.0;
            for (int pass = 0; pass < 2; ++pass)
                for (int b = 0; b < nb; ++b) {
                    double d = 0; for (int t = 0; t < nv; ++t) d += v[t] * B[b][t];
                    for (int t = 0; t < nv; ++t) v[t] -= d * B[b][t];
                }
            double nn = 0; for (int t = 0; t < nv; ++t) nn += v[t] * v[t];
            nn = sqrt(nn);
            if (nn < 1e-8) continue;
            for (int t = 0; t < nv; ++t) B[nb][t] = v[t] / nn;
            nb++;
        }
        int k = nb - nrow;
        if (k <= 0) { converged = 1; break; }   /* composition fixes the state */
        double (*Nn)[MAXQ] = &B[nrow];

        /* exact derivatives of R/n along each direction w_a = X * Nn[a] */
        double u = 0, v = 0, ua[MAXK], va[MAXK];
        for (int t = 0; t < nv; ++t) { u += m->rq[var[t]] * X[var[t]]; v += m->cq[var[t]] * X[var[t]]; }
        for (int a = 0; a < k; ++a) {
            ua[a] = va[a] = 0;
            for (int t = 0; t < nv; ++t) {
                double w = X[var[t]] * Nn[a][t];
                ua[a] += m->rq[var[t]] * w; va[a] += m->cq[var[t]] * w;
            }
        }
        double g[MAXK], H[MAXK * MAXK];
        for (int a = 0; a < k; ++a) {
            g[a] = (ua[a] * v - u * va[a]) / (v * v);
            for (int b = 0; b < k; ++b)
                H[a*k+b] = -(ua[a] * va[b] + ua[b] * va[a]) / (v * v) + 2 * u * va[a] * va[b] / (v * v * v);
        }
        /* differenced derivatives of M/n */
#define EVAL(out, da, sa, db_, sb) do { \
            for (int t = 0; t < nv; ++t) \
                Xt[var[t]] = X[var[t]] * (1.0 + (sa) * hs * Nn[da][t] + (sb) * hs * Nn[db_][t]); \
            out = liqm_mix(m, Xt); } while (0)
        for (int a = 0; a < k; ++a) {
            double fp, fm;
            EVAL(fp, a, 1.0, a, 0.0);
            EVAL(fm, a, -1.0, a, 0.0);
            g[a] += (fp - fm) / (2 * hs);
            H[a*k+a] += (fp - 2 * fn + fm) / (hs * hs);
            for (int b = 0; b < a; ++b) {
                double fpp, fpm, fmp, fmm;
                EVAL(fpp, a, 1.0, b, 1.0); EVAL(fpm, a, 1.0, b, -1.0);
                EVAL(fmp, a, -1.0, b, 1.0); EVAL(fmm, a, -1.0, b, -1.0);
                double hab = (fpp - fpm - fmp + fmm) / (4 * hs * hs);
                H[a*k+b] += hab; H[b*k+a] += hab;
            }
        }
#undef EVAL
        /* Levenberg-Marquardt: the damping persists across iterations, easing after a
         * good step and growing after a failed one. No fraction may fall below a tenth of
         * its value in one step. Converged when the scaled gradient is below GTOL, about
         * a hundred times the rounding noise of the differences; that leaves the energy
         * within ~1e-9 J of the minimum. */
        double gn = 0; for (int a = 0; a < k; ++a) gn += g[a] * g[a];
        gn = sqrt(gn);
        if (gn < GTOL) { converged = 1; break; }
        double d[MAXK], fnew = fn;
        int moved = 0;
        for (int tries = 0; tries < 40 && !moved; ++tries) {
            double A[MAXK * MAXK];
            for (int a = 0; a < k * k; ++a) A[a] = H[a];
            for (int a = 0; a < k; ++a) { A[a*k+a] += lam * (fabs(H[a*k+a]) + 1e-12); d[a] = -g[a]; }
            if (small_solve(A, d, k) == 0) {
                double amax = 1.0;
                for (int t = 0; t < nv; ++t) {
                    double dy = 0; for (int a = 0; a < k; ++a) dy += Nn[a][t] * d[a];
                    if (dy < 0 && 1.0 + amax * dy < 0.1) amax = 0.9 / -dy;
                }
                for (double al = amax; al > 1e-6 * amax && !moved; al *= 0.5) {
                    double du = 0, dv = 0;
                    for (int t = 0; t < nv; ++t) {
                        double dy = 0; for (int a = 0; a < k; ++a) dy += Nn[a][t] * d[a];
                        double dx = X[var[t]] * al * dy;
                        Xt[var[t]] = X[var[t]] + dx;
                        du += m->rq[var[t]] * dx; dv += m->cq[var[t]] * dx;
                    }
                    double ft = liqm_mix(m, Xt);
                    double dlin = (du * v - u * dv) / (v * (v + dv));
                    if (isfinite(ft) && dlin + (ft - fn) < 0) { fnew = ft; moved = 1; gain[iter % 10] = -(dlin + (ft - fn)); }
                }
            }
            if (!moved) lam = lam > 0 ? lam * 10 : 1e-3;
            if (lam > 1e12) break;
        }
        /* No descent at any damping: the differences have reached rounding. That is a
         * minimum only if the gradient is already small; a solve stuck with a large one
         * (the failure of the old Nelder-Mead path) is reported, not returned. The
         * directions still above GTOL here are those of fractions below ~1e-6, whose
         * whole energy share is of order 1e-3 J. */
        if (!moved) { converged = gn < GSTALL; break; }
        lam *= 0.3;
        if (lam < 1e-8) lam = 0.0;
        for (int t = 0; t < nv; ++t) X[var[t]] = Xt[var[t]];
        fn = fnew;
        /* The gradient can sit a little above GTOL on the rounding noise of the energy
         * routines while the steps buy nothing: ten steps together under 1e-9 J with a
         * small gradient is the minimum. */
        double tot = 0; for (int j = 0; j < 10; ++j) tot += gain[j];
        if (iter >= 9 && tot < 1e-9 && gn < GSTALL) { converged = 1; break; }
    }
    for (int q = 0; q < nq; ++q) Xt[q] = X[q];
    double f = liqm_gcat(m, X);
    /* composition actually reached */
    double n[8] = {0}, tot = 0.0;
    for (int q = 0; q < nq; ++q)
        for (int i = 0; i < ncat; ++i) n[i] += X[q] * m->ccat[(size_t)q * ncat + i];
    for (int i = 0; i < ncat; ++i) tot += n[i];
    double worst = 0.0;
    for (int i = 0; i < ncat; ++i) if (fabs(n[i] / tot - x[i]) > worst) worst = fabs(n[i] / tot - x[i]);
    if (err) *err = worst;
    return converged ? f : NAN;
}

double vis3d_liquid_gibbs(const mqmqa_db *db, int phase, double T, double x2, double x3,
                          double *X_out)
{
    if (!db || phase < 0 || phase >= mqmqa_db_num_phases(db) || mqmqa_db_phase_kind(db, phase) != 0 ||
        mqmqa_ph_num_cations(db, phase) != 3 || mqmqa_ph_num_anions(db, phase) != 1) {
        mqmqa_db_set_error("vis3d: phase %d is not a three-cation, single-anion MQMQA liquid", phase);
        return NAN;
    }
    const char *uns = mqmqa_ph_excess_unsupported(db, phase);
    if (uns) { mqmqa_db_set_error("%s", uns); return NAN; }
    LiqModel m;
    if (liqm_build(&m, db, phase, T)) { liqm_free(&m); mqmqa_db_set_error("vis3d: out of memory"); return NAN; }
    double x[3] = {1.0 - x2 - x3, x2, x3}, err;
    double g = (x[0] < 0 || x2 < 0 || x3 < 0) ? NAN : liqm_minimize(&m, x, &err);
    if (X_out) for (int q = 0; q < m.nq; ++q) X_out[q] = m.X[q];
    liqm_free(&m);
    return g;
}

struct vis3d_hull {
    const mqmqa_db *db;
    double T;
    LiqModel lm;
    Slot *slot; int nslot;
    int liq_db_phase;
    char cat_sym[3][NAME_MAX], an_sym[NAME_MAX];
    double cat_q[3], an_q;
    int cat_el[3], an_el;      /* db element indices */
    int ndbel;
    /* candidates */
    double *P; int *tag; double *par; double *perr; int n, cap;   /* P: (x2, x3, g per cation) */
    double gref[3];            /* conditioning plane through the corners */
    double *R;                 /* relative points for the hull */
    int *facets; int nf;
    /* point location */
    int nb; int *bin_start; int *bin_item;
    /* diagnostics */
    int passes; double last_shift; double max_comp_err;
    /* liquid edges already tested for a miscibility gap: sorted (a, b) pairs, a < b */
    int *gpair; char *gflag; int ngap, gcap;
};

static int in_system(const vis3d_hull *h, const char *sym)
{
    if (!strcmp(sym, h->an_sym)) return 3;
    for (int i = 0; i < 3; ++i) if (!strcmp(sym, h->cat_sym[i])) return i;
    return -1;
}

static int setup_liquid(vis3d_hull *h, int p)
{
    const mqmqa_db *db = h->db;
    if (mqmqa_ph_num_cations(db, p) != 3 || mqmqa_ph_num_anions(db, p) != 1) {
        mqmqa_db_set_error("vis3d: liquid %s needs three cations and one anion",
                           mqmqa_db_phase_name(db, p));
        return -2;
    }
    const char *uns = mqmqa_ph_excess_unsupported(db, p);
    if (uns) { mqmqa_db_set_error("%s", uns); return -3; }
    h->liq_db_phase = p;
    h->ndbel = mqmqa_db_num_elements(db);
    for (int i = 0; i < 3; ++i) {
        el_of(mqmqa_ph_cation(db, p, i), h->cat_sym[i]);
        h->cat_q[i] = mqmqa_ph_cation_charge(db, p, i);
    }
    el_of(mqmqa_ph_anion(db, p, 0), h->an_sym);
    h->an_q = fabs(mqmqa_ph_anion_charge(db, p, 0));
    if (!strcmp(h->cat_sym[0], h->cat_sym[1]) || !strcmp(h->cat_sym[0], h->cat_sym[2]) ||
        !strcmp(h->cat_sym[1], h->cat_sym[2]) || !(h->an_q > 0)) {
        mqmqa_db_set_error("vis3d: liquid %s needs three distinct cation elements",
                           mqmqa_db_phase_name(db, p));
        return -2;
    }
    h->an_el = -1;
    for (int i = 0; i < 3; ++i) h->cat_el[i] = -1;
    for (int e = 0; e < h->ndbel; ++e) {
        const char *s = mqmqa_db_element(db, e);
        if (!strcmp(s, h->an_sym)) h->an_el = e;
        for (int i = 0; i < 3; ++i) if (!strcmp(s, h->cat_sym[i])) h->cat_el[i] = e;
    }
    if (h->an_el < 0 || h->cat_el[0] < 0 || h->cat_el[1] < 0 || h->cat_el[2] < 0) {
        mqmqa_db_set_error("vis3d: liquid %s names an element the database does not list",
                           mqmqa_db_phase_name(db, p));
        return -2;
    }
    if (liqm_build(&h->lm, db, p, h->T)) { mqmqa_db_set_error("vis3d: out of memory"); return -5; }
    return 0;
}

/* A CEF phase qualifies when every constituent is a system element, one sublattice
 * mixes two cations and the others hold one constituent each (the line phases the
 * existing ternary sections sample). *skip is set for a phase outside the system. */
static int setup_cef(vis3d_hull *h, int p, Slot *s, int *skip)
{
    const mqmqa_db *db = h->db;
    *skip = 0;
    int nsub = mqmqa_ph_cef_num_subl(db, p);
    int nc[32]; double sr[32];
    if (nsub < 1 || nsub > 32) { *skip = 1; return 0; }
    mqmqa_ph_cef_subl_ncon(db, p, nc);
    mqmqa_ph_cef_site_ratio(db, p, sr);
    int ncon = 0, mix = -1, nmix = 0;
    for (int k = 0; k < nsub; ++k) {
        for (int c = 0; c < nc[k]; ++c) {
            char sym[NAME_MAX]; el_of(mqmqa_ph_cef_constituent(db, p, k, c), sym);
            if (in_system(h, sym) < 0) { *skip = 1; return 0; }
        }
        if (nc[k] == 2) {
            nmix++; mix = ncon;
            for (int c = 0; c < 2; ++c) {
                char sym[NAME_MAX]; el_of(mqmqa_ph_cef_constituent(db, p, k, c), sym);
                if (in_system(h, sym) == 3) nmix += 2;   /* anion mixing: not a cation line */
            }
        }
        else if (nc[k] != 1) nmix += 2;
        ncon += nc[k];
    }
    if (nmix > 1) {
        mqmqa_db_set_error("vis3d: CEF phase %s mixes on more than one sublattice or more "
                           "than two constituents; only line solutions are sampled",
                           mqmqa_db_phase_name(db, p));
        return -2;
    }
    s->kind = SLOT_CEF; s->index = p; s->nsub = nsub; s->ncon = ncon; s->mix0 = mix;
    strncpy(s->name, mqmqa_db_phase_name(db, p), NAME_MAX - 1);
    s->Y = malloc((size_t)ncon * sizeof(double));
    if (!s->Y) { mqmqa_db_set_error("vis3d: out of memory"); return -5; }
    for (int i = 0; i < ncon; ++i) s->Y[i] = 1.0;
    /* composition at both ends of the line */
    for (int end = 0; end < 2; ++end) {
        double mol[3] = {0, 0, 0}, cat = 0.0;
        int flat = 0;
        for (int k = 0; k < nsub; ++k)
            for (int c = 0; c < nc[k]; ++c, ++flat) {
                double y = 1.0;
                if (flat == mix) y = end ? 0.0 : 1.0;
                else if (mix >= 0 && flat == mix + 1) y = end ? 1.0 : 0.0;
                char sym[NAME_MAX]; el_of(mqmqa_ph_cef_constituent(db, p, k, c), sym);
                int w = in_system(h, sym);
                if (w < 3) { mol[w] += sr[k] * y; cat += sr[k] * y; }
            }
        if (!(cat > 0)) {
            mqmqa_db_set_error("vis3d: CEF phase %s holds no cation at one end of its line",
                               mqmqa_db_phase_name(db, p));
            return -2;
        }
        double *q = end ? s->p1 : s->p0;
        q[0] = mol[1] / cat; q[1] = mol[2] / cat;
        s->cat_mol = cat;
    }
    if (mix < 0) { s->p1[0] = s->p0[0]; s->p1[1] = s->p0[1]; }
    s->line_len = hypot(s->p1[0] - s->p0[0], s->p1[1] - s->p0[1]);
    s->gap = 3.0 * s->line_len / CEF_SAMPLES;
    return 0;
}

static int add_point(vis3d_hull *h, double x2, double x3, double g, int tag, double par,
                     double perr)
{
    if (h->n >= MAX_POINTS) return -1;
    int old = h->cap;
    if (grow((void **)&h->P, &h->cap, h->n + 1, 3 * sizeof(double))) return -1;
    if (h->cap != old) {   /* tag and par follow P's capacity */
        int *t = realloc(h->tag, (size_t)h->cap * sizeof(int));
        if (!t) return -1;
        h->tag = t;
        double *pr = realloc(h->par, (size_t)h->cap * sizeof(double));
        if (!pr) return -1;
        h->par = pr;
        double *pe = realloc(h->perr, (size_t)h->cap * sizeof(double));
        if (!pe) return -1;
        h->perr = pe;
    }
    h->P[3*h->n] = x2; h->P[3*h->n+1] = x3; h->P[3*h->n+2] = g;
    h->tag[h->n] = tag; h->par[h->n] = par; h->perr[h->n] = perr;
    h->n++;
    return 0;
}

/* Liquid Gibbs energy per mole of cations at (x2, x3); a solve that does not converge
 * is an error, never a skipped sample. */
static int liq_point(vis3d_hull *h, double x2, double x3)
{
    double x1 = 1.0 - x2 - x3;
    if (x1 < -1e-12 || x2 < -1e-12 || x3 < -1e-12) return 0;
    double x[3] = {x1 > 0 ? x1 : 0.0, x2 > 0 ? x2 : 0.0, x3 > 0 ? x3 : 0.0};
    double err = 0.0, g = liqm_minimize(&h->lm, x, &err);
    if (!isfinite(g) && (x[0] == 0.0 || x[1] == 0.0 || x[2] == 0.0)) {
        /* The excess routine returns NaN at some exact end-members (the FeO-SiO2 Q term
         * at pure FeO); the sample moves 1e-9 toward the centre, about 1e-4 J away. */
        for (int i = 0; i < 3; ++i) x[i] += 1e-9 * (1.0 / 3.0 - x[i]);
        x2 = x[1]; x3 = x[2];
        g = liqm_minimize(&h->lm, x, &err);
    }
    if (!isfinite(g)) {
        mqmqa_db_set_error("vis3d: the liquid could not be equilibrated at x2 = %.17g, "
                           "x3 = %.17g, T = %.2f K", x2, x3, h->T);
        return -4;
    }
    if (err > h->max_comp_err) h->max_comp_err = err;
    if (add_point(h, x2, x3, g, 0, NAN, err)) { mqmqa_db_set_error("vis3d: more than %d samples", MAX_POINTS); return -5; }
    return 0;
}

static int cef_point(vis3d_hull *h, int k, double y)
{
    Slot *s = &h->slot[k];
    if (y < 0) y = 0; if (y > 1) y = 1;
    if (s->mix0 >= 0) { s->Y[s->mix0] = 1.0 - y; s->Y[s->mix0 + 1] = y; }
    double g = mqmqa_ph_cef_gibbs(h->db, s->index, s->Y, h->T, 0);
    if (!isfinite(g)) {
        mqmqa_db_set_error("vis3d: %s has no finite Gibbs energy at y = %.6f, T = %.2f K",
                           s->name, y, h->T);
        return -4;
    }
    double x2 = s->p0[0] + y * (s->p1[0] - s->p0[0]);
    double x3 = s->p0[1] + y * (s->p1[1] - s->p0[1]);
    if (add_point(h, x2, x3, g / s->cat_mol, k, y, 0.0)) { mqmqa_db_set_error("vis3d: more than %d samples", MAX_POINTS); return -5; }
    return 0;
}

static int stoich_point(vis3d_hull *h, int k)
{
    Slot *s = &h->slot[k];
    double *ev = malloc((size_t)h->ndbel * sizeof(double));
    if (!ev) { mqmqa_db_set_error("vis3d: out of memory"); return -5; }
    mqmqa_db_stoich_elems(h->db, s->index, ev);
    double mol[3] = {0, 0, 0}, cat = 0.0;
    for (int e = 0; e < h->ndbel; ++e) {
        for (int i = 0; i < 3; ++i) if (e == h->cat_el[i]) { mol[i] += ev[e]; cat += ev[e]; }
    }
    free(ev);
    double g = mqmqa_db_stoich_gibbs(h->db, s->index, h->T);
    if (!(cat > 0) || !isfinite(g)) {
        mqmqa_db_set_error("vis3d: compound %s has no cation or no finite Gibbs energy at %.2f K",
                           s->name, h->T);
        return -4;
    }
    if (add_point(h, mol[1] / cat, mol[2] / cat, g / cat, k, NAN, 0.0)) { mqmqa_db_set_error("vis3d: out of memory"); return -5; }
    return 0;
}

static int stoich_in_system(const vis3d_hull *h, int j)
{
    double *ev = malloc((size_t)h->ndbel * sizeof(double));
    if (!ev) return 0;
    mqmqa_db_stoich_elems(h->db, j, ev);
    int ok = 1; double cat = 0.0;
    for (int e = 0; e < h->ndbel; ++e) {
        if (ev[e] == 0.0) continue;
        int in = (e == h->an_el);
        for (int i = 0; i < 3; ++i) if (e == h->cat_el[i]) { in = 1; cat += ev[e]; }
        if (!in) ok = 0;
    }
    free(ev);
    return ok && cat > 0;
}

static int add_slot(vis3d_hull *h, int *cap)
{
    if (grow((void **)&h->slot, cap, h->nslot + 1, sizeof(Slot))) return -1;
    memset(&h->slot[h->nslot], 0, sizeof(Slot));
    return h->nslot++;
}

static int resolve_phases(vis3d_hull *h, const char *const *phases, int n_phases)
{
    const mqmqa_db *db = h->db;
    int np = mqmqa_db_num_phases(db), nst = mqmqa_db_num_stoich(db), cap = 0, rc;
    int liq = -1;
    if (phases) {
        for (int k = 0; k < n_phases; ++k) {
            int p = mqmqa_db_phase_index(db, phases[k]);
            if (p >= 0 && mqmqa_db_phase_kind(db, p) == 0) {
                if (liq >= 0) { mqmqa_db_set_error("vis3d: more than one MQMQA liquid named"); return -2; }
                liq = p;
            }
        }
    } else {
        for (int p = 0; p < np && liq < 0; ++p)
            if (mqmqa_db_phase_kind(db, p) == 0 && mqmqa_ph_num_cations(db, p) == 3 &&
                mqmqa_ph_num_anions(db, p) == 1) liq = p;
    }
    if (liq < 0) { mqmqa_db_set_error("vis3d: no three-cation, single-anion MQMQA liquid"); return -2; }
    if ((rc = setup_liquid(h, liq))) return rc;
    int k = add_slot(h, &cap);
    if (k < 0) { mqmqa_db_set_error("vis3d: out of memory"); return -5; }
    h->slot[k].kind = SLOT_LIQ; h->slot[k].index = liq;
    strncpy(h->slot[k].name, mqmqa_db_phase_name(db, liq), NAME_MAX - 1);

    int nwant = phases ? n_phases : np + nst;
    for (int w = 0; w < nwant; ++w) {
        int p = -1, st = -1;
        if (phases) {
            p = mqmqa_db_phase_index(db, phases[w]);
            if (p < 0) {
                for (int j = 0; j < nst; ++j)
                    if (!strcmp(mqmqa_db_stoich_name(db, j), phases[w])) { st = j; break; }
                if (st < 0) { mqmqa_db_set_error("vis3d: no phase named %s", phases[w]); return -1; }
            }
        } else if (w < np) p = w;
        else st = w - np;
        if (p == liq) continue;
        if (p >= 0) {
            if (mqmqa_db_phase_kind(db, p) != 1) {
                if (phases) { mqmqa_db_set_error("vis3d: %s is a second MQMQA phase", phases[w]); return -2; }
                continue;
            }
            Slot tmp; memset(&tmp, 0, sizeof tmp);
            int skip = 0;
            if ((rc = setup_cef(h, p, &tmp, &skip))) { free(tmp.Y); return rc; }
            if (skip) {
                if (phases) { mqmqa_db_set_error("vis3d: %s holds an element outside the liquid's system", phases[w]); return -2; }
                continue;
            }
            k = add_slot(h, &cap);
            if (k < 0) { free(tmp.Y); mqmqa_db_set_error("vis3d: out of memory"); return -5; }
            h->slot[k] = tmp;
        } else {
            if (!stoich_in_system(h, st)) {
                if (phases) { mqmqa_db_set_error("vis3d: %s holds an element outside the liquid's system", phases[w]); return -2; }
                continue;
            }
            k = add_slot(h, &cap);
            if (k < 0) { mqmqa_db_set_error("vis3d: out of memory"); return -5; }
            h->slot[k].kind = SLOT_STOICH; h->slot[k].index = st;
            strncpy(h->slot[k].name, mqmqa_db_stoich_name(db, st), NAME_MAX - 1);
        }
    }
    return 0;
}

/* ------------------------------------------------------------- hull and location */

static int rehull(vis3d_hull *h)
{
    double *R = realloc(h->R, (size_t)h->n * 3 * sizeof(double));
    if (!R) { mqmqa_db_set_error("vis3d: out of memory"); return -5; }
    h->R = R;
    for (int i = 0; i < h->n; ++i) {
        double x2 = h->P[3*i], x3 = h->P[3*i+1], x1 = 1.0 - x2 - x3;
        R[3*i] = x2; R[3*i+1] = x3;
        R[3*i+2] = h->P[3*i+2] - (h->gref[0]*x1 + h->gref[1]*x2 + h->gref[2]*x3);
    }
    free(h->facets); h->facets = NULL;
    h->nf = exact_lower_hull(R, h->n, &h->facets);
    if (h->nf <= 0) { mqmqa_db_set_error("vis3d: lower hull failed (%d samples)", h->n); return -6; }

    /* bin the facets for point location */
    free(h->bin_start); free(h->bin_item); h->bin_start = h->bin_item = NULL;
    int nb = (int)sqrt((double)h->nf / 2.0);
    if (nb < 8) nb = 8;
    if (nb > 512) nb = 512;
    h->nb = nb;
    int *cnt = calloc((size_t)nb * nb + 1, sizeof(int));
    if (!cnt) { mqmqa_db_set_error("vis3d: out of memory"); return -5; }
    for (int pass = 0; pass < 2; ++pass) {
        if (pass == 1) {
            h->bin_start = malloc(((size_t)nb * nb + 1) * sizeof(int));
            if (!h->bin_start) { free(cnt); mqmqa_db_set_error("vis3d: out of memory"); return -5; }
            int acc = 0;
            for (int b = 0; b < nb * nb; ++b) { h->bin_start[b] = acc; acc += cnt[b]; cnt[b] = 0; }
            h->bin_start[nb * nb] = acc;
            h->bin_item = malloc((size_t)(acc ? acc : 1) * sizeof(int));
            if (!h->bin_item) { free(cnt); mqmqa_db_set_error("vis3d: out of memory"); return -5; }
        }
        for (int f = 0; f < h->nf; ++f) {
            double lo[2] = {1e300, 1e300}, hi[2] = {-1e300, -1e300};
            for (int k = 0; k < 3; ++k) {
                int v = h->facets[3*f+k];
                for (int d = 0; d < 2; ++d) {
                    if (R[3*v+d] < lo[d]) lo[d] = R[3*v+d];
                    if (R[3*v+d] > hi[d]) hi[d] = R[3*v+d];
                }
            }
            int i0 = (int)floor((lo[0] - 1e-9) * nb), i1 = (int)floor((hi[0] + 1e-9) * nb);
            int j0 = (int)floor((lo[1] - 1e-9) * nb), j1 = (int)floor((hi[1] + 1e-9) * nb);
            if (i0 < 0) i0 = 0; if (j0 < 0) j0 = 0;
            if (i1 >= nb) i1 = nb - 1; if (j1 >= nb) j1 = nb - 1;
            for (int i = i0; i <= i1; ++i)
                for (int j = j0; j <= j1; ++j) {
                    int b = i * nb + j;
                    if (pass == 0) cnt[b]++;
                    else h->bin_item[h->bin_start[b] + cnt[b]++] = f;
                }
        }
    }
    free(cnt);
    return 0;
}

/* covering facet at (x2, x3): the same barycentric test and tolerance as
 * mqmqa_hull_assemblage_2d; facets are tried in index order, so ties are reproducible */
static int locate(const vis3d_hull *h, double x2, double x3, double w[3])
{
    const double tol = 1e-9;
    int nb = h->nb;
    int i = (int)floor(x2 * nb), j = (int)floor(x3 * nb);
    if (i < 0) i = 0; if (j < 0) j = 0;
    if (i >= nb) i = nb - 1; if (j >= nb) j = nb - 1;
    int b = i * nb + j;
    int best = -1;
    for (int t = h->bin_start[b]; t < h->bin_start[b+1]; ++t) {
        int f = h->bin_item[t];
        if (best >= 0 && f > best) continue;
        const double *A = h->R + 3*h->facets[3*f], *B = h->R + 3*h->facets[3*f+1],
                     *C = h->R + 3*h->facets[3*f+2];
        double det = (A[0] - C[0]) * (B[1] - C[1]) - (B[0] - C[0]) * (A[1] - C[1]);
        if (fabs(det) < 1e-15) continue;
        double l1 = ((B[1] - C[1]) * (x2 - C[0]) + (C[0] - B[0]) * (x3 - C[1])) / det;
        double l2 = ((C[1] - A[1]) * (x2 - C[0]) + (A[0] - C[0]) * (x3 - C[1])) / det;
        double l3 = 1.0 - l1 - l2;
        if (l1 >= -tol && l2 >= -tol && l3 >= -tol) { best = f; w[0] = l1; w[1] = l2; w[2] = l3; }
    }
    return best;
}

static int cmp_pair(const void *p, const void *q)
{
    const int *a = p, *b = q;
    if (a[0] != b[0]) return a[0] < b[0] ? -1 : 1;
    return (a[1] > b[1]) - (a[1] < b[1]);
}

/* ---- miscibility gaps ----
 * Two liquid samples joined by a hull edge are one liquid when the liquid between them is
 * stable, and the two sides of a gap when it is not. The midpoint decides: above the
 * chord, the liquid there is unstable against the pair, so the edge is a two-liquid
 * tie-line; below it, the edge just spans under-sampled single-phase liquid. A fixed
 * distance cannot make this call near the ends of a gap, where tie-lines shrink to the
 * sampling spacing. Edges shorter than GAP_MIN are taken as one liquid, so a gap whose
 * tie-lines are shorter than that (the last 0.01 before a critical point) is not resolved. CEF lines keep the distance rule. */
#define GAP_MIN 1e-2
#define GAP_EPS 1e-2          /* J; ten times the liquid solver's energy noise */

static int gap_find(const vis3d_hull *h, int a, int b)
{
    int lo = 0, hi = h->ngap - 1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2, pa = h->gpair[2*mid], pb = h->gpair[2*mid+1];
        if (pa == a && pb == b) return mid;
        if (pa < a || (pa == a && pb < b)) lo = mid + 1; else hi = mid - 1;
    }
    return -1;
}

static int is_gap(const vis3d_hull *h, int a, int b)
{
    const Slot *s = &h->slot[h->tag[a]];
    if (s->kind == SLOT_STOICH) return 0;
    if (s->kind == SLOT_CEF)
        return hypot(h->P[3*a] - h->P[3*b], h->P[3*a+1] - h->P[3*b+1]) > s->gap;
    if (a > b) { int t = a; a = b; b = t; }
    int k = gap_find(h, a, b);
    return k >= 0 ? h->gflag[k] : 0;
}

static int liq_point(vis3d_hull *h, double x2, double x3);

/* test every untested liquid-liquid hull edge longer than GAP_MIN */
static int classify_gaps(vis3d_hull *h)
{
    int *cand = NULL, nc = 0, ccap = 0, rc = 0;
    for (int f = 0; f < h->nf; ++f)
        for (int e = 0; e < 3; ++e) {
            int a = h->facets[3*f+e], b = h->facets[3*f+(e+1)%3];
            if (h->tag[a] != h->tag[b] || h->slot[h->tag[a]].kind != SLOT_LIQ) continue;
            if (a > b) { int t = a; a = b; b = t; }
            if (hypot(h->P[3*a] - h->P[3*b], h->P[3*a+1] - h->P[3*b+1]) <= GAP_MIN) continue;
            if (gap_find(h, a, b) >= 0) continue;
            if (grow((void **)&cand, &ccap, 2*(nc + 1), sizeof(int))) { free(cand); return -5; }
            cand[2*nc] = a; cand[2*nc+1] = b; nc++;
        }
    if (nc > 1) qsort(cand, (size_t)nc, 2 * sizeof(int), cmp_pair);
    int nu = 0;
    for (int t = 0; t < nc; ++t)
        if (t == 0 || cand[2*t] != cand[2*nu-2] || cand[2*t+1] != cand[2*nu-1]) {
            cand[2*nu] = cand[2*t]; cand[2*nu+1] = cand[2*t+1]; nu++;
        }
    if (nu == 0) { free(cand); return 0; }
    char *flag = malloc((size_t)nu);
    if (!flag) { free(cand); return -5; }
    int n0 = h->n;
    for (int t = 0; t < nu && !rc; ++t) {
        int a = cand[2*t], b = cand[2*t+1];
        double mx = 0.5 * (h->P[3*a] + h->P[3*b]), my = 0.5 * (h->P[3*a+1] + h->P[3*b+1]);
        /* evaluate through liq_point for its checks, then take the sample back out: a
         * midpoint is a test, not a hull candidate */
        rc = liq_point(h, mx, my);
        if (rc) break;
        if (h->n == n0) { flag[t] = 0; continue; }
        double gm = h->P[3*(h->n - 1) + 2];
        h->n = n0;
        flag[t] = gm > 0.5 * (h->P[3*a+2] + h->P[3*b+2]) + GAP_EPS;
    }
    if (!rc) {
        /* merge into the sorted cache */
        int tot = h->ngap + nu;
        int *np_ = malloc((size_t)tot * 2 * sizeof(int));
        char *nf_ = malloc((size_t)tot);
        if (!np_ || !nf_) rc = -5;
        else {
            int i = 0, j = 0, o = 0;
            while (i < h->ngap || j < nu) {
                int takeold = j >= nu || (i < h->ngap && (h->gpair[2*i] < cand[2*j] ||
                              (h->gpair[2*i] == cand[2*j] && h->gpair[2*i+1] < cand[2*j+1])));
                if (takeold) { np_[2*o] = h->gpair[2*i]; np_[2*o+1] = h->gpair[2*i+1]; nf_[o] = h->gflag[i]; i++; }
                else { np_[2*o] = cand[2*j]; np_[2*o+1] = cand[2*j+1]; nf_[o] = flag[j]; j++; }
                o++;
            }
            free(h->gpair); free(h->gflag);
            h->gpair = np_; h->gflag = nf_; h->ngap = tot; h->gcap = tot;
            np_ = NULL; nf_ = NULL;
        }
        free(np_); free(nf_);
    }
    free(cand); free(flag);
    return rc;
}

/* Phase instances in facet f with lever weights w: vertices of one phase merge unless a
 * miscibility gap separates them. */
typedef struct { int slot; double amt, x2, x3; int nmem; int mem[3]; } Inst;

static int facet_instances(const vis3d_hull *h, int f, const double w[3], Inst out[3])
{
    int m = 0;
    for (int k = 0; k < 3; ++k) {
        if (w[k] <= W_MIN) continue;
        int v = h->facets[3*f+k], s = h->tag[v];
        double x2 = h->P[3*v], x3 = h->P[3*v+1];
        int found = -1;
        for (int q = 0; q < m && found < 0; ++q) {
            if (out[q].slot != s) continue;
            int sep = 0;
            for (int j = 0; j < out[q].nmem; ++j) if (is_gap(h, out[q].mem[j], v)) sep = 1;
            if (!sep) found = q;
        }
        if (found < 0) {
            out[m].slot = s; out[m].amt = 0; out[m].x2 = out[m].x3 = 0; out[m].nmem = 0;
            found = m++;
        }
        out[found].amt += w[k]; out[found].x2 += w[k] * x2; out[found].x3 += w[k] * x3;
        out[found].mem[out[found].nmem++] = v;
    }
    for (int q = 0; q < m; ++q) { out[q].x2 /= out[q].amt; out[q].x3 /= out[q].amt; }
    return m;
}

/* -------------------------------------------------------------- refinement loop */

/* A tangency vertex joins its facet to a different phase, or to the far side of a
 * miscibility gap; only solution-phase vertices can be refined. */
static int is_tangency_edge(const vis3d_hull *h, int a, int b)
{
    return h->tag[a] != h->tag[b] || is_gap(h, a, b);
}

static int refinable(const vis3d_hull *h, int v)
{
    const Slot *s = &h->slot[h->tag[v]];
    return s->kind == SLOT_LIQ || (s->kind == SLOT_CEF && s->mix0 >= 0);
}

static int collect_tangents(const vis3d_hull *h, int *nout, int **partner_start,
                            int **partners, char *flag)
{
    /* flag[v] = 1 for refinable tangency vertices; partners grouped per vertex */
    int n = h->n, *deg = calloc((size_t)n + 1, sizeof(int));
    if (!deg) return -1;
    memset(flag, 0, (size_t)n);
    for (int f = 0; f < h->nf; ++f)
        for (int e = 0; e < 3; ++e) {
            int a = h->facets[3*f+e], b = h->facets[3*f+(e+1)%3];
            if (!is_tangency_edge(h, a, b)) continue;
            if (refinable(h, a)) { flag[a] = 1; deg[a]++; }
            if (refinable(h, b)) { flag[b] = 1; deg[b]++; }
        }
    int *st = malloc(((size_t)n + 1) * sizeof(int));
    if (!st) { free(deg); return -1; }
    int acc = 0;
    for (int v = 0; v < n; ++v) { st[v] = acc; acc += deg[v]; deg[v] = 0; }
    st[n] = acc;
    int *pt = malloc((size_t)(acc ? acc : 1) * sizeof(int));
    int nt = 0;
    for (int v = 0; v < n; ++v) nt += flag[v];
    if (!pt) { free(deg); free(st); return -1; }
    for (int f = 0; f < h->nf; ++f)
        for (int e = 0; e < 3; ++e) {
            int a = h->facets[3*f+e], b = h->facets[3*f+(e+1)%3];
            if (!is_tangency_edge(h, a, b)) continue;
            if (flag[a]) pt[st[a] + deg[a]++] = b;
            if (flag[b]) pt[st[b] + deg[b]++] = a;
        }
    free(deg);
    *nout = nt; *partner_start = st; *partners = pt;
    return 0;
}

/* Tie-line endpoints at a fixed bulk composition, compared pass to pass. */
typedef struct { int m; Inst in[3]; } Probe;

static void sort_instances(Inst *in, int m)
{
    for (int a = 0; a < m; ++a)
        for (int b = a + 1; b < m; ++b) {
            int swap = in[b].slot < in[a].slot ||
                       (in[b].slot == in[a].slot && (in[b].x2 < in[a].x2 ||
                        (in[b].x2 == in[a].x2 && in[b].x3 < in[a].x3)));
            if (swap) { Inst t = in[a]; in[a] = in[b]; in[b] = t; }
        }
}

/* largest endpoint displacement, or -1 when the phase sets differ */
static double probe_shift(const Probe *a, const Probe *b)
{
    if (a->m != b->m) return -1.0;
    double d = 0.0;
    for (int k = 0; k < a->m; ++k) {
        if (a->in[k].slot != b->in[k].slot) return -1.0;
        double e = hypot(a->in[k].x2 - b->in[k].x2, a->in[k].x3 - b->in[k].x3);
        if (e > d) d = e;
    }
    return d;
}

/* the code of the last vis3d_hull_build failure; the engine is single-threaded */
static int last_build_rc = 0;

vis3d_hull *vis3d_hull_build(const mqmqa_db *db, const char *const *phases, int n_phases,
                             double T, const VisOptions *opt_in)
{
    last_build_rc = -1;
    VisOptions opt;
    if (opt_in) opt = *opt_in; else vis3d_default_options(&opt);
    if (!db || !(T > 0) || !(opt.x_tol > 0) || opt.max_refine < 0 || (phases && n_phases < 1)) {
        mqmqa_db_set_error("vis3d: invalid arguments");
        return NULL;
    }
    vis3d_hull *h = calloc(1, sizeof *h);
    if (!h) { mqmqa_db_set_error("vis3d: out of memory"); return NULL; }
    h->db = db; h->T = T;
    int rc = resolve_phases(h, phases, n_phases);
    if (rc) goto fail;

    /* initial liquid lattice; the seed moves interior nodes by up to a quarter step */
    uint64_t rs = opt.seed;
    double h0 = 1.0 / LIQ_LATTICE;
    for (int i = 0; i <= LIQ_LATTICE; ++i)
        for (int j = 0; j <= LIQ_LATTICE - i; ++j) {
            double x2 = i * h0, x3 = j * h0;
            if (opt.seed && i > 0 && j > 0 && i + j < LIQ_LATTICE) {
                x2 += (mix_unit(&rs) - 0.5) * 0.5 * h0;
                x3 += (mix_unit(&rs) - 0.5) * 0.5 * h0;
            }
            if ((rc = liq_point(h, x2, x3))) goto fail;
        }
    for (int k = 0; k < h->nslot; ++k) {
        if (h->slot[k].kind == SLOT_CEF) {
            int ns = h->slot[k].mix0 >= 0 ? CEF_SAMPLES : 0;
            for (int t = 0; t <= ns; ++t)
                if ((rc = cef_point(h, k, ns ? (double)t / ns : 0.0))) goto fail;
        } else if (h->slot[k].kind == SLOT_STOICH) {
            if ((rc = stoich_point(h, k))) goto fail;
        }
    }
    /* conditioning plane: the liquid lattice corners (the first-order term the hull
     * ignores, taken out so the rounded Gibbs energies keep their resolution) */
    h->gref[0] = h->P[2];                                             /* (0, 0) */
    h->gref[2] = h->P[3*LIQ_LATTICE + 2];                             /* (0, 1) */
    {
        int last = (LIQ_LATTICE + 1) * (LIQ_LATTICE + 2) / 2 - 1;     /* (1, 0) */
        h->gref[1] = h->P[3*last + 2];
    }

    Probe *pprev = NULL, *pcur = NULL;
    int nprobe = (PROBE_N + 1) * (PROBE_N + 2) / 2;
    double hl = h0, hc = 1.0 / CEF_SAMPLES;
    const double h_floor = 0.5 * opt.x_tol;
    char *flag = NULL;
    double *pref = NULL; int pref_n = 0;   /* smallest step each sample was refined at */
    int *marked = NULL, nmark = 0, mcap = 0;
    int *edges = NULL, ecap = 0;
    int converged = 0;
    pprev = malloc((size_t)nprobe * sizeof(Probe));
    pcur = malloc((size_t)nprobe * sizeof(Probe));
    if (!pprev || !pcur) { rc = -5; mqmqa_db_set_error("vis3d: out of memory"); }
    for (int pass = 0; !rc; ++pass) {
        if ((rc = rehull(h))) break;
        if ((rc = classify_gaps(h))) { if (rc == -5) mqmqa_db_set_error("vis3d: out of memory"); break; }
        int ncur; int *pst, *ptn;
        char *nf_ = realloc(flag, (size_t)h->n);
        if (!nf_) { rc = -5; mqmqa_db_set_error("vis3d: out of memory"); break; }
        flag = nf_;
        double *np_ = realloc(pref, (size_t)h->n * sizeof(double));
        if (!np_) { rc = -5; mqmqa_db_set_error("vis3d: out of memory"); break; }
        pref = np_;
        for (int i = pref_n; i < h->n; ++i) pref[i] = INFINITY;
        pref_n = h->n;
        if (collect_tangents(h, &ncur, &pst, &ptn, flag)) { rc = -5; mqmqa_db_set_error("vis3d: out of memory"); break; }
        /* tie-line endpoints at the fixed probes, against the previous pass */
        nmark = 0;
        double pshift = 0.0;
        for (int i = 0, k = 0; i <= PROBE_N && !rc; ++i)
            for (int j = 0; j <= PROBE_N - i; ++j, ++k) {
                double w[3];
                int f = locate(h, (double)i / PROBE_N, (double)j / PROBE_N, w);
                if (f < 0) {
                    mqmqa_db_set_error("vis3d: no hull facet covers a probe at %.2f K", T);
                    rc = -6; break;
                }
                pcur[k].m = facet_instances(h, f, w, pcur[k].in);
                sort_instances(pcur[k].in, pcur[k].m);
                if (pass == 0 || pcur[k].m < 2) continue;
                double d = probe_shift(&pprev[k], &pcur[k]);
                if (d < 0) continue;                     /* phase set changed: boundary moved */
                if (d > pshift) pshift = d;
                if (d > opt.x_tol) {
                    if (grow((void **)&marked, &mcap, nmark + 1, sizeof(int))) { rc = -5; break; }
                    marked[nmark++] = f;
                }
            }
        if (rc) { free(pst); free(ptn); if (rc == -5) mqmqa_db_set_error("vis3d: out of memory"); break; }
        { Probe *t = pprev; pprev = pcur; pcur = t; }
        if (pass == 0) pshift = INFINITY;
        h->passes = pass;
        h->last_shift = pshift;
        double cef_step = 0.0;
        for (int k = 0; k < h->nslot; ++k)
            if (h->slot[k].kind == SLOT_CEF && hc * h->slot[k].line_len > cef_step)
                cef_step = hc * h->slot[k].line_len;
        if (ncur == 0 || (hl <= opt.x_tol && cef_step <= opt.x_tol && pshift <= opt.x_tol)) {
            converged = 1;
            free(pst); free(ptn);
            break;
        }
        if (pass >= opt.max_refine) {
            mqmqa_db_set_error("vis3d: phase boundaries at %.2f K did not converge to %.3g in "
                               "%d refinement passes (tie-line shift %.3g)",
                               T, opt.x_tol, pass, pshift);
            rc = -4;
            free(pst); free(ptn);
            break;
        }
        if (hl > h_floor) { hl *= 0.5; hc *= 0.5; }
        int nbase = h->n;
        /* Next to every tangency vertex not yet refined at this step: all round while the
         * step is coarse, so a tie-line the coarse hull cannot yet see still gets sampled;
         * then only along the tie-line directions. CEF lines one step either way. */
        for (int v = 0; v < nbase && !rc; ++v) {
            if (!flag[v] || pref[v] <= hl) continue;
            pref[v] = hl;
            int s = h->tag[v];
            if (h->slot[s].kind == SLOT_CEF) {
                double y = h->par[v];
                if (y - hc >= 0) rc = cef_point(h, s, y - hc);
                if (!rc && y + hc <= 1) rc = cef_point(h, s, y + hc);
                continue;
            }
            if (hl >= H_ISO) {
                for (int k = 0; k < 6 && !rc; ++k) {
                    double a = k * (3.14159265358979323846 / 3.0);
                    rc = liq_point(h, h->P[3*v] + hl * cos(a), h->P[3*v+1] + hl * sin(a));
                }
                continue;
            }
            double used[64][2]; int nused = 0;
            for (int t = pst[v]; t < pst[v+1] && !rc; ++t) {
                int q = ptn[t];
                double dx = h->P[3*q] - h->P[3*v], dy = h->P[3*q+1] - h->P[3*v+1];
                double L = hypot(dx, dy);
                if (!(L > 0)) continue;
                dx /= L; dy /= L;
                int dup = 0;   /* one pair of samples per distinct direction (within ~6 deg) */
                for (int u = 0; u < nused; ++u)
                    if (fabs(used[u][0]*dy - used[u][1]*dx) < 0.1 && used[u][0]*dx + used[u][1]*dy > 0) { dup = 1; break; }
                if (dup || nused == 64) continue;
                used[nused][0] = dx; used[nused][1] = dy; nused++;
                rc = liq_point(h, h->P[3*v] + hl*dx, h->P[3*v+1] + hl*dy);
                if (!rc) rc = liq_point(h, h->P[3*v] - hl*dx, h->P[3*v+1] - hl*dy);
            }
        }
        /* Where a probe's tie-line still moves, the samples along the boundary are too far
         * apart: split the same-phase edges of that facet. */
        int ne = 0;
        for (int t = 0; t < nmark && !rc; ++t) {
            int f = marked[t];
            for (int e = 0; e < 3; ++e) {
                int a = h->facets[3*f+e], b = h->facets[3*f+(e+1)%3];
                if (a > b) { int u = a; a = b; b = u; }
                if (h->tag[a] != h->tag[b] || !refinable(h, a) || is_tangency_edge(h, a, b)) continue;
                if (hypot(h->P[3*a] - h->P[3*b], h->P[3*a+1] - h->P[3*b+1]) <= h_floor) continue;
                if (grow((void **)&edges, &ecap, 2*(ne + 1), sizeof(int))) { rc = -5; mqmqa_db_set_error("vis3d: out of memory"); break; }
                edges[2*ne] = a; edges[2*ne+1] = b; ne++;
            }
        }
        if (!rc && ne > 1) qsort(edges, (size_t)ne, 2 * sizeof(int), cmp_pair);
        for (int t = 0; t < ne && !rc; ++t) {
            if (t > 0 && edges[2*t] == edges[2*t-2] && edges[2*t+1] == edges[2*t-1]) continue;
            int a = edges[2*t], b = edges[2*t+1], s = h->tag[a];
            if (h->slot[s].kind == SLOT_CEF) rc = cef_point(h, s, 0.5 * (h->par[a] + h->par[b]));
            else rc = liq_point(h, 0.5 * (h->P[3*a] + h->P[3*b]), 0.5 * (h->P[3*a+1] + h->P[3*b+1]));
        }
        free(pst); free(ptn);
        if (!rc && h->n == nbase && hl <= h_floor) {
            /* nothing left to add, yet not converged: stop rather than spin */
            mqmqa_db_set_error("vis3d: phase boundaries at %.2f K stalled at tie-line shift %.3g",
                               T, pshift);
            rc = -4;
        }
    }
    free(pprev); free(pcur); free(marked); free(edges); free(pref);
    free(flag);
    if (!converged) { if (!rc) rc = -4; goto fail; }
    last_build_rc = 0;
    return h;
fail:
    last_build_rc = rc ? rc : -1;
    vis3d_hull_free(h);
    return NULL;
}

void vis3d_hull_free(vis3d_hull *h)
{
    if (!h) return;
    for (int k = 0; k < h->nslot; ++k) free(h->slot[k].Y);
    free(h->slot);
    liqm_free(&h->lm);
    free(h->P); free(h->tag); free(h->par); free(h->perr); free(h->R); free(h->facets);
    free(h->bin_start); free(h->bin_item);
    free(h->gpair); free(h->gflag);
    free(h);
}

int vis3d_hull_passes(const vis3d_hull *h) { return h ? h->passes : -1; }
double vis3d_hull_last_shift(const vis3d_hull *h) { return h ? h->last_shift : NAN; }
double vis3d_hull_max_comp_err(const vis3d_hull *h) { return h ? h->max_comp_err : NAN; }
int vis3d_hull_num_points(const vis3d_hull *h) { return h ? h->n : -1; }
int vis3d_hull_num_phases(const vis3d_hull *h) { return h ? h->nslot : -1; }

int vis3d_hull_point(const vis3d_hull *h, int i, double *x2, double *x3, double *g,
                     double *comp_err)
{
    if (!h || i < 0 || i >= h->n) return -1;
    *x2 = h->P[3*i]; *x3 = h->P[3*i+1]; *g = h->P[3*i+2];
    if (comp_err) *comp_err = h->perr[i];
    return h->tag[i];
}

int vis3d_hull_num_facets(const vis3d_hull *h) { return h ? h->nf : -1; }
const int *vis3d_hull_facets(const vis3d_hull *h) { return h ? h->facets : NULL; }
const char *vis3d_hull_phase_name(const vis3d_hull *h, int k)
{
    return (h && k >= 0 && k < h->nslot) ? h->slot[k].name : NULL;
}

int vis3d_lower_hull(const double *pts, int n, int *facets, int max_facets)
{
    if (!pts || n < 4 || !facets) return -1;
    double *P = malloc((size_t)n * 3 * sizeof(double));
    if (!P) return -1;
    memcpy(P, pts, (size_t)n * 3 * sizeof(double));
    int *F = NULL;
    int nf = exact_lower_hull(P, n, &F);
    free(P);
    if (nf < 0 || nf > max_facets) { free(F); return -1; }
    memcpy(facets, F, (size_t)nf * 3 * sizeof(int));
    free(F);
    return nf;
}

double vis3d_hull_gibbs(const vis3d_hull *h, double x2, double x3)
{
    if (!h || x2 < -1e-12 || x3 < -1e-12 || x2 + x3 > 1.0 + 1e-12) return NAN;
    double w[3];
    int f = locate(h, x2, x3, w);
    if (f < 0) return NAN;
    double g = 0.0;
    for (int k = 0; k < 3; ++k) g += w[k] * h->P[3*h->facets[3*f+k] + 2];
    return g;
}

int vis3d_hull_assemblage(const vis3d_hull *h, double x2, double x3, int *phase_out,
                          double *amt_out, double *comp_out, int max_out)
{
    if (!h || max_out < 0) return -1;
    if (x2 < -1e-12 || x3 < -1e-12 || x2 + x3 > 1.0 + 1e-12) return 0;
    double w[3];
    int f = locate(h, x2, x3, w);
    if (f < 0) {
        mqmqa_db_set_error("vis3d: no hull facet covers x2 = %.6f, x3 = %.6f", x2, x3);
        return -6;
    }
    Inst in[3];
    int m = facet_instances(h, f, w, in);
    if (m > max_out) { mqmqa_db_set_error("vis3d: %d phases, room for %d", m, max_out); return -1; }
    for (int q = 0; q < m; ++q) {
        phase_out[q] = in[q].slot; amt_out[q] = in[q].amt;
        if (comp_out) { comp_out[2*q] = in[q].x2; comp_out[2*q+1] = in[q].x3; }
    }
    return m;
}

/* ------------------------------------------------------------ section meshing */

typedef struct { char (*s)[LABEL_LEN]; int n, cap; } Labels;

/* raw triangle soup, one label per triangle, plus boundary segments */
typedef struct {
    double *v; int *lab; int nt, cap;       /* v: nt * 6 doubles (x2, x3 per corner) */
    double *seg; int ns, scap;              /* seg: ns * 4 doubles */
} Soup;

static int soup_tri(Soup *S, int lab, const double *a, const double *b, const double *c)
{
    /* counter-clockwise in (x2, x3), which the map to (X, Y) preserves, so every normal
     * of a flat section points the same way; exactly degenerate slivers carry no area */
    double area2 = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
    if (fabs(area2) <= 1e-15) return 0;
    if (area2 < 0) { const double *t = b; b = c; c = t; }
    if (grow((void **)&S->v, &S->cap, S->nt + 1, 6 * sizeof(double))) return -5;
    int *l = realloc(S->lab, (size_t)S->cap * sizeof(int));
    if (!l) return -5;
    S->lab = l;
    double *d = S->v + 6*S->nt;
    d[0] = a[0]; d[1] = a[1]; d[2] = b[0]; d[3] = b[1]; d[4] = c[0]; d[5] = c[1];
    S->lab[S->nt++] = lab;
    return 0;
}
static int soup_seg(Soup *S, const double *a, const double *b)
{
    if (grow((void **)&S->seg, &S->scap, S->ns + 1, 4 * sizeof(double))) return -5;
    double *d = S->seg + 4*S->ns++;
    d[0] = a[0]; d[1] = a[1]; d[2] = b[0]; d[3] = b[1];
    return 0;
}

/* ---- the section as an overlay of the lattice on the hull ----
 * The phase regions of the section are unions of hull facets, so their boundaries are
 * the facet edges whose two facets carry different labels: straight segments known
 * exactly. A lattice triangle no boundary crosses lies in one field and is kept whole;
 * one that a boundary crosses is clipped against each hull facet it overlaps, every
 * piece taking that facet's label. Nothing is located by search, so a field narrower
 * than the lattice (a thin three-phase triangle) cannot fall between samples. */
typedef struct {
    const vis3d_hull *h;
    Labels *L;
    Soup *S;
    int *flab;                  /* label of each facet */
    double *be; int nbe;        /* boundary edges: nbe * 4 doubles (x2, x3 of both ends) */
    int nbb; int *bstart, *bitem;
    int *stamp, tick;           /* per-facet visit marks */
} Overlay;

static int facet_label(const vis3d_hull *h, Labels *L, int f, int *out)
{
    /* The region label is the whole facet's assemblage: a point exactly on a facet edge
     * (a lattice node on a tie-line between two compounds) must not take the zero-width
     * field of that edge. Name-sorted, repeats kept: "LIQUID+LIQUID" is a gap. */
    const double wall[3] = {1.0 / 3, 1.0 / 3, 1.0 / 3};
    Inst in[3];
    int m = facet_instances(h, f, wall, in);
    const char *nm[3];
    for (int q = 0; q < m; ++q) nm[q] = h->slot[in[q].slot].name;
    for (int a = 0; a < m; ++a)
        for (int b = a + 1; b < m; ++b)
            if (strcmp(nm[a], nm[b]) > 0) { const char *t = nm[a]; nm[a] = nm[b]; nm[b] = t; }
    char buf[3 * NAME_MAX + 4] = "";
    for (int q = 0; q < m; ++q) { if (q) strcat(buf, "+"); strcat(buf, nm[q]); }
    if (strlen(buf) >= LABEL_LEN) {
        mqmqa_db_set_error("vis3d: assemblage label %s is longer than %d characters", buf, LABEL_LEN - 1);
        return -2;
    }
    for (int k = 0; k < L->n; ++k) if (!strcmp(L->s[k], buf)) { *out = k; return 0; }
    if (grow((void **)&L->s, &L->cap, L->n + 1, LABEL_LEN)) return -5;
    strcpy(L->s[L->n], buf);
    *out = L->n++;
    return 0;
}

static int cmp_edge3(const void *p, const void *q)
{
    const int *a = p, *b = q;
    if (a[0] != b[0]) return a[0] < b[0] ? -1 : 1;
    return (a[1] > b[1]) - (a[1] < b[1]);
}

static void overlay_free(Overlay *O)
{
    free(O->flab); free(O->be); free(O->bstart); free(O->bitem); free(O->stamp);
}

static int overlay_build(Overlay *O, const vis3d_hull *h, Labels *L, Soup *S, int nbb)
{
    memset(O, 0, sizeof *O);
    O->h = h; O->L = L; O->S = S; O->nbb = nbb;
    int nf = h->nf, rc;
    O->flab = malloc((size_t)nf * sizeof(int));
    O->stamp = calloc((size_t)nf, sizeof(int));
    int *e = malloc((size_t)nf * 9 * sizeof(int));          /* (a, b, facet) per edge */
    if (!O->flab || !O->stamp || !e) { free(e); return -5; }
    for (int f = 0; f < nf; ++f)
        if ((rc = facet_label(h, L, f, &O->flab[f]))) { free(e); return rc; }
    for (int f = 0; f < nf; ++f)
        for (int k = 0; k < 3; ++k) {
            int a = h->facets[3*f+k], b = h->facets[3*f+(k+1)%3];
            if (a > b) { int t = a; a = b; b = t; }
            e[9*f+3*k] = a; e[9*f+3*k+1] = b; e[9*f+3*k+2] = f;
        }
    qsort(e, (size_t)nf * 3, 3 * sizeof(int), cmp_edge3);
    int cap = 0;
    for (int i = 0; i + 1 < 3 * nf; ++i) {
        if (e[3*i] != e[3*i+3] || e[3*i+1] != e[3*i+4]) continue;
        if (O->flab[e[3*i+2]] != O->flab[e[3*i+5]]) {
            if (grow((void **)&O->be, &cap, 4 * (O->nbe + 1), sizeof(double))) { free(e); return -5; }
            double *d = O->be + 4 * O->nbe++;
            d[0] = h->R[3*e[3*i]]; d[1] = h->R[3*e[3*i]+1];
            d[2] = h->R[3*e[3*i+1]]; d[3] = h->R[3*e[3*i+1]+1];
        }
        ++i;
    }
    free(e);
    /* bin the boundary edges by their bounding boxes */
    O->bstart = calloc((size_t)nbb * nbb + 1, sizeof(int));
    if (!O->bstart) return -5;
    int total = 0;
    for (int pass = 0; pass < 2; ++pass) {
        if (pass == 1) {
            int acc = 0;
            for (int b = 0; b < nbb * nbb; ++b) { int c = O->bstart[b]; O->bstart[b] = acc; acc += c; }
            O->bstart[nbb * nbb] = acc; total = acc;
            O->bitem = malloc((size_t)(total ? total : 1) * sizeof(int));
            if (!O->bitem) return -5;
        }
        int *fill = pass ? malloc((size_t)nbb * nbb * sizeof(int)) : NULL;
        if (pass && !fill) return -5;
        if (pass) memcpy(fill, O->bstart, (size_t)nbb * nbb * sizeof(int));
        for (int s = 0; s < O->nbe; ++s) {
            const double *d = O->be + 4*s;
            int i0 = (int)floor(fmin(d[0], d[2]) * nbb), i1 = (int)floor(fmax(d[0], d[2]) * nbb);
            int j0 = (int)floor(fmin(d[1], d[3]) * nbb), j1 = (int)floor(fmax(d[1], d[3]) * nbb);
            if (i0 < 0) i0 = 0; if (j0 < 0) j0 = 0;
            if (i1 >= nbb) i1 = nbb - 1; if (j1 >= nbb) j1 = nbb - 1;
            for (int i = i0; i <= i1; ++i)
                for (int j = j0; j <= j1; ++j) {
                    if (pass == 0) O->bstart[i * nbb + j]++;
                    else O->bitem[fill[i * nbb + j]++] = s;
                }
        }
        free(fill);
    }
    return 0;
}

static double orient2(const double *a, const double *b, const double *c)
{
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
}

/* Clip segment p-q to triangle t (counter-clockwise); returns 1 with the part inside. */
static int clip_segment(const double t[3][2], const double *p, const double *q, double *a, double *b)
{
    double lo = 0.0, hi = 1.0;
    for (int e = 0; e < 3; ++e) {
        const double *u = t[e], *v = t[(e+1)%3];
        double dp = orient2(u, v, p), dq = orient2(u, v, q);   /* >= 0 inside */
        if (dp < 0 && dq < 0) return 0;
        if (dp < 0) { double s = dp / (dp - dq); if (s > lo) lo = s; }
        else if (dq < 0) { double s = dp / (dp - dq); if (s < hi) hi = s; }
    }
    if (hi - lo <= 1e-12) return 0;
    a[0] = p[0] + lo * (q[0] - p[0]); a[1] = p[1] + lo * (q[1] - p[1]);
    b[0] = p[0] + hi * (q[0] - p[0]); b[1] = p[1] + hi * (q[1] - p[1]);
    return 1;
}

/* Sutherland-Hodgman: polygon (n points, up to 9 after three cuts) inside the
 * counter-clockwise triangle c. */
static int clip_polygon(double poly[][2], int n, const double c[3][2])
{
    double tmp[12][2];
    for (int e = 0; e < 3 && n > 0; ++e) {
        const double *u = c[e], *v = c[(e+1)%3];
        int m = 0;
        for (int k = 0; k < n; ++k) {
            const double *s = poly[k], *t = poly[(k+1)%n];
            double ds = orient2(u, v, s), dt = orient2(u, v, t);
            if (ds >= 0) { tmp[m][0] = s[0]; tmp[m][1] = s[1]; m++; }
            if ((ds >= 0) != (dt >= 0)) {
                double r = ds / (ds - dt);
                tmp[m][0] = s[0] + r * (t[0] - s[0]); tmp[m][1] = s[1] + r * (t[1] - s[1]); m++;
            }
        }
        for (int k = 0; k < m; ++k) { poly[k][0] = tmp[k][0]; poly[k][1] = tmp[k][1]; }
        n = m;
    }
    return n;
}

static int overlay_triangle(Overlay *O, const double t[3][2])
{
    const vis3d_hull *h = O->h;
    int nbb = O->nbb, rc;
    double lo[2], hi[2];
    for (int d = 0; d < 2; ++d) {
        lo[d] = fmin(t[0][d], fmin(t[1][d], t[2][d]));
        hi[d] = fmax(t[0][d], fmax(t[1][d], t[2][d]));
    }
    /* boundary segments inside this triangle, drawn as seams */
    int crossed = 0;
    int i0 = (int)floor(lo[0] * nbb), i1 = (int)floor(hi[0] * nbb);
    int j0 = (int)floor(lo[1] * nbb), j1 = (int)floor(hi[1] * nbb);
    if (i0 < 0) i0 = 0; if (j0 < 0) j0 = 0;
    if (i1 >= nbb) i1 = nbb - 1; if (j1 >= nbb) j1 = nbb - 1;
    O->tick++;
    for (int i = i0; i <= i1; ++i)
        for (int j = j0; j <= j1; ++j)
            for (int k = O->bstart[i*nbb+j]; k < O->bstart[i*nbb+j+1]; ++k) {
                int s = O->bitem[k];
                double a[2], b[2];
                if (!clip_segment(t, O->be + 4*s, O->be + 4*s + 2, a, b)) continue;
                crossed = 1;
                if ((rc = soup_seg(O->S, a, b))) return rc;
            }
    if (!crossed) {
        double w[3], cx = (t[0][0] + t[1][0] + t[2][0]) / 3.0, cy = (t[0][1] + t[1][1] + t[2][1]) / 3.0;
        int f = locate(h, cx, cy, w);
        if (f < 0) { mqmqa_db_set_error("vis3d: no hull facet covers x2 = %.6f, x3 = %.6f", cx, cy); return -6; }
        return soup_tri(O->S, O->flab[f], t[0], t[1], t[2]);
    }
    /* the facets overlapping this triangle, each clipped to it */
    int nb = h->nb;
    int a0 = (int)floor(lo[0] * nb), a1 = (int)floor(hi[0] * nb);
    int b0 = (int)floor(lo[1] * nb), b1 = (int)floor(hi[1] * nb);
    if (a0 < 0) a0 = 0; if (b0 < 0) b0 = 0;
    if (a1 >= nb) a1 = nb - 1; if (b1 >= nb) b1 = nb - 1;
    for (int i = a0; i <= a1; ++i)
        for (int j = b0; j <= b1; ++j)
            for (int k = h->bin_start[i*nb+j]; k < h->bin_start[i*nb+j+1]; ++k) {
                int f = h->bin_item[k];
                if (O->stamp[f] == O->tick) continue;
                O->stamp[f] = O->tick;
                double c[3][2];
                for (int v = 0; v < 3; ++v) {
                    c[v][0] = h->R[3*h->facets[3*f+v]];
                    c[v][1] = h->R[3*h->facets[3*f+v]+1];
                }
                double o = orient2(c[0], c[1], c[2]);
                if (o == 0.0) continue;
                if (o < 0) { double t0 = c[1][0], t1 = c[1][1]; c[1][0] = c[2][0]; c[1][1] = c[2][1]; c[2][0] = t0; c[2][1] = t1; }
                if (fmax(c[0][0], fmax(c[1][0], c[2][0])) < lo[0] || fmin(c[0][0], fmin(c[1][0], c[2][0])) > hi[0] ||
                    fmax(c[0][1], fmax(c[1][1], c[2][1])) < lo[1] || fmin(c[0][1], fmin(c[1][1], c[2][1])) > hi[1])
                    continue;
                double poly[12][2];
                for (int v = 0; v < 3; ++v) { poly[v][0] = t[v][0]; poly[v][1] = t[v][1]; }
                int m = clip_polygon(poly, 3, (const double (*)[2])c);
                for (int v = 1; v + 1 < m; ++v)
                    if ((rc = soup_tri(O->S, O->flab[f], poly[0], poly[v], poly[v+1]))) return rc;
            }
    return 0;
}

/* Vertex dedupe inside one label. Neighbouring triangles clip the same boundary in a
 * different order and can land a hair apart, so coordinates are compared on a 2^-36 grid. */
typedef struct { int64_t x, y; int lab, id; } VKey;
static int cmp_vkey(const void *a, const void *b)
{
    const VKey *p = a, *q = b;
    if (p->lab != q->lab) return p->lab < q->lab ? -1 : 1;
    if (p->x != q->x) return p->x < q->x ? -1 : 1;
    if (p->y != q->y) return p->y < q->y ? -1 : 1;
    return 0;
}

static int uf_find(int *u, int a) { while (u[a] != a) { u[a] = u[u[a]]; a = u[a]; } return a; }

static int join_t_junctions(const Soup *S, const int *vid, int nv, int *uf, int nbin)
{
    double *vx = malloc((size_t)(nv ? nv : 1) * sizeof(double));
    double *vy = malloc((size_t)(nv ? nv : 1) * sizeof(double));
    int *vl = malloc((size_t)(nv ? nv : 1) * sizeof(int));
    int *start = calloc((size_t)nbin * nbin + 1, sizeof(int));
    int *item = malloc((size_t)(nv ? nv : 1) * sizeof(int));
    if (!vx || !vy || !vl || !start || !item) { free(vx); free(vy); free(vl); free(start); free(item); return -5; }
    for (int c = 0; c < 3 * S->nt; ++c) {
        vx[vid[c]] = S->v[2*c]; vy[vid[c]] = S->v[2*c+1]; vl[vid[c]] = S->lab[c / 3];
    }
#define BIN(x) ((int)((x) * nbin) < 0 ? 0 : (int)((x) * nbin) >= nbin ? nbin - 1 : (int)((x) * nbin))
    for (int v = 0; v < nv; ++v) start[BIN(vx[v]) * nbin + BIN(vy[v]) + 1]++;
    for (int b = 0; b < nbin * nbin; ++b) start[b + 1] += start[b];
    int *fill = malloc(((size_t)nbin * nbin + 1) * sizeof(int));
    if (!fill) { free(vx); free(vy); free(vl); free(start); free(item); return -5; }
    memcpy(fill, start, ((size_t)nbin * nbin + 1) * sizeof(int));
    for (int v = 0; v < nv; ++v) item[fill[BIN(vx[v]) * nbin + BIN(vy[v])]++] = v;
    free(fill);
    for (int t = 0; t < S->nt; ++t)
        for (int e = 0; e < 3; ++e) {
            int a = vid[3*t+e], b = vid[3*t+(e+1)%3], lab = S->lab[t];
            double ex = vx[b] - vx[a], ey = vy[b] - vy[a], L2 = ex*ex + ey*ey, L = sqrt(L2);
            int i0 = BIN(fmin(vx[a], vx[b])), i1 = BIN(fmax(vx[a], vx[b]));
            int j0 = BIN(fmin(vy[a], vy[b])), j1 = BIN(fmax(vy[a], vy[b]));
            for (int i = i0; i <= i1; ++i)
                for (int j = j0; j <= j1; ++j)
                    for (int s = start[i*nbin+j]; s < start[i*nbin+j+1]; ++s) {
                        int w = item[s];
                        if (w == a || w == b || vl[w] != lab) continue;
                        double wx = vx[w] - vx[a], wy = vy[w] - vy[a];
                        double cr = ex * wy - ey * wx, dt = ex * wx + ey * wy;
                        if (fabs(cr) <= 1e-12 * L && dt > 0 && dt < L2) {
                            int ra = uf_find(uf, a), rw = uf_find(uf, w);
                            if (ra != rw) uf[rw] = ra;
                        }
                    }
        }
#undef BIN
    free(vx); free(vy); free(vl); free(start); free(item);
    return 0;
}

static size_t align8(size_t s) { return (s + 7) & ~(size_t)7; }

void vis3d_free(VisMesh *m)
{
    if (!m) return;
    free(m->arena);
    memset(m, 0, sizeof *m);
}

int vis3d_section(const mqmqa_db *db, const char *const *phases, int n_phases,
                  double T, const VisOptions *opt_in, VisMesh *out)
{
    if (!out) { mqmqa_db_set_error("vis3d: no output mesh"); return -1; }
    memset(out, 0, sizeof *out);
    if (opt_in && (opt_in->lattice_n < 1 || opt_in->lattice_n > 2000)) {
        mqmqa_db_set_error("vis3d: lattice_n out of range");   /* before the costly hull */
        return -1;
    }
    vis3d_hull *h = vis3d_hull_build(db, phases, n_phases, T, opt_in);
    if (!h) return last_build_rc;   /* the reason is in mqmqa_db_error */
    int rc = vis3d_hull_section(h, opt_in, out);
    vis3d_hull_free(h);
    return rc;
}

int vis3d_hull_section(const vis3d_hull *h, const VisOptions *opt_in, VisMesh *out)
{
    if (!out) { mqmqa_db_set_error("vis3d: no output mesh"); return -1; }
    memset(out, 0, sizeof *out);
    if (!h) { mqmqa_db_set_error("vis3d: no hull"); return -1; }
    VisOptions opt;
    if (opt_in) opt = *opt_in; else vis3d_default_options(&opt);
    if (opt.lattice_n < 1 || opt.lattice_n > 2000) { mqmqa_db_set_error("vis3d: lattice_n out of range"); return -1; }
    const double T = h->T;

    int rc = 0, n = opt.lattice_n;
    Labels L = {0};
    Soup S = {0};
    Overlay O;
    VKey *keys = NULL; int *vid = NULL, *uf = NULL, *order = NULL, *pat = NULL;
    rc = overlay_build(&O, h, &L, &S, n);
    /* lattice triangles, counter-clockwise, node (i, j) at x2 = i/n, x3 = j/n */
    for (int i = 0; i < n && !rc; ++i)
        for (int j = 0; j < n - i && !rc; ++j) {
            double up[3][2] = {{(double)i/n, (double)j/n}, {(double)(i+1)/n, (double)j/n}, {(double)i/n, (double)(j+1)/n}};
            rc = overlay_triangle(&O, (const double (*)[2])up);
            if (!rc && i + j + 2 <= n) {
                double dn[3][2] = {{(double)(i+1)/n, (double)j/n}, {(double)(i+1)/n, (double)(j+1)/n}, {(double)i/n, (double)(j+1)/n}};
                rc = overlay_triangle(&O, (const double (*)[2])dn);
            }
        }
    overlay_free(&O);
    if (rc) { if (rc == -5) mqmqa_db_set_error("vis3d: out of memory"); goto done; }

    /* vertices: merge equal coordinates within a label, never across labels */
    int nc = 3 * S.nt;
    keys = malloc((size_t)(nc ? nc : 1) * sizeof(VKey));
    vid = malloc((size_t)(nc ? nc : 1) * sizeof(int));
    if (!keys || !vid) { rc = -5; mqmqa_db_set_error("vis3d: out of memory"); goto done; }
    for (int c = 0; c < nc; ++c) {
        keys[c].x = llround(S.v[2*c] * 68719476736.0); keys[c].y = llround(S.v[2*c+1] * 68719476736.0);
        keys[c].lab = S.lab[c / 3]; keys[c].id = c;
    }
    qsort(keys, (size_t)nc, sizeof(VKey), cmp_vkey);
    int nv = 0;
    for (int c = 0; c < nc; ++c) {
        if (c > 0 && cmp_vkey(&keys[c], &keys[c-1]) == 0) { vid[keys[c].id] = nv - 1; continue; }
        vid[keys[c].id] = nv++;
    }
    /* patches: connected components of triangles sharing a vertex */
    uf = malloc((size_t)(nv ? nv : 1) * sizeof(int));
    if (!uf) { rc = -5; mqmqa_db_set_error("vis3d: out of memory"); goto done; }
    for (int v = 0; v < nv; ++v) uf[v] = v;
    for (int t = 0; t < S.nt; ++t) {
        int a = uf_find(uf, vid[3*t]);
        for (int k = 1; k < 3; ++k) { int b = uf_find(uf, vid[3*t+k]); if (a != b) uf[b] = a; }
    }
    /* Where one triangle was subdivided and its neighbour was not, a vertex of one sits
     * inside an edge of the other (a T-junction) and they share no vertex; join them. */
    if ((rc = join_t_junctions(&S, vid, nv, uf, n))) { mqmqa_db_set_error("vis3d: out of memory"); goto done; }
    /* order triangles by (label, component) so each patch is one contiguous run */
    order = malloc((size_t)(S.nt ? S.nt : 1) * sizeof(int));
    pat = malloc((size_t)(nv ? nv : 1) * sizeof(int));
    if (!order || !pat) { rc = -5; mqmqa_db_set_error("vis3d: out of memory"); goto done; }
    for (int v = 0; v < nv; ++v) pat[v] = -1;
    int npatch = 0;
    int *root_patch = pat;   /* reused: patch id per component root */
    int *tri_patch = malloc((size_t)(S.nt ? S.nt : 1) * sizeof(int));
    int *patch_lab = malloc((size_t)(S.nt ? S.nt : 1) * sizeof(int));
    if (!tri_patch || !patch_lab) { free(tri_patch); free(patch_lab); rc = -5; mqmqa_db_set_error("vis3d: out of memory"); goto done; }
    for (int lab = 0; lab < L.n; ++lab)
        for (int t = 0; t < S.nt; ++t) {
            if (S.lab[t] != lab) continue;
            int r = uf_find(uf, vid[3*t]);
            if (root_patch[r] < 0) { root_patch[r] = npatch; patch_lab[npatch] = lab; npatch++; }
            tri_patch[t] = root_patch[r];
        }
    int *pcount = calloc((size_t)npatch + 1, sizeof(int));
    if (!pcount) { free(tri_patch); free(patch_lab); rc = -5; mqmqa_db_set_error("vis3d: out of memory"); goto done; }
    for (int t = 0; t < S.nt; ++t) pcount[tri_patch[t] + 1]++;
    for (int p = 0; p < npatch; ++p) pcount[p + 1] += pcount[p];
    {
        int *fill = malloc((size_t)(npatch ? npatch : 1) * sizeof(int));
        if (!fill) { free(tri_patch); free(patch_lab); free(pcount); rc = -5; mqmqa_db_set_error("vis3d: out of memory"); goto done; }
        for (int p = 0; p < npatch; ++p) fill[p] = pcount[p];
        for (int t = 0; t < S.nt; ++t) order[fill[tri_patch[t]]++] = t;
        free(fill);
    }

    /* one arena for the whole result */
    size_t o_pos = 0;
    size_t o_comp = align8(o_pos + (size_t)nv * 3 * sizeof(float));
    size_t o_temp = align8(o_comp + (size_t)nv * 3 * sizeof(double));
    size_t o_tri = align8(o_temp + (size_t)nv * sizeof(double));
    size_t o_pst = align8(o_tri + (size_t)S.nt * 3 * sizeof(uint32_t));
    size_t o_pph = align8(o_pst + (size_t)(npatch + 1) * sizeof(int32_t));
    size_t o_lpos = align8(o_pph + (size_t)npatch * sizeof(int32_t));
    size_t o_lst = align8(o_lpos + (size_t)S.ns * 2 * 3 * sizeof(float));
    size_t o_lab = align8(o_lst + (size_t)(S.ns + 1) * sizeof(int32_t));
    size_t total = o_lab + (size_t)L.n * LABEL_LEN;
    char *A = malloc(total ? total : 1);
    if (!A) { free(tri_patch); free(patch_lab); free(pcount); rc = -5; mqmqa_db_set_error("vis3d: out of memory"); goto done; }
    out->arena = A;
    out->pos = (float *)(A + o_pos);
    out->comp = (double *)(A + o_comp);
    out->temp = (double *)(A + o_temp);
    out->scalar = NULL;
    out->tri = (uint32_t *)(A + o_tri);
    out->patch_start = (int32_t *)(A + o_pst);
    out->patch_phase = (int32_t *)(A + o_pph);
    out->line_pos = (float *)(A + o_lpos);
    out->line_start = (int32_t *)(A + o_lst);
    out->label = (char (*)[64])(A + o_lab);
    out->n_vert = nv; out->n_tri = S.nt; out->n_patch = npatch;
    out->n_line = S.ns; out->n_line_pts = 2 * S.ns; out->n_label = L.n;

    /* vertices are renumbered in patch order so each patch's vertices are contiguous */
    int *remap = malloc((size_t)(nv ? nv : 1) * sizeof(int));
    if (!remap) { vis3d_free(out); free(tri_patch); free(patch_lab); free(pcount); rc = -5; mqmqa_db_set_error("vis3d: out of memory"); goto done; }
    for (int v = 0; v < nv; ++v) remap[v] = -1;
    int next = 0;
    double z = T * opt.z_per_kelvin;
    for (int k = 0; k < S.nt; ++k) {
        int t = order[k];
        for (int c = 0; c < 3; ++c) {
            int v = vid[3*t+c];
            if (remap[v] < 0) {
                remap[v] = next;
                double x2 = S.v[6*t+2*c], x3 = S.v[6*t+2*c+1], X, Y;
                vis3d_bary_to_xy(x2, x3, &X, &Y);
                out->pos[3*next] = (float)X; out->pos[3*next+1] = (float)Y; out->pos[3*next+2] = (float)z;
                out->comp[3*next] = 1.0 - x2 - x3; out->comp[3*next+1] = x2; out->comp[3*next+2] = x3;
                out->temp[next] = T;
                next++;
            }
            out->tri[3*k+c] = (uint32_t)remap[v];
        }
    }
    free(remap);
    for (int p = 0; p <= npatch; ++p) out->patch_start[p] = pcount[p];
    for (int p = 0; p < npatch; ++p) out->patch_phase[p] = patch_lab[p];
    for (int s = 0; s < S.ns; ++s) {
        for (int e = 0; e < 2; ++e) {
            double X, Y;
            vis3d_bary_to_xy(S.seg[4*s+2*e], S.seg[4*s+2*e+1], &X, &Y);
            out->line_pos[6*s+3*e] = (float)X; out->line_pos[6*s+3*e+1] = (float)Y;
            out->line_pos[6*s+3*e+2] = (float)z;
        }
        out->line_start[s] = 2 * s;
    }
    out->line_start[S.ns] = 2 * S.ns;
    for (int k = 0; k < L.n; ++k) memcpy(out->label[k], L.s[k], LABEL_LEN);
    free(tri_patch); free(patch_lab); free(pcount);

done:
    free(keys); free(vid); free(uf); free(order); free(pat);
    free(L.s); free(S.v); free(S.lab); free(S.seg);
    return rc;
}

/* ---- scalar accessors, so JavaScript never lays out the struct by hand ---- */

VisMesh *vis3d_mesh_new(void) { return calloc(1, sizeof(VisMesh)); }
void vis3d_mesh_delete(VisMesh *m) { if (m) { vis3d_free(m); free(m); } }
int vis3d_mesh_n_vert(const VisMesh *m) { return m->n_vert; }
int vis3d_mesh_n_tri(const VisMesh *m) { return m->n_tri; }
int vis3d_mesh_n_patch(const VisMesh *m) { return m->n_patch; }
int vis3d_mesh_n_line(const VisMesh *m) { return m->n_line; }
int vis3d_mesh_n_line_pts(const VisMesh *m) { return m->n_line_pts; }
int vis3d_mesh_n_label(const VisMesh *m) { return m->n_label; }
const float *vis3d_mesh_pos(const VisMesh *m) { return m->pos; }
const double *vis3d_mesh_comp(const VisMesh *m) { return m->comp; }
const double *vis3d_mesh_temp(const VisMesh *m) { return m->temp; }
const uint32_t *vis3d_mesh_tri(const VisMesh *m) { return m->tri; }
const int32_t *vis3d_mesh_patch_start(const VisMesh *m) { return m->patch_start; }
const int32_t *vis3d_mesh_patch_phase(const VisMesh *m) { return m->patch_phase; }
const float *vis3d_mesh_line_pos(const VisMesh *m) { return m->line_pos; }
const int32_t *vis3d_mesh_line_start(const VisMesh *m) { return m->line_start; }
const char *vis3d_mesh_label(const VisMesh *m, int k)
{
    return (k >= 0 && k < m->n_label) ? m->label[k] : NULL;
}

int vis3d_section_js(const mqmqa_db *db, const char *phase_list, double T, int lattice_n,
                     double x_tol, uint32_t seed, int max_refine, double z_per_kelvin,
                     VisMesh *out)
{
    VisOptions o;
    vis3d_default_options(&o);
    o.lattice_n = lattice_n; o.x_tol = x_tol; o.seed = seed; o.max_refine = max_refine;
    o.z_per_kelvin = z_per_kelvin;
    if (!phase_list || !*phase_list) return vis3d_section(db, NULL, 0, T, &o, out);
    /* comma-separated names */
    int n = 1;
    for (const char *p = phase_list; *p; ++p) n += *p == ',';
    char *buf = malloc(strlen(phase_list) + 1);
    const char **names = malloc((size_t)n * sizeof(char *));
    if (!buf || !names) { free(buf); free(names); mqmqa_db_set_error("vis3d: out of memory"); return -5; }
    strcpy(buf, phase_list);
    int k = 0;
    for (char *tok = buf, *c = buf; ; ++c) {
        if (*c == ',' || *c == '\0') {
            int end = *c == '\0';
            *c = '\0';
            names[k++] = tok;
            if (end) break;
            tok = c + 1;
        }
    }
    int rc = vis3d_section(db, names, k, T, &o, out);
    free(buf); free(names);
    return rc;
}
