#include "mqmqa.h"
#include <math.h>
#include <stddef.h>
#include <stdlib.h>

/* CALPHAD/SGTE conventional gas constant, matching pycalphad's v.R and the value
 * used to assess every SGTE database. NOT the CODATA 2018 value; using CODATA here
 * would make energies inconsistent with the databases this engine reads. */
#define MQMQA_R_CONST 8.3145

double mqmqa_R(void)
{
    return MQMQA_R_CONST;
}

double mqmqa_ideal_entropy_binary(double x)
{
    if (x <= 0.0 || x >= 1.0) {
        return 0.0; /* endpoints: pure, zero configurational entropy */
    }
    return -MQMQA_R_CONST * (x * log(x) + (1.0 - x) * log(1.0 - x));
}

double mqmqa_reference_energy(
    int n_quads,
    const int *quad_ca, const int *quad_cb,
    const int *quad_ax, const int *quad_ay,
    const double *X,
    int n_pairs,
    const int *pair_c, const int *pair_a,
    const double *Gax, const double *stoich,
    const double *Z)
{
    double total = 0.0;
    for (int p = 0; p < n_pairs; ++p) {
        const int a = pair_c[p];
        const int x = pair_a[p];
        const double *Zp = Z + (size_t)p * (size_t)n_quads;
        double Xax = 0.0;
        for (int q = 0; q < n_quads; ++q) {
            const int cnt_a = (quad_ca[q] == a) + (quad_cb[q] == a);
            const int cnt_x = (quad_ax[q] == x) + (quad_ay[q] == x);
            if (cnt_a != 0 && cnt_x != 0) {
                Xax += X[q] * (double)(cnt_a * cnt_x) / (2.0 * Zp[q]);
            }
        }
        total += Xax * Gax[p] / stoich[p];
    }
    return total;
}

double mqmqa_ideal_mixing_energy(
    double T,
    int n_cat, int n_an, int n_quads,
    const int *quad_ca, const int *quad_cb,
    const int *quad_ax, const int *quad_ay,
    const double *X,
    const double *Za, const double *Zb, const double *Zx, const double *Zy,
    const double *zeta,
    int soln_type)
{
    const int subq = (soln_type == 1);
    const double pow_Xik = subq ? 0.75 : 1.0;
    const double pow_Yi = subq ? 0.50 : 1.0;

    double *ni_c = (double *)calloc((size_t)n_cat, sizeof(double));
    double *ni_a = (double *)calloc((size_t)n_an, sizeof(double));
    double *Yc = (double *)calloc((size_t)n_cat, sizeof(double));
    double *Ya = (double *)calloc((size_t)n_an, sizeof(double));
    double *nik = (double *)calloc((size_t)n_cat * (size_t)n_an, sizeof(double));

    /* moles of species (eq 7,8), site-equivalent fractions Y (eq 11,12), and pair
     * amounts n_ik (eq 5), all by accumulating each quadruplet slot in turn. */
    for (int q = 0; q < n_quads; ++q) {
        const int ca = quad_ca[q], cb = quad_cb[q], ax = quad_ax[q], ay = quad_ay[q];
        const double xq = X[q];
        ni_c[ca] += xq / Za[q];
        ni_c[cb] += xq / Zb[q];
        ni_a[ax] += xq / Zx[q];
        ni_a[ay] += xq / Zy[q];
        Yc[ca] += 0.5 * xq;
        Yc[cb] += 0.5 * xq;
        Ya[ax] += 0.5 * xq;
        Ya[ay] += 0.5 * xq;
        nik[(size_t)ca * n_an + ax] += xq;
        nik[(size_t)ca * n_an + ay] += xq;
        nik[(size_t)cb * n_an + ax] += xq;
        nik[(size_t)cb * n_an + ay] += xq;
    }

    double sum_nc = 0.0, sum_na = 0.0, sum_nik = 0.0, sum_niks = 0.0;
    for (int i = 0; i < n_cat; ++i) sum_nc += ni_c[i];
    for (int k = 0; k < n_an; ++k) sum_na += ni_a[k];
    double *niks = (double *)calloc((size_t)n_cat * (size_t)n_an, sizeof(double));
    for (int i = 0; i < n_cat; ++i) {
        for (int k = 0; k < n_an; ++k) {
            const size_t ik = (size_t)i * n_an + k;
            niks[ik] = nik[ik] / zeta[ik];
            sum_nik += nik[ik];
            sum_niks += niks[ik];
        }
    }

    /* F_i coordination-equivalent fractions (eq 13,14): sums of the pair fractions
     * (star for SUBQ, plain for SUBG). */
    double *Fc = (double *)calloc((size_t)n_cat, sizeof(double));
    double *Fa = (double *)calloc((size_t)n_an, sizeof(double));
    for (int i = 0; i < n_cat; ++i) {
        for (int k = 0; k < n_an; ++k) {
            const size_t ik = (size_t)i * n_an + k;
            const double xik = subq ? (niks[ik] / sum_niks) : (nik[ik] / sum_nik);
            Fc[i] += xik;
            Fa[k] += xik;
        }
    }

    double Sid = 0.0;
    for (int i = 0; i < n_cat; ++i)
        if (ni_c[i] > 0.0) Sid += ni_c[i] * log(ni_c[i] / sum_nc);
    for (int k = 0; k < n_an; ++k)
        if (ni_a[k] > 0.0) Sid += ni_a[k] * log(ni_a[k] / sum_na);

    for (int i = 0; i < n_cat; ++i) {
        for (int k = 0; k < n_an; ++k) {
            const size_t ik = (size_t)i * n_an + k;
            const double npair = subq ? niks[ik] : nik[ik];
            if (npair > 0.0) {
                const double xik = subq ? (niks[ik] / sum_niks) : (nik[ik] / sum_nik);
                Sid += npair * log(xik / (Fc[i] * Fa[k]));
            }
        }
    }

    for (int q = 0; q < n_quads; ++q) {
        const double xq = X[q];
        if (xq <= 0.0) continue;
        const int ca = quad_ca[q], cb = quad_cb[q], ax = quad_ax[q], ay = quad_ay[q];
        const double C = (2.0 - (ca == cb)) * (2.0 - (ax == ay));
        const double xik_ca_ax = nik[(size_t)ca * n_an + ax] / sum_nik;
        const double xik_ca_ay = nik[(size_t)ca * n_an + ay] / sum_nik;
        const double xik_cb_ax = nik[(size_t)cb * n_an + ax] / sum_nik;
        const double xik_cb_ay = nik[(size_t)cb * n_an + ay] / sum_nik;
        const double prodXik = xik_ca_ax * xik_ca_ay * xik_cb_ax * xik_cb_ay;
        const double prodY = Yc[ca] * Yc[cb] * Ya[ax] * Ya[ay];
        const double inner = C * pow(prodXik, pow_Xik) / pow(prodY, pow_Yi);
        Sid += xq * log(xq / inner);
    }

    free(ni_c); free(ni_a); free(Yc); free(Ya);
    free(nik); free(niks); free(Fc); free(Fa);
    return Sid * T * MQMQA_R_CONST;
}

/* Find the index of the canonical quadruplet with cation pair {a,b} and anion
 * pair {x,y}; -1 if absent. Quadruplet lists are stored sorted, so match by the
 * sorted pair. */
static int find_quad(int n_quads,
                     const int *ca, const int *cb, const int *ax, const int *ay,
                     int a, int b, int x, int y)
{
    const int clo = a < b ? a : b, chi = a < b ? b : a;
    const int xlo = x < y ? x : y, xhi = x < y ? y : x;
    for (int q = 0; q < n_quads; ++q) {
        if (ca[q] == clo && cb[q] == chi && ax[q] == xlo && ay[q] == xhi)
            return q;
    }
    return -1;
}

/* Coordination of anion index s in quadruplet q (its two anion slots). */
static double z_anion(int q, int s, const int *ax, const int *ay,
                      const double *Zx, const double *Zy)
{
    if (ax[q] == s) return Zx[q];
    if (ay[q] == s) return Zy[q];
    return 1.0; /* unreachable when s is in the quad */
}

/* Coordination of cation index s in quadruplet q (its two cation slots). */
static double z_cation(int q, int s, const int *ca, const int *cb,
                       const double *Za, const double *Zb)
{
    if (ca[q] == s) return Za[q];
    if (cb[q] == s) return Zb[q];
    return 1.0; /* unreachable when s is in the quad */
}

/* Excess energy for a set of MQMX interaction parameters, J per mole of quadruplets
 * (Poschmann eqs 19,20,24 for the mixing term, eq 17 for the assembly). Handles the
 * Q mixing code (cation and anion mixing) and the G code with zero exponents
 * (mixing term = 1). Assumes each mixing sublattice is a single chemical group, so
 * the nu/gamma expansion is empty (true for the databases targeted first).
 *
 * Per parameter k: par_mix = 0 for cation mixing (A != B, single anion X = Y),
 * 1 for anion mixing (single cation A = B, anions X != Y). par_code = 0 for Q,
 * 1 for G. For cation mixing par_A,par_B are the mixing cations and par_X the
 * anion; for anion mixing par_A is the cation and par_X,par_Y the mixing anions.
 */
double mqmqa_excess_energy(
    int n_cat, int n_an, int n_quads,
    const int *quad_ca, const int *quad_cb,
    const int *quad_ax, const int *quad_ay,
    const double *X,
    const double *Za, const double *Zb, const double *Zx, const double *Zy,
    int n_params,
    const int *par_mix, const int *par_code,
    const int *par_A, const int *par_B, const int *par_X, const int *par_Y,
    const double *par_p, const double *par_q, const double *par_L)
{
    double *nik = (double *)calloc((size_t)n_cat * (size_t)n_an, sizeof(double));
    for (int q = 0; q < n_quads; ++q) {
        const double xq = X[q];
        nik[(size_t)quad_ca[q] * n_an + quad_ax[q]] += xq;
        nik[(size_t)quad_ca[q] * n_an + quad_ay[q]] += xq;
        nik[(size_t)quad_cb[q] * n_an + quad_ax[q]] += xq;
        nik[(size_t)quad_cb[q] * n_an + quad_ay[q]] += xq;
    }
#define NIK(i, k) nik[(size_t)(i) * n_an + (k)]

    double energy = 0.0;
    for (int k = 0; k < n_params; ++k) {
        const int A = par_A[k], B = par_B[k], Xn = par_X[k], Yn = par_Y[k];
        const double p = par_p[k], qx = par_q[k];

        /* mixing term */
        double g;
        if (par_code[k] == 1) {                     /* G code */
            if (p != 0.0 || qx != 0.0)
                return NAN;    /* nonzero-exponent G needs Chi_mix, not yet implemented */
            g = par_L[k];                           /* zero exponents: mixing term is 1 */
        } else {                                    /* Q code, eq 24 */
            double Xi_i, Xi_j;
            if (par_mix[k] == 0) {                  /* cation mixing: Xi over anion Xn */
                Xi_i = NIK(A, Xn) / 4.0;
                Xi_j = NIK(B, Xn) / 4.0;
            } else {                                /* anion mixing: Xi over cation A */
                Xi_i = NIK(A, Xn) / 4.0;
                Xi_j = NIK(A, Yn) / 4.0;
            }
            const double mix = pow(Xi_i, p) * pow(Xi_j, qx)
                               / pow(Xi_i + Xi_j, p + qx);
            g = par_L[k] * mix;
        }

        const int qbase = find_quad(n_quads, quad_ca, quad_cb, quad_ax, quad_ay,
                                    A, B, Xn, Yn);
        const double Xbase = X[qbase];

        /* cation factor (A == B branch): spread over other cations */
        double cation_factor = 0.0;
        if (A == B) {
            for (int m = 0; m < n_cat; ++m) {
                if (m == A) continue;
                const int qi = find_quad(n_quads, quad_ca, quad_cb, quad_ax, quad_ay,
                                         A, m, Xn, Yn);
                if (qi >= 0)
                    cation_factor += X[qi] / z_cation(qi, A, quad_ca, quad_cb, Za, Zb);
            }
            cation_factor *= z_cation(qbase, A, quad_ca, quad_cb, Za, Zb) / 2.0;
        }

        /* anion factor (X == Y branch): spread over other anions */
        double anion_factor = 0.0;
        if (Xn == Yn) {
            for (int m = 0; m < n_an; ++m) {
                if (m == Xn) continue;
                const int qi = find_quad(n_quads, quad_ca, quad_cb, quad_ax, quad_ay,
                                         A, B, Xn, m);
                if (qi >= 0)
                    anion_factor += X[qi] / z_anion(qi, Xn, quad_ax, quad_ay, Zx, Zy);
            }
            anion_factor *= z_anion(qbase, Xn, quad_ax, quad_ay, Zx, Zy) / 2.0;
        }

        energy += 0.5 * g * (Xbase + cation_factor + anion_factor);
    }
#undef NIK

    free(nik);
    return energy;
}

/* ------------------------------------------------------------------ *
 * Coordination numbers Z (Pelton, Chartrand, Eriksson 2001, eqs 23-24)
 *
 * Pure-pair coordinations (A==B, X==Y) are read from the database's MQMZ
 * parameters; mixed and reciprocal quadruplets are computed recursively from
 * them. The recursion always reduces toward pure pairs, which are the base case.
 * ------------------------------------------------------------------ */

typedef struct {
    int n_cat, n_an;
    const double *qc, *qa;                   /* |charges| */
    int n_mqmz;
    const int *mA, *mB, *mX, *mY;            /* canonical (A<=B, X<=Y) indices */
    const double *mZ;                        /* [n_mqmz*4], slots A,B,X,Y */
} zctx;

static int mqmz_lookup(const zctx *c, int A, int B, int X, int Y)
{
    for (int i = 0; i < c->n_mqmz; ++i)
        if (c->mA[i] == A && c->mB[i] == B && c->mX[i] == X && c->mY[i] == Y)
            return i;
    return -1;
}

static double z_calc(const zctx *c, int sp_cat, int sp, int A, int B, int X, int Y);

static double z_get(const zctx *c, int sp_cat, int sp, int A, int B, int X, int Y)
{
    if (A > B) { int t = A; A = B; B = t; }
    if (X > Y) { int t = X; X = Y; Y = t; }
    const int idx = mqmz_lookup(c, A, B, X, Y);
    if (idx >= 0) {
        const int slot = sp_cat ? (sp == A ? 0 : 1) : (sp == X ? 2 : 3);
        return c->mZ[(size_t)idx * 4 + slot];
    }
    return z_calc(c, sp_cat, sp, A, B, X, Y);
}

static double z_calc(const zctx *c, int sp_cat, int sp, int A, int B, int X, int Y)
{
    if (A == B && X == Y)
        return NAN;                          /* pure pair must be an MQMZ parameter */

    if (A != B && X != Y) {                  /* reciprocal, eqs 23-24 */
        const double F = 0.125 * (
            c->qc[A] / z_get(c, 1, A, A, A, X, Y)
            + c->qc[B] / z_get(c, 1, B, B, B, X, Y)
            + c->qa[X] / z_get(c, 0, X, A, B, X, X)
            + c->qa[Y] / z_get(c, 0, Y, A, B, Y, Y));
        double inv;
        if (sp_cat) {
            inv = F * (
                z_get(c, 0, X, A, B, X, X) / (c->qa[X] * z_get(c, 1, sp, A, B, X, X))
                + z_get(c, 0, Y, A, B, Y, Y) / (c->qa[Y] * z_get(c, 1, sp, A, B, Y, Y)));
        } else {
            inv = F * (
                z_get(c, 1, A, A, A, X, Y) / (c->qc[A] * z_get(c, 0, sp, A, A, X, Y))
                + z_get(c, 1, B, B, B, X, Y) / (c->qc[B] * z_get(c, 0, sp, B, B, X, Y)));
        }
        return 1.0 / inv;
    }

    if (A != B) {                            /* X == Y */
        if (sp_cat)
            return z_get(c, 1, sp, sp, sp, X, X);
        return 2.0 * c->qa[sp] / (
            c->qc[A] / z_get(c, 1, A, A, A, sp, sp)
            + c->qc[B] / z_get(c, 1, B, B, B, sp, sp));
    }

    /* A == B, X != Y */
    if (sp_cat)
        return 2.0 * c->qc[sp] / (
            c->qa[X] / z_get(c, 0, X, sp, sp, X, X)
            + c->qa[Y] / z_get(c, 0, Y, sp, sp, Y, Y));
    return z_get(c, 0, sp, A, A, sp, sp);
}

double mqmqa_coordination(
    int sp_is_cation, int sp_idx,
    int A, int B, int X, int Y,
    int n_cat, int n_an,
    const double *q_cat, const double *q_an,
    int n_mqmz,
    const int *mz_A, const int *mz_B, const int *mz_X, const int *mz_Y,
    const double *mz_Z)
{
    (void)n_cat; (void)n_an;
    zctx c = {n_cat, n_an, q_cat, q_an, n_mqmz, mz_A, mz_B, mz_X, mz_Y, mz_Z};
    return z_get(&c, sp_is_cation, sp_idx, A, B, X, Y);
}
