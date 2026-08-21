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

double mqmqa_excess_energy_q_cation(
    int n_cat, int n_an, int n_quads,
    const int *quad_ca, const int *quad_cb,
    const int *quad_ax, const int *quad_ay,
    const double *X,
    const double *Zx, const double *Zy,
    int n_params,
    const int *par_A, const int *par_B, const int *par_X,
    const double *par_p, const double *par_q, const double *par_L)
{
    /* pair amounts n_ik (eq 5), needed for Xi = Y_ik = n_ik/4 (no chemical-group
     * expansion in this first cut). */
    double *nik = (double *)calloc((size_t)n_cat * (size_t)n_an, sizeof(double));
    for (int q = 0; q < n_quads; ++q) {
        const double xq = X[q];
        nik[(size_t)quad_ca[q] * n_an + quad_ax[q]] += xq;
        nik[(size_t)quad_ca[q] * n_an + quad_ay[q]] += xq;
        nik[(size_t)quad_cb[q] * n_an + quad_ax[q]] += xq;
        nik[(size_t)quad_cb[q] * n_an + quad_ay[q]] += xq;
    }

    double energy = 0.0;
    for (int k = 0; k < n_params; ++k) {
        const int A = par_A[k], B = par_B[k], Xn = par_X[k];
        const double p = par_p[k], qx = par_q[k];
        const double Xi_i = nik[(size_t)A * n_an + Xn] / 4.0;
        const double Xi_j = nik[(size_t)B * n_an + Xn] / 4.0;
        const double mix = pow(Xi_i, p) * pow(Xi_j, qx)
                           / pow(Xi_i + Xi_j, p + qx);
        const double g = par_L[k] * mix;

        const int qbase = find_quad(n_quads, quad_ca, quad_cb, quad_ax, quad_ay,
                                    A, B, Xn, Xn);
        const double Xbase = X[qbase];
        const double zX_base = z_anion(qbase, Xn, quad_ax, quad_ay, Zx, Zy);

        /* anion factor (X == Y branch), Poschmann eq 17: spread over other anions */
        double anion_factor = 0.0;
        for (int m = 0; m < n_an; ++m) {
            if (m == Xn) continue;
            const int qi = find_quad(n_quads, quad_ca, quad_cb, quad_ax, quad_ay,
                                     A, B, Xn, m);
            if (qi >= 0)
                anion_factor += X[qi] / z_anion(qi, Xn, quad_ax, quad_ay, Zx, Zy);
        }
        anion_factor *= zX_base / 2.0;

        energy += 0.5 * g * (Xbase + anion_factor);
    }

    free(nik);
    return energy;
}
