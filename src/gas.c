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
    double tol = 1e-13 * (bsum > 1.0 ? bsum : 1.0);
    for (int i = 0; i < nsp; ++i) grt[i] = mqmqa_gas_species_grt(g, i, T) + lnphi[i];
    for (int e = 0; e < nel; ++e) pi[e] = 0.0;
    for (int outer = 0; outer < 60; ++outer) {
        double lnxt = log(xt);
        for (int inner = 0; inner < 40; ++inner) {
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
