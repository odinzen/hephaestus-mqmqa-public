"""Gibbs-Duhem internal-consistency check of Stolyarova's a(CaO) vs a(SiO2).

G-D: x_CaO d ln a_CaO + x_SiO2 d ln a_SiO2 = 0, so a(CaO) is NOT independent of
a(SiO2). Integrate ln a_CaO from a(SiO2):
    ln a_CaO(x) = ln a_CaO(x0) - INT_{x0}^{x} (x_SiO2/x_CaO) d ln a_SiO2
and compare the G-D-predicted a(CaO) to Stolyarova's measured a(CaO). Divergence =
the two columns are internally inconsistent (a sign the dataset is the outlier).
"""
import numpy as np
# x_SiO2: (a_CaO, a_SiO2), Stolyarova 1991 Tables IIa/IIb (solid reference)
D = {0.25:(1.00,0.004),0.33:(0.96,0.003),0.38:(0.63,0.023),0.39:(0.52,0.04),
     0.40:(0.52,0.03),0.41:(0.29,0.05),0.44:(0.26,0.10),0.49:(0.11,0.09),0.50:(0.07,0.20)}
x = np.array(sorted(D)); aC = np.array([D[t][0] for t in x]); aS = np.array([D[t][1] for t in x])
lnS = np.log(aS)
# integrate from the CaO-rich end (x[0]) where a_CaO measured; trapezoid on (xSi/xCa) d lnS
lnaC_gd = np.zeros_like(x); lnaC_gd[0] = np.log(aC[0])
for i in range(1,len(x)):
    xm = 0.5*(x[i]+x[i-1]); ratio = xm/(1-xm)          # x_SiO2/x_CaO at midpoint
    lnaC_gd[i] = lnaC_gd[i-1] - ratio*(lnS[i]-lnS[i-1])
print(" x_SiO2  aCaO_meas  aCaO_GD(from aSiO2)  ln-ratio")
for i in range(len(x)):
    print(f"  {x[i]:.2f}    {aC[i]:7.3f}     {np.exp(lnaC_gd[i]):10.3f}       {lnaC_gd[i]-np.log(aC[i]):+.2f}")
dev = np.sqrt(np.mean((lnaC_gd-np.log(aC))**2))
print(f"\n RMS ln-deviation (measured vs G-D) = {dev:.2f}  "
      f"({'INTERNALLY INCONSISTENT' if dev>0.5 else 'consistent'})")
print(" note: low-x points (0.25,0.33) are two-phase/saturated; the single-phase")
print(" test is the trend over x_SiO2>=0.38 where a(SiO2) is noisy (0.03 vs 0.04, 0.09 vs 0.20).")
