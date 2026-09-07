/* Self-contained multiphase equilibrium for a 3-cation MQMQA system: generate
 * candidate (cation-composition, Gibbs) points from every phase in C, take the lower
 * hull, read the stable assemblage under a bulk composition. Reuses the validated
 * bricks - mqmqa_equilibrate_db (liquid), mqmqa_ph_cef_gibbs (solid solutions),
 * mqmqa_db_stoich_gibbs (compounds), and the hull/assemblage in hull.c.
 *
 * mqmqa_equilibrium_ternary_ex adds two OCASI-relevant conditions:
 *   stoich_suspend  a per-compound mask (1 = phase suspended, excluded from the hull),
 *                   so a metastable equilibrium can be computed with a phase held out;
 *   refine          adaptive refinement passes that densify the liquid sampling around
 *                   the liquid hull vertices, sharpening the liquid tie-line endpoints
 *                   from grid resolution toward the true boundary.
 * mqmqa_equilibrium_ternary is the no-conditions, no-refinement wrapper.
 *
 * Composition basis: cation fractions of two chosen cation elements (elem_a, elem_b);
 * energies per mole of cation so every phase sits on one hull. Single-anion systems;
 * CEF phases with a single binary mixing sublattice (olivine, pyroxene, ...).
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

/* context for evaluating one liquid point at cation fractions (fa, fb) */
typedef struct {
    const mqmqa_db *db; int liq; double T; int ncat, ndbel;
    char (*cat_sym)[ELEN]; double *cat_q;
    char an_sym[ELEN]; double an_charge;
    const char *ea, *eb;
    double *tgt, *Xout;
} LiqCtx;

static double liq_gcat(LiqCtx *L, double fa, double fb)
{
    double fc = 1.0 - fa - fb;
    if (fc < -1e-12 || fa < -1e-12 || fb < -1e-12) return NAN;
    for (int e = 0; e < L->ndbel; ++e) L->tgt[e] = 0.0;
    double catcharge = 0.0;
    for (int ci = 0; ci < L->ncat; ++ci) {
        double f = (!strcmp(L->cat_sym[ci], L->ea)) ? fa
                 : (!strcmp(L->cat_sym[ci], L->eb)) ? fb : fc;
        for (int e = 0; e < L->ndbel; ++e)
            if (!strcmp(mqmqa_db_element(L->db, e), L->cat_sym[ci])) { L->tgt[e] += f; break; }
        catcharge += f * L->cat_q[ci];
    }
    double O = catcharge / fabs(L->an_charge);
    for (int e = 0; e < L->ndbel; ++e)
        if (!strcmp(mqmqa_db_element(L->db, e), L->an_sym)) { L->tgt[e] += O; break; }
    double ga = mqmqa_equilibrate_db(L->db, L->liq, L->T, L->tgt, L->Xout, NULL);
    return isfinite(ga) ? ga * (1.0 + O) : NAN;
}

int mqmqa_equilibrium_ternary_ex(const mqmqa_db *db, int liq_phase,
                                 const int *cef_phases, int n_cef, double T,
                                 int nliq, int ncef, int elem_a, int elem_b,
                                 double qa, double qb, const int *stoich_suspend,
                                 int refine, int *phase_out, double *amt_out,
                                 int max_out, double *gm_out)
{
    if (!db || mqmqa_db_phase_kind(db, liq_phase) != 0) return -1;
    int ndbel = mqmqa_db_num_elements(db);
    int ncat = mqmqa_ph_num_cations(db, liq_phase);
    int nan  = mqmqa_ph_num_anions(db, liq_phase);
    if (ncat != 3 || nan != 1) return -2;

    LiqCtx L;
    L.db = db; L.liq = liq_phase; L.T = T; L.ncat = ncat; L.ndbel = ndbel;
    L.cat_sym = malloc((size_t)ncat*sizeof(*L.cat_sym));
    L.cat_q = malloc((size_t)ncat*sizeof(double));
    for (int i = 0; i < ncat; ++i) {
        el_of(mqmqa_ph_cation(db, liq_phase, i), L.cat_sym[i]);
        L.cat_q[i] = mqmqa_ph_cation_charge(db, liq_phase, i);
    }
    L.an_charge = mqmqa_ph_anion_charge(db, liq_phase, 0);
    el_of(mqmqa_ph_anion(db, liq_phase, 0), L.an_sym);
    L.ea = mqmqa_db_element(db, elem_a);
    L.eb = mqmqa_db_element(db, elem_b);
    L.tgt = malloc((size_t)ndbel*sizeof(double));
    int nq = mqmqa_num_quadruplets(ncat, nan);
    L.Xout = malloc((size_t)nq*sizeof(double));

    Cands C = {0};

    /* ---- liquid: grid over the cation simplex ---- */
    for (int i = 0; i <= nliq; ++i)
        for (int j = 0; j <= nliq - i; ++j) {
            double fa = (double)i/nliq, fb = (double)j/nliq;
            double g = liq_gcat(&L, fa, fb);
            if (isfinite(g)) cand_add(&C, fa, fb, g, liq_phase);
        }

    /* ---- CEF solid solutions: sample the single binary mixing sublattice ---- */
    for (int p = 0; p < n_cef; ++p) {
        int ph = cef_phases[p];
        int nsub = mqmqa_ph_cef_num_subl(db, ph);
        int *nc = malloc((size_t)nsub*sizeof(int));
        double *sr = malloc((size_t)nsub*sizeof(double));
        mqmqa_ph_cef_subl_ncon(db, ph, nc);
        mqmqa_ph_cef_site_ratio(db, ph, sr);
        int ntot = 0, mix = -1;
        for (int s = 0; s < nsub; ++s) { ntot += nc[s]; if (nc[s]==2 && mix<0) mix = s; }
        double *Y = malloc((size_t)ntot*sizeof(double));
        int samples = (mix >= 0) ? ncef : 1;
        for (int t = 0; t <= samples; ++t) {
            double yb = (mix >= 0) ? (double)t/samples : 0.0;
            int flat = 0;
            for (int s = 0; s < nsub; ++s)
                for (int ci = 0; ci < nc[s]; ++ci)
                    Y[flat++] = (nc[s]==1) ? 1.0 : (ci==0 ? 1.0-yb : yb);
            double ma=0, mb=0, catmol=0; flat=0;
            for (int s = 0; s < nsub; ++s)
                for (int ci = 0; ci < nc[s]; ++ci, ++flat) {
                    char sym[ELEN]; el_of(mqmqa_ph_cef_constituent(db, ph, s, ci), sym);
                    if (!strcmp(sym, L.an_sym)) continue;
                    double m = sr[s]*Y[flat]; catmol += m;
                    if (!strcmp(sym, L.ea)) ma += m;
                    if (!strcmp(sym, L.eb)) mb += m;
                }
            if (catmol > 0) {
                double gf = mqmqa_ph_cef_gibbs(db, ph, Y, T, 0);
                cand_add(&C, ma/catmol, mb/catmol, gf/catmol, ph);
            }
            if (mix < 0) break;
        }
        free(nc); free(sr); free(Y);
    }

    /* ---- stoichiometric compounds (respecting the suspend mask) ---- */
    int nst = mqmqa_db_num_stoich(db);
    double *ev = malloc((size_t)ndbel*sizeof(double));
    for (int j = 0; j < nst; ++j) {
        if (stoich_suspend && stoich_suspend[j]) continue;
        mqmqa_db_stoich_elems(db, j, ev);
        double ma=0, mb=0, catmol=0;
        for (int e = 0; e < ndbel; ++e) {
            if (ev[e] <= 0) continue;
            const char *s = mqmqa_db_element(db, e);
            if (!strcmp(s, L.an_sym)) continue;
            catmol += ev[e];
            if (!strcmp(s, L.ea)) ma += ev[e];
            if (!strcmp(s, L.eb)) mb += ev[e];
        }
        if (catmol > 0)
            cand_add(&C, ma/catmol, mb/catmol, mqmqa_db_stoich_gibbs(db, j, T)/catmol, -(j+1));
    }
    free(ev);

    /* ---- hull, optional adaptive refinement, assemblage ---- */
    int rc = -3;
    int *facets = malloc((size_t)(6*(C.n+1)+64)*3*sizeof(int));
    int nf = (C.n >= 3) ? mqmqa_lower_hull_2d(C.xyz, C.n, facets, 6*(C.n+1)+64) : -1;

    for (int pass = 0; pass < refine && nf > 0; ++pass) {
        double h = 1.0 / (nliq * (1 << (pass+1)));   /* shrinking neighbourhood */
        int base = C.n;
        for (int f = 0; f < nf; ++f)
            for (int k = 0; k < 3; ++k) {
                int vi = facets[3*f+k];
                if (vi >= base || C.tag[vi] != liq_phase) continue;   /* liquid vertices only */
                double vx = C.xyz[3*vi], vy = C.xyz[3*vi+1];
                for (int di = -1; di <= 1; ++di)
                    for (int dj = -1; dj <= 1; ++dj) {
                        if (!di && !dj) continue;
                        double g = liq_gcat(&L, vx+di*h, vy+dj*h);
                        if (isfinite(g)) cand_add(&C, vx+di*h, vy+dj*h, g, liq_phase);
                    }
            }
        if (C.n == base) break;
        facets = realloc(facets, (size_t)(6*(C.n+1)+64)*3*sizeof(int));
        nf = mqmqa_lower_hull_2d(C.xyz, C.n, facets, 6*(C.n+1)+64);
    }

    if (nf > 0) {
        int tri[3]; double w[3], g;
        if (mqmqa_hull_assemblage_2d(C.xyz, C.n, facets, nf, qa, qb, tri, w, &g)) {
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
    free(C.xyz); free(C.tag);
    free(L.cat_sym); free(L.cat_q); free(L.tgt); free(L.Xout);
    return rc;
}

int mqmqa_equilibrium_ternary(const mqmqa_db *db, int liq_phase,
                              const int *cef_phases, int n_cef, double T,
                              int nliq, int ncef, int elem_a, int elem_b,
                              double qa, double qb, int *phase_out,
                              double *amt_out, int max_out, double *gm_out)
{
    return mqmqa_equilibrium_ternary_ex(db, liq_phase, cef_phases, n_cef, T, nliq, ncef,
                                        elem_a, elem_b, qa, qb, NULL, 0,
                                        phase_out, amt_out, max_out, gm_out);
}
