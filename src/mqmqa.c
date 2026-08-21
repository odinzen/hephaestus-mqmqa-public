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

        /* Only Q and G codes, and simple cation/anion mixing, are implemented.
         * Bragg-Williams (B/H), reciprocal (R), and reciprocal mixing return NaN
         * rather than a wrong number. */
        if (par_code[k] != 0 && par_code[k] != 1) return NAN;
        if (par_mix[k] != 0 && par_mix[k] != 1) return NAN;

        /* mixing term */
        double g;
        if (par_code[k] == 1) {                     /* G code, Chi_mix (Poschmann eq 21/23) */
            /* Single chemical group per sublattice, so the nu/gamma sums vanish and
             * Chi_i = X(i,i)/[X(i,i)+X(i,j)+X(j,j)] over the two mixing constituents. */
            int qii, qij, qjj;
            if (par_mix[k] == 0) {                  /* cation mixing over anion Xn */
                qii = find_quad(n_quads, quad_ca, quad_cb, quad_ax, quad_ay, A, A, Xn, Xn);
                qij = find_quad(n_quads, quad_ca, quad_cb, quad_ax, quad_ay, A, B, Xn, Xn);
                qjj = find_quad(n_quads, quad_ca, quad_cb, quad_ax, quad_ay, B, B, Xn, Xn);
            } else {                                /* anion mixing over cation A */
                qii = find_quad(n_quads, quad_ca, quad_cb, quad_ax, quad_ay, A, A, Xn, Xn);
                qij = find_quad(n_quads, quad_ca, quad_cb, quad_ax, quad_ay, A, A, Xn, Yn);
                qjj = find_quad(n_quads, quad_ca, quad_cb, quad_ax, quad_ay, A, A, Yn, Yn);
            }
            const double den = X[qii] + X[qij] + X[qjj];
            const double chi_i = X[qii] / den, chi_j = X[qjj] / den;
            g = par_L[k] * pow(chi_i, p) * pow(chi_j, qx);
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

/* ------------------------------------------------------------------ *
 * Single-phase equilibrium (constrained Gibbs minimization)
 *
 * The constraints are linear in X, so the feasible set is an affine subspace.
 * We reduce to unconstrained minimization over that subspace's coordinates and
 * run Nelder-Mead there. Small dense linear algebra (Gauss-Jordan) builds the
 * subspace; the reduced dimension is n_quads - rank, typically 1-3.
 * ------------------------------------------------------------------ */

/* Gauss-Jordan reduction of the augmented system [C | d] (m rows, n unknowns) to
 * reduced row echelon form, then read off one particular solution and a null-space
 * basis. Writes the particular solution to x0 (n) and stacks the null-space basis
 * vectors as columns 0..(*n_null-1) of Nspace (n rows by n columns, row-major).
 * Returns the rank, or -1 if the system is inconsistent. */
static int constraint_nullspace(const double *Cin, const double *d, int m, int n,
                                double *x0, double *Nspace, int *n_null)
{
    const double tol = 1e-12;
    double *M = (double *)malloc((size_t)m * (n + 1) * sizeof(double));
    int *pivcol = (int *)malloc((size_t)m * sizeof(int));
    if (!M || !pivcol) { free(M); free(pivcol); return -1; }
    for (int i = 0; i < m; ++i) {
        for (int j = 0; j < n; ++j) M[(size_t)i * (n + 1) + j] = Cin[(size_t)i * n + j];
        M[(size_t)i * (n + 1) + n] = d[i];
    }

    int rank = 0;
    for (int col = 0; col < n && rank < m; ++col) {
        int piv = -1;
        double best = tol;
        for (int r = rank; r < m; ++r) {
            const double v = fabs(M[(size_t)r * (n + 1) + col]);
            if (v > best) { best = v; piv = r; }
        }
        if (piv < 0) continue;                       /* free column */
        for (int j = 0; j <= n; ++j) {
            double t = M[(size_t)rank * (n + 1) + j];
            M[(size_t)rank * (n + 1) + j] = M[(size_t)piv * (n + 1) + j];
            M[(size_t)piv * (n + 1) + j] = t;
        }
        const double p = M[(size_t)rank * (n + 1) + col];
        for (int j = 0; j <= n; ++j) M[(size_t)rank * (n + 1) + j] /= p;
        for (int r = 0; r < m; ++r) {
            if (r == rank) continue;
            const double f = M[(size_t)r * (n + 1) + col];
            if (f == 0.0) continue;
            for (int j = 0; j <= n; ++j)
                M[(size_t)r * (n + 1) + j] -= f * M[(size_t)rank * (n + 1) + j];
        }
        pivcol[rank] = col;
        ++rank;
    }

    /* inconsistent if a pivot-free row still carries a nonzero right-hand side */
    for (int r = rank; r < m; ++r) {
        if (fabs(M[(size_t)r * (n + 1) + n]) > 1e-9) {
            free(M); free(pivcol); return -1;
        }
    }

    char *is_pivot = (char *)calloc((size_t)n, 1);
    for (int r = 0; r < rank; ++r) is_pivot[pivcol[r]] = 1;

    for (int j = 0; j < n; ++j) x0[j] = 0.0;
    for (int r = 0; r < rank; ++r)
        x0[pivcol[r]] = M[(size_t)r * (n + 1) + n];   /* free vars = 0 */

    int nn = 0;
    for (int f = 0; f < n; ++f) {
        if (is_pivot[f]) continue;
        double *v = Nspace + (size_t)nn * n;
        for (int j = 0; j < n; ++j) v[j] = 0.0;
        v[f] = 1.0;
        for (int r = 0; r < rank; ++r)
            v[pivcol[r]] = -M[(size_t)r * (n + 1) + f];
        double norm = 0.0;
        for (int j = 0; j < n; ++j) norm += v[j] * v[j];
        norm = sqrt(norm);
        if (norm > 0.0) for (int j = 0; j < n; ++j) v[j] /= norm;  /* unit t scale */
        ++nn;
    }
    *n_null = nn;

    free(is_pivot); free(M); free(pivcol);
    return rank;
}

/* Everything the objective needs to turn reduced coordinates t into an energy. */
typedef struct {
    double T;
    int n_cat, n_an, n_quads;
    const int *ca, *cb, *ax, *ay;
    const double *Za, *Zb, *Zx, *Zy, *zeta;
    int soln_type;
    int n_pairs;
    const int *pair_c, *pair_a;
    const double *Gax, *stoich, *Zref;
    int n_params;
    const int *par_mix, *par_code, *par_A, *par_B, *par_X, *par_Y;
    const double *par_p, *par_q, *par_L;
    const double *x0, *N;                            /* affine subspace X = x0 + N t */
    int n_null;
    double *Xbuf;                                    /* scratch, length n_quads */
} eqctx;

static void ctx_X_from_t(const eqctx *c, const double *t)
{
    for (int q = 0; q < c->n_quads; ++q) {
        double x = c->x0[q];
        for (int j = 0; j < c->n_null; ++j)
            x += c->N[(size_t)j * c->n_quads + q] * t[j];
        c->Xbuf[q] = x;
    }
}

static double ctx_gibbs_per_quad(const eqctx *c, const double *X)
{
    return mqmqa_reference_energy(c->n_quads, c->ca, c->cb, c->ax, c->ay, X,
                                  c->n_pairs, c->pair_c, c->pair_a,
                                  c->Gax, c->stoich, c->Zref)
         + mqmqa_ideal_mixing_energy(c->T, c->n_cat, c->n_an, c->n_quads,
                                     c->ca, c->cb, c->ax, c->ay, X,
                                     c->Za, c->Zb, c->Zx, c->Zy, c->zeta, c->soln_type)
         + mqmqa_excess_energy(c->n_cat, c->n_an, c->n_quads,
                               c->ca, c->cb, c->ax, c->ay, X,
                               c->Za, c->Zb, c->Zx, c->Zy,
                               c->n_params, c->par_mix, c->par_code,
                               c->par_A, c->par_B, c->par_X, c->par_Y,
                               c->par_p, c->par_q, c->par_L);
}

#define EQ_XMIN 1e-11

/* Phase-1 objective: the negated smallest quadruplet fraction. Minimizing it
 * maximizes min(X), driving toward the interior of the feasible segment (a
 * Chebyshev-style center) rather than stopping at the first feasible vertex,
 * which would strand the energy descent in a corner. */
static double obj_feasible(const double *t, void *vc)
{
    eqctx *c = (eqctx *)vc;
    ctx_X_from_t(c, t);
    double lo = c->Xbuf[0];
    for (int q = 1; q < c->n_quads; ++q)
        if (c->Xbuf[q] < lo) lo = c->Xbuf[q];
    return -lo;
}

/* Phase-2 objective: G_per_quad on the feasible subspace, with a large offset for
 * any bound violation so the simplex is driven back inside rather than into the
 * log-domain errors of the energy routines. */
static double obj_energy(const double *t, void *vc)
{
    eqctx *c = (eqctx *)vc;
    ctx_X_from_t(c, t);
    double viol = 0.0;
    for (int q = 0; q < c->n_quads; ++q)
        if (c->Xbuf[q] < EQ_XMIN) viol += (EQ_XMIN - c->Xbuf[q]);
    if (viol > 0.0) return 1e12 + 1e6 * viol;
    return ctx_gibbs_per_quad(c, c->Xbuf);
}

typedef double (*eq_objfn)(const double *t, void *ctx);

/* Nelder-Mead simplex minimization of f over k reduced coordinates, refining t
 * in place. Small k (1-3 here), so the O(k^2) bookkeeping is negligible. */
static void nelder_mead(eq_objfn f, void *ctx, int k, double *t,
                        double step, int maxiter, double tol)
{
    if (k <= 0) return;
    const int np = k + 1;
    double *pts = (double *)malloc((size_t)np * k * sizeof(double));
    double *fv = (double *)malloc((size_t)np * sizeof(double));
    double *cen = (double *)malloc((size_t)k * sizeof(double));
    double *xr = (double *)malloc((size_t)k * sizeof(double));
    double *xe = (double *)malloc((size_t)k * sizeof(double));
    if (!pts || !fv || !cen || !xr || !xe) {
        free(pts); free(fv); free(cen); free(xr); free(xe); return;
    }

    for (int i = 0; i < np; ++i) {
        for (int j = 0; j < k; ++j) pts[(size_t)i * k + j] = t[j];
        if (i > 0) pts[(size_t)i * k + (i - 1)] += step;
        fv[i] = f(&pts[(size_t)i * k], ctx);
    }

    for (int iter = 0; iter < maxiter; ++iter) {
        /* order the simplex: index of best (lo), worst (hi), second worst (nh) */
        int lo = 0, hi = 0, nh = -1;
        for (int i = 1; i < np; ++i) {
            if (fv[i] < fv[lo]) lo = i;
            if (fv[i] > fv[hi]) hi = i;
        }
        for (int i = 0; i < np; ++i)
            if (i != hi && (nh < 0 || fv[i] > fv[nh])) nh = i;

        if (fabs(fv[hi] - fv[lo]) <= tol * (fabs(fv[lo]) + tol)) break;

        for (int j = 0; j < k; ++j) {
            double s = 0.0;
            for (int i = 0; i < np; ++i) if (i != hi) s += pts[(size_t)i * k + j];
            cen[j] = s / k;
        }

        for (int j = 0; j < k; ++j) xr[j] = cen[j] + (cen[j] - pts[(size_t)hi * k + j]);
        double fr = f(xr, ctx);

        if (fr < fv[lo]) {                           /* expand */
            for (int j = 0; j < k; ++j) xe[j] = cen[j] + 2.0 * (xr[j] - cen[j]);
            double fe = f(xe, ctx);
            const double *src = (fe < fr) ? xe : xr;
            const double fbest = (fe < fr) ? fe : fr;
            for (int j = 0; j < k; ++j) pts[(size_t)hi * k + j] = src[j];
            fv[hi] = fbest;
        } else if (fr < fv[nh]) {                    /* accept reflection */
            for (int j = 0; j < k; ++j) pts[(size_t)hi * k + j] = xr[j];
            fv[hi] = fr;
        } else {                                     /* contract */
            for (int j = 0; j < k; ++j) xe[j] = cen[j] + 0.5 * (pts[(size_t)hi * k + j] - cen[j]);
            double fc = f(xe, ctx);
            if (fc < fv[hi]) {
                for (int j = 0; j < k; ++j) pts[(size_t)hi * k + j] = xe[j];
                fv[hi] = fc;
            } else {                                 /* shrink toward best */
                for (int i = 0; i < np; ++i) {
                    if (i == lo) continue;
                    for (int j = 0; j < k; ++j)
                        pts[(size_t)i * k + j] = pts[(size_t)lo * k + j]
                            + 0.5 * (pts[(size_t)i * k + j] - pts[(size_t)lo * k + j]);
                    fv[i] = f(&pts[(size_t)i * k], ctx);
                }
            }
        }
    }

    int lo = 0;
    for (int i = 1; i < np; ++i) if (fv[i] < fv[lo]) lo = i;
    for (int j = 0; j < k; ++j) t[j] = pts[(size_t)lo * k + j];

    free(pts); free(fv); free(cen); free(xr); free(xe);
}

double mqmqa_equilibrate(
    double T,
    int n_cat, int n_an, int n_quads,
    const int *quad_ca, const int *quad_cb,
    const int *quad_ax, const int *quad_ay,
    const double *Za, const double *Zb, const double *Zx, const double *Zy,
    const double *zeta,
    int soln_type,
    int n_pairs,
    const int *pair_c, const int *pair_a,
    const double *Gax, const double *stoich,
    const double *Zref,
    int n_params,
    const int *par_mix, const int *par_code,
    const int *par_A, const int *par_B, const int *par_X, const int *par_Y,
    const double *par_p, const double *par_q, const double *par_L,
    int n_elem,
    const int *cat_elem, const int *an_elem,
    const double *target,
    double *X_out, double *comp_err_out)
{
    /* per-element linear coefficients E[e][q] and atoms-per-quadruplet A[q] */
    double *E = (double *)calloc((size_t)n_elem * n_quads, sizeof(double));
    double *A = (double *)calloc((size_t)n_quads, sizeof(double));
    if (!E || !A) { free(E); free(A); return NAN; }
    for (int q = 0; q < n_quads; ++q) {
        const double ia = 1.0 / Za[q], ib = 1.0 / Zb[q];
        const double ix = 1.0 / Zx[q], iy = 1.0 / Zy[q];
        E[(size_t)cat_elem[quad_ca[q]] * n_quads + q] += ia;
        E[(size_t)cat_elem[quad_cb[q]] * n_quads + q] += ib;
        E[(size_t)an_elem[quad_ax[q]] * n_quads + q] += ix;
        E[(size_t)an_elem[quad_ay[q]] * n_quads + q] += iy;
        A[q] = ia + ib + ix + iy;
    }

    /* Constraint rows: one per element fixing X_e = target_e (the element-fraction
     * rows sum to the normalization, so one element row is dropped as redundant),
     * plus the explicit normalization sum(X) = 1 as the last row. */
    const int m = n_elem;                            /* (n_elem - 1) element rows + 1 */
    double *C = (double *)calloc((size_t)m * n_quads, sizeof(double));
    double *d = (double *)calloc((size_t)m, sizeof(double));
    if (!C || !d) { free(E); free(A); free(C); free(d); return NAN; }
    for (int e = 0; e < n_elem - 1; ++e) {
        for (int q = 0; q < n_quads; ++q)
            C[(size_t)e * n_quads + q] = E[(size_t)e * n_quads + q] - target[e] * A[q];
        d[e] = 0.0;
    }
    for (int q = 0; q < n_quads; ++q) C[(size_t)(m - 1) * n_quads + q] = 1.0;
    d[m - 1] = 1.0;

    double *x0 = (double *)malloc((size_t)n_quads * sizeof(double));
    double *N = (double *)malloc((size_t)n_quads * n_quads * sizeof(double));
    if (!x0 || !N) { free(E); free(A); free(C); free(d); free(x0); free(N); return NAN; }
    int n_null = 0;
    const int rank = constraint_nullspace(C, d, m, n_quads, x0, N, &n_null);
    free(C); free(d);
    if (rank < 0) { free(E); free(A); free(x0); free(N); return NAN; }

    eqctx ctx = {
        T, n_cat, n_an, n_quads,
        quad_ca, quad_cb, quad_ax, quad_ay,
        Za, Zb, Zx, Zy, zeta, soln_type,
        n_pairs, pair_c, pair_a, Gax, stoich, Zref,
        n_params, par_mix, par_code, par_A, par_B, par_X, par_Y,
        par_p, par_q, par_L,
        x0, N, n_null,
        (double *)malloc((size_t)n_quads * sizeof(double)),
    };
    if (!ctx.Xbuf) { free(E); free(A); free(x0); free(N); return NAN; }

    double gm = NAN;
    if (n_null == 0) {
        ctx_X_from_t(&ctx, NULL);                    /* unique solution */
    } else {
        double *t = (double *)calloc((size_t)n_null, sizeof(double));
        if (!t) { free(ctx.Xbuf); free(E); free(A); free(x0); free(N); return NAN; }

        /* Phase 1: reach a strictly interior feasible point. */
        nelder_mead(obj_feasible, &ctx, n_null, t, 0.1, 4000, 1e-16);
        /* Phase 2: descend the energy, restarting the simplex to sharpen it. */
        for (int r = 0; r < 4; ++r)
            nelder_mead(obj_energy, &ctx, n_null, t, 0.05, 4000, 1e-12);
        ctx_X_from_t(&ctx, t);
        free(t);
    }

    /* Clamp roundoff-negative fractions to zero before the final evaluation: the
     * energy routines skip zero-weight quadruplets, so this keeps a fraction left
     * a hair below zero by the minimizer from poisoning G with a log of a negative. */
    for (int q = 0; q < n_quads; ++q)
        if (ctx.Xbuf[q] < 0.0) ctx.Xbuf[q] = 0.0;

    /* GM per mole of atoms; report the worst element mole-fraction error. */
    double n_atoms = 0.0;
    for (int q = 0; q < n_quads; ++q) n_atoms += ctx.Xbuf[q] * A[q];
    if (n_atoms > 0.0) {
        double worst = 0.0;
        for (int e = 0; e < n_elem; ++e) {
            double xe = 0.0;
            for (int q = 0; q < n_quads; ++q) xe += ctx.Xbuf[q] * E[(size_t)e * n_quads + q];
            const double err = fabs(xe / n_atoms - target[e]);
            if (err > worst) worst = err;
        }
        if (comp_err_out) *comp_err_out = worst;
        gm = ctx_gibbs_per_quad(&ctx, ctx.Xbuf) / n_atoms;
    }

    if (X_out) for (int q = 0; q < n_quads; ++q) X_out[q] = ctx.Xbuf[q];

    free(ctx.Xbuf); free(E); free(A); free(x0); free(N);
    return gm;
}
