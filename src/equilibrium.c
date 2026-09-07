/* Self-contained multiphase equilibrium for a 3-cation MQMQA system: generate
 * candidate (cation-composition, Gibbs) points from every phase in C, take the lower
 * hull, read the stable assemblage under a bulk composition. Reuses the validated
 * bricks - mqmqa_equilibrate_db (liquid), mqmqa_ph_cef_gibbs (solid solutions),
 * mqmqa_db_stoich_gibbs (compounds), and the hull/assemblage in hull.c. This is the
 * engine the OCASI/TQ interface drives (docs/EQUILIBRIUM_ENGINE.md).
 *
 * Composition basis: cation fractions of two chosen cation elements (elem_a, elem_b);
 * the third cation is the dependent corner. Energies are per mole of cation so every
 * phase sits on one hull. Single-anion oxide/salt systems; CEF phases with a single
 * binary mixing sublattice (the solid-solution case: olivine, pyroxene, ...).
 */
#include "mqmqa.h"
#include "cs_dat.h"
#include "hull.h"

#include <ctype.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

#define ELEN 8

static void el_of(const char *name, char *out)
{
    int j = 0;
    for (const char *p = name; *p && j < ELEN-1 && isalpha((unsigned char)*p); ++p)
        out[j++] = (char)toupper((unsigned char)*p);
    out[j] = '\0';
    if (j == 0) { strncpy(out, name, ELEN-1); out[ELEN-1] = '\0'; }
}

/* growable candidate list */
typedef struct { double *xyz; int *tag; int n, cap; } Cands;
static void cand_add(Cands *c, double x, double y, double g, int tag)
{
    if (!isfinite(g) || !isfinite(x) || !isfinite(y)) return;
    if (c->n == c->cap) {
        c->cap = c->cap ? c->cap*2 : 256;
        c->xyz = realloc(c->xyz, (size_t)c->cap*3*sizeof(double));
        c->tag = realloc(c->tag, (size_t)c->cap*sizeof(int));
    }
    c->xyz[3*c->n]=x; c->xyz[3*c->n+1]=y; c->xyz[3*c->n+2]=g; c->tag[c->n]=tag; c->n++;
}

int mqmqa_equilibrium_ternary(const mqmqa_db *db, int liq_phase,
                              const int *cef_phases, int n_cef, double T,
                              int nliq, int ncef, int elem_a, int elem_b,
                              double qa, double qb,
                              int *phase_out, double *amt_out, int max_out,
                              double *gm_out)
{
    if (!db || mqmqa_db_phase_kind(db, liq_phase) != 0) return -1;
    int ndbel = mqmqa_db_num_elements(db);
    const char *ea = mqmqa_db_element(db, elem_a);
    const char *eb = mqmqa_db_element(db, elem_b);

    /* the liquid's cation elements and charges; require a single anion */
    int ncat = mqmqa_ph_num_cations(db, liq_phase);
    int nan  = mqmqa_ph_num_anions(db, liq_phase);
    if (nan != 1) return -2;
    double an_charge = mqmqa_ph_anion_charge(db, liq_phase, 0);
    const char *an_el = mqmqa_ph_anion(db, liq_phase, 0);
    char an_sym[ELEN]; el_of(an_el, an_sym);

    char (*cat_sym)[ELEN] = malloc((size_t)ncat*sizeof(*cat_sym));
    double *cat_q = malloc((size_t)ncat*sizeof(double));
    for (int i = 0; i < ncat; ++i) {
        el_of(mqmqa_ph_cation(db, liq_phase, i), cat_sym[i]);
        cat_q[i] = mqmqa_ph_cation_charge(db, liq_phase, i);
    }

    Cands C = {0};
    int nq = mqmqa_num_quadruplets(ncat, nan);
    double *Xout = malloc((size_t)nq*sizeof(double));
    double *tgt  = malloc((size_t)ndbel*sizeof(double));

    /* ---- liquid: grid over the cation simplex ---- */
    for (int i = 0; i <= nliq; ++i) {
        for (int j = 0; j <= nliq - i; ++j) {
            double fa = (double)i/nliq, fb = (double)j/nliq, fc = 1.0 - fa - fb;
            if (fc < -1e-12) continue;
            /* cation fractions per element: fa on elem_a, fb on elem_b, rest on the
             * remaining cation. Build the element target (per mole cation). */
            for (int e = 0; e < ndbel; ++e) tgt[e] = 0.0;
            double catcharge = 0.0;
            for (int ci = 0; ci < ncat; ++ci) {
                double f = (!strcmp(cat_sym[ci], ea)) ? fa
                         : (!strcmp(cat_sym[ci], eb)) ? fb : fc;
                /* only the first "other" cation takes fc; guard 3-cation systems */
                for (int e = 0; e < ndbel; ++e)
                    if (!strcmp(mqmqa_db_element(db, e), cat_sym[ci])) { tgt[e] += f; break; }
                catcharge += f * cat_q[ci];
            }
            double O = catcharge / fabs(an_charge);          /* neutrality, per mole cation */
            for (int e = 0; e < ndbel; ++e)
                if (!strcmp(mqmqa_db_element(db, e), an_sym)) { tgt[e] += O; break; }
            double g_atom = mqmqa_equilibrate_db(db, liq_phase, T, tgt, Xout, NULL);
            if (isfinite(g_atom)) cand_add(&C, fa, fb, g_atom * (1.0 + O), liq_phase);
        }
    }

    /* ---- CEF solid solutions: sample the single binary mixing sublattice ---- */
    for (int p = 0; p < n_cef; ++p) {
        int ph = cef_phases[p];
        int nsub = mqmqa_ph_cef_num_subl(db, ph);
        int *ncon = malloc((size_t)nsub*sizeof(int));
        double *sr = malloc((size_t)nsub*sizeof(double));
        mqmqa_ph_cef_subl_ncon(db, ph, ncon);
        mqmqa_ph_cef_site_ratio(db, ph, sr);
        int ntot = 0, mix = -1;
        for (int s = 0; s < nsub; ++s) { ntot += ncon[s]; if (ncon[s] == 2 && mix < 0) mix = s; }
        double *Y = malloc((size_t)ntot*sizeof(double));
        int samples = (mix >= 0) ? ncef : 1;
        for (int t = 0; t <= samples; ++t) {
            double yb = (mix >= 0) ? (double)t/samples : 0.0;
            /* fill Y: single constituent -> 1; binary mixing sublattice -> (yb, 1-yb) */
            int flat = 0;
            for (int s = 0; s < nsub; ++s) {
                for (int i = 0; i < ncon[s]; ++i) {
                    double yv = (ncon[s] == 1) ? 1.0 : (i == 0 ? 1.0 - yb : yb);
                    Y[flat++] = yv;
                }
            }
            /* element moles per formula, and cation-element fractions */
            double mole_a = 0, mole_b = 0, catmol = 0;
            flat = 0;
            for (int s = 0; s < nsub; ++s) {
                for (int i = 0; i < ncon[s]; ++i, ++flat) {
                    char sym[ELEN]; el_of(mqmqa_ph_cef_constituent(db, ph, s, i), sym);
                    double m = sr[s] * Y[flat];
                    if (!strcmp(sym, an_sym)) continue;         /* anion, not a cation */
                    catmol += m;
                    if (!strcmp(sym, ea)) mole_a += m;
                    if (!strcmp(sym, eb)) mole_b += m;
                }
            }
            if (catmol <= 0) continue;
            double gf = mqmqa_ph_cef_gibbs(db, ph, Y, T, 0);   /* per formula */
            cand_add(&C, mole_a/catmol, mole_b/catmol, gf/catmol, ph);
            if (mix < 0) break;
        }
        free(ncon); free(sr); free(Y);
    }

    /* ---- stoichiometric compounds ---- */
    int nst = mqmqa_db_num_stoich(db);
    double *ev = malloc((size_t)ndbel*sizeof(double));
    for (int j = 0; j < nst; ++j) {
        mqmqa_db_stoich_elems(db, j, ev);
        double mole_a = 0, mole_b = 0, catmol = 0;
        for (int e = 0; e < ndbel; ++e) {
            if (ev[e] <= 0) continue;
            const char *s = mqmqa_db_element(db, e);
            if (!strcmp(s, an_sym)) continue;
            catmol += ev[e];
            if (!strcmp(s, ea)) mole_a += ev[e];
            if (!strcmp(s, eb)) mole_b += ev[e];
        }
        if (catmol <= 0) continue;
        double gf = mqmqa_db_stoich_gibbs(db, j, T);
        cand_add(&C, mole_a/catmol, mole_b/catmol, gf/catmol, -(j+1));
    }
    free(ev);

    /* ---- hull + assemblage ---- */
    int rc = -3;
    if (C.n >= 3) {
        int *facets = malloc((size_t)(6*C.n+64)*3*sizeof(int));
        int nf = mqmqa_lower_hull_2d(C.xyz, C.n, facets, 6*C.n+64);
        if (nf > 0) {
            int tri[3]; double w[3], g;
            if (mqmqa_hull_assemblage_2d(C.xyz, C.n, facets, nf, qa, qb, tri, w, &g)) {
                /* aggregate weights by tag */
                int m = 0;
                for (int k = 0; k < 3; ++k) {
                    if (w[k] <= 1e-6) continue;
                    int tg = C.tag[tri[k]], found = -1;
                    for (int q = 0; q < m; ++q) if (phase_out[q] == tg) { found = q; break; }
                    if (found >= 0) amt_out[found] += w[k];
                    else if (m < max_out) { phase_out[m] = tg; amt_out[m] = w[k]; m++; }
                }
                if (gm_out) *gm_out = g;
                rc = m;
            } else rc = 0;
        }
        free(facets);
    }

    free(C.xyz); free(C.tag); free(Xout); free(tgt);
    free(cat_sym); free(cat_q);
    return rc;
}
