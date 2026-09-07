/* Database-level single-phase equilibrium for the multiphase engine.
 *
 * mqmqa_equilibrate takes fully marshalled arrays; the browser assembled them in
 * JavaScript across the WASM boundary. This does the same assembly in C, straight
 * from the parsed database via the public getters, so the C core can equilibrate a
 * phase at a target composition without a host layer. It is the candidate generator
 * the convex-hull multiphase equilibrium calls (docs/EQUILIBRIUM_ENGINE.md).
 *
 * The port mirrors python/mqmqa/equilibrium.build_inputs + solveEquilibrium exactly,
 * keeping every cation and anion of the phase (no subsystem restriction): the target
 * simply drives absent elements to zero.
 */
#include "mqmqa.h"
#include "cs_dat.h"

#include <ctype.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

#define ELEN 8

/* leading element symbol of a constituent name (NA+1 -> NA), uppercased */
static void elem_of(const char *name, char *out)
{
    int j = 0;
    for (const char *p = name; *p && j < ELEN - 1 && isalpha((unsigned char)*p); ++p)
        out[j++] = (char)toupper((unsigned char)*p);
    out[j] = '\0';
    if (j == 0) { strncpy(out, name, ELEN - 1); out[ELEN - 1] = '\0'; }
}

static int eidx_of(const char els[][ELEN], int nel, const char *s)
{
    for (int e = 0; e < nel; ++e) if (!strcmp(els[e], s)) return e;
    return -1;
}

/* Equilibrate MQMQA phase `phase` at temperature T and a target composition given
 * over the database elements (length mqmqa_db_num_elements). Writes quadruplet
 * fractions to X_out (length mqmqa_num_quadruplets(ncat,nan)) and the max element
 * mole-fraction error to err_out (may be NULL). Returns GM per mole of atoms, or
 * NaN on failure. */
MQMQA_API double mqmqa_equilibrate_db(const mqmqa_db *db, int phase, double T,
                                      const double *target_elem,
                                      double *X_out, double *err_out)
{
    if (!db || mqmqa_db_phase_kind(db, phase) != 0) return NAN;
    int ncat = mqmqa_ph_num_cations(db, phase);
    int nan  = mqmqa_ph_num_anions(db, phase);
    if (ncat < 1 || nan < 1) return NAN;

    double *q_cat = malloc((size_t)ncat * sizeof(double));
    double *q_an  = malloc((size_t)nan  * sizeof(double));
    char (*cat_el)[ELEN] = malloc((size_t)ncat * sizeof(*cat_el));
    char (*an_el)[ELEN]  = malloc((size_t)nan  * sizeof(*an_el));
    for (int i = 0; i < ncat; ++i) {
        q_cat[i] = mqmqa_ph_cation_charge(db, phase, i);
        elem_of(mqmqa_ph_cation(db, phase, i), cat_el[i]);
    }
    for (int k = 0; k < nan; ++k) {
        q_an[k] = mqmqa_ph_anion_charge(db, phase, k);
        elem_of(mqmqa_ph_anion(db, phase, k), an_el[k]);
    }

    /* compact element space over the phase's own elements, sorted (JS parity) */
    char (*els)[ELEN] = malloc((size_t)(ncat + nan) * sizeof(*els));
    int nel = 0;
    for (int i = 0; i < ncat + nan; ++i) {
        const char *s = i < ncat ? cat_el[i] : an_el[i - ncat];
        if (eidx_of(els, nel, s) < 0) { strncpy(els[nel], s, ELEN); els[nel][ELEN-1]='\0'; nel++; }
    }
    for (int a = 0; a < nel - 1; ++a)
        for (int b = a + 1; b < nel; ++b)
            if (strcmp(els[a], els[b]) > 0) {
                char t[ELEN]; strcpy(t, els[a]); strcpy(els[a], els[b]); strcpy(els[b], t);
            }
    int *cat_elem = malloc((size_t)ncat * sizeof(int));
    int *an_elem  = malloc((size_t)nan  * sizeof(int));
    for (int i = 0; i < ncat; ++i) cat_elem[i] = eidx_of(els, nel, cat_el[i]);
    for (int k = 0; k < nan; ++k) an_elem[k]  = eidx_of(els, nel, an_el[k]);

    /* target over the compact space, normalized to sum 1 */
    int ndbel = mqmqa_db_num_elements(db);
    double *target = calloc((size_t)nel, sizeof(double));
    double tot = 0.0;
    for (int e = 0; e < ndbel; ++e) {
        double v = target_elem[e];
        if (v == 0.0) continue;
        int j = eidx_of(els, nel, mqmqa_db_element(db, e));
        if (j >= 0) { target[j] += v; tot += v; }
    }
    double GM = NAN;
    if (tot <= 0.0) goto done;
    for (int e = 0; e < nel; ++e) target[e] /= tot;

    /* quadruplet enumeration */
    int nq = mqmqa_num_quadruplets(ncat, nan);
    int *qca = malloc((size_t)nq*sizeof(int)), *qcb = malloc((size_t)nq*sizeof(int));
    int *qax = malloc((size_t)nq*sizeof(int)), *qay = malloc((size_t)nq*sizeof(int));
    mqmqa_enumerate_quadruplets(ncat, nan, qca, qcb, qax, qay);

    /* coordination table */
    int nmz = mqmqa_ph_num_mqmz(db, phase);
    int *mzA = malloc((size_t)nmz*sizeof(int)), *mzB = malloc((size_t)nmz*sizeof(int));
    int *mzX = malloc((size_t)nmz*sizeof(int)), *mzY = malloc((size_t)nmz*sizeof(int));
    double *mzZ = malloc((size_t)nmz*4*sizeof(double));
    mqmqa_ph_mqmz(db, phase, mzA, mzB, mzX, mzY, mzZ);

    #define ZC(is_cat, sp, A, B, X, Y) \
        mqmqa_coordination((is_cat),(sp),(A),(B),(X),(Y),ncat,nan,q_cat,q_an,nmz,mzA,mzB,mzX,mzY,mzZ)

    double *Za = malloc((size_t)nq*sizeof(double)), *Zb = malloc((size_t)nq*sizeof(double));
    double *Zx = malloc((size_t)nq*sizeof(double)), *Zy = malloc((size_t)nq*sizeof(double));
    for (int q = 0; q < nq; ++q) {
        Za[q] = ZC(1, qca[q], qca[q], qcb[q], qax[q], qay[q]);
        Zb[q] = ZC(1, qcb[q], qca[q], qcb[q], qax[q], qay[q]);
        Zx[q] = ZC(0, qax[q], qca[q], qcb[q], qax[q], qay[q]);
        Zy[q] = ZC(0, qay[q], qca[q], qcb[q], qax[q], qay[q]);
    }

    /* pairs and reference coordinations */
    int np = mqmqa_ph_num_pairs(db, phase);
    int *pc = malloc((size_t)np*sizeof(int)), *pa = malloc((size_t)np*sizeof(int));
    double *pG = malloc((size_t)np*sizeof(double)), *pst = malloc((size_t)np*sizeof(double));
    double *pz = malloc((size_t)np*sizeof(double));
    mqmqa_ph_pair_indices(db, phase, pc, pa);
    mqmqa_ph_pair_gibbs(db, phase, T, pG);
    mqmqa_ph_pair_stoich(db, phase, pst);
    mqmqa_ph_pair_zeta(db, phase, pz);
    double *Ztab = malloc((size_t)np*nq*sizeof(double));
    for (int i = 0; i < np; ++i)
        for (int q = 0; q < nq; ++q)
            Ztab[i*nq+q] = (pc[i]==qca[q]||pc[i]==qcb[q])
                           ? ZC(1, pc[i], qca[q], qcb[q], qax[q], qay[q]) : 1.0;
    double *zeta = calloc((size_t)ncat*nan, sizeof(double));
    for (int i = 0; i < np; ++i) zeta[pc[i]*nan + pa[i]] = pz[i];

    /* excess parameters */
    int nx = mqmqa_ph_num_mqmx(db, phase);
    int *xm = malloc((size_t)nx*sizeof(int)), *xc = malloc((size_t)nx*sizeof(int));
    int *xA = malloc((size_t)nx*sizeof(int)), *xB = malloc((size_t)nx*sizeof(int));
    int *xX = malloc((size_t)nx*sizeof(int)), *xY = malloc((size_t)nx*sizeof(int));
    int *xp = malloc((size_t)nx*sizeof(int)), *xq = malloc((size_t)nx*sizeof(int));
    double *xL = malloc((size_t)nx*sizeof(double)), *xr = malloc((size_t)nx*sizeof(double));
    int *xac = malloc((size_t)nx*sizeof(int));
    mqmqa_ph_mqmx(db, phase, xm, xc, xA, xB, xX, xY, xp, xq);
    mqmqa_ph_mqmx_L(db, phase, T, xL);
    mqmqa_ph_mqmx_ternary(db, phase, xr, xac);
    double *xpp = malloc((size_t)nx*sizeof(double));  /* p,q as double for the core */
    double *xqp = malloc((size_t)nx*sizeof(double));
    for (int i = 0; i < nx; ++i) { xpp[i] = xp[i]; xqp[i] = xq[i]; }

    int soln = mqmqa_db_phase_is_subq(db, phase);
    GM = mqmqa_equilibrate(
        T, ncat, nan, nq, qca, qcb, qax, qay,
        Za, Zb, Zx, Zy, zeta, soln,
        np, pc, pa, pG, pst, Ztab,
        nx, xm, xc, xA, xB, xX, xY, xpp, xqp, xL, xr, xac,
        nel, cat_elem, an_elem, target, X_out, err_out);

    #undef ZC
    free(qca); free(qcb); free(qax); free(qay);
    free(mzA); free(mzB); free(mzX); free(mzY); free(mzZ);
    free(Za); free(Zb); free(Zx); free(Zy);
    free(pc); free(pa); free(pG); free(pst); free(pz); free(Ztab); free(zeta);
    free(xm); free(xc); free(xA); free(xB); free(xX); free(xY);
    free(xp); free(xq); free(xL); free(xr); free(xac); free(xpp); free(xqp);

done:
    free(q_cat); free(q_an); free(cat_el); free(an_el); free(els);
    free(cat_elem); free(an_elem); free(target);
    return GM;
}
