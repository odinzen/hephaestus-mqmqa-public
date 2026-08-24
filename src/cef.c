#include "cef.h"

#include <math.h>

/* CALPHAD gas constant (matches mqmqa_R and cef.py), not CODATA. */
#define CEF_R 8.3145

double mqmqa_cef_gibbs(
    double T,
    int n_subl,
    const double *site_ratio,
    const int *subl_ncon,
    const int *subl_off,
    const double *Y,
    const double *atoms,
    int n_em,
    const int *em_con,
    const double *em_G,
    int n_ex,
    const int *ex_subl,
    const int *ex_i,
    const int *ex_j,
    const int *ex_order,
    const double *ex_L,
    const int *ex_other,
    int per_mole_atoms)
{
    double G = 0.0;

    /* reference: sum over endmembers of (product of site fractions) * G_endmember */
    for (int e = 0; e < n_em; ++e) {
        double prod = 1.0;
        for (int s = 0; s < n_subl; ++s)
            prod *= Y[subl_off[s] + em_con[e * n_subl + s]];
        G += prod * em_G[e];
    }

    /* ideal configurational entropy, per sublattice weighted by site multiplicity */
    for (int s = 0; s < n_subl; ++s) {
        for (int i = 0; i < subl_ncon[s]; ++i) {
            double y = Y[subl_off[s] + i];
            if (y > 0.0)
                G += CEF_R * T * site_ratio[s] * y * log(y);
        }
    }

    /* excess: Redlich-Kister interactions */
    for (int k = 0; k < n_ex; ++k) {
        int s = ex_subl[k];
        double yi = Y[subl_off[s] + ex_i[k]];
        double yj = Y[subl_off[s] + ex_j[k]];
        double other = 1.0;
        for (int s2 = 0; s2 < n_subl; ++s2)
            if (s2 != s)
                other *= Y[subl_off[s2] + ex_other[k * n_subl + s2]];
        G += other * yi * yj * ex_L[k] * pow(yi - yj, (double)ex_order[k]);
    }

    if (per_mole_atoms) {
        double tot = 0.0;
        for (int s = 0; s < n_subl; ++s) {
            if (atoms) {
                double ssum = 0.0;
                for (int i = 0; i < subl_ncon[s]; ++i)
                    ssum += Y[subl_off[s] + i] * atoms[subl_off[s] + i];
                tot += site_ratio[s] * ssum;
            } else {
                tot += site_ratio[s];  /* every constituent is one atom */
            }
        }
        G /= tot;
    }
    return G;
}
