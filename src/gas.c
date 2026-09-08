/* Ideal-gas equilibrium from NASA 7-coefficient polynomials. See gas.h.
 *
 * Element-potential (RAND/CEA) method: at fixed T and P the equilibrium mole
 * numbers satisfy ln(n_i/n_tot) + G_i(T)/RT + ln(P/P0) = sum_e a_ie * pi_e, with
 * pi the element chemical potentials over RT. Newton on the element balance gives
 * a positive-definite Gram system for pi; an outer fixed point on total moles
 * carries the pressure term. This is the exact algorithm validated in
 * python/mqmqa/gas.py against Cantera to 1e-10 mole fraction.
 */
#include "gas.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define GAS_NAME 24
#define GAS_MAXEL 96
#define P_REF 101325.0
#define GAS_R 8.314462618
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

typedef struct {
    char name[GAS_NAME];
    int nel;                 /* distinct elements in this species */
    int el[8];               /* element indices */
    double cnt[8];           /* atom counts */
    double t_lo, t_mid, t_hi;
    double low[7], high[7];
    double tc, pc, omega;    /* critical constants for the Peng-Robinson EOS */
    int has_crit;            /* 1 if tc/pc/omega set (else the species stays ideal) */
} GasSpecies;

/* Critical constants Tc (K), Pc (bar), acentric factor for the shipped species,
 * from the standard compilations (Poling, Prausnitz & O'Connell, "The Properties
 * of Gases and Liquids", 5th ed.; NIST WebBook). Radicals (H, O, OH, HO2) have no
 * meaningful critical point and are left ideal. Read, not fitted. */
static const struct { const char *name; double tc, pc_bar, omega; } CRIT[] = {
    {"CO",  132.86, 34.99, 0.048}, {"CO2", 304.13, 73.77, 0.225},
    {"H2",   33.15, 12.96, -0.219}, {"H2O", 647.10, 220.64, 0.344},
    {"O2",  154.58, 50.43, 0.022}, {"N2",  126.19, 33.96, 0.037},
    {"CH4", 190.56, 45.99, 0.011}, {"H2O2", 728.00, 220.00, 0.358},
    {"NO",  180.00, 64.80, 0.582}, {"NO2", 431.00, 101.30, 0.834},
    {"C2H2", 308.30, 61.38, 0.187}, {"C2H4", 282.34, 50.41, 0.087},
};

struct gas_db {
    int n_sp;
    GasSpecies *sp;
    int n_el;
    char (*el)[4];           /* element symbols */
};

static char g_err[160];

const char *mqmqa_gas_error(void) { return g_err; }

static int el_index(gas_db *g, const char *sym)
{
    for (int e = 0; e < g->n_el; ++e)
        if (strcmp(g->el[e], sym) == 0) return e;
    if (g->n_el >= GAS_MAXEL) return -1;
    snprintf(g->el[g->n_el], 4, "%s", sym);
    return g->n_el++;
}

/* read a fixed-width scientific field (15 chars) */
static double field15(const char *line, int start)
{
    char buf[16];
    memcpy(buf, line + start, 15);
    buf[15] = '\0';
    return atof(buf);
}

static void trim(char *s)
{
    int n = (int)strlen(s);
    while (n > 0 && (s[n - 1] == ' ' || s[n - 1] == '\r' || s[n - 1] == '\n' || s[n - 1] == '\t'))
        s[--n] = '\0';
}

/* copy one physical line (up to newline) into buf; returns advance or -1 at end */
static int getline_at(const char *text, int pos, char *buf, int cap)
{
    int i = 0;
    memset(buf, 0, (size_t)cap);   /* fixed-column reads on short lines see zeros,
                                      never uninitialized stack */
    if (!text[pos]) return -1;
    while (text[pos + i] && text[pos + i] != '\n' && i < cap - 1) {
        buf[i] = text[pos + i];
        ++i;
    }
    buf[i] = '\0';
    int adv = i;
    if (text[pos + adv] == '\n') ++adv;
    return adv > 0 ? adv : (i > 0 ? i : -1);
}

gas_db *mqmqa_gas_read_string(const char *text)
{
    g_err[0] = '\0';
    gas_db *g = calloc(1, sizeof *g);
    if (!g) { snprintf(g_err, sizeof g_err, "out of memory"); return NULL; }
    g->el = calloc(GAS_MAXEL, sizeof *g->el);
    int cap = 64;
    g->sp = calloc((size_t)cap, sizeof *g->sp);
    if (!g->el || !g->sp) { snprintf(g_err, sizeof g_err, "out of memory"); mqmqa_gas_free(g); return NULL; }

    char l1[256], l2[256], l3[256], l4[256];
    int pos = 0, adv;
    while ((adv = getline_at(text, pos, l1, sizeof l1)) > 0 || text[pos]) {
        if (adv <= 0) break;
        int lp = pos; pos += adv;
        /* skip THERMO / END / range / blank lines; a header card has a name in
         * column 1 and the "1" tag as its last non-space character */
        char tmp[256]; snprintf(tmp, sizeof tmp, "%s", l1); trim(tmp);
        int len = (int)strlen(tmp);
        if (len == 0) continue;
        if (l1[0] == ' ' || l1[0] == '\t') continue;
        if (strncmp(tmp, "THERMO", 6) == 0 || strncmp(tmp, "END", 3) == 0) continue;
        if (tmp[len - 1] != '1' || (int)strlen(l1) < 73) continue;

        /* read the three following data lines */
        adv = getline_at(text, pos, l2, sizeof l2); if (adv <= 0) break; pos += adv;
        adv = getline_at(text, pos, l3, sizeof l3); if (adv <= 0) break; pos += adv;
        adv = getline_at(text, pos, l4, sizeof l4); if (adv <= 0) break; pos += adv;
        (void)lp;

        if (g->n_sp >= cap) {
            cap *= 2;
            GasSpecies *ns = realloc(g->sp, (size_t)cap * sizeof *g->sp);
            if (!ns) { snprintf(g_err, sizeof g_err, "out of memory"); mqmqa_gas_free(g); return NULL; }
            g->sp = ns;
        }
        GasSpecies *s = &g->sp[g->n_sp];
        memset(s, 0, sizeof *s);
        /* name: columns 0..17, first token */
        char nm[19]; memcpy(nm, l1, 18); nm[18] = '\0';
        char *sp0 = nm; while (*sp0 == ' ') ++sp0;
        char *e0 = sp0; while (*e0 && *e0 != ' ') ++e0; *e0 = '\0';
        snprintf(s->name, GAS_NAME, "%s", sp0);
        /* composition: columns 24..43, four 5-char (2 sym + 3 count) groups */
        for (int k = 0; k < 4; ++k) {
            char sym[3] = {0}, cnt[4] = {0};
            memcpy(sym, l1 + 24 + 5 * k, 2);
            memcpy(cnt, l1 + 24 + 5 * k + 2, 3);
            /* trim symbol */
            char csym[3] = {0}; int ci = 0;
            for (int z = 0; z < 2; ++z) if (sym[z] != ' ') csym[ci++] = sym[z];
            double c = atof(cnt);
            if (csym[0] && c != 0.0 && s->nel < 8) {
                int ei = el_index(g, csym);
                if (ei < 0) { snprintf(g_err, sizeof g_err, "too many elements"); mqmqa_gas_free(g); return NULL; }
                s->el[s->nel] = ei; s->cnt[s->nel] = c; s->nel++;
            }
        }
        { char b[11]={0}; memcpy(b,l1+45,10); s->t_lo=atof(b); }
        { char b[11]={0}; memcpy(b,l1+55,10); s->t_hi=atof(b); }
        { char b[9]={0};  memcpy(b,l1+65,8);  s->t_mid=atof(b); }
        for (int k = 0; k < 5; ++k) s->high[k] = field15(l2, 15 * k);
        s->high[5] = field15(l3, 0); s->high[6] = field15(l3, 15);
        s->low[0] = field15(l3, 30); s->low[1] = field15(l3, 45); s->low[2] = field15(l3, 60);
        for (int k = 0; k < 4; ++k) s->low[3 + k] = field15(l4, 15 * k);
        g->n_sp++;
    }
    if (g->n_sp == 0) { snprintf(g_err, sizeof g_err, "no NASA species found"); mqmqa_gas_free(g); return NULL; }
    /* attach critical constants where known; the rest stay ideal */
    for (int i = 0; i < g->n_sp; ++i) {
        g->sp[i].has_crit = 0;
        for (size_t k = 0; k < sizeof CRIT / sizeof CRIT[0]; ++k) {
            if (strcmp(g->sp[i].name, CRIT[k].name) == 0) {
                g->sp[i].tc = CRIT[k].tc;
                g->sp[i].pc = CRIT[k].pc_bar * 1e5;   /* bar -> Pa */
                g->sp[i].omega = CRIT[k].omega;
                g->sp[i].has_crit = 1;
                break;
            }
        }
    }
    return g;
}

void mqmqa_gas_free(gas_db *g)
{
    if (!g) return;
    free(g->sp);
    free(g->el);
    free(g);
}

int mqmqa_gas_num_species(const gas_db *g) { return g ? g->n_sp : 0; }
const char *mqmqa_gas_species_name(const gas_db *g, int i)
{
    return (g && i >= 0 && i < g->n_sp) ? g->sp[i].name : "";
}
int mqmqa_gas_num_elements(const gas_db *g) { return g ? g->n_el : 0; }
const char *mqmqa_gas_element(const gas_db *g, int e)
{
    return (g && e >= 0 && e < g->n_el) ? g->el[e] : "";
}

double mqmqa_gas_species_grt(const gas_db *g, int i, double T)
{
    if (!g || i < 0 || i >= g->n_sp) return 0.0;
    const GasSpecies *s = &g->sp[i];
    const double *a = (T < s->t_mid) ? s->low : s->high;
    double h_rt = a[0] + a[1] * T / 2 + a[2] * T * T / 3 + a[3] * T * T * T / 4
                + a[4] * T * T * T * T / 5 + a[5] / T;
    double s_r = a[0] * log(T) + a[1] * T + a[2] * T * T / 2 + a[3] * T * T * T / 3
               + a[4] * T * T * T * T / 4 + a[6];
    return h_rt - s_r;
}

/* dense linear solve A x = rhs (n<=GAS_MAXEL), Gaussian elimination with partial
 * pivoting; A and rhs are overwritten. Returns 0 on success. */
static int lin_solve(double *A, double *rhs, int n)
{
    for (int col = 0; col < n; ++col) {
        int piv = col; double best = fabs(A[col * n + col]);
        for (int r = col + 1; r < n; ++r) {
            double v = fabs(A[r * n + col]);
            if (v > best) { best = v; piv = r; }
        }
        if (best < 1e-300) return 1;
        if (piv != col) {
            for (int c = 0; c < n; ++c) {
                double t = A[col * n + c]; A[col * n + c] = A[piv * n + c]; A[piv * n + c] = t;
            }
            double t = rhs[col]; rhs[col] = rhs[piv]; rhs[piv] = t;
        }
        double d = A[col * n + col];
        for (int r = 0; r < n; ++r) {
            if (r == col) continue;
            double f = A[r * n + col] / d;
            if (f == 0.0) continue;
            for (int c = col; c < n; ++c) A[r * n + c] -= f * A[col * n + c];
            rhs[r] -= f * rhs[col];
        }
    }
    for (int i = 0; i < n; ++i) rhs[i] /= A[i * n + i];
    return 0;
}

static double clip(double v, double lo, double hi)
{
    return v < lo ? lo : (v > hi ? hi : v);
}

/* largest real root of z^3 + c2 z^2 + c1 z + c0 (the vapor compressibility) */
static double cubic_max_root(double c2, double c1, double c0)
{
    double p = c1 - c2 * c2 / 3.0;
    double q = 2.0 * c2 * c2 * c2 / 27.0 - c2 * c1 / 3.0 + c0;
    double disc = q * q / 4.0 + p * p * p / 27.0;
    double shift = -c2 / 3.0;
    if (disc > 0) {
        double s = sqrt(disc);
        double u = cbrt(-q / 2.0 + s), v = cbrt(-q / 2.0 - s);
        return u + v + shift;               /* one real root */
    }
    double r = sqrt(-p * p * p / 27.0);
    double phi = acos(clip(-q / (2.0 * r), -1.0, 1.0));
    double m = 2.0 * cbrt(r);
    double z0 = m * cos(phi / 3.0) + shift;
    double z1 = m * cos((phi + 2.0 * M_PI) / 3.0) + shift;
    double z2 = m * cos((phi + 4.0 * M_PI) / 3.0) + shift;
    double mx = z0; if (z1 > mx) mx = z1; if (z2 > mx) mx = z2;
    return mx;
}

/* Peng-Robinson fugacity coefficients for the mixture x[] (van der Waals one-fluid,
 * no binary interaction parameters). Species without critical data act ideally. */
static void pr_fugacity(const gas_db *g, double T, double P, const double *x, double *phi)
{
    int nsp = g->n_sp;
    double *ai = malloc((size_t)nsp * sizeof(double));
    double *bi = malloc((size_t)nsp * sizeof(double));
    if (!ai || !bi) { for (int i = 0; i < nsp; ++i) phi[i] = 1.0; free(ai); free(bi); return; }
    for (int i = 0; i < nsp; ++i) {
        const GasSpecies *s = &g->sp[i];
        if (s->has_crit) {
            double kappa = 0.37464 + 1.54226 * s->omega - 0.26992 * s->omega * s->omega;
            double alpha = 1.0 + kappa * (1.0 - sqrt(T / s->tc));
            alpha *= alpha;
            ai[i] = 0.45724 * GAS_R * GAS_R * s->tc * s->tc / s->pc * alpha;
            bi[i] = 0.07780 * GAS_R * s->tc / s->pc;
        } else { ai[i] = 0.0; bi[i] = 0.0; }
    }
    double a_mix = 0.0, b_mix = 0.0;
    for (int i = 0; i < nsp; ++i) {
        b_mix += x[i] * bi[i];
        for (int j = 0; j < nsp; ++j) a_mix += x[i] * x[j] * sqrt(ai[i] * ai[j]);
    }
    double RT = GAS_R * T;
    double A = a_mix * P / (RT * RT), B = b_mix * P / RT;
    if (B <= 0.0) { for (int i = 0; i < nsp; ++i) phi[i] = 1.0; free(ai); free(bi); return; }
    double Z = cubic_max_root(-(1.0 - B), A - 3.0 * B * B - 2.0 * B, -(A * B - B * B - B * B * B));
    if (Z <= B) Z = B + 1e-9;
    double sq2 = sqrt(2.0);
    double lg = log((Z + (1.0 + sq2) * B) / (Z + (1.0 - sq2) * B));
    for (int i = 0; i < nsp; ++i) {
        double si = 0.0;
        for (int j = 0; j < nsp; ++j) si += x[j] * sqrt(ai[i] * ai[j]);
        double ln_phi = bi[i] / b_mix * (Z - 1.0) - log(Z - B)
                      - A / (2.0 * sq2 * B) * (2.0 * si / a_mix - bi[i] / b_mix) * lg;
        phi[i] = exp(clip(ln_phi, -80.0, 80.0));
    }
    free(ai); free(bi);
}

/* element-potential solve with per-species log-fugacity offset lnphi[] (all zero
 * for an ideal gas). Fills x[] with equilibrium mole numbers (unnormalized). */
static int gas_solve(const gas_db *g, double T, double P, const double *b,
                     const double *lnphi, double *x, double *pi)
{
    int nsp = g->n_sp, nel = g->n_el;
    double *grt = malloc((size_t)nsp * sizeof(double));
    double *resid = malloc((size_t)nel * sizeof(double));
    double *jac = malloc((size_t)nel * nel * sizeof(double));
    if (!grt || !resid || !jac) { free(grt); free(resid); free(jac); return 2; }
    double bsum = 0.0;
    for (int e = 0; e < nel; ++e) bsum += b[e];
    if (bsum <= 0.0) bsum = 1e-12;
    double xt = bsum, lnPP = log(P / P_REF);
    double tol = 1e-14 * (bsum > 1.0 ? bsum : 1.0);
    for (int i = 0; i < nsp; ++i) grt[i] = mqmqa_gas_species_grt(g, i, T) + lnphi[i];
    for (int e = 0; e < nel; ++e) pi[e] = 0.0;
    for (int outer = 0; outer < 120; ++outer) {
        double lnxt = log(xt);
        for (int inner = 0; inner < 200; ++inner) {
            for (int i = 0; i < nsp; ++i) {
                double lnx = -grt[i] - lnPP + lnxt;
                for (int k = 0; k < g->sp[i].nel; ++k) lnx += g->sp[i].cnt[k] * pi[g->sp[i].el[k]];
                x[i] = exp(clip(lnx, -80.0, 80.0));
            }
            for (int e = 0; e < nel; ++e) resid[e] = -b[e];
            for (int i = 0; i < nsp; ++i)
                for (int k = 0; k < g->sp[i].nel; ++k)
                    resid[g->sp[i].el[k]] += g->sp[i].cnt[k] * x[i];
            double mx = 0.0;
            for (int e = 0; e < nel; ++e) if (fabs(resid[e]) > mx) mx = fabs(resid[e]);
            if (mx < tol) break;
            memset(jac, 0, (size_t)nel * nel * sizeof(double));
            for (int i = 0; i < nsp; ++i) {
                const GasSpecies *s = &g->sp[i];
                for (int a = 0; a < s->nel; ++a)
                    for (int c = 0; c < s->nel; ++c)
                        jac[s->el[a] * nel + s->el[c]] += s->cnt[a] * s->cnt[c] * x[i];
            }
            double dmax = 1.0;
            for (int e = 0; e < nel; ++e) if (jac[e * nel + e] > dmax) dmax = jac[e * nel + e];
            double ridge = 1e-10 * dmax;
            for (int e = 0; e < nel; ++e) jac[e * nel + e] += ridge;
            for (int e = 0; e < nel; ++e) resid[e] = -resid[e];
            if (lin_solve(jac, resid, nel)) break;
            for (int e = 0; e < nel; ++e) pi[e] += clip(resid[e], -2.0, 2.0);
        }
        double xt_new = 0.0;
        for (int i = 0; i < nsp; ++i) xt_new += x[i];
        if (fabs(xt_new - xt) < 1e-12 * xt) { xt = xt_new; break; }
        xt = xt_new;
    }
    free(grt); free(resid); free(jac);
    return 0;
}

int mqmqa_gas_equilibrium_ex(const gas_db *g, double T, double P,
                             const double *b, int nonideal, double *out_x)
{
    if (!g || g->n_sp == 0) return 1;
    int nsp = g->n_sp, nel = g->n_el;
    double *x = malloc((size_t)nsp * sizeof(double));
    double *pi = calloc((size_t)nel, sizeof(double));
    double *lnphi = calloc((size_t)nsp, sizeof(double));
    double *phi = malloc((size_t)nsp * sizeof(double));
    if (!x || !pi || !lnphi || !phi) { free(x); free(pi); free(lnphi); free(phi); return 2; }

    int rc = gas_solve(g, T, P, b, lnphi, x, pi);   /* ideal pass seeds real-gas */
    if (rc == 0 && nonideal) {
        for (int it = 0; it < 40; ++it) {
            double sum = 0.0;
            for (int i = 0; i < nsp; ++i) sum += x[i];
            double *frac = phi;                     /* reuse phi buffer for fractions */
            for (int i = 0; i < nsp; ++i) frac[i] = x[i] / sum;
            double lnphi_new;
            double *phi2 = malloc((size_t)nsp * sizeof(double));
            if (!phi2) break;
            pr_fugacity(g, T, P, frac, phi2);
            double dmax = 0.0;
            for (int i = 0; i < nsp; ++i) {
                lnphi_new = log(phi2[i] > 1e-300 ? phi2[i] : 1e-300);
                double d = fabs(lnphi_new - lnphi[i]);
                if (d > dmax) dmax = d;
                lnphi[i] = 0.5 * lnphi[i] + 0.5 * lnphi_new;   /* damped for stability */
            }
            free(phi2);
            rc = gas_solve(g, T, P, b, lnphi, x, pi);
            if (rc != 0 || dmax < 1e-10) break;
        }
    }
    double sum = 0.0;
    for (int i = 0; i < nsp; ++i) sum += x[i];
    for (int i = 0; i < nsp; ++i) out_x[i] = x[i] / sum;
    free(x); free(pi); free(lnphi); free(phi);
    return rc;
}

int mqmqa_gas_equilibrium(const gas_db *g, double T, double P,
                          const double *b, double *out_x)
{
    return mqmqa_gas_equilibrium_ex(g, T, P, b, 0, out_x);
}

/* ---- coupled gas + pure-condensed equilibrium (see gas.h) ---------------------------
 * Primal element-potential method with the gas closure sum(X)=1 and each present
 * condensed species on its saturation line a_k.pi = g_k, so pi are the true element
 * potentials shared by gas and condensate. A damped Newton over [pi, nt, condensed
 * amounts] solves one present set; the stable assemblage is the lowest-Gibbs valid set,
 * enumerated over condensed subsets up to the phase-rule limit. This is the C port of the
 * validated python/mqmqa/gas.py:gas_condensed_equilibrium. */

/* gas mole fractions X_j = exp(a_j.pi - g_j - ln(P/P0)); makes mu_j/RT = a_j.pi exactly */
static void gc_Xgas(const gas_db *g, const double *grt, double lnPP,
                    const double *pi, double *X)
{
    for (int i = 0; i < g->n_sp; ++i) {
        const GasSpecies *s = &g->sp[i];
        double lnx = -grt[i] - lnPP;
        for (int k = 0; k < s->nel; ++k) lnx += s->cnt[k] * pi[s->el[k]];
        X[i] = exp(clip(lnx, -300.0, 300.0));
    }
}

/* residual F = [element balance (nE); gas closure sum(X)-1; saturation lines (m)] and
 * its max-abs; X is filled as a side effect */
static double gc_residual(const gas_db *g, const double *grt, double lnPP,
                          const double *Ac, const double *gcv, const double *b, int nE,
                          const int *active, int m, const double *pi, double nt,
                          const double *nk, double *X, double *F)
{
    int nsp = g->n_sp, n = nE + 1 + m;
    gc_Xgas(g, grt, lnPP, pi, X);
    for (int e = 0; e < nE; ++e) F[e] = -b[e];
    double sX = 0.0;
    for (int i = 0; i < nsp; ++i) {
        const GasSpecies *s = &g->sp[i];
        sX += X[i];
        for (int k = 0; k < s->nel; ++k) F[s->el[k]] += nt * s->cnt[k] * X[i];
    }
    for (int j = 0; j < m; ++j) {
        const double *row = &Ac[active[j] * nE];
        for (int e = 0; e < nE; ++e) F[e] += row[e] * nk[j];
    }
    F[nE] = sX - 1.0;
    for (int j = 0; j < m; ++j) {
        const double *row = &Ac[active[j] * nE];
        double q = -gcv[active[j]];
        for (int e = 0; e < nE; ++e) q += row[e] * pi[e];
        F[nE + 1 + j] = q;
    }
    double mx = 0.0;
    for (int i = 0; i < n; ++i) if (fabs(F[i]) > mx) mx = fabs(F[i]);
    return mx;
}

/* Newton solve for one present set; returns 0 on convergence, non-zero otherwise. */
static int gc_solve_active(const gas_db *g, const double *grt, double lnPP,
                           const double *Ac, const double *gcv, const double *b,
                           double bscale, int nE, const int *active, int m,
                           double *pi, double *ntp, double *nk)
{
    int nsp = g->n_sp, n = nE + 1 + m;
    double *X = malloc((size_t)nsp * sizeof(double));
    double *F = malloc((size_t)n * sizeof(double));
    double *J = malloc((size_t)n * n * sizeof(double));
    double *dz = malloc((size_t)n * sizeof(double));
    double *aX = malloc((size_t)nE * sizeof(double));
    double *pin = malloc((size_t)nE * sizeof(double));
    double *nkn = malloc((size_t)(m ? m : 1) * sizeof(double));
    if (!X || !F || !J || !dz || !aX || !pin || !nkn) {
        free(X); free(F); free(J); free(dz); free(aX); free(pin); free(nkn); return 2;
    }
    double nt = *ntp;
    for (int j = 0; j < m; ++j) nk[j] = 0.0;
    int rc = 1;
    for (int iter = 0; iter < 200; ++iter) {
        double f0 = gc_residual(g, grt, lnPP, Ac, gcv, b, nE, active, m, pi, nt, nk, X, F);
        if (f0 < 1e-12 * bscale) { rc = 0; break; }
        memset(J, 0, (size_t)n * n * sizeof(double));
        for (int e = 0; e < nE; ++e) aX[e] = 0.0;
        for (int i = 0; i < nsp; ++i) {
            const GasSpecies *s = &g->sp[i];
            double xi = X[i];
            for (int a = 0; a < s->nel; ++a) {
                aX[s->el[a]] += s->cnt[a] * xi;
                for (int c = 0; c < s->nel; ++c)
                    J[s->el[a] * n + s->el[c]] += nt * s->cnt[a] * s->cnt[c] * xi;   /* nt*G */
            }
        }
        double dmax = 1.0;
        for (int e = 0; e < nE; ++e) if (J[e * n + e] > dmax) dmax = J[e * n + e];
        double ridge = 1e-12 * dmax;
        for (int e = 0; e < nE; ++e) {
            J[e * n + e] += ridge;
            J[e * n + nE] = aX[e];                       /* dRe/dnt */
            J[nE * n + e] = aX[e];                       /* dR0/dpi */
        }
        for (int j = 0; j < m; ++j) {
            const double *row = &Ac[active[j] * nE];
            for (int e = 0; e < nE; ++e) {
                J[e * n + (nE + 1 + j)] = row[e];        /* dRe/dnk */
                J[(nE + 1 + j) * n + e] = row[e];        /* dQk/dpi */
            }
        }
        for (int i = 0; i < n; ++i) dz[i] = -F[i];
        if (lin_solve(J, dz, n)) break;
        double alpha = 1.0; int ok = 0;
        for (int ls = 0; ls < 60; ++ls) {
            for (int e = 0; e < nE; ++e) pin[e] = pi[e] + alpha * dz[e];
            double ntn = nt + alpha * dz[nE];
            for (int j = 0; j < m; ++j) nkn[j] = nk[j] + alpha * dz[nE + 1 + j];
            if (ntn > 0.0) {
                double fn = gc_residual(g, grt, lnPP, Ac, gcv, b, nE, active, m,
                                        pin, ntn, nkn, X, F);
                if (isfinite(fn) && fn <= (1.0 - 1e-4 * alpha) * f0) {
                    for (int e = 0; e < nE; ++e) pi[e] = pin[e];
                    nt = ntn;
                    for (int j = 0; j < m; ++j) nk[j] = nkn[j];
                    ok = 1; break;
                }
            }
            alpha *= 0.5;
        }
        if (!ok) break;
    }
    *ntp = nt;
    free(X); free(F); free(J); free(dz); free(aX); free(pin); free(nkn);
    return rc;
}

/* total Gibbs over RT of a converged assemblage (the arbiter between phase choices) */
static double gc_gibbs(const gas_db *g, const double *grt, double lnPP,
                       const double *gcv, int nE, const int *active, int m,
                       const double *pi, double nt, const double *nk, double *X)
{
    (void)nE;
    int nsp = g->n_sp;
    gc_Xgas(g, grt, lnPP, pi, X);
    double sX = 0.0;
    for (int i = 0; i < nsp; ++i) sX += X[i];
    double gas_g = 0.0;
    for (int i = 0; i < nsp; ++i) {
        double Xn = X[i] / sX;
        if (Xn > 1e-300) gas_g += nt * Xn * (grt[i] + lnPP + log(Xn));
    }
    double cg = 0.0;
    for (int j = 0; j < m; ++j) cg += nk[j] * gcv[active[j]];
    return gas_g + cg;
}

/* solve the given present set from the seed and return its Gibbs if it is a valid
 * equilibrium (converged, non-negative amounts, no supersaturated absentee), else HUGE_VAL */
static double gc_evaluate(const gas_db *g, const double *grt, double lnPP,
                          const double *Ac, const double *gcv, const double *b,
                          double bscale, int nE, int n_cond, const int *active, int m,
                          const double *pi_seed, double nt_seed,
                          double *pi_out, double *nt_out, double *nk_out, double *X)
{
    for (int e = 0; e < nE; ++e) pi_out[e] = pi_seed[e];
    double nt = nt_seed;
    if (gc_solve_active(g, grt, lnPP, Ac, gcv, b, bscale, nE, active, m, pi_out, &nt, nk_out))
        return HUGE_VAL;
    *nt_out = nt;
    for (int j = 0; j < m; ++j) if (nk_out[j] < -1e-7 * bscale) return HUGE_VAL;
    for (int i = 0; i < n_cond; ++i) {
        int in = 0;
        for (int j = 0; j < m; ++j) if (active[j] == i) { in = 1; break; }
        if (in) continue;
        const double *row = &Ac[i * nE];
        double drive = -gcv[i];
        for (int e = 0; e < nE; ++e) drive += row[e] * pi_out[e];
        double sc = fabs(gcv[i]); if (sc < 1.0) sc = 1.0;
        if (drive > 1e-6 * sc) return HUGE_VAL;
    }
    return gc_gibbs(g, grt, lnPP, gcv, nE, active, m, pi_out, nt, nk_out, X);
}

int mqmqa_gas_condensed_equilibrium(
    const gas_db *g, int n_elem, const double *b, double T, double P,
    int n_cond, const double *cond_grt, const double *cond_stoich,
    double *out_x, double *out_cond, double *out_pi)
{
    if (!g || g->n_sp == 0 || n_elem < g->n_el) return 1;
    int nsp = g->n_sp, nE = n_elem;
    double lnPP = log(P / P_REF);
    double bscale = 0.0;
    for (int e = 0; e < nE; ++e) bscale += b[e];
    if (bscale < 1.0) bscale = 1.0;

    double *grt = malloc((size_t)nsp * sizeof(double));
    double *X = malloc((size_t)nsp * sizeof(double));
    double *pi_seed = calloc((size_t)nE, sizeof(double));
    double *pi_best = malloc((size_t)nE * sizeof(double));
    double *pi_try = malloc((size_t)nE * sizeof(double));
    double *nk_best = calloc((size_t)(n_cond ? n_cond : 1), sizeof(double));
    double *nk_try = calloc((size_t)(n_cond ? n_cond : 1), sizeof(double));
    int *active = malloc((size_t)(n_cond ? n_cond : 1) * sizeof(int));
    int *best_active = malloc((size_t)(n_cond ? n_cond : 1) * sizeof(int));
    if (!grt || !X || !pi_seed || !pi_best || !pi_try || !nk_best || !nk_try
        || !active || !best_active) {
        free(grt); free(X); free(pi_seed); free(pi_best); free(pi_try);
        free(nk_best); free(nk_try); free(active); free(best_active); return 2;
    }
    for (int i = 0; i < nsp; ++i) grt[i] = mqmqa_gas_species_grt(g, i, T);

    /* seed pi from the gas-only element potentials (gas elements are combined 0..n_el-1) */
    {
        double *xg = malloc((size_t)nsp * sizeof(double));
        double *pig = calloc((size_t)g->n_el, sizeof(double));
        double *lnphi0 = calloc((size_t)nsp, sizeof(double));
        if (xg && pig && lnphi0 && gas_solve(g, T, P, b, lnphi0, xg, pig) == 0) {
            for (int e = 0; e < g->n_el; ++e)
                if (isfinite(pig[e])) pi_seed[e] = pig[e];
        }
        free(xg); free(pig); free(lnphi0);
    }
    double nt_seed = bscale, nt_best = bscale, nt_try = bscale;

    int kmax = n_cond < nE ? n_cond : nE;
    /* count subsets up to kmax to decide enumeration vs a greedy fallback */
    double ncombo = 0.0; { double c = 1.0;
        for (int k = 0; k <= kmax; ++k) { ncombo += c; c = c * (n_cond - k) / (k + 1); } }
    double gbest = HUGE_VAL; int mbest = -1;

    if (n_cond == 0 || ncombo <= 60000.0) {
        int *idx = malloc((size_t)(kmax + 1) * sizeof(int));
        for (int k = 0; k <= kmax; ++k) {
            for (int j = 0; j < k; ++j) idx[j] = j;
            while (1) {
                for (int j = 0; j < k; ++j) active[j] = idx[j];
                double gv = gc_evaluate(g, grt, lnPP, cond_stoich, cond_grt, b, bscale,
                                        nE, n_cond, active, k, pi_seed, nt_seed,
                                        pi_try, &nt_try, nk_try, X);
                if (gv < gbest) {
                    gbest = gv; mbest = k;
                    for (int e = 0; e < nE; ++e) pi_best[e] = pi_try[e];
                    for (int j = 0; j < k; ++j) { best_active[j] = active[j]; nk_best[j] = nk_try[j]; }
                    nt_best = nt_try;
                }
                if (k == 0) break;
                int j = k - 1;
                while (j >= 0 && idx[j] == n_cond - k + j) --j;
                if (j < 0) break;
                ++idx[j];
                for (int t = j + 1; t < k; ++t) idx[t] = idx[t - 1] + 1;
            }
        }
        free(idx);
    } else {
        /* greedy add-most-supersaturated / drop-negative, then single-toggle local search */
        int m = 0;
        for (int outer = 0; outer < 4 * n_cond + 4; ++outer) {
            if (gc_solve_active(g, grt, lnPP, cond_stoich, cond_grt, b, bscale,
                                nE, active, m, pi_best, &nt_best, nk_best)) break;
            int neg = -1; double negv = -1e-7 * bscale;
            for (int j = 0; j < m; ++j) if (nk_best[j] < negv) { negv = nk_best[j]; neg = j; }
            if (neg >= 0) { for (int j = neg; j < m - 1; ++j) active[j] = active[j + 1]; --m; continue; }
            int add = -1; double amax = 1e-9;
            for (int i = 0; i < n_cond; ++i) {
                int in = 0; for (int j = 0; j < m; ++j) if (active[j] == i) in = 1;
                if (in) continue;
                const double *row = &cond_stoich[i * nE];
                double drive = -cond_grt[i];
                for (int e = 0; e < nE; ++e) drive += row[e] * pi_best[e];
                if (drive > amax) { amax = drive; add = i; }
            }
            if (add >= 0) { active[m++] = add; continue; }
            break;
        }
        mbest = m; for (int j = 0; j < m; ++j) best_active[j] = active[j];
        gbest = gc_evaluate(g, grt, lnPP, cond_stoich, cond_grt, b, bscale, nE, n_cond,
                            best_active, mbest, pi_seed, nt_seed, pi_best, &nt_best, nk_best, X);
    }

    int rc = 0;
    if (mbest < 0 || gbest == HUGE_VAL) {
        /* no valid assemblage converged: fall back to the pure-gas result */
        int z[1];
        gbest = gc_evaluate(g, grt, lnPP, cond_stoich, cond_grt, b, bscale, nE, n_cond,
                            z, 0, pi_seed, nt_seed, pi_best, &nt_best, nk_best, X);
        mbest = 0;
        if (gbest == HUGE_VAL) rc = 3;
    }
    gc_Xgas(g, grt, lnPP, pi_best, X);
    double sX = 0.0; for (int i = 0; i < nsp; ++i) sX += X[i];
    for (int i = 0; i < nsp; ++i) out_x[i] = X[i] / sX;
    for (int i = 0; i < n_cond; ++i) out_cond[i] = 0.0;
    for (int j = 0; j < mbest; ++j) {
        double v = nk_best[j];
        out_cond[best_active[j]] = v > 0.0 ? v : 0.0;
    }
    for (int e = 0; e < nE; ++e) out_pi[e] = pi_best[e];

    free(grt); free(X); free(pi_seed); free(pi_best); free(pi_try);
    free(nk_best); free(nk_try); free(active); free(best_active);
    return rc;
}
