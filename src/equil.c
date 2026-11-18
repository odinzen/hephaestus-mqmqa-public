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
#include "cs_dat_priv.h"

#include <ctype.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

#define ELEN NAME_MAX   /* a whole constituent name fits, so a symbol is never cut */

/* leading element symbol of a constituent name (NA+1 -> NA), uppercased */
static void elem_of(const char *name, char *out)
{
    int j = 0;
    for (const char *p = name; *p && j < ELEN - 1 && isalpha((unsigned char)*p); ++p)
        out[j++] = (char)toupper((unsigned char)*p);
    out[j] = '\0';
    if (j == 0) { strncpy(out, name, ELEN - 1); out[ELEN - 1] = '\0'; }
}

/* index here of database element e, -1 when the phase holds none of it */
static int jx_of(const int *dbe, int nel, int e)
{
    for (int j = 0; j < nel; ++j) if (dbe[j] == e) return j;
    return -1;
}

/* Every model input of one MQMQA phase at one temperature, over the phase's own
 * elements (sorted by symbol, for parity with the browser). */
typedef struct {
    int ncat, nan, nel, nq, np, nx, soln;
    double R_own;
    char (*els)[ELEN];
    double *icomp;                  /* element amounts of each ion, (ncat + nan) x nel */
    int *dbe;                       /* database index of each element here */
    int *qca, *qcb, *qax, *qay;
    double *Za, *Zb, *Zx, *Zy;
    int *pc, *pa;
    double *pG, *pst, *Ztab, *zeta;
    int *xm, *xc, *xA, *xB, *xX, *xY, *xac, *cgrp, *agrp;
    double *xpp, *xqp, *xL, *xr;
    int nfull, *orig;               /* ions of the full phase; full index of each ion here */
} PhInputs;

static void inputs_free(PhInputs *I)
{
    free(I->els); free(I->icomp); free(I->dbe);
    free(I->qca); free(I->qcb); free(I->qax); free(I->qay);
    free(I->Za); free(I->Zb); free(I->Zx); free(I->Zy);
    free(I->pc); free(I->pa); free(I->pG); free(I->pst); free(I->Ztab); free(I->zeta);
    free(I->xm); free(I->xc); free(I->xA); free(I->xB); free(I->xX); free(I->xY);
    free(I->xac); free(I->cgrp); free(I->agrp);
    free(I->xpp); free(I->xqp); free(I->xL); free(I->xr); free(I->orig);
    memset(I, 0, sizeof(*I));
}

/* 0 on success; -1 when the phase is not an MQMQA phase the engine evaluates (the
 * reason, if any, in mqmqa_db_error()) */
static int inputs_build(const mqmqa_db *db, int phase, double T, PhInputs *I)
{
    memset(I, 0, sizeof(*I));
    if (!db || mqmqa_db_phase_kind(db, phase) != 0) return -1;
    const int ncat = mqmqa_ph_num_cations(db, phase);
    const int nan  = mqmqa_ph_num_anions(db, phase);
    if (ncat < 1 || nan < 1) return -1;
    const char *unsupported = mqmqa_ph_excess_unsupported(db, phase);
    if (unsupported) { mqmqa_db_set_error("%s", unsupported); return -1; }
    I->ncat = ncat;
    I->nan = nan;

    const int ndbel = mqmqa_db_num_elements(db);
    double *q_cat = malloc((size_t)ncat * sizeof(double));
    double *q_an  = malloc((size_t)nan  * sizeof(double));
    double *full = malloc((size_t)(ncat + nan) * ndbel * sizeof(double));
    int *mzA = NULL, *mzB = NULL, *mzX = NULL, *mzY = NULL, *xp = NULL, *xq = NULL;
    double *mzZ = NULL, *pz = NULL;
    int rc = -1;
    I->els = malloc((size_t)ndbel * sizeof(*I->els));
    I->dbe = malloc((size_t)ndbel * sizeof(int));
    if (!q_cat || !q_an || !full || !I->els || !I->dbe) goto out;
    for (int i = 0; i < ncat; ++i) q_cat[i] = mqmqa_ph_cation_charge(db, phase, i);
    for (int k = 0; k < nan; ++k) q_an[k] = mqmqa_ph_anion_charge(db, phase, k);
    if (mqmqa_ph_ion_comps((const Db *)db, phase, full)) goto out;

    /* compact element space over the elements the phase's ions hold, sorted by symbol
     * (JS parity) */
    int nel = 0;
    for (int e = 0; e < ndbel; ++e) {
        int used = 0;
        for (int i = 0; i < ncat + nan && !used; ++i) used = full[(size_t)i * ndbel + e] != 0.0;
        if (!used) continue;
        elem_of(mqmqa_db_element(db, e), I->els[nel]);
        I->dbe[nel++] = e;
    }
    for (int a = 0; a < nel - 1; ++a)
        for (int b = a + 1; b < nel; ++b)
            if (strcmp(I->els[a], I->els[b]) > 0) {
                char t[ELEN]; strcpy(t, I->els[a]); strcpy(I->els[a], I->els[b]); strcpy(I->els[b], t);
                int u = I->dbe[a]; I->dbe[a] = I->dbe[b]; I->dbe[b] = u;
            }
    I->nel = nel;
    I->icomp = calloc((size_t)(ncat + nan) * (nel ? nel : 1), sizeof(double));
    if (!I->icomp) goto out;
    for (int i = 0; i < ncat + nan; ++i)
        for (int j = 0; j < nel; ++j) I->icomp[(size_t)i * nel + j] = full[(size_t)i * ndbel + I->dbe[j]];

    /* quadruplet enumeration */
    const int nq = mqmqa_num_quadruplets(ncat, nan);
    I->nq = nq;
    I->qca = malloc((size_t)nq*sizeof(int)); I->qcb = malloc((size_t)nq*sizeof(int));
    I->qax = malloc((size_t)nq*sizeof(int)); I->qay = malloc((size_t)nq*sizeof(int));
    if (!I->qca || !I->qcb || !I->qax || !I->qay) goto out;
    mqmqa_enumerate_quadruplets(ncat, nan, I->qca, I->qcb, I->qax, I->qay);

    /* coordination table */
    const int nmz = mqmqa_ph_num_mqmz(db, phase);
    mzA = malloc((size_t)nmz*sizeof(int) + 1); mzB = malloc((size_t)nmz*sizeof(int) + 1);
    mzX = malloc((size_t)nmz*sizeof(int) + 1); mzY = malloc((size_t)nmz*sizeof(int) + 1);
    mzZ = malloc((size_t)nmz*4*sizeof(double) + 1);
    if (!mzA || !mzB || !mzX || !mzY || !mzZ) goto out;
    mqmqa_ph_mqmz(db, phase, mzA, mzB, mzX, mzY, mzZ);

    #define ZC(is_cat, sp, A, B, X, Y) \
        mqmqa_coordination((is_cat),(sp),(A),(B),(X),(Y),ncat,nan,q_cat,q_an,nmz,mzA,mzB,mzX,mzY,mzZ)

    I->Za = malloc((size_t)nq*sizeof(double)); I->Zb = malloc((size_t)nq*sizeof(double));
    I->Zx = malloc((size_t)nq*sizeof(double)); I->Zy = malloc((size_t)nq*sizeof(double));
    if (!I->Za || !I->Zb || !I->Zx || !I->Zy) goto out;
    for (int q = 0; q < nq; ++q) {
        const int A = I->qca[q], B = I->qcb[q], X = I->qax[q], Y = I->qay[q];
        I->Za[q] = ZC(1, A, A, B, X, Y);
        I->Zb[q] = ZC(1, B, A, B, X, Y);
        I->Zx[q] = ZC(0, X, A, B, X, Y);
        I->Zy[q] = ZC(0, Y, A, B, X, Y);
    }

    /* pairs and reference coordinations */
    const int np = mqmqa_ph_num_pairs(db, phase);
    I->np = np;
    I->pc = malloc((size_t)np*sizeof(int) + 1); I->pa = malloc((size_t)np*sizeof(int) + 1);
    I->pG = malloc((size_t)np*sizeof(double) + 1); I->pst = malloc((size_t)np*sizeof(double) + 1);
    pz = malloc((size_t)np*sizeof(double) + 1);
    I->Ztab = malloc((size_t)np*nq*sizeof(double) + 1);
    I->zeta = calloc((size_t)ncat*nan, sizeof(double));
    if (!I->pc || !I->pa || !I->pG || !I->pst || !pz || !I->Ztab || !I->zeta) goto out;
    mqmqa_ph_pair_indices(db, phase, I->pc, I->pa);
    mqmqa_ph_pair_gibbs(db, phase, T, I->pG);
    mqmqa_ph_pair_stoich(db, phase, I->pst);
    mqmqa_ph_pair_zeta(db, phase, pz);
    for (int i = 0; i < np; ++i)
        for (int q = 0; q < nq; ++q)
            I->Ztab[i*nq+q] = (I->pc[i]==I->qca[q]||I->pc[i]==I->qcb[q])
                              ? ZC(1, I->pc[i], I->qca[q], I->qcb[q], I->qax[q], I->qay[q]) : 1.0;
    for (int i = 0; i < np; ++i) I->zeta[I->pc[i]*nan + I->pa[i]] = pz[i];
    #undef ZC

    /* excess parameters */
    const int nx = mqmqa_ph_num_mqmx(db, phase);
    I->nx = nx;
    const size_t ni = (size_t)nx * sizeof(int) + 1, nd = (size_t)nx * sizeof(double) + 1;
    I->xm = malloc(ni); I->xc = malloc(ni); I->xA = malloc(ni); I->xB = malloc(ni);
    I->xX = malloc(ni); I->xY = malloc(ni); xp = malloc(ni); xq = malloc(ni);
    I->xL = malloc(nd); I->xr = malloc(nd); I->xac = malloc(ni);
    I->xpp = malloc(nd); I->xqp = malloc(nd);
    I->cgrp = malloc((size_t)ncat*sizeof(int)); I->agrp = malloc((size_t)nan*sizeof(int));
    if (!I->xm || !I->xc || !I->xA || !I->xB || !I->xX || !I->xY || !xp || !xq || !I->xL ||
        !I->xr || !I->xac || !I->xpp || !I->xqp || !I->cgrp || !I->agrp) goto out;
    mqmqa_ph_mqmx(db, phase, I->xm, I->xc, I->xA, I->xB, I->xX, I->xY, xp, xq);
    mqmqa_ph_mqmx_L(db, phase, T, I->xL);
    mqmqa_ph_mqmx_ternary(db, phase, I->xr, I->xac);
    for (int i = 0; i < ncat; ++i) I->cgrp[i] = mqmqa_ph_cation_group(db, phase, i);
    for (int k = 0; k < nan; ++k) I->agrp[k] = mqmqa_ph_anion_group(db, phase, k);
    for (int i = 0; i < nx; ++i) { I->xpp[i] = xp[i]; I->xqp[i] = xq[i]; }  /* p,q as double for the core */

    I->soln = mqmqa_db_phase_is_subq(db, phase);
    I->R_own = mqmqa_db_R_own(db);
    I->nfull = ncat + nan;
    I->orig = malloc((size_t)I->nfull * sizeof(int));
    if (!I->orig) goto out;
    for (int i = 0; i < I->nfull; ++i) I->orig[i] = i;
    rc = 0;
out:
    free(q_cat); free(q_an); free(full);
    free(mzA); free(mzB); free(mzX); free(mzY); free(mzZ); free(pz); free(xp); free(xq);
    if (rc) inputs_free(I);
    return rc;
}

/* Cut the phase down to the ions whose element el_keep (over the database elements)
 * marks present. Every quadruplet, pair and excess term naming a dropped ion goes; with
 * those ions absent their weight is zero, so the energy is unchanged. Coordination
 * numbers are copied from the full phase, and orig maps each kept ion (cations, then
 * anions) to its index in the full phase. Returns -1 when a sublattice would be
 * left empty, or a ternary term with exponent 0 names a dropped ion (its factor is then 1,
 * not 0, and the cut would change the energy). */
static int inputs_restrict(PhInputs *I, const mqmqa_db *db, const int *el_keep, const int *ion_off)
{
    const int nc = I->ncat, na = I->nan, nq = I->nq, nel = I->nel;
    (void)db;
    int *keep_el = calloc((size_t)(nel ? nel : 1), sizeof(int));
    int *newc = malloc((size_t)nc * sizeof(int)), *newa = malloc((size_t)na * sizeof(int));
    PhInputs R;
    memset(&R, 0, sizeof R);
    int rc = -1;
    if (!keep_el || !newc || !newa) goto out;
    for (int j = 0; j < nel; ++j) keep_el[j] = !el_keep || el_keep[I->dbe[j]] != 0;
    /* an ion stays when every element it holds does (a vacancy always) and it is not held out */
    int nc2 = 0, na2 = 0;
    for (int i = 0; i < nc + na; ++i) {
        int ok = !(ion_off && ion_off[I->orig[i]]);
        for (int j = 0; j < nel; ++j) if (I->icomp[(size_t)i * nel + j] != 0.0 && !keep_el[j]) ok = 0;
        if (i < nc) newc[i] = ok ? nc2++ : -1;
        else newa[i - nc] = ok ? na2++ : -1;
    }
    if (!nc2 || !na2) goto out;
    R.nfull = I->nfull;
    R.orig = malloc((size_t)(nc2 + na2) * sizeof(int));
    if (!R.orig) goto out;
    int *orig_ion = R.orig;
    for (int i = 0; i < nc; ++i) if (newc[i] >= 0) orig_ion[newc[i]] = I->orig[i];
    for (int k = 0; k < na; ++k) if (newa[k] >= 0) orig_ion[nc2 + newa[k]] = I->orig[nc + k];

    R.ncat = nc2; R.nan = na2; R.soln = I->soln; R.R_own = I->R_own;
    /* the kept elements, in the full phase's order, and the kept ions' compositions */
    R.els = malloc((size_t)(nel ? nel : 1) * sizeof(*R.els));
    R.dbe = malloc((size_t)(nel ? nel : 1) * sizeof(int));
    int *col = malloc((size_t)(nel ? nel : 1) * sizeof(int));
    if (!R.els || !R.dbe || !col) { free(col); goto out; }
    for (int j = 0; j < nel; ++j)
        if (keep_el[j]) { memcpy(R.els[R.nel], I->els[j], ELEN); R.dbe[R.nel] = I->dbe[j]; col[R.nel++] = j; }
    R.icomp = calloc((size_t)(nc2 + na2) * (R.nel ? R.nel : 1), sizeof(double));
    if (!R.icomp) { free(col); goto out; }
    for (int i = 0; i < nc + na; ++i) {
        const int to = i < nc ? newc[i] : (newa[i - nc] >= 0 ? nc2 + newa[i - nc] : -1);
        if (to < 0) continue;
        for (int j = 0; j < R.nel; ++j) R.icomp[(size_t)to * R.nel + j] = I->icomp[(size_t)i * nel + col[j]];
    }
    free(col);

    /* quadruplets, each mapped to the full one holding the same ions */
    R.nq = mqmqa_num_quadruplets(nc2, na2);
    int *qfull = malloc((size_t)R.nq * sizeof(int));
    R.qca = malloc((size_t)R.nq * sizeof(int)); R.qcb = malloc((size_t)R.nq * sizeof(int));
    R.qax = malloc((size_t)R.nq * sizeof(int)); R.qay = malloc((size_t)R.nq * sizeof(int));
    R.Za = malloc((size_t)R.nq * sizeof(double)); R.Zb = malloc((size_t)R.nq * sizeof(double));
    R.Zx = malloc((size_t)R.nq * sizeof(double)); R.Zy = malloc((size_t)R.nq * sizeof(double));
    if (!qfull || !R.qca || !R.qcb || !R.qax || !R.qay || !R.Za || !R.Zb || !R.Zx || !R.Zy) { free(qfull); goto out; }
    mqmqa_enumerate_quadruplets(nc2, na2, R.qca, R.qcb, R.qax, R.qay);
    for (int q = 0; q < R.nq; ++q) {
        const int A = orig_ion[R.qca[q]], B = orig_ion[R.qcb[q]];
        const int X = orig_ion[nc2 + R.qax[q]] - nc, Y = orig_ion[nc2 + R.qay[q]] - nc;
        qfull[q] = -1;
        for (int f = 0; f < nq; ++f)
            if (I->qca[f] == A && I->qcb[f] == B && I->qax[f] == X && I->qay[f] == Y) { qfull[q] = f; break; }
        if (qfull[q] < 0) { free(qfull); goto out; }
        R.Za[q] = I->Za[qfull[q]]; R.Zb[q] = I->Zb[qfull[q]];
        R.Zx[q] = I->Zx[qfull[q]]; R.Zy[q] = I->Zy[qfull[q]];
    }

    /* pairs */
    R.pc = malloc((size_t)I->np * sizeof(int) + 1); R.pa = malloc((size_t)I->np * sizeof(int) + 1);
    R.pG = malloc((size_t)I->np * sizeof(double) + 1); R.pst = malloc((size_t)I->np * sizeof(double) + 1);
    R.Ztab = malloc((size_t)I->np * R.nq * sizeof(double) + 1);
    R.zeta = calloc((size_t)nc2 * na2, sizeof(double));
    if (!R.pc || !R.pa || !R.pG || !R.pst || !R.Ztab || !R.zeta) { free(qfull); goto out; }
    for (int p = 0; p < I->np; ++p) {
        const int c = newc[I->pc[p]], a = newa[I->pa[p]];
        if (c < 0 || a < 0) continue;
        R.pc[R.np] = c; R.pa[R.np] = a; R.pG[R.np] = I->pG[p]; R.pst[R.np] = I->pst[p];
        for (int q = 0; q < R.nq; ++q) R.Ztab[(size_t)R.np * R.nq + q] = I->Ztab[(size_t)p * nq + qfull[q]];
        R.zeta[c * na2 + a] = I->zeta[I->pc[p] * na + I->pa[p]];
        R.np++;
    }
    free(qfull);

    /* excess terms naming only kept ions */
    const size_t ni = (size_t)I->nx * sizeof(int) + 1, nd = (size_t)I->nx * sizeof(double) + 1;
    R.xm = malloc(ni); R.xc = malloc(ni); R.xA = malloc(ni); R.xB = malloc(ni);
    R.xX = malloc(ni); R.xY = malloc(ni); R.xac = malloc(ni);
    R.xpp = malloc(nd); R.xqp = malloc(nd); R.xL = malloc(nd); R.xr = malloc(nd);
    R.cgrp = malloc((size_t)nc2 * sizeof(int)); R.agrp = malloc((size_t)na2 * sizeof(int));
    if (!R.xm || !R.xc || !R.xA || !R.xB || !R.xX || !R.xY || !R.xac || !R.xpp || !R.xqp ||
        !R.xL || !R.xr || !R.cgrp || !R.agrp) goto out;
#define KEPT_C(i) ((i) < 0 || newc[(i)] >= 0)
#define KEPT_A(k) ((k) < 0 || newa[(k)] >= 0)
#define MAP_C(i) ((i) < 0 ? (i) : newc[(i)])
#define MAP_A(k) ((k) < 0 ? (k) : newa[(k)])
    for (int t = 0; t < I->nx; ++t) {
        if (!KEPT_C(I->xA[t]) || !KEPT_C(I->xB[t]) || !KEPT_A(I->xX[t]) || !KEPT_A(I->xY[t])) continue;
        int add = I->xac[t];
        if (add >= 0 && newc[add] < 0) {
            if (I->xr[t] == 0.0) goto out;
            continue;
        }
        const int u = R.nx++;
        R.xm[u] = I->xm[t]; R.xc[u] = I->xc[t];
        R.xA[u] = MAP_C(I->xA[t]); R.xB[u] = MAP_C(I->xB[t]);
        R.xX[u] = MAP_A(I->xX[t]); R.xY[u] = MAP_A(I->xY[t]);
        R.xac[u] = MAP_C(add);
        R.xpp[u] = I->xpp[t]; R.xqp[u] = I->xqp[t]; R.xL[u] = I->xL[t]; R.xr[u] = I->xr[t];
    }
#undef KEPT_C
#undef KEPT_A
#undef MAP_C
#undef MAP_A
    for (int i = 0; i < nc; ++i) if (newc[i] >= 0) R.cgrp[newc[i]] = I->cgrp[i];
    for (int k = 0; k < na; ++k) if (newa[k] >= 0) R.agrp[newa[k]] = I->agrp[k];
    inputs_free(I);
    *I = R;
    memset(&R, 0, sizeof R);
    rc = 0;
out:
    inputs_free(&R);
    free(keep_el); free(newc); free(newa);
    return rc;
}

/* The phase's inputs, cut down to the ions of the elements el_keep marks (NULL: all) and
 * without the ions the general solver holds out of this phase (Phase.ion_off) */
static int inputs_get(const mqmqa_db *db, int phase, double T, const int *el_keep, PhInputs *I)
{
    if (inputs_build(db, phase, T, I)) return -1;
    const int *ion_off = ((const Db *)db)->phases[phase].ion_off;
    if (!el_keep && !ion_off) return 0;
    int all = 1;
    for (int j = 0; el_keep && j < I->nel && all; ++j) if (!el_keep[I->dbe[j]]) all = 0;
    if (all && !ion_off) return 0;
    if (inputs_restrict(I, db, el_keep, ion_off)) {
        inputs_free(I);
        mqmqa_db_set_error("phase %d cannot be restricted to the elements present", phase);
        return -1;
    }
    return 0;
}

static double equilibrate_inputs(PhInputs *I, const mqmqa_db *db, double T,
                                 const double *target_elem, double *X_out, double *err_out)
{
    /* target over the compact space, normalized to sum 1 */
    const int ndbel = mqmqa_db_num_elements(db);
    double *target = calloc((size_t)I->nel, sizeof(double));
    double GM = NAN;
    if (!target) return NAN;
    double tot = 0.0;
    for (int e = 0; e < ndbel; ++e) {
        double v = target_elem[e];
        if (v == 0.0) continue;
        int j = jx_of(I->dbe, I->nel, e);
        if (j >= 0) { target[j] += v; tot += v; }
    }
    if (tot > 0.0) {
        for (int e = 0; e < I->nel; ++e) target[e] /= tot;
        GM = mqmqa_equilibrate_comp(
            T, I->ncat, I->nan, I->nq, I->qca, I->qcb, I->qax, I->qay,
            I->Za, I->Zb, I->Zx, I->Zy, I->zeta, I->soln,
            I->np, I->pc, I->pa, I->pG, I->pst, I->Ztab,
            I->nx, I->xm, I->xc, I->xA, I->xB, I->xX, I->xY, I->xpp, I->xqp, I->xL, I->xr, I->xac,
            I->cgrp, I->agrp,
            I->R_own,
            I->nel, I->icomp, target, X_out, err_out);
    }
    free(target);
    return GM;
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
    PhInputs I;
    if (inputs_build(db, phase, T, &I)) return NAN;
    /* An element of the phase absent from the target (an edge of a ternary section) is
     * taken out of the phase with its ions. Left in at zero amount, the solve came out
     * 1.0 to 2.6 kJ/mol high there, and the web app's ternary calculator named the wrong
     * phases on the edges. A target with every element present takes the path as before. */
    int absent = 0;
    for (int j = 0; j < I.nel; ++j) if (target_elem[I.dbe[j]] == 0.0) absent = 1;
    if (!absent) {
        const double GM = equilibrate_inputs(&I, db, T, target_elem, X_out, err_out);
        inputs_free(&I);
        return GM;
    }
    const int ndbel = mqmqa_db_num_elements(db), ncat = I.ncat, nan = I.nan, nq = I.nq;
    int *keep = malloc((size_t)ndbel * sizeof(int));
    int *qa = malloc((size_t)nq * 4 * sizeof(int));
    double *Xr = NULL, GM = NAN;
    if (!keep || !qa) goto done;
    for (int e = 0; e < ndbel; ++e) keep[e] = target_elem[e] != 0.0;
    /* the full phase's quadruplets, to write X_out over them */
    mqmqa_enumerate_quadruplets(ncat, nan, qa, qa + nq, qa + 2 * nq, qa + 3 * nq);
    if (inputs_restrict(&I, db, keep, NULL)) goto done;
    Xr = malloc((size_t)I.nq * sizeof(double));
    if (!Xr) goto done;
    GM = equilibrate_inputs(&I, db, T, target_elem, Xr, err_out);
    if (X_out) {
        for (int q = 0; q < nq; ++q) X_out[q] = 0.0;
        for (int q = 0; q < I.nq; ++q) {
            const int A = I.orig[I.qca[q]], B = I.orig[I.qcb[q]];
            const int X = I.orig[I.ncat + I.qax[q]] - ncat, Y = I.orig[I.ncat + I.qay[q]] - ncat;
            for (int f = 0; f < nq; ++f)
                if (qa[f] == A && qa[nq + f] == B && qa[2 * nq + f] == X && qa[3 * nq + f] == Y) {
                    X_out[f] = Xr[q];
                    break;
                }
        }
    }
done:
    free(keep); free(qa); free(Xr);
    inputs_free(&I);
    return GM;
}

double mqmqa_equilibrate_sub_err(const mqmqa_db *db, int phase, double T,
                                 const double *target_elem, const int *el_keep, double *err_out)
{
    PhInputs I;
    if (inputs_get(db, phase, T, el_keep, &I)) return NAN;
    const double GM = equilibrate_inputs(&I, db, T, target_elem, NULL, err_out);
    inputs_free(&I);
    return GM;
}

MQMQA_API double mqmqa_equilibrate_sub_db(const mqmqa_db *db, int phase, double T,
                                          const double *target_elem, const int *el_keep)
{
    return mqmqa_equilibrate_sub_err(db, phase, T, target_elem, el_keep, NULL);
}

MQMQA_API int mqmqa_driving_force_db(const mqmqa_db *db, int phase, double T,
                                     const double *mu_elem, const int *el_keep, int max_out,
                                     double *y_out, double *g_out, double *df_out)
{
    PhInputs I;
    if (inputs_get(db, phase, T, el_keep, &I)) return -1;
    const int ndbel = mqmqa_db_num_elements(db), ni = I.ncat + I.nan;
    double *mu = calloc((size_t)I.nel, sizeof(double));
    double *X = malloc((size_t)(max_out > 0 ? max_out : 1) * I.nq * sizeof(double));
    double *y = malloc((size_t)ni * sizeof(double));
    int n = -1;
    if (!mu || !X || !y) goto done;
    for (int j = 0; j < I.nel; ++j) mu[j] = mu_elem[I.dbe[j]];
    (void)ndbel;
    n = mqmqa_driving_force_minima_comp(
        T, I.ncat, I.nan, I.nq, I.qca, I.qcb, I.qax, I.qay,
        I.Za, I.Zb, I.Zx, I.Zy, I.zeta, I.soln,
        I.np, I.pc, I.pa, I.pG, I.pst, I.Ztab,
        I.nx, I.xm, I.xc, I.xA, I.xB, I.xX, I.xY, I.xpp, I.xqp, I.xL, I.xr, I.xac, I.cgrp, I.agrp,
        I.R_own,
        I.nel, I.icomp, mu, max_out, X, df_out);
    if (n < 0) mqmqa_db_set_error("driving force: phase %d could not be evaluated", phase);
    /* ion amounts per quadruplet are 1/Z of each site it holds; their fractions on each
     * sublattice, and with them the composition, follow from X. Written over the full
     * phase's ions, a dropped one at zero. */
    for (int k = 0; k < n; ++k) {
        const double *Xk = X + (size_t)k * I.nq;
        memset(y, 0, (size_t)ni * sizeof(double));
        for (int q = 0; q < I.nq; ++q) {
            y[I.qca[q]] += Xk[q] / I.Za[q];
            y[I.qcb[q]] += Xk[q] / I.Zb[q];
            y[I.ncat + I.qax[q]] += Xk[q] / I.Zx[q];
            y[I.ncat + I.qay[q]] += Xk[q] / I.Zy[q];
        }
        double sc = 0.0, sa = 0.0, mux = 0.0, atoms = 0.0;
        for (int i = 0; i < ni; ++i) {
            if (i < I.ncat) sc += y[i]; else sa += y[i];
            for (int j = 0; j < I.nel; ++j) {
                mux += mu[j] * I.icomp[(size_t)i * I.nel + j] * y[i];
                atoms += I.icomp[(size_t)i * I.nel + j] * y[i];
            }
        }
        g_out[k] = df_out[k] + mux / atoms;          /* G per mole of atoms */
        double *yk = y_out + (size_t)k * I.nfull;
        memset(yk, 0, (size_t)I.nfull * sizeof(double));
        for (int i = 0; i < I.ncat; ++i) yk[I.orig[i]] = y[i] / sc;
        for (int a = 0; a < I.nan; ++a) yk[I.orig[I.ncat + a]] = y[I.ncat + a] / sa;
    }
done:
    free(mu); free(X); free(y);
    inputs_free(&I);
    return n;
}

struct mqmqa_quad_ctx {
    const mqmqa_db *db;
    double T;
    int ndbel;
    PhInputs I;
};

mqmqa_quad_ctx *mqmqa_quad_open(const mqmqa_db *db, int phase, double T, const int *el_keep)
{
    mqmqa_quad_ctx *c = calloc(1, sizeof(*c));
    if (!c) return NULL;
    if (inputs_get(db, phase, T, el_keep, &c->I)) { free(c); return NULL; }
    c->db = db;
    c->T = T;
    c->ndbel = mqmqa_db_num_elements(db);
    return c;
}

void mqmqa_quad_close(mqmqa_quad_ctx *c)
{
    if (!c) return;
    inputs_free(&c->I);
    free(c);
}

int mqmqa_quad_count(const mqmqa_quad_ctx *c) { return c ? c->I.nq : 0; }

void mqmqa_quad_elements(const mqmqa_quad_ctx *c, double *comp)
{
    const PhInputs *I = &c->I;
    memset(comp, 0, (size_t)I->nq * c->ndbel * sizeof(double));
    for (int k = 0; k < I->nq; ++k) {
        const int ion[4] = { I->qca[k], I->qcb[k], I->ncat + I->qax[k], I->ncat + I->qay[k] };
        const double inv[4] = { 1.0 / I->Za[k], 1.0 / I->Zb[k], 1.0 / I->Zx[k], 1.0 / I->Zy[k] };
        for (int t = 0; t < 4; ++t)
            for (int j = 0; j < I->nel; ++j)
                comp[(size_t)k * c->ndbel + I->dbe[j]] += I->icomp[(size_t)ion[t] * I->nel + j] * inv[t];
    }
}

double mqmqa_quad_gibbs(const mqmqa_quad_ctx *c, const double *X, double *grad)
{
    const PhInputs *I = &c->I;
    const double g =
        mqmqa_reference_energy(I->nq, I->qca, I->qcb, I->qax, I->qay, X,
                               I->np, I->pc, I->pa, I->pG, I->pst, I->Ztab)
      + mqmqa_ideal_mixing_energy(c->T, I->ncat, I->nan, I->nq, I->qca, I->qcb, I->qax, I->qay, X,
                                  I->Za, I->Zb, I->Zx, I->Zy, I->zeta, I->soln, I->R_own)
      + mqmqa_excess_energy(I->ncat, I->nan, I->nq, I->qca, I->qcb, I->qax, I->qay, X,
                            I->Za, I->Zb, I->Zx, I->Zy, I->soln,
                            I->nx, I->xm, I->xc, I->xA, I->xB, I->xX, I->xY, I->xpp, I->xqp, I->xL,
                            I->xr, I->xac, I->cgrp, I->agrp);
    if (grad)
        mqmqa_gibbs_gradient(
            c->T, I->ncat, I->nan, I->nq, I->qca, I->qcb, I->qax, I->qay,
            I->Za, I->Zb, I->Zx, I->Zy, I->zeta, I->soln,
            I->np, I->pc, I->pa, I->pG, I->pst, I->Ztab,
            I->nx, I->xm, I->xc, I->xA, I->xB, I->xX, I->xY, I->xpp, I->xqp, I->xL, I->xr, I->xac,
            I->cgrp, I->agrp, I->R_own, X, grad);
    return g;
}

int mqmqa_quad_start(mqmqa_quad_ctx *c, const double *target_elem, double *X_out)
{
    return isfinite(equilibrate_inputs(&c->I, c->db, c->T, target_elem, X_out, NULL)) ? 0 : -1;
}

MQMQA_API int mqmqa_tangent_rows_db(const mqmqa_db *db, int phase, double T,
                                    const double *target_elem, const int *el_keep, int max_rows,
                                    double *A_out, double *b_out)
{
    PhInputs I;
    if (inputs_get(db, phase, T, el_keep, &I)) return -1;
    const int ndbel = mqmqa_db_num_elements(db), nq = I.nq;
    double *X = malloc((size_t)nq * sizeof(double));
    double *grad = malloc((size_t)nq * sizeof(double));
    int *dbel = malloc((size_t)I.nel * sizeof(int));     /* compact element -> database element */
    int rows = -1;
    if (!X || !grad || !dbel) goto done;
    for (int j = 0; j < I.nel; ++j) dbel[j] = I.dbe[j];
    if (!isfinite(equilibrate_inputs(&I, db, T, target_elem, X, NULL))) goto done;
    mqmqa_gibbs_gradient(
        T, I.ncat, I.nan, nq, I.qca, I.qcb, I.qax, I.qay,
        I.Za, I.Zb, I.Zx, I.Zy, I.zeta, I.soln,
        I.np, I.pc, I.pa, I.pG, I.pst, I.Ztab,
        I.nx, I.xm, I.xc, I.xA, I.xB, I.xX, I.xY, I.xpp, I.xqp, I.xL, I.xr, I.xac, I.cgrp, I.agrp,
        I.R_own, X, grad);
    /* for every quadruplet present dG/dX_q = sum_e mu_e n_e(q) + lambda; the reference
     * quadruplet (the most abundant) takes lambda out */
    int q0 = 0;
    for (int q = 1; q < nq; ++q) if (X[q] > X[q0]) q0 = q;
    rows = 0;
    for (int q = 0; q < nq && rows < max_rows; ++q) {
        if (q == q0 || !(X[q] > 1e-8) || !isfinite(grad[q] - grad[q0])) continue;
        double *A = A_out + (size_t)rows * ndbel;
        memset(A, 0, (size_t)ndbel * sizeof(double));
        const int qq[2] = { q, q0 };
        for (int s = 0; s < 2; ++s) {
            const int k = qq[s];
            const double sg = s ? -1.0 : 1.0;
            const int ion[4] = { I.qca[k], I.qcb[k], I.ncat + I.qax[k], I.ncat + I.qay[k] };
            const double inv[4] = { 1.0 / I.Za[k], 1.0 / I.Zb[k], 1.0 / I.Zx[k], 1.0 / I.Zy[k] };
            for (int t = 0; t < 4; ++t)
                for (int j = 0; j < I.nel; ++j)
                    A[dbel[j]] += sg * I.icomp[(size_t)ion[t] * I.nel + j] * inv[t];
        }
        b_out[rows++] = grad[q] - grad[q0];
    }
done:
    free(X); free(grad); free(dbel);
    inputs_free(&I);
    return rows;
}
