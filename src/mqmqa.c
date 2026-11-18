/* MQMQA energy, translated into C from pycalphad's ModelMQMQA
 * (pycalphad/models/model_mqmqa.py). pycalphad is MIT licensed, Copyright (c) 2014-2019
 * Richard Otis and Zi-Kui Liu and the other holders listed in NOTICE. */

#include "mqmqa.h"
#include "fmtbuf.h"
#include "mqmqa_priv.h"
#include <math.h>
#include <stddef.h>
#include <stdlib.h>
#include <ctype.h>
#include <stdio.h>
#include <string.h>

/* The one table of gas-constant values. A database's energies are only consistent with
 * the R it was assessed with, so each part of the engine keeps its data's own value
 * unless the user forces one. */
static const double R_CHOICE[4] = { 0.0, 8.3145, 8.31451, 8.314462618 };
static int g_R_mode = MQMQA_R_AS_ASSESSED;

int mqmqa_set_gas_constant(int mode)
{
    if (mode < MQMQA_R_AS_ASSESSED || mode > MQMQA_R_SI) return -1;
    if (mode != g_R_mode) {
        g_R_mode = mode;
        mqmqa_gas_constant_changed();
    }
    return 0;
}

int mqmqa_gas_constant_mode(void) { return g_R_mode; }

double mqmqa_gas_constant_choice(int choice)
{
    return (choice >= MQMQA_R_CALPHAD && choice <= MQMQA_R_SI) ? R_CHOICE[choice] : NAN;
}

double mqmqa_gas_constant(double own)
{
    return g_R_mode == MQMQA_R_AS_ASSESSED ? own : R_CHOICE[g_R_mode];
}

/* ---- a database's own R ---- */

/* Gas-constant literals in the expressions: numbers from 8.3139 to 8.3149 standing
 * alone (not part of a longer number or a name). kind 1 skips TDB comment lines, kind 2
 * reads only the Expr="..." attributes of XTDB. Returns the count of distinct values
 * (up to cap written to vals). */
static int R_literals(const char *text, int kind, double *vals, int cap)
{
    int n = 0;
    const char *p = text;
    while (*p) {
        const char *end;
        if (kind == 1) {
            if (*p == '$') { while (*p && *p != '\n') ++p; continue; }
            end = p + strcspn(p, "$");
        } else {
            const char *a = strstr(p, "Expr=\"");
            if (!a) break;
            p = a + 6;
            end = strchr(p, '"');
            if (!end) break;
        }
        for (const char *q = p; q < end; ++q) {
            if (!isdigit((unsigned char)*q)) continue;
            if (q > text && (isalnum((unsigned char)q[-1]) || q[-1] == '.' || q[-1] == '_')) continue;
            char *stop;
            const double v = strtod(q, &stop);
            if (v > 8.3139 && v < 8.3149 && !isalpha((unsigned char)*stop) && *stop != '_') {
                int seen = 0;
                for (int k = 0; k < n; ++k) seen |= vals[k] == v;
                if (!seen && n < cap) vals[n++] = v;
            }
            q = stop - 1;
        }
        p = end;
    }
    return n;
}

void rinfo_detect(RInfo *ri, const char *format, double convention, int stated,
                  double stated_value, const char *text, int kind)
{
    memset(ri, 0, sizeof *ri);
    snprintf(ri->format, sizeof ri->format, "%s", format);
    double lit[8];
    const int n = (!stated && text) ? R_literals(text, kind, lit, 8) : 0;
    if (stated) {
        ri->found = stated_value;
        ri->found_src = MQMQA_R_SRC_FILE;
    } else if (n == 1) {
        ri->found = lit[0];
        ri->found_src = MQMQA_R_SRC_INFERRED;
    } else {
        ri->found = convention;
        ri->found_src = MQMQA_R_SRC_CONVENTION;
        if (n > 1) {
            /* disagreeing literals: which one is R cannot be told, so none is guessed */
            int cut = fmt_to(ri->detail, sizeof ri->detail, "its constants disagree (");
            for (int k = 0; k < n; ++k)
                cut |= fmt_cat(ri->detail, sizeof ri->detail, "%s%.10g", k ? ", " : "", lit[k]);
            cut |= fmt_cat(ri->detail, sizeof ri->detail, ")");
            if (cut) fmt_mark_cut(ri->detail, sizeof ri->detail);
        }
    }
    ri->own = ri->found;
    ri->src = ri->found_src;
}

int rinfo_declare(RInfo *ri, int choice)
{
    if (choice < MQMQA_R_AS_ASSESSED || choice > MQMQA_R_SI) return -2;
    if (ri->found_src == MQMQA_R_SRC_FILE) return -1;
    if (choice == MQMQA_R_AS_ASSESSED) {
        ri->own = ri->found;
        ri->src = ri->found_src;
    } else {
        ri->own = R_CHOICE[choice];
        ri->src = MQMQA_R_SRC_DECLARED;
    }
    return 0;
}

double rinfo_value(const RInfo *ri) { return mqmqa_gas_constant(ri->own); }

int rinfo_source(const RInfo *ri)
{
    return g_R_mode == MQMQA_R_AS_ASSESSED ? ri->src : MQMQA_R_SRC_OVERRIDE;
}

static const char *own_phrase(int src)
{
    switch (src) {
    case MQMQA_R_SRC_FILE: return "read from this file";
    case MQMQA_R_SRC_INFERRED: return "inferred from constants in this file";
    case MQMQA_R_SRC_DECLARED: return "declared by you for this database";
    default: return "not stated in the file";
    }
}

const char *rinfo_note(const RInfo *ri)
{
    static char buf[512];   /* not _Thread_local, see g_error in cs_dat.c */
    const char *sep = ri->detail[0] ? "; " : "";
    if (g_R_mode != MQMQA_R_AS_ASSESSED)
        fmt_msg(buf, sizeof buf, "R = %.10g, the gas-constant setting, overriding this "
                "database's own %.10g (%s)", R_CHOICE[g_R_mode], ri->own, own_phrase(ri->src));
    else if (ri->src == MQMQA_R_SRC_CONVENTION)
        fmt_msg(buf, sizeof buf, "Not stated in the file; using %.10g, the convention for "
                "%s%s%s", ri->own, ri->format, sep, ri->detail);
    else
        fmt_msg(buf, sizeof buf, "R = %.10g, %s%s%s", ri->own, own_phrase(ri->src), sep,
                ri->detail);
    return buf;
}

double mqmqa_R(void)
{
    return mqmqa_gas_constant(R_CHOICE[MQMQA_R_CALPHAD]);
}

double mqmqa_ideal_entropy_binary(double x)
{
    if (x <= 0.0 || x >= 1.0) {
        return 0.0; /* endpoints: pure, zero configurational entropy */
    }
    return -mqmqa_R() * (x * log(x) + (1.0 - x) * log(1.0 - x));
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
    int soln_type, double R_own)
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
    return Sid * T * mqmqa_gas_constant(R_own);
}

/* Gradient of mqmqa_ideal_mixing_energy with respect to each quadruplet fraction, for
 * strictly positive X. Differentiating the four sums of that function term by term:
 *   species terms    sum_i a_iq ln(n_i / sum n), a_iq the 1/Z weights of q's slots;
 *   pair terms       sum_ik b_ikq/zeta ln(x_ik / (F_i F_k)), b_ikq the pair counts of q
 *                    (zeta only for SUBQ, whose pair fractions are starred);
 *   quadruplet term  ln(X_q / inner_q) + 1 + 4 pow_Yi.
 * In the last, the X-weighted derivatives of the pair-fraction product cancel (each
 * quadruplet has four pair slots and the pair total is 4 sum X), and those of the Y
 * product sum to 4, since Y is half the slot count. The logs are the ones the energy
 * itself evaluates, so the gradient is exact where finite differences of the energy
 * lose all precision, next to a vanishing fraction. */
void mqmqa_ideal_mixing_gradient(
    double T,
    int n_cat, int n_an, int n_quads,
    const int *quad_ca, const int *quad_cb,
    const int *quad_ax, const int *quad_ay,
    const double *X,
    const double *Za, const double *Zb, const double *Zx, const double *Zy,
    const double *zeta,
    int soln_type, double R_own, double *grad)
{
    const int subq = (soln_type == 1);
    const double pow_Xik = subq ? 0.75 : 1.0;
    const double pow_Yi = subq ? 0.50 : 1.0;
    const size_t npair = (size_t)n_cat * (size_t)n_an;

    double *ni_c = (double *)calloc((size_t)n_cat, sizeof(double));
    double *ni_a = (double *)calloc((size_t)n_an, sizeof(double));
    double *Yc = (double *)calloc((size_t)n_cat, sizeof(double));
    double *Ya = (double *)calloc((size_t)n_an, sizeof(double));
    double *nik = (double *)calloc(npair, sizeof(double));
    double *lpair = (double *)calloc(npair, sizeof(double));
    double *Rc = (double *)calloc((size_t)n_cat, sizeof(double));
    double *Ca = (double *)calloc((size_t)n_an, sizeof(double));
    if (!ni_c || !ni_a || !Yc || !Ya || !nik || !lpair || !Rc || !Ca) {
        for (int q = 0; q < n_quads; ++q) grad[q] = NAN;
        goto out;
    }
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
    double sum_nc = 0.0, sum_na = 0.0, sum_nik = 0.0, M = 0.0;
    for (int i = 0; i < n_cat; ++i) sum_nc += ni_c[i];
    for (int k = 0; k < n_an; ++k) sum_na += ni_a[k];
    for (int i = 0; i < n_cat; ++i)
        for (int k = 0; k < n_an; ++k) {
            const size_t ik = (size_t)i * n_an + k;
            const double m = subq ? nik[ik] / zeta[ik] : nik[ik];
            sum_nik += nik[ik];
            M += m;
            Rc[i] += m;
            Ca[k] += m;
        }
    /* ln(x_ik / (F_i F_k)) with x = m/M, F_i = Rc_i/M, F_k = Ca_k/M */
    for (int i = 0; i < n_cat; ++i)
        for (int k = 0; k < n_an; ++k) {
            const size_t ik = (size_t)i * n_an + k;
            const double m = subq ? nik[ik] / zeta[ik] : nik[ik];
            lpair[ik] = m > 0.0 ? log(m * M / (Rc[i] * Ca[k])) / (subq ? zeta[ik] : 1.0) : 0.0;
        }
    const double RT = T * mqmqa_gas_constant(R_own);
    for (int q = 0; q < n_quads; ++q) {
        const int ca = quad_ca[q], cb = quad_cb[q], ax = quad_ax[q], ay = quad_ay[q];
        double g = log(ni_c[ca] / sum_nc) / Za[q] + log(ni_c[cb] / sum_nc) / Zb[q]
                 + log(ni_a[ax] / sum_na) / Zx[q] + log(ni_a[ay] / sum_na) / Zy[q];
        g += lpair[(size_t)ca * n_an + ax] + lpair[(size_t)ca * n_an + ay]
           + lpair[(size_t)cb * n_an + ax] + lpair[(size_t)cb * n_an + ay];
        const double C = (2.0 - (ca == cb)) * (2.0 - (ax == ay));
        const double prodXik = (nik[(size_t)ca * n_an + ax] / sum_nik) * (nik[(size_t)ca * n_an + ay] / sum_nik)
                             * (nik[(size_t)cb * n_an + ax] / sum_nik) * (nik[(size_t)cb * n_an + ay] / sum_nik);
        const double prodY = Yc[ca] * Yc[cb] * Ya[ax] * Ya[ay];
        const double inner = C * pow(prodXik, pow_Xik) / pow(prodY, pow_Yi);
        g += log(X[q] / inner) + 1.0 + 4.0 * pow_Yi;
        grad[q] = g * RT;
    }
out:
    free(ni_c); free(ni_a); free(Yc); free(Ya); free(nik); free(lpair); free(Rc); free(Ca);
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

/* Chemical groups (Pelton et al. 2001; Poschmann et al. 2021; the equations as
 * restated in Paz Soldan Palma et al., arXiv:2204.09111, Eqs 8-10). In the i-j term
 * of a mixing sublattice, a third species k is interpolated with i (it belongs to
 * nu_ij) when it shares i's group but not j's; a species in both groups or in neither
 * (gamma) stays out of both sides. With i and j in one group every nu set is empty
 * and the interpolation reduces to the plain i-j variables. */
static int in_nu(const int *grp, int k, int i, int j)
{
    return grp[k] == grp[i] && grp[k] != grp[j];
}

/* k is on the i side of the i-j term: i itself or a member of nu_ij. */
static int on_side(const int *grp, int k, int i, int j)
{
    return k == i || (grp && k != j && in_nu(grp, k, i, j));
}

static int needs_groups(const int *grp, int n, int i, int j)
{
    if (!grp) return 0;
    for (int k = 0; k < n; ++k)
        if (k != i && k != j && (in_nu(grp, k, i, j) || in_nu(grp, k, j, i)))
            return 1;
    return 0;
}

/* What the quadruplets of mixing-sublattice species a,b over the fixed ion f add to
 * the G-code Chi variables: X(ab/ff), and in a SUBQ phase also every reciprocal
 * quadruplet X(ab/fm) with another ion m of f's sublattice (in cation mixing; the
 * roles swap in anion mixing). A missing quadruplet counts as zero.
 *
 * The reciprocal terms carry weight 1.0, as in pycalphad's ModelMQMQA._Chi_mix, whose
 * sum over both slots of the fixed sublattice counts each X(ab/fm) twice at 1/2. The
 * equation as published (Paz Soldan Palma et al., arXiv:2204.09111, Eq 9, after
 * Poschmann et al. 2021) weights them 0.5; this engine uses 1.0 to match pycalphad. */
static double chi_quads(int n_quads, const int *ca, const int *cb,
                        const int *ax, const int *ay, const double *X,
                        int cmix, int n_fixed, int subq, int a, int b, int f)
{
    int q = cmix ? find_quad(n_quads, ca, cb, ax, ay, a, b, f, f)
                 : find_quad(n_quads, ca, cb, ax, ay, f, f, a, b);
    double s = q >= 0 ? X[q] : 0.0;
    if (!subq) return s;
    for (int m = 0; m < n_fixed; ++m) {
        if (m == f) continue;
        q = cmix ? find_quad(n_quads, ca, cb, ax, ay, a, b, f, m)
                 : find_quad(n_quads, ca, cb, ax, ay, f, m, a, b);
        if (q >= 0) s += X[q];
    }
    return s;
}

/* The group interpolation of the Q code and the r > 1 factor are implemented where
 * the other sublattice holds a single species. With several, the published equations
 * can be read with overall site fractions or with pair fractions within the fixed
 * ion; those cases stay refused. The G code's Chi variables have one reading there
 * (chi_quads), with or without groups, as long as no additional constituent brings in
 * the Xi-based factor. */
mqmqa_xs_status mqmqa_excess_term_status(int n_cat, int n_an, int mix, int code,
                                         int A, int B, int X, int Y,
                                         double r, int addcat,
                                         const int *cat_group, const int *an_group)
{
    if (code != 0 && code != 1) return XS_CODE;
    if (mix != 0 && mix != 1) return XS_MIX;
    const int n_other = mix == 0 ? n_an : n_cat;
    if (addcat >= 0) {
        if (mix != 0) return XS_TERN_ANION;
        if (r < 1.0 || (r != 1.0 && n_other > 1)) return XS_TERN_R;
    }
    if (n_other > 1 && (code != 1 || addcat >= 0)
        && needs_groups(mix == 0 ? cat_group : an_group, mix == 0 ? n_cat : n_an,
                        mix == 0 ? A : X, mix == 0 ? B : Y))
        return XS_GROUPS;
    return XS_OK;
}

/* Excess energy for a set of MQMX interaction parameters, J per mole of quadruplets
 * (Poschmann eqs 19,20,24 for the mixing term, eq 17 for the assembly). Handles the
 * Q and G mixing codes (cation and anion mixing) with their chemical-group
 * interpolation, and an additional (ternary) cation with any exponent r >= 1
 * (Poschmann eqs 25-26). A term mqmqa_excess_term_status refuses returns NaN.
 *
 * Per parameter k: par_mix = 0 for cation mixing (A != B, single anion X = Y),
 * 1 for anion mixing (single cation A = B, anions X != Y). par_code = 0 for Q,
 * 1 for G. For cation mixing par_A,par_B are the mixing cations and par_X the
 * anion; for anion mixing par_A is the cation and par_X,par_Y the mixing anions.
 * soln_type (1 SUBQ, otherwise SUBG) decides whether Chi takes in the reciprocal
 * quadruplets (chi_quads).
 */
double mqmqa_excess_energy(
    int n_cat, int n_an, int n_quads,
    const int *quad_ca, const int *quad_cb,
    const int *quad_ax, const int *quad_ay,
    const double *X,
    const double *Za, const double *Zb, const double *Zx, const double *Zy,
    int soln_type,
    int n_params,
    const int *par_mix, const int *par_code,
    const int *par_A, const int *par_B, const int *par_X, const int *par_Y,
    const double *par_p, const double *par_q, const double *par_L,
    const double *par_r, const int *par_addcat,
    const int *cat_group, const int *an_group)
{
    for (int k = 0; k < n_params; ++k) {
        if (mqmqa_excess_term_status(n_cat, n_an, par_mix[k], par_code[k],
                                     par_A[k], par_B[k], par_X[k], par_Y[k],
                                     par_r ? par_r[k] : 1.0,
                                     par_addcat ? par_addcat[k] : -1,
                                     cat_group, an_group) != XS_OK)
            return NAN;
    }

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

        /* the mixing sublattice, its two species si,sj, the fixed ion f and the size
         * of its sublattice, and whether the term needs the group interpolation
         * (status guarantees a single fixed ion on the other side, except for the
         * G code's Chi) */
        const int cmix = par_mix[k] == 0;
        const int *grp = cmix ? cat_group : an_group;
        const int n_mix = cmix ? n_cat : n_an;
        const int si = cmix ? A : Xn, sj = cmix ? B : Yn;
        const int f = cmix ? Xn : A, n_fixed = cmix ? n_an : n_cat;
        const int subq = soln_type == 1;
        const int grouped = needs_groups(grp, n_mix, si, sj);

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

        /* With none of the term's quadruplets present the weight is exactly zero, and
         * the mixing fractions below can be 0/0 (a pure end-member); they are bounded,
         * so the term adds nothing, and skipping it keeps that zero from becoming NaN. */
        const double weight = Xbase + cation_factor + anion_factor;
        if (weight == 0.0) continue;

        /* mixing term */
        double g;
        if (grouped && par_code[k] == 1) {
            /* Chi of each side: the quadruplets built only from that side's species,
             * over those built from either side (gamma species excluded) */
            double s_i = 0.0, s_j = 0.0, s_all = 0.0;
            for (int a = 0; a < n_mix; ++a) {
                const int ai = on_side(grp, a, si, sj), aj = on_side(grp, a, sj, si);
                if (!ai && !aj) continue;
                for (int b = a; b < n_mix; ++b) {
                    const int bi = on_side(grp, b, si, sj), bj = on_side(grp, b, sj, si);
                    if (!bi && !bj) continue;
                    const double x = chi_quads(n_quads, quad_ca, quad_cb, quad_ax, quad_ay,
                                               X, cmix, n_fixed, subq, a, b, f);
                    s_all += x;
                    if (ai && bi) s_i += x;
                    if (aj && bj) s_j += x;
                }
            }
            g = par_L[k] * pow(s_i / s_all, p) * pow(s_j / s_all, qx);
        } else if (grouped) {
            /* Xi of each side: its species' pair fractions with the fixed ion */
            double xi_i = 0.0, xi_j = 0.0;
            for (int m = 0; m < n_mix; ++m) {
                const double f = cmix ? NIK(m, Xn) / 4.0 : NIK(A, m) / 4.0;
                if (on_side(grp, m, si, sj)) xi_i += f;
                else if (on_side(grp, m, sj, si)) xi_j += f;
            }
            g = par_L[k] * pow(xi_i, p) * pow(xi_j, qx) / pow(xi_i + xi_j, p + qx);
        } else if (par_code[k] == 1) {              /* G code, Chi_mix (Poschmann eq 21/23) */
            /* empty nu sets: Chi_i = X(i,i)/[X(i,i)+X(i,j)+X(j,j)] over the two
             * mixing constituents */
            const double xii = chi_quads(n_quads, quad_ca, quad_cb, quad_ax, quad_ay,
                                         X, cmix, n_fixed, subq, si, si, f);
            const double xij = chi_quads(n_quads, quad_ca, quad_cb, quad_ax, quad_ay,
                                         X, cmix, n_fixed, subq, si, sj, f);
            const double xjj = chi_quads(n_quads, quad_ca, quad_cb, quad_ax, quad_ay,
                                         X, cmix, n_fixed, subq, sj, sj, f);
            const double den = xii + xij + xjj;
            const double chi_i = xii / den, chi_j = xjj / den;
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

        /* Additional (ternary) cation m with exponent r, Poschmann Eq 25-26. When m
         * is interpolated with A (or B) the factor is m's share of that side times
         * (1 - A's (B's) share)^(r-1); otherwise m's pair fraction times
         * (1 - Xi_AB - Xi_BA)^(r-1). Beyond r = 1 or with groups the phase has a single
         * anion (status), whose site fraction Y_X is 1. */
        if (par_addcat && par_addcat[k] >= 0) {
            const int m = par_addcat[k];
            const double r = par_r ? par_r[k] : 1.0;
            const double xm = NIK(m, Xn) / 4.0;
            if (!grouped && r == 1.0) {
                g *= xm;
            } else {
                double xi_i = 0.0, xi_j = 0.0;
                for (int c = 0; c < n_cat; ++c) {
                    if (on_side(grp, c, A, B)) xi_i += NIK(c, Xn) / 4.0;
                    else if (on_side(grp, c, B, A)) xi_j += NIK(c, Xn) / 4.0;
                }
                if (grouped && on_side(grp, m, B, A))
                    g *= xm / xi_j * pow(1.0 - NIK(B, Xn) / 4.0 / xi_j, r - 1.0);
                else if (grouped && on_side(grp, m, A, B))
                    g *= xm / xi_i * pow(1.0 - NIK(A, Xn) / 4.0 / xi_i, r - 1.0);
                else
                    g *= xm * pow(1.0 - xi_i - xi_j, r - 1.0);
            }
        }

        energy += 0.5 * g * weight;
    }
#undef NIK

    free(nik);
    return energy;
}

/* add coef * d NIK(i,k)/dX to d: the pair count of each quadruplet */
static void nik_grad(int n_quads, const int *ca, const int *cb, const int *ax, const int *ay,
                     int i, int k, double coef, double *d)
{
    for (int q = 0; q < n_quads; ++q) {
        const int cnt = ((ca[q] == i) + (cb[q] == i)) * ((ax[q] == k) + (ay[q] == k));
        if (cnt) d[q] += coef * cnt;
    }
}

/* chi_quads, also adding coef to d for every quadruplet it counts */
static double chi_quads_grad(int n_quads, const int *ca, const int *cb,
                             const int *ax, const int *ay, const double *X,
                             int cmix, int n_fixed, int subq, int a, int b, int f,
                             double coef, double *d)
{
    int q = cmix ? find_quad(n_quads, ca, cb, ax, ay, a, b, f, f)
                 : find_quad(n_quads, ca, cb, ax, ay, f, f, a, b);
    double s = 0.0;
    if (q >= 0) { s = X[q]; d[q] += coef; }
    if (!subq) return s;
    for (int m = 0; m < n_fixed; ++m) {
        if (m == f) continue;
        q = cmix ? find_quad(n_quads, ca, cb, ax, ay, a, b, f, m)
                 : find_quad(n_quads, ca, cb, ax, ay, f, m, a, b);
        if (q >= 0) { s += X[q]; d[q] += coef; }
    }
    return s;
}

/* Gradient of mqmqa_excess_energy with respect to each quadruplet fraction, for strictly
 * positive X. Every term is 0.5 * weight * g with weight linear in X and
 * g = L u^p v^q / w^(p+q) (times the additional-cation factor), where u, v, w are linear
 * in X; the code below mirrors the energy routine branch by branch, carrying each linear
 * quantity with its gradient and applying the chain rule. grad is all NaN when a term is
 * one the engine refuses. */
void mqmqa_excess_gradient(
    int n_cat, int n_an, int n_quads,
    const int *quad_ca, const int *quad_cb,
    const int *quad_ax, const int *quad_ay,
    const double *X,
    const double *Za, const double *Zb, const double *Zx, const double *Zy,
    int soln_type,
    int n_params,
    const int *par_mix, const int *par_code,
    const int *par_A, const int *par_B, const int *par_X, const int *par_Y,
    const double *par_p, const double *par_q, const double *par_L,
    const double *par_r, const int *par_addcat,
    const int *cat_group, const int *an_group, double *grad)
{
    const int n = n_quads;
    for (int q = 0; q < n; ++q) grad[q] = 0.0;
    for (int k = 0; k < n_params; ++k) {
        if (mqmqa_excess_term_status(n_cat, n_an, par_mix[k], par_code[k],
                                     par_A[k], par_B[k], par_X[k], par_Y[k],
                                     par_r ? par_r[k] : 1.0,
                                     par_addcat ? par_addcat[k] : -1,
                                     cat_group, an_group) != XS_OK) {
            for (int q = 0; q < n; ++q) grad[q] = NAN;
            return;
        }
    }
    double *nik = (double *)calloc((size_t)n_cat * (size_t)n_an, sizeof(double));
    /* work vectors: weight, u, v, w, g, and three for the additional-cation factor */
    double *W = (double *)malloc((size_t)8 * n * sizeof(double));
    if (!nik || !W) {
        for (int q = 0; q < n; ++q) grad[q] = NAN;
        free(nik); free(W);
        return;
    }
    double *dwt = W, *du = W + n, *dv = W + 2 * n, *dw = W + 3 * n, *dg = W + 4 * n;
    double *dxm = W + 5 * n, *dxi = W + 6 * n, *dxj = W + 7 * n;
    for (int q = 0; q < n; ++q) {
        const double xq = X[q];
        nik[(size_t)quad_ca[q] * n_an + quad_ax[q]] += xq;
        nik[(size_t)quad_ca[q] * n_an + quad_ay[q]] += xq;
        nik[(size_t)quad_cb[q] * n_an + quad_ax[q]] += xq;
        nik[(size_t)quad_cb[q] * n_an + quad_ay[q]] += xq;
    }
#define NIK(i, k) nik[(size_t)(i) * n_an + (k)]
#define NIKG(i, k, coef, d) nik_grad(n, quad_ca, quad_cb, quad_ax, quad_ay, (i), (k), (coef), (d))

    for (int k = 0; k < n_params; ++k) {
        const int A = par_A[k], B = par_B[k], Xn = par_X[k], Yn = par_Y[k];
        const double p = par_p[k], qx = par_q[k];
        const int cmix = par_mix[k] == 0;
        const int *grp = cmix ? cat_group : an_group;
        const int n_mix = cmix ? n_cat : n_an;
        const int si = cmix ? A : Xn, sj = cmix ? B : Yn;
        const int f = cmix ? Xn : A, n_fixed = cmix ? n_an : n_cat;
        const int subq = soln_type == 1;
        const int grouped = needs_groups(grp, n_mix, si, sj);
        memset(W, 0, (size_t)8 * n * sizeof(double));

        const int qbase = find_quad(n, quad_ca, quad_cb, quad_ax, quad_ay, A, B, Xn, Yn);
        double weight = X[qbase];
        dwt[qbase] += 1.0;
        if (A == B) {
            const double zb = z_cation(qbase, A, quad_ca, quad_cb, Za, Zb) / 2.0;
            for (int m = 0; m < n_cat; ++m) {
                if (m == A) continue;
                const int qi = find_quad(n, quad_ca, quad_cb, quad_ax, quad_ay, A, m, Xn, Yn);
                if (qi < 0) continue;
                const double c = zb / z_cation(qi, A, quad_ca, quad_cb, Za, Zb);
                weight += c * X[qi];
                dwt[qi] += c;
            }
        }
        if (Xn == Yn) {
            const double zb = z_anion(qbase, Xn, quad_ax, quad_ay, Zx, Zy) / 2.0;
            for (int m = 0; m < n_an; ++m) {
                if (m == Xn) continue;
                const int qi = find_quad(n, quad_ca, quad_cb, quad_ax, quad_ay, A, B, Xn, m);
                if (qi < 0) continue;
                const double c = zb / z_anion(qi, Xn, quad_ax, quad_ay, Zx, Zy);
                weight += c * X[qi];
                dwt[qi] += c;
            }
        }
        if (weight == 0.0) continue;

        /* the mixing term's three linear quantities */
        double u = 0.0, v = 0.0, w = 0.0;
        if (grouped && par_code[k] == 1) {
            for (int a = 0; a < n_mix; ++a) {
                const int ai = on_side(grp, a, si, sj), aj = on_side(grp, a, sj, si);
                if (!ai && !aj) continue;
                for (int b = a; b < n_mix; ++b) {
                    const int bi = on_side(grp, b, si, sj), bj = on_side(grp, b, sj, si);
                    if (!bi && !bj) continue;
                    const double x = chi_quads_grad(n, quad_ca, quad_cb, quad_ax, quad_ay, X,
                                                    cmix, n_fixed, subq, a, b, f, 1.0, dw);
                    w += x;
                    if (ai && bi) {
                        u += chi_quads_grad(n, quad_ca, quad_cb, quad_ax, quad_ay, X,
                                            cmix, n_fixed, subq, a, b, f, 1.0, du);
                    }
                    if (aj && bj) {
                        v += chi_quads_grad(n, quad_ca, quad_cb, quad_ax, quad_ay, X,
                                            cmix, n_fixed, subq, a, b, f, 1.0, dv);
                    }
                }
            }
        } else if (grouped) {
            for (int m = 0; m < n_mix; ++m) {
                const int ci = cmix ? m : A, ck = cmix ? Xn : m;
                if (on_side(grp, m, si, sj)) { u += NIK(ci, ck) / 4.0; NIKG(ci, ck, 0.25, du); }
                else if (on_side(grp, m, sj, si)) { v += NIK(ci, ck) / 4.0; NIKG(ci, ck, 0.25, dv); }
            }
            w = u + v;
            for (int q = 0; q < n; ++q) dw[q] = du[q] + dv[q];
        } else if (par_code[k] == 1) {
            u = chi_quads_grad(n, quad_ca, quad_cb, quad_ax, quad_ay, X, cmix, n_fixed, subq,
                               si, si, f, 1.0, du);
            v = chi_quads_grad(n, quad_ca, quad_cb, quad_ax, quad_ay, X, cmix, n_fixed, subq,
                               sj, sj, f, 1.0, dv);
            w = u + v + chi_quads_grad(n, quad_ca, quad_cb, quad_ax, quad_ay, X, cmix, n_fixed,
                                       subq, si, sj, f, 1.0, dw);
            for (int q = 0; q < n; ++q) dw[q] += du[q] + dv[q];
        } else {
            const int jc = cmix ? B : A, jk = cmix ? Xn : Yn;
            u = NIK(A, Xn) / 4.0;
            NIKG(A, Xn, 0.25, du);
            v = NIK(jc, jk) / 4.0;
            NIKG(jc, jk, 0.25, dv);
            w = u + v;
            for (int q = 0; q < n; ++q) dw[q] = du[q] + dv[q];
        }
        /* g = L u^p v^q / w^(p+q) and its gradient by the logarithmic derivative. A zero
         * u or v with a positive exponent makes g zero; at strictly positive X that only
         * happens when the quantity has no quadruplet at all, so its gradient is zero too. */
        double g = par_L[k] * pow(u, p) * pow(v, qx) / pow(w, p + qx);
        if (!isfinite(g)) g = 0.0;
        for (int q = 0; q < n; ++q) {
            double l = 0.0;
            if (p != 0.0 && u > 0.0) l += p * du[q] / u;
            if (qx != 0.0 && v > 0.0) l += qx * dv[q] / v;
            if (p + qx != 0.0 && w > 0.0) l -= (p + qx) * dw[q] / w;
            dg[q] = g * l;
        }

        if (par_addcat && par_addcat[k] >= 0) {
            const int m = par_addcat[k];
            const double r = par_r ? par_r[k] : 1.0;
            const double xm = NIK(m, Xn) / 4.0;
            NIKG(m, Xn, 0.25, dxm);
            double T = 0.0;                 /* the factor; its gradient goes into du */
            memset(du, 0, (size_t)n * sizeof(double));
            if (!grouped && r == 1.0) {
                T = xm;
                memcpy(du, dxm, (size_t)n * sizeof(double));
            } else {
                double xi_i = 0.0, xi_j = 0.0;
                for (int c = 0; c < n_cat; ++c) {
                    if (on_side(grp, c, A, B)) { xi_i += NIK(c, Xn) / 4.0; NIKG(c, Xn, 0.25, dxi); }
                    else if (on_side(grp, c, B, A)) { xi_j += NIK(c, Xn) / 4.0; NIKG(c, Xn, 0.25, dxj); }
                }
                const int with_b = grouped && on_side(grp, m, B, A);
                const int with_a = !with_b && grouped && on_side(grp, m, A, B);
                if (with_b || with_a) {
                    /* T = xm / xs * (1 - ns/xs)^(r-1), s the side m is interpolated with */
                    const int side = with_b ? B : A;
                    const double xs = with_b ? xi_j : xi_i;
                    const double *dxs = with_b ? dxj : dxi;
                    const double ns = NIK(side, Xn) / 4.0;
                    const double s = 1.0 - ns / xs;
                    const double sp = pow(s, r - 1.0);
                    T = xm / xs * sp;
                    memset(dv, 0, (size_t)n * sizeof(double));
                    NIKG(side, Xn, 0.25, dv);                      /* d ns */
                    for (int q = 0; q < n; ++q) {
                        const double ds = -dv[q] / xs + ns * dxs[q] / (xs * xs);
                        double t = sp * (dxm[q] / xs - xm * dxs[q] / (xs * xs));
                        if (r != 1.0) t += xm / xs * (r - 1.0) * pow(s, r - 2.0) * ds;
                        du[q] = t;
                    }
                } else {
                    const double s = 1.0 - xi_i - xi_j;
                    const double sp = pow(s, r - 1.0);
                    T = xm * sp;
                    for (int q = 0; q < n; ++q) {
                        double t = sp * dxm[q];
                        if (r != 1.0) t -= xm * (r - 1.0) * pow(s, r - 2.0) * (dxi[q] + dxj[q]);
                        du[q] = t;
                    }
                }
            }
            for (int q = 0; q < n; ++q) dg[q] = dg[q] * T + g * du[q];
            g *= T;
        }

        for (int q = 0; q < n; ++q) grad[q] += 0.5 * (dg[q] * weight + g * dwt[q]);
    }
#undef NIK
#undef NIKG
    free(nik); free(W);
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
    /* Coordination numbers come from files at seven decimals, so quadruplet charge balance,
     * and with it the dependence between element rows, holds only to ~1e-7. A pivot or a
     * leftover right-hand side below 1e-6 is that rounding, not an independent constraint;
     * at 1e-12 a rounded mixed-coordination row (Mg-Si in the FeO-MgO-SiO2 slag) read as one
     * more constraint and pinned the liquid to an unmixed state 11 kJ/mol-atom too high. */
    const double tol = 1e-6;
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
        if (fabs(M[(size_t)r * (n + 1) + n]) > tol) {
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
    const double *par_r;                             /* ternary additional-constituent */
    const int *par_addcat;                           /* exponent r and cation (-1 none) */
    const int *cat_group, *an_group;                 /* chemical groups, NULL = one group */
    double R_own;                                    /* the data's own gas constant */
    const double *x0, *N;                            /* affine subspace X = x0 + N t */
    int n_null;
    double *Xbuf;                                    /* scratch, length n_quads */
    const double *lin;                               /* per-quadruplet term added to the
                                                        energy (-mu.n), NULL for none */
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
                                     c->Za, c->Zb, c->Zx, c->Zy, c->zeta, c->soln_type,
                                     c->R_own)
         + mqmqa_excess_energy(c->n_cat, c->n_an, c->n_quads,
                               c->ca, c->cb, c->ax, c->ay, X,
                               c->Za, c->Zb, c->Zx, c->Zy, c->soln_type,
                               c->n_params, c->par_mix, c->par_code,
                               c->par_A, c->par_B, c->par_X, c->par_Y,
                               c->par_p, c->par_q, c->par_L,
                               c->par_r, c->par_addcat,
                               c->cat_group, c->an_group);
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
    double g = ctx_gibbs_per_quad(c, c->Xbuf);
    if (c->lin)
        for (int q = 0; q < c->n_quads; ++q) g += c->lin[q] * c->Xbuf[q];
    return g;
}

/* Start points for the energy descent. The energy can have many minima on the feasible
 * set: ordering pairs give ordered and unmixed branches, and with several cations the
 * ordered states form separate pockets. A hit-and-run walk wanders over the whole
 * feasible polytope (a random direction, the chord through the current point, a uniform
 * point on it), and the lowest points it visits become the starts, best first; t itself
 * is always one. Deterministic, so a composition always gives the same answer. Returns
 * the number of starts written to seeds (k values each, at most max_seeds). */
static int eq_seeds(eqctx *c, const double *t, double *seeds, int max_seeds)
{
    enum { NSTEP = 3000 };
    const int k = c->n_null, n = c->n_quads;
    double *dir = (double *)malloc((size_t)k * sizeof(double));
    double *cur = (double *)malloc((size_t)k * sizeof(double));
    double *xc = (double *)malloc((size_t)n * sizeof(double));
    double *fs = (double *)malloc((size_t)max_seeds * sizeof(double));
    int ns = 0;
    if (!dir || !cur || !xc || !fs || max_seeds < 1) goto out;
    memcpy(cur, t, (size_t)k * sizeof(double));
    memcpy(seeds, t, (size_t)k * sizeof(double));
    fs[0] = obj_energy(t, c);
    ns = 1;
    /* One start per quadruplet, pushed from t as far toward that quadruplet as the
     * bounds allow (98% of the chord). Strong ordering puts the minimum near such a
     * corner, with one mixed quadruplet dominant and others nearly absent, where a
     * random walk seldom goes. These starts are kept whatever their energy. */
    ctx_X_from_t(c, t);
    for (int q = 0; q < n; ++q) xc[q] = c->Xbuf[q];
    for (int qq = 0; qq < n && ns < max_seeds; ++qq) {
        double nrm = 0.0;
        for (int j = 0; j < k; ++j) { dir[j] = c->N[(size_t)j * n + qq]; nrm += dir[j] * dir[j]; }
        if (nrm < 1e-24) continue;
        nrm = sqrt(nrm);
        for (int j = 0; j < k; ++j) dir[j] /= nrm;
        double hi = INFINITY;
        for (int q = 0; q < n; ++q) {
            double v = 0.0;
            for (int j = 0; j < k; ++j) v += c->N[(size_t)j * n + q] * dir[j];
            if (v < -1e-14) { double b = (EQ_XMIN - xc[q]) / v; if (b < hi) hi = b; }
        }
        if (!(hi > 0.0) || !isfinite(hi)) continue;
        double *sd = seeds + (size_t)ns * k;
        for (int j = 0; j < k; ++j) sd[j] = t[j] + 0.98 * hi * dir[j];
        fs[ns] = obj_energy(sd, c);
        if (fs[ns] < 1e11) ns++;
    }
    const int fixed = ns;
    unsigned long long s = 0x9E3779B97F4A7C15ull;
#define EQ_RAND() (s = s * 6364136223846793005ull + 1442695040888963407ull,                    (double)(s >> 11) / 9007199254740992.0)
    for (int step = 0; step < NSTEP; ++step) {
        double nrm = 0.0;
        for (int j = 0; j < k; ++j) { dir[j] = EQ_RAND() - 0.5; nrm += dir[j] * dir[j]; }
        if (nrm <= 0.0) continue;
        nrm = sqrt(nrm);
        for (int j = 0; j < k; ++j) dir[j] /= nrm;
        ctx_X_from_t(c, cur);
        for (int q = 0; q < n; ++q) xc[q] = c->Xbuf[q];
        double lo = -INFINITY, hi = INFINITY;
        for (int q = 0; q < n; ++q) {
            double v = 0.0;
            for (int j = 0; j < k; ++j) v += c->N[(size_t)j * n + q] * dir[j];
            if (v > 1e-14) { double b = (EQ_XMIN - xc[q]) / v; if (b > lo) lo = b; }
            else if (v < -1e-14) { double b = (EQ_XMIN - xc[q]) / v; if (b < hi) hi = b; }
        }
        if (!(hi > lo) || !isfinite(lo) || !isfinite(hi)) continue;
        const double a = lo + (hi - lo) * (0.02 + 0.96 * EQ_RAND());
        for (int j = 0; j < k; ++j) cur[j] += a * dir[j];
        const double f = obj_energy(cur, c);
        if (!(f < 1e11)) continue;
        int slot = ns < max_seeds ? ns++ : -1;
        if (slot < 0) {
            if (fixed >= max_seeds) continue;        /* t and the corner starts stay */
            int worst = fixed;
            for (int q = fixed + 1; q < max_seeds; ++q) if (fs[q] > fs[worst]) worst = q;
            if (f >= fs[worst]) continue;
            slot = worst;
        }
        memcpy(seeds + (size_t)slot * k, cur, (size_t)k * sizeof(double));
        fs[slot] = f;
    }
#undef EQ_RAND
out:
    free(dir); free(cur); free(xc); free(fs);
    return ns;
}

/* A point strictly inside the feasible set, by alternating projections: clip the
 * fractions up to a floor, then project back onto the affine set X = x0 + N t (least
 * squares through N^T N). When some quadruplets must be nearly absent the set is a thin
 * sliver, and the simplex on -min(X) alone can stay outside it, which left every later
 * start infeasible. t is overwritten only when an interior point is found. */
static void eq_feasible_start(eqctx *c, double *t)
{
    const int k = c->n_null, n = c->n_quads;
    double *G = malloc((size_t)k * k * sizeof(double));
    double *rhs = malloc((size_t)k * sizeof(double));
    double *tt = calloc((size_t)k, sizeof(double));
    double *Y = malloc((size_t)n * sizeof(double));
    if (!G || !rhs || !tt || !Y) goto out;
    for (int a = 0; a < k; ++a)
        for (int b = 0; b < k; ++b) {
            double v = 0.0;
            for (int q = 0; q < n; ++q) v += c->N[(size_t)a * n + q] * c->N[(size_t)b * n + q];
            G[a * k + b] = v;
        }
    /* Cholesky of N^T N (positive definite: the null-space columns are independent) */
    for (int a = 0; a < k; ++a)
        for (int b = 0; b <= a; ++b) {
            double v = G[a * k + b];
            for (int q = 0; q < b; ++q) v -= G[a * k + q] * G[b * k + q];
            if (a == b) { if (v <= 0.0) goto out; G[a * k + a] = sqrt(v); }
            else G[a * k + b] = v / G[b * k + b];
        }
    const double floor_ = 1e-9;
    for (int it = 0; it < 5000; ++it) {
        ctx_X_from_t(c, tt);
        double xmin = 1.0;
        for (int q = 0; q < n; ++q) if (c->Xbuf[q] < xmin) xmin = c->Xbuf[q];
        if (xmin >= 0.5 * floor_) { memcpy(t, tt, (size_t)k * sizeof(double)); break; }
        for (int q = 0; q < n; ++q) Y[q] = (c->Xbuf[q] < floor_ ? floor_ : c->Xbuf[q]) - c->x0[q];
        for (int a = 0; a < k; ++a) {
            double v = 0.0;
            for (int q = 0; q < n; ++q) v += c->N[(size_t)a * n + q] * Y[q];
            rhs[a] = v;
        }
        for (int a = 0; a < k; ++a) {
            double v = rhs[a];
            for (int q = 0; q < a; ++q) v -= G[a * k + q] * tt[q];
            tt[a] = v / G[a * k + a];
        }
        for (int a = k - 1; a >= 0; --a) {
            double v = tt[a];
            for (int q = a + 1; q < k; ++q) v -= G[q * k + a] * tt[q];
            tt[a] = v / G[a * k + a];
        }
    }
out:
    free(G); free(rhs); free(tt); free(Y);
}

/* Move t to the lowest-energy point found on chords through it: 32 directions, 7
 * points each between the chord's two ends on the feasible set. Deterministic, so a
 * composition always gives the same answer. */
static void eq_seed_global(eqctx *c, double *t)
{
    enum { NDIR = 32, NPT = 7 };
    const int k = c->n_null, n = c->n_quads;
    double *dir = (double *)malloc((size_t)k * sizeof(double));
    double *nd = (double *)malloc((size_t)n * sizeof(double));
    double *xc = (double *)malloc((size_t)n * sizeof(double));
    double *tt = (double *)malloc((size_t)k * sizeof(double));
    double *best = (double *)malloc((size_t)k * sizeof(double));
    if (!dir || !nd || !xc || !tt || !best) {
        free(dir); free(nd); free(xc); free(tt); free(best); return;
    }
    ctx_X_from_t(c, t);
    for (int q = 0; q < n; ++q) xc[q] = c->Xbuf[q];
    for (int j = 0; j < k; ++j) best[j] = t[j];
    double fbest = obj_energy(t, c);
    unsigned long long s = 0x9E3779B97F4A7C15ull;
    for (int r = 0; r < NDIR; ++r) {
        double nrm = 0.0;
        for (int j = 0; j < k; ++j) {
            s = s * 6364136223846793005ull + 1442695040888963407ull;
            dir[j] = (double)(s >> 11) / 9007199254740992.0 - 0.5;
            nrm += dir[j] * dir[j];
        }
        if (nrm <= 0.0) continue;
        nrm = sqrt(nrm);
        for (int j = 0; j < k; ++j) dir[j] /= nrm;
        /* chord ends where the first fraction reaches EQ_XMIN */
        double lo = -INFINITY, hi = INFINITY;
        for (int q = 0; q < n; ++q) {
            double v = 0.0;
            for (int j = 0; j < k; ++j) v += c->N[(size_t)j * n + q] * dir[j];
            nd[q] = v;
            if (v > 1e-14) { double b = (EQ_XMIN - xc[q]) / v; if (b > lo) lo = b; }
            else if (v < -1e-14) { double b = (EQ_XMIN - xc[q]) / v; if (b < hi) hi = b; }
        }
        if (!(hi > lo) || !isfinite(lo) || !isfinite(hi)) continue;
        for (int i = 1; i <= NPT; ++i) {
            double a = lo + (hi - lo) * i / (NPT + 1.0);
            for (int j = 0; j < k; ++j) tt[j] = t[j] + a * dir[j];
            double f = obj_energy(tt, c);
            if (f < fbest) { fbest = f; for (int j = 0; j < k; ++j) best[j] = tt[j]; }
        }
    }
    for (int j = 0; j < k; ++j) t[j] = best[j];
    free(dir); free(nd); free(xc); free(tt); free(best);
}

typedef double (*eq_objfn)(const double *t, void *ctx);

/* Gradient of ctx_gibbs_per_quad with respect to each quadruplet fraction, X strictly
 * positive: the reference energy is linear in X, and the entropy and the excess terms
 * have the exact gradients above. work has n_quads entries. */
static void ctx_gradient(const eqctx *c, const double *X, double *g, double *work)
{
    const int n = c->n_quads;
    mqmqa_ideal_mixing_gradient(c->T, c->n_cat, c->n_an, n, c->ca, c->cb, c->ax, c->ay, X,
                                c->Za, c->Zb, c->Zx, c->Zy, c->zeta, c->soln_type,
                                c->R_own, g);
    for (int p = 0; p < c->n_pairs; ++p) {
        const int a = c->pair_c[p], x = c->pair_a[p];
        const double *Zp = c->Zref + (size_t)p * (size_t)n;
        const double w = c->Gax[p] / c->stoich[p];
        for (int q = 0; q < n; ++q) {
            const int cnt_a = (c->ca[q] == a) + (c->cb[q] == a);
            const int cnt_x = (c->ax[q] == x) + (c->ay[q] == x);
            if (cnt_a && cnt_x) g[q] += w * (double)(cnt_a * cnt_x) / (2.0 * Zp[q]);
        }
    }
    if (c->lin) for (int q = 0; q < n; ++q) g[q] += c->lin[q];
    if (c->n_params <= 0) return;
    mqmqa_excess_gradient(c->n_cat, c->n_an, n, c->ca, c->cb, c->ax, c->ay, X,
                          c->Za, c->Zb, c->Zx, c->Zy, c->soln_type,
                          c->n_params, c->par_mix, c->par_code,
                          c->par_A, c->par_B, c->par_X, c->par_Y,
                          c->par_p, c->par_q, c->par_L, c->par_r, c->par_addcat,
                          c->cat_group, c->an_group, work);
    for (int q = 0; q < n; ++q) g[q] += work[q];
}

/* reduced gradient N^T grad at t; returns 0 when t is outside the bounds */
static int eq_reduced_gradient(eqctx *c, const double *t, double *gr, double *gX, double *work)
{
    const int k = c->n_null, n = c->n_quads;
    ctx_X_from_t(c, t);
    for (int q = 0; q < n; ++q) if (c->Xbuf[q] < EQ_XMIN) return 0;
    ctx_gradient(c, c->Xbuf, gX, work);
    for (int a = 0; a < k; ++a) {
        double v = 0.0;
        for (int q = 0; q < n; ++q) v += c->N[(size_t)a * n + q] * gX[q];
        gr[a] = v;
    }
    return 1;
}

/* Newton finish on the feasible subspace. The simplex stops short of the minimum, and
 * near a vanishing fraction its steps and any finite difference of the energy lose all
 * precision. With the gradient above the Hessian comes from differences of gradients,
 * taken over a step well inside the nearest bound, where the entropy's 1/X curvature
 * dominates and is resolved cleanly. Steps are damped toward the gradient direction
 * when the Hessian is not positive definite and backtracked to stay inside the bounds. */
static void eq_newton(eqctx *c, double *t)
{
    const int k = c->n_null, n = c->n_quads;
    if (k <= 0) return;
    double *g = malloc((size_t)k * sizeof(double));
    double *g1 = malloc((size_t)k * sizeof(double));
    double *g2 = malloc((size_t)k * sizeof(double));
    double *H = malloc((size_t)k * k * sizeof(double));
    double *M = malloc((size_t)k * k * sizeof(double));
    double *p = malloc((size_t)k * sizeof(double));
    double *tt = malloc((size_t)k * sizeof(double));
    double *gX = malloc((size_t)n * sizeof(double));
    double *work = malloc((size_t)n * sizeof(double));
    if (!g || !g1 || !g2 || !H || !M || !p || !tt || !gX || !work) goto out;
    double f0 = obj_energy(t, c);
    for (int iter = 0; iter < 60 && f0 < 1e11; ++iter) {
        if (!eq_reduced_gradient(c, t, g, gX, work)) break;
        double xmin = 1.0;
        for (int q = 0; q < n; ++q) if (c->Xbuf[q] < xmin) xmin = c->Xbuf[q];
        double h = 1e-3 * xmin;
        if (h > 1e-6) h = 1e-6;
        memcpy(tt, t, (size_t)k * sizeof(double));
        int ok = 1;
        for (int b = 0; b < k && ok; ++b) {
            tt[b] = t[b] + h;
            ok = eq_reduced_gradient(c, tt, g1, gX, work);
            tt[b] = t[b] - h;
            ok = ok && eq_reduced_gradient(c, tt, g2, gX, work);
            tt[b] = t[b];
            for (int a = 0; a < k; ++a) H[a * k + b] = (g1[a] - g2[a]) / (2.0 * h);
        }
        if (!ok) break;
        for (int a = 0; a < k; ++a)
            for (int b = 0; b < a; ++b) H[a * k + b] = H[b * k + a] = 0.5 * (H[a * k + b] + H[b * k + a]);
        double scale = 0.0;
        for (int a = 0; a < k; ++a) scale = fmax(scale, fabs(H[a * k + a]));
        double lambda = 0.0;
        ok = 0;
        for (int tries = 0; tries < 40 && !ok; ++tries) {
            memcpy(M, H, (size_t)k * k * sizeof(double));
            for (int a = 0; a < k; ++a) M[a * k + a] += lambda;
            ok = 1;
            for (int a = 0; a < k && ok; ++a)
                for (int b = 0; b <= a; ++b) {
                    double v = M[a * k + b];
                    for (int q = 0; q < b; ++q) v -= M[a * k + q] * M[b * k + q];
                    if (a == b) { if (v <= 0.0) { ok = 0; break; } M[a * k + a] = sqrt(v); }
                    else M[a * k + b] = v / M[b * k + b];
                }
            if (!ok) lambda = lambda > 0.0 ? 10.0 * lambda : 1e-8 * (scale > 0.0 ? scale : 1.0);
        }
        if (!ok) break;
        for (int a = 0; a < k; ++a) {               /* L L^T p = -g */
            double v = -g[a];
            for (int q = 0; q < a; ++q) v -= M[a * k + q] * p[q];
            p[a] = v / M[a * k + a];
        }
        for (int a = k - 1; a >= 0; --a) {
            double v = p[a];
            for (int q = a + 1; q < k; ++q) v -= M[q * k + a] * p[q];
            p[a] = v / M[a * k + a];
        }
        double decrease = 0.0;
        for (int a = 0; a < k; ++a) decrease -= g[a] * p[a];
        if (!(decrease > 1e-14 * (fabs(f0) + 1.0))) break;      /* converged */
        double alpha = 1.0, f1 = f0;
        for (int ls = 0; ls < 60; ++ls, alpha *= 0.5) {
            for (int a = 0; a < k; ++a) tt[a] = t[a] + alpha * p[a];
            f1 = obj_energy(tt, c);
            if (f1 < f0) break;
        }
        if (!(f1 < f0)) break;
        memcpy(t, tt, (size_t)k * sizeof(double));
        f0 = f1;
    }
out:
    free(g); free(g1); free(g2); free(H); free(M); free(p); free(tt); free(gX); free(work);
}

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

/* Element amounts per quadruplet E[e][q] and atoms per quadruplet A[q]; the caller frees
 * both. Returns -1 when out of memory. */
static int quad_elements(int n_cat, int n_quads, const int *quad_ca, const int *quad_cb,
                         const int *quad_ax, const int *quad_ay,
                         const double *Za, const double *Zb, const double *Zx, const double *Zy,
                         int n_elem, const double *ion_comp,
                         double **E_out, double **A_out)
{
    double *E = (double *)calloc((size_t)n_elem * n_quads, sizeof(double));
    double *A = (double *)calloc((size_t)n_quads, sizeof(double));
    if (!E || !A) { free(E); free(A); return -1; }
    for (int q = 0; q < n_quads; ++q) {
        /* each site the quadruplet holds contributes 1/Z of its ion, in this order */
        const int ion[4] = { quad_ca[q], quad_cb[q], n_cat + quad_ax[q], n_cat + quad_ay[q] };
        const double inv[4] = { 1.0 / Za[q], 1.0 / Zb[q], 1.0 / Zx[q], 1.0 / Zy[q] };
        double atoms = 0.0;
        for (int k = 0; k < 4; ++k) {
            const double *c = ion_comp + (size_t)ion[k] * n_elem;
            double na = 0.0;
            for (int e = 0; e < n_elem; ++e) {
                E[(size_t)e * n_quads + q] += c[e] * inv[k];
                na += c[e];
            }
            atoms += na * inv[k];
        }
        A[q] = atoms;
    }
    *E_out = E;
    *A_out = A;
    return 0;
}

/* One atom of element cat_elem[i] (an_elem[k]) per ion, as a composition matrix */
static double *one_atom_comp(int n_cat, int n_an, int n_elem, const int *cat_elem, const int *an_elem)
{
    double *c = calloc((size_t)(n_cat + n_an) * n_elem, sizeof(double));
    if (!c) return NULL;
    for (int i = 0; i < n_cat; ++i) c[(size_t)i * n_elem + cat_elem[i]] = 1.0;
    for (int k = 0; k < n_an; ++k) c[(size_t)(n_cat + k) * n_elem + an_elem[k]] = 1.0;
    return c;
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
    const double *par_r, const int *par_addcat,
    const int *cat_group, const int *an_group,
    double R_own,
    int n_elem,
    const int *cat_elem, const int *an_elem,
    const double *target,
    double *X_out, double *comp_err_out)
{
    double *ion_comp = one_atom_comp(n_cat, n_an, n_elem, cat_elem, an_elem);
    if (!ion_comp) return NAN;
    const double r = mqmqa_equilibrate_comp(
        T, n_cat, n_an, n_quads, quad_ca, quad_cb, quad_ax, quad_ay, Za, Zb, Zx, Zy, zeta,
        soln_type, n_pairs, pair_c, pair_a, Gax, stoich, Zref, n_params, par_mix, par_code,
        par_A, par_B, par_X, par_Y, par_p, par_q, par_L, par_r, par_addcat, cat_group,
        an_group, R_own, n_elem, ion_comp, target, X_out, comp_err_out);
    free(ion_comp);
    return r;
}

/* The descents stop where their tolerances stop them, and on a liquid with strongly ordered
 * pairs that was hundreds of J/mol above the minimum: CuFeC-Kang's Fe-C liquid at 1600 K came
 * out 425 J/mol above pycalphad's energy at the same composition, and a ClAlNa melt holding
 * the Al2 dimer 3.4 kJ/mol above the state the driving-force minimizer reaches. The
 * conditions at the minimum are checked directly (each quadruplet's potential, from the exact
 * gradient, the sum of its elements' potentials, these fitted by least squares over the
 * quadruplets present). Only where they fail by more than EQX_GATE is Newton run on them, the
 * quadruplets taken as species and the composition held; its result replaces X only when the
 * energy drops by more than 1e-9 of itself. A liquid the descent already reached is left bit
 * for bit as it was. */
#define EQX_GATE 1e-3       /* potential residual in units of RT that calls for the finish */
/* On everywhere since 16 November 2026 (Michael), the web app's liquids included. Before then
 * only the general solver used it; on 7000 random compositions of the shipped liquids the
 * finish lowered 69 energies, median 0.03 J/mol, at most 386 (CaO-Al2O3-SiO2 at 1673 K).
 * mqmqa_exact_finish(0) gives back the earlier path for comparison. */
static int eq_exact_on = 1;

int mqmqa_exact_finish(int on)
{
    const int old = eq_exact_on;
    eq_exact_on = on;
    return old;
}
#define EQX_TOL 1e-10       /* potential residual in units of RT to stop at */
#define EQX_TOLB 1e-15      /* composition residual, mol per mol of atoms */
#define EQX_ZERO 69.0       /* log amount, about 1e-30, at which a quadruplet is held at zero:
                               pair products of smaller fractions underflow and the gradient's
                               logs turn NaN */

static void eqx_grad(const eqctx *c, const double *X, double *grad)
{
    mqmqa_gibbs_gradient(c->T, c->n_cat, c->n_an, c->n_quads, c->ca, c->cb, c->ax, c->ay,
                         c->Za, c->Zb, c->Zx, c->Zy, c->zeta, c->soln_type,
                         c->n_pairs, c->pair_c, c->pair_a, c->Gax, c->stoich, c->Zref,
                         c->n_params, c->par_mix, c->par_code, c->par_A, c->par_B, c->par_X,
                         c->par_Y, c->par_p, c->par_q, c->par_L, c->par_r, c->par_addcat,
                         c->cat_group, c->an_group, c->R_own, X, grad);
}

/* rows at log amounts u (quadruplets) and m (element potentials over RT): the quadruplet
 * rows, then the composition rows; rest gets each quadruplet row less ln X. -1 if not
 * evaluable. */
static int eqx_rows(const eqctx *c, int ne, const int *el, const double *E, const double *target,
                    const double *u, const char *frz, double RT, double *X, double *grad,
                    double *r, double *rest)
{
    const int n = c->n_quads;
    double tot = 0.0;
    for (int q = 0; q < n; ++q) {
        if (u[q] > 700.0) return -1;
        X[q] = exp(u[q]);
        tot += X[q];
    }
    double *bal = r + n;
    for (int k = 0; k < ne; ++k) {
        bal[k] = -target[el[k]];
        for (int q = 0; q < n; ++q) bal[k] += X[q] * E[(size_t)el[k] * n + q];
    }
    for (int q = 0; q < n; ++q) X[q] /= tot;
    const double g = ctx_gibbs_per_quad(c, X);
    eqx_grad(c, X, grad);
    double sg = 0.0;
    for (int q = 0; q < n; ++q) sg += X[q] * grad[q];
    if (!isfinite(g) || !isfinite(sg)) return -1;
    const double *m = u + n;
    for (int q = 0; q < n; ++q) {
        double v = (g + grad[q] - sg) / RT;
        for (int k = 0; k < ne; ++k) v -= E[(size_t)el[k] * n + q] * m[k];
        if (rest) rest[q] = v - log(X[q]);
        r[q] = frz[q] ? 0.0 : v;
    }
    return 0;
}

static double eqx_ss(const double *r, int n)
{
    double s = 0.0;
    for (int i = 0; i < n; ++i) s += r[i] * r[i];
    return s;
}

static void eq_exact(eqctx *c, int n_elem, const double *E, const double *A, const double *target)
{
    const int n = c->n_quads;
    int el[64], ne = 0;
    for (int e = 0; e < n_elem; ++e) if (target[e] > 0.0) { if (ne == 64) return; el[ne++] = e; }
    if (ne == 0) return;
    const int N = n + ne;
    const double RT = mqmqa_gas_constant(c->R_own) * c->T;
    double *u = malloc((size_t)N * sizeof(double)), *u1 = malloc((size_t)N * sizeof(double));
    double *r = malloc((size_t)N * sizeof(double)), *r1 = malloc((size_t)N * sizeof(double));
    double *J = malloc((size_t)N * N * sizeof(double)), *st = malloc((size_t)N * sizeof(double));
    double *X = malloc((size_t)n * sizeof(double)), *grad = malloc((size_t)n * sizeof(double));
    double *rest = malloc((size_t)n * sizeof(double)), *rp = malloc((size_t)N * sizeof(double));
    double *X0 = malloc((size_t)n * sizeof(double));
    char *frz = calloc((size_t)n, 1);
    if (!u || !u1 || !r || !r1 || !J || !st || !X || !grad || !rest || !rp || !X0 || !frz) goto out;

    /* The descent's X, per mole of atoms; a quadruplet of an element the composition lacks is
     * held at zero */
    memcpy(X0, c->Xbuf, (size_t)n * sizeof(double));
    double atoms = 0.0;
    for (int q = 0; q < n; ++q) atoms += X0[q] * A[q];
    if (!(atoms > 0.0)) goto out;
    for (int q = 0; q < n; ++q) {
        for (int e = 0; e < n_elem; ++e) if (!(target[e] > 0.0) && E[(size_t)e * n + q] > 0.0) frz[q] = 1;
        u[q] = frz[q] ? -EQX_ZERO : fmax(log(fmax(X0[q], 1e-300) / atoms), -EQX_ZERO);
    }
    /* the gate: element potentials by least squares over the quadruplets present */
    for (int k = 0; k < ne; ++k) u[n + k] = 0.0;
    if (eqx_rows(c, ne, el, E, target, u, frz, RT, X, grad, r, NULL)) goto out;
    {
        double M[64 * 64] = {0}, b[64] = {0};
        for (int q = 0; q < n; ++q) {
            if (frz[q] || !(X[q] > 1e-6)) continue;
            for (int a = 0; a < ne; ++a) {
                b[a] += X[q] * E[(size_t)el[a] * n + q] * r[q];
                for (int bb = 0; bb < ne; ++bb)
                    M[a * ne + bb] += X[q] * E[(size_t)el[a] * n + q] * E[(size_t)el[bb] * n + q];
            }
        }
        for (int a = 0; a < ne; ++a) M[a * ne + a] += 1e-12;
        for (int cc = 0; cc < ne; ++cc) {                  /* Gauss on the small normal system */
            int p = cc;
            for (int rr = cc + 1; rr < ne; ++rr) if (fabs(M[rr * ne + cc]) > fabs(M[p * ne + cc])) p = rr;
            if (!(fabs(M[p * ne + cc]) > 0.0)) goto out;
            for (int k = 0; k < ne; ++k) { double t = M[cc * ne + k]; M[cc * ne + k] = M[p * ne + k]; M[p * ne + k] = t; }
            double t = b[cc]; b[cc] = b[p]; b[p] = t;
            for (int rr = cc + 1; rr < ne; ++rr) {
                const double f = M[rr * ne + cc] / M[cc * ne + cc];
                for (int k = cc; k < ne; ++k) M[rr * ne + k] -= f * M[cc * ne + k];
                b[rr] -= f * b[cc];
            }
        }
        for (int rr = ne - 1; rr >= 0; --rr) {
            double s = b[rr];
            for (int k = rr + 1; k < ne; ++k) s -= M[rr * ne + k] * b[k];
            u[n + rr] = s / M[rr * ne + rr];
        }
    }
    if (eqx_rows(c, ne, el, E, target, u, frz, RT, X, grad, r, rest)) goto out;
    double worst = 0.0;
    for (int q = 0; q < n; ++q) if (!frz[q] && X[q] > 1e-6) worst = fmax(worst, fabs(r[q]));
    if (!(worst > EQX_GATE)) goto out;

    double f = eqx_ss(r, N), floor2 = 100.0 * (n * EQX_TOL * EQX_TOL + ne * EQX_TOLB * EQX_TOLB);
    int done = 0;
    for (int it = 0; it < 80 && !done; ++it) {
        int changed = 0;
        for (int q = 0; q < n; ++q)
            if (!frz[q] && u[q] < -EQX_ZERO + 9.0 && rest[q] > EQX_ZERO - 10.0) { frz[q] = 1; u[q] = -EQX_ZERO; changed = 1; }
        if (changed) {
            if (eqx_rows(c, ne, el, E, target, u, frz, RT, X, grad, r, rest)) goto out;
            f = eqx_ss(r, N);
        }
        memset(J, 0, (size_t)N * N * sizeof(double));
        for (int k = 0; k < n; ++k) {
            if (frz[k]) { J[k * N + k] = 1.0; continue; }
            const double d = 1e-6;
            memcpy(u1, u, (size_t)N * sizeof(double));
            u1[k] = u[k] + d;
            if (eqx_rows(c, ne, el, E, target, u1, frz, RT, X, grad, rp, NULL)) goto out;
            u1[k] = u[k] - d;
            if (eqx_rows(c, ne, el, E, target, u1, frz, RT, X, grad, r1, NULL)) goto out;
            for (int i = 0; i < N; ++i)
                if (i >= n || !frz[i]) J[i * N + k] = (rp[i] - r1[i]) / (2 * d);
        }
        for (int q = 0; q < n; ++q)
            if (!frz[q])
                for (int kk = 0; kk < ne; ++kk) J[q * N + n + kk] = -E[(size_t)el[kk] * n + q];
        for (int i = 0; i < N; ++i) st[i] = -r[i];
        /* Gauss with partial pivoting on the whole system */
        int bad = 0;
        for (int cc = 0; cc < N && !bad; ++cc) {
            int p = cc;
            for (int rr = cc + 1; rr < N; ++rr) if (fabs(J[rr * N + cc]) > fabs(J[p * N + cc])) p = rr;
            if (!(fabs(J[p * N + cc]) > 0.0) || !isfinite(J[p * N + cc])) { bad = 1; break; }
            if (p != cc) {
                for (int k = 0; k < N; ++k) { double t = J[cc * N + k]; J[cc * N + k] = J[p * N + k]; J[p * N + k] = t; }
                double t = st[cc]; st[cc] = st[p]; st[p] = t;
            }
            for (int rr = cc + 1; rr < N; ++rr) {
                const double fct = J[rr * N + cc] / J[cc * N + cc];
                if (fct == 0.0) continue;
                for (int k = cc; k < N; ++k) J[rr * N + k] -= fct * J[cc * N + k];
                st[rr] -= fct * st[cc];
            }
        }
        if (bad) goto out;
        for (int rr = N - 1; rr >= 0; --rr) {
            double s = st[rr];
            for (int k = rr + 1; k < N; ++k) s -= J[rr * N + k] * st[k];
            st[rr] = s / J[rr * N + rr];
        }
        double big = 0.0;
        for (int q = 0; q < n; ++q) if (!frz[q] && u[q] > -20.0) big = fmax(big, fabs(st[q]));
        const double alpha0 = big > 2.0 ? 2.0 / big : 1.0;
        double alpha = alpha0, f1 = INFINITY;
        int ok = 0;
        for (int ls = 0; ls < 30 && !ok; ++ls, alpha *= 0.5) {
            for (int pass = 0; pass < 2 && !ok; ++pass) {       /* as in gem.c's finish */
                const double beta = pass ? alpha / alpha0 : 1.0;
                if (pass && ls == 0) continue;
                for (int i = 0; i < N; ++i) u1[i] = u[i] + alpha * st[i];
                for (int q = 0; q < n; ++q) {
                    if (frz[q]) continue;
                    if (u[q] < -20.0) u1[q] = fmin(u[q] + beta * fmax(fmin(st[q], 60.0), -60.0), fmax(u[q], -15.0));
                    if (u1[q] < -EQX_ZERO) u1[q] = -EQX_ZERO;
                }
                ok = !eqx_rows(c, ne, el, E, target, u1, frz, RT, X, grad, r1, rest)
                     && ((f1 = eqx_ss(r1, N)) < f * (1.0 - 1e-4 * alpha) || f1 < floor2);
            }
        }
        if (!ok) break;
        memcpy(u, u1, (size_t)N * sizeof(double));
        memcpy(r, r1, (size_t)N * sizeof(double));
        f = f1;
        done = 1;
        for (int q = 0; q < n && done; ++q) if (fabs(r[q]) > EQX_TOL) done = 0;
        for (int k = 0; k < ne && done; ++k) if (fabs(r[n + k]) > EQX_TOLB) done = 0;
    }
    if (!done) goto out;
    {
        double tot = 0.0;
        for (int q = 0; q < n; ++q) { X[q] = frz[q] ? 0.0 : exp(u[q]); tot += X[q]; }
        for (int q = 0; q < n; ++q) X[q] /= tot;
        double a1 = 0.0, a0 = 0.0;
        for (int q = 0; q < n; ++q) { a1 += X[q] * A[q]; a0 += X0[q] * A[q]; }
        const double g1 = ctx_gibbs_per_quad(c, X) / a1, g0 = ctx_gibbs_per_quad(c, X0) / a0;
        if (isfinite(g1) && g1 < g0 - 1e-9 * fabs(g0)) memcpy(c->Xbuf, X, (size_t)n * sizeof(double));
    }
out:
    free(u); free(u1); free(r); free(r1); free(J); free(st); free(X); free(grad); free(rest); free(rp);
    free(X0); free(frz);
}

double mqmqa_equilibrate_comp(
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
    const double *par_r, const int *par_addcat,
    const int *cat_group, const int *an_group,
    double R_own,
    int n_elem,
    const double *ion_comp,
    const double *target,
    double *X_out, double *comp_err_out)
{
    /* An excess term the engine cannot evaluate makes every energy NaN; stop here
     * rather than hand the minimizer a NaN landscape. */
    for (int k = 0; k < n_params; ++k)
        if (mqmqa_excess_term_status(n_cat, n_an, par_mix[k], par_code[k],
                                     par_A[k], par_B[k], par_X[k], par_Y[k],
                                     par_r ? par_r[k] : 1.0,
                                     par_addcat ? par_addcat[k] : -1,
                                     cat_group, an_group) != XS_OK)
            return NAN;

    double *E, *A;
    if (quad_elements(n_cat, n_quads, quad_ca, quad_cb, quad_ax, quad_ay, Za, Zb, Zx, Zy,
                      n_elem, ion_comp, &E, &A)) return NAN;

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
        par_p, par_q, par_L, par_r, par_addcat,
        cat_group, an_group, R_own,
        x0, N, n_null,
        (double *)malloc((size_t)n_quads * sizeof(double)),
        NULL,
    };
    if (!ctx.Xbuf) { free(E); free(A); free(x0); free(N); return NAN; }

    double gm = NAN;
    if (n_null == 0) {
        ctx_X_from_t(&ctx, NULL);                    /* unique solution */
    } else {
        double *t = (double *)calloc((size_t)n_null, sizeof(double));
        if (!t) { free(ctx.Xbuf); free(E); free(A); free(x0); free(N); return NAN; }

        /* Phase 1: reach a strictly interior feasible point. */
        /* Up to three cations (six quadruplets with one anion) the shipped descent below
         * reaches the minimum, checked against pycalphad on one-liquid compositions, and it
         * runs unchanged. Larger liquids also get a feasible start by projection and a
         * multi-start search, without which ordered pockets are missed by kJ. */
        const int multi = n_quads > 6;
        if (multi) eq_feasible_start(&ctx, t);
        nelder_mead(obj_feasible, &ctx, n_null, t, 0.1, 4000, 1e-16);
        if (!multi) {
            eq_seed_global(&ctx, t);
            for (int r = 0; r < 4; ++r)
                nelder_mead(obj_energy, &ctx, n_null, t, 0.05, 4000, 1e-12);
        } else {
            const int NSEED = 1 + n_quads + 6;          /* t, the corners, six from the walk */
            double *seeds = (double *)malloc((size_t)NSEED * n_null * sizeof(double));
            double *tt = (double *)malloc((size_t)n_null * sizeof(double));
            if (!seeds || !tt) { free(seeds); free(tt); free(t); free(ctx.Xbuf); free(E); free(A); free(x0); free(N); return NAN; }
            const int ns = eq_seeds(&ctx, t, seeds, NSEED);
            /* Phase 2, from every start: the simplex into the basin, Newton to its floor;
             * keep the lowest. With every vertex outside the bounds the penalties differ by
             * less than the loose tolerance and the simplex can stop there, so that case
             * falls back to the tight search, which never does. */
            double fbest = INFINITY;
            for (int sd = 0; sd < ns; ++sd) {
                memcpy(tt, seeds + (size_t)sd * n_null, (size_t)n_null * sizeof(double));
                eq_newton(&ctx, tt);
                const double f = obj_energy(tt, &ctx);
                if (f < fbest) { fbest = f; memcpy(t, tt, (size_t)n_null * sizeof(double)); }
            }
            /* Also the shipped careful descent (four tight simplex runs) from the lowest
             * start, then Newton: one more candidate, which one composition in 24 needed. */
            {
                int lowest = 0;
                double flow = INFINITY;
                for (int sd = 0; sd < ns; ++sd) {
                    double f0 = obj_energy(seeds + (size_t)sd * n_null, &ctx);
                    if (f0 < flow) { flow = f0; lowest = sd; }
                }
                memcpy(tt, seeds + (size_t)lowest * n_null, (size_t)n_null * sizeof(double));
                for (int r = 0; r < 4; ++r)
                    nelder_mead(obj_energy, &ctx, n_null, tt, 0.05, 4000, 1e-12);
                eq_newton(&ctx, tt);
                const double f = obj_energy(tt, &ctx);
                if (f < fbest) { fbest = f; memcpy(t, tt, (size_t)n_null * sizeof(double)); }
            }
            free(seeds); free(tt);
        }
        ctx_X_from_t(&ctx, t);
        free(t);
    }

    /* Clamp roundoff-negative fractions to zero before the final evaluation: the
     * energy routines skip zero-weight quadruplets, so this keeps a fraction left
     * a hair below zero by the minimizer from poisoning G with a log of a negative. */
    for (int q = 0; q < n_quads; ++q)
        if (ctx.Xbuf[q] < 0.0) ctx.Xbuf[q] = 0.0;
    if (n_null > 0 && eq_exact_on) eq_exact(&ctx, n_elem, E, A, target);

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

/* t whose X = x0 + N t is closest to X (least squares through N^T N); 0 on success */
static int eq_t_of_X(const eqctx *c, const double *X, double *t)
{
    const int k = c->n_null, n = c->n_quads;
    double *G = malloc((size_t)k * k * sizeof(double));
    int rc = -1;
    if (!G) return -1;
    for (int a = 0; a < k; ++a) {
        for (int b = 0; b < k; ++b) {
            double v = 0.0;
            for (int q = 0; q < n; ++q) v += c->N[(size_t)a * n + q] * c->N[(size_t)b * n + q];
            G[a * k + b] = v;
        }
        double v = 0.0;
        for (int q = 0; q < n; ++q) v += c->N[(size_t)a * n + q] * (X[q] - c->x0[q]);
        t[a] = v;
    }
    for (int a = 0; a < k; ++a)
        for (int b = 0; b <= a; ++b) {
            double v = G[a * k + b];
            for (int q = 0; q < b; ++q) v -= G[a * k + q] * G[b * k + q];
            if (a == b) { if (v <= 0.0) goto out; G[a * k + a] = sqrt(v); }
            else G[a * k + b] = v / G[b * k + b];
        }
    for (int a = 0; a < k; ++a) {
        for (int q = 0; q < a; ++q) t[a] -= G[a * k + q] * t[q];
        t[a] /= G[a * k + a];
    }
    for (int a = k - 1; a >= 0; --a) {
        for (int q = a + 1; q < k; ++q) t[a] -= G[q * k + a] * t[q];
        t[a] /= G[a * k + a];
    }
    rc = 0;
out:
    free(G);
    return rc;
}

int mqmqa_driving_force_minima(
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
    const double *par_r, const int *par_addcat,
    const int *cat_group, const int *an_group,
    double R_own,
    int n_elem,
    const int *cat_elem, const int *an_elem,
    const double *mu,
    int max_out, double *X_out, double *df_out)
{
    double *ion_comp = one_atom_comp(n_cat, n_an, n_elem, cat_elem, an_elem);
    if (!ion_comp) return -1;
    const int r = mqmqa_driving_force_minima_comp(
        T, n_cat, n_an, n_quads, quad_ca, quad_cb, quad_ax, quad_ay, Za, Zb, Zx, Zy, zeta,
        soln_type, n_pairs, pair_c, pair_a, Gax, stoich, Zref, n_params, par_mix, par_code,
        par_A, par_B, par_X, par_Y, par_p, par_q, par_L, par_r, par_addcat, cat_group,
        an_group, R_own, n_elem, ion_comp, mu, max_out, X_out, df_out);
    free(ion_comp);
    return r;
}

int mqmqa_driving_force_minima_comp(
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
    const double *par_r, const int *par_addcat,
    const int *cat_group, const int *an_group,
    double R_own,
    int n_elem,
    const double *ion_comp,
    const double *mu,
    int max_out, double *X_out, double *df_out)
{
    for (int k = 0; k < n_params; ++k)
        if (mqmqa_excess_term_status(n_cat, n_an, par_mix[k], par_code[k],
                                     par_A[k], par_B[k], par_X[k], par_Y[k],
                                     par_r ? par_r[k] : 1.0,
                                     par_addcat ? par_addcat[k] : -1,
                                     cat_group, an_group) != XS_OK)
            return -1;
    if (max_out < 1 || n_quads < 1) return 0;

    const int n = n_quads;
    double *E = NULL, *A = NULL;
    if (quad_elements(n_cat, n, quad_ca, quad_cb, quad_ax, quad_ay, Za, Zb, Zx, Zy,
                      n_elem, ion_comp, &E, &A)) return -1;
    /* starts: the centre, one pushed toward each quadruplet, six from the walk, and three
     * where each quadruplet dominates (90, 99, 99.9%). A minimum pinned against a corner,
     * the silica-rich liquid of a miscibility gap at 98.5% Si, is out of reach of the rest. */
    const int NWALK = 1 + n + 6, NSEED = NWALK + 3 * n;
    double *lin = malloc((size_t)n * sizeof(double));
    double *ones = malloc((size_t)n * sizeof(double));
    double *x0 = malloc((size_t)n * sizeof(double));
    double *N = malloc((size_t)n * n * sizeof(double));
    double *Xbuf = malloc((size_t)n * sizeof(double));
    double *t = calloc((size_t)n, sizeof(double));
    double *seeds = malloc((size_t)NSEED * n * sizeof(double));
    double *cX = malloc((size_t)NSEED * n * sizeof(double));      /* candidates */
    double *cx = malloc((size_t)NSEED * n_elem * sizeof(double));
    double *cf = malloc((size_t)NSEED * sizeof(double));
    int nc = 0, rc = -1;
    if (!lin || !ones || !x0 || !N || !Xbuf || !t || !seeds || !cX || !cx || !cf) goto out;
    for (int q = 0; q < n; ++q) {
        double v = 0.0;
        for (int e = 0; e < n_elem; ++e) v -= mu[e] * E[(size_t)e * n + q];
        lin[q] = v;
        ones[q] = 1.0;
    }
    const double one = 1.0;
    int n_null = 0;
    if (constraint_nullspace(ones, &one, 1, n, x0, N, &n_null) < 0) goto out;

    eqctx ctx = {
        T, n_cat, n_an, n,
        quad_ca, quad_cb, quad_ax, quad_ay,
        Za, Zb, Zx, Zy, zeta, soln_type,
        n_pairs, pair_c, pair_a, Gax, stoich, Zref,
        n_params, par_mix, par_code, par_A, par_B, par_X, par_Y,
        par_p, par_q, par_L, par_r, par_addcat,
        cat_group, an_group, R_own,
        x0, N, n_null, Xbuf, lin,
    };

    int ns = 1;
    if (n_null > 0) {
        for (int q = 0; q < n; ++q) Xbuf[q] = 1.0 / n;   /* the centre of the simplex */
        double *u = cX;                                  /* scratch until candidates exist */
        memcpy(u, Xbuf, (size_t)n * sizeof(double));
        if (eq_t_of_X(&ctx, u, t)) goto out;
        ns = eq_seeds(&ctx, t, seeds, NWALK);
        static const double eps[3] = { 1e-1, 1e-2, 1e-3 };
        for (int q = 0; q < n && n > 1; ++q)
            for (int k = 0; k < 3; ++k) {
                for (int r = 0; r < n; ++r) Xbuf[r] = r == q ? 1.0 - eps[k] : eps[k] / (n - 1);
                if (!eq_t_of_X(&ctx, Xbuf, seeds + (size_t)ns * n_null)) ns++;
            }
    }
    for (int sd = 0; sd < ns; ++sd) {
        double *ts = seeds + (size_t)sd * n_null;
        if (n_null > 0) eq_newton(&ctx, ts);
        const double F = n_null > 0 ? obj_energy(ts, &ctx) : 0.0;
        if (n_null == 0) {
            memcpy(Xbuf, x0, (size_t)n * sizeof(double));
        } else {
            if (!(F < 1e11)) continue;
            ctx_X_from_t(&ctx, ts);
        }
        double atoms = 0.0, Fq = 0.0;
        for (int q = 0; q < n; ++q) atoms += Xbuf[q] * A[q];
        if (!(atoms > 0.0)) continue;
        if (n_null == 0) {
            Fq = ctx_gibbs_per_quad(&ctx, Xbuf);
            for (int q = 0; q < n; ++q) Fq += lin[q] * Xbuf[q];
        } else {
            Fq = F;
        }
        const double df = Fq / atoms;
        if (!isfinite(df)) continue;
        double xe[64];
        if (n_elem > 64) goto out;
        for (int e = 0; e < n_elem; ++e) {
            double v = 0.0;
            for (int q = 0; q < n; ++q) v += Xbuf[q] * E[(size_t)e * n + q];
            xe[e] = v / atoms;
        }
        /* one candidate per minimum: starts that reach the same composition are one */
        int same = -1;
        for (int j = 0; j < nc && same < 0; ++j) {
            double dx = 0.0;
            for (int e = 0; e < n_elem; ++e) dx = fmax(dx, fabs(cx[(size_t)j * n_elem + e] - xe[e]));
            if (dx < 1e-5) same = j;
        }
        int slot = same >= 0 ? (df < cf[same] ? same : -1) : nc++;
        if (slot < 0) continue;
        memcpy(cX + (size_t)slot * n, Xbuf, (size_t)n * sizeof(double));
        memcpy(cx + (size_t)slot * n_elem, xe, (size_t)n_elem * sizeof(double));
        cf[slot] = df;
    }
    /* lowest first */
    for (int a = 1; a < nc; ++a)
        for (int b = a; b > 0 && cf[b] < cf[b - 1]; --b) {
            double f = cf[b]; cf[b] = cf[b - 1]; cf[b - 1] = f;
            for (int q = 0; q < n; ++q) {
                double v = cX[(size_t)b * n + q];
                cX[(size_t)b * n + q] = cX[(size_t)(b - 1) * n + q];
                cX[(size_t)(b - 1) * n + q] = v;
            }
            for (int e = 0; e < n_elem; ++e) {
                double v = cx[(size_t)b * n_elem + e];
                cx[(size_t)b * n_elem + e] = cx[(size_t)(b - 1) * n_elem + e];
                cx[(size_t)(b - 1) * n_elem + e] = v;
            }
        }
    rc = nc < max_out ? nc : max_out;
    for (int j = 0; j < rc; ++j) {
        for (int q = 0; q < n; ++q) {
            double v = cX[(size_t)j * n + q];
            X_out[(size_t)j * n + q] = v < 0.0 ? 0.0 : v;
        }
        df_out[j] = cf[j];
    }
out:
    free(E); free(A); free(lin); free(ones); free(x0); free(N); free(Xbuf); free(t);
    free(seeds); free(cX); free(cx); free(cf);
    return rc;
}

void mqmqa_gibbs_gradient(
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
    const double *par_r, const int *par_addcat,
    const int *cat_group, const int *an_group,
    double R_own,
    const double *X, double *grad)
{
    double *work = malloc((size_t)n_quads * sizeof(double));
    if (!work) { for (int q = 0; q < n_quads; ++q) grad[q] = NAN; return; }
    const eqctx ctx = {
        T, n_cat, n_an, n_quads,
        quad_ca, quad_cb, quad_ax, quad_ay,
        Za, Zb, Zx, Zy, zeta, soln_type,
        n_pairs, pair_c, pair_a, Gax, stoich, Zref,
        n_params, par_mix, par_code, par_A, par_B, par_X, par_Y,
        par_p, par_q, par_L, par_r, par_addcat,
        cat_group, an_group, R_own,
        NULL, NULL, 0, NULL, NULL,
    };
    ctx_gradient(&ctx, X, grad, work);
    free(work);
}
