"""Validate the CEF Gibbs implementation against pycalphad's Model.GM to machine
precision, for a single-sublattice binary and a two-sublattice reciprocal solution.
"""
import os
import numpy as np
from pycalphad import Database, calculate
import cef

HERE = os.path.dirname(os.path.abspath(__file__))

# --- case 1: single sublattice (A,B)1 ---
TDB1 = """
ELEMENT A   FCC_A1  1.0 0.0 0.0 !
ELEMENT B   FCC_A1  1.0 0.0 0.0 !
PHASE SOL  %  1  1.0  !
CONSTITUENT SOL :A,B: !
PARAMETER G(SOL,A;0) 298.15  -10000+10*T; 6000 N !
PARAMETER G(SOL,B;0) 298.15   -8000+8*T;  6000 N !
PARAMETER G(SOL,A,B;0) 298.15  5000-2*T;   6000 N !
PARAMETER G(SOL,A,B;1) 298.15  1500;        6000 N !
"""
PHASE1 = cef.CEFPhase(
    sublattices=[(1.0, ["A", "B"])],
    endmembers={(0,): (-10000.0, 10.0), (1,): (-8000.0, 8.0)},
    interactions=[dict(sublattice=0, pair=(0, 1), others={},
                       L=[(5000.0, -2.0), (1500.0,)])],
)

# --- case 2: two sublattices (A,B)1(X,Y)2 reciprocal ---
TDB2 = """
ELEMENT A   FCC_A1  1.0 0.0 0.0 !
ELEMENT B   FCC_A1  1.0 0.0 0.0 !
ELEMENT X   FCC_A1  1.0 0.0 0.0 !
ELEMENT Y   FCC_A1  1.0 0.0 0.0 !
PHASE REC  %  2  1.0 2.0  !
CONSTITUENT REC :A,B:X,Y: !
PARAMETER G(REC,A:X;0) 298.15  -50000+5*T;  6000 N !
PARAMETER G(REC,B:X;0) 298.15  -42000+4*T;  6000 N !
PARAMETER G(REC,A:Y;0) 298.15  -38000+6*T;  6000 N !
PARAMETER G(REC,B:Y;0) 298.15  -30000+3*T;  6000 N !
PARAMETER G(REC,A,B:X;0) 298.15  8000;       6000 N !
PARAMETER G(REC,A,B:Y;0) 298.15  6000-1*T;   6000 N !
PARAMETER G(REC,A:X,Y;0) 298.15  4000;       6000 N !
"""
PHASE2 = cef.CEFPhase(
    sublattices=[(1.0, ["A", "B"]), (2.0, ["X", "Y"])],
    endmembers={(0, 0): (-50000.0, 5.0), (1, 0): (-42000.0, 4.0),
                (0, 1): (-38000.0, 6.0), (1, 1): (-30000.0, 3.0)},
    interactions=[
        dict(sublattice=0, pair=(0, 1), others={1: 0}, L=[(8000.0,)]),      # A,B : X
        dict(sublattice=0, pair=(0, 1), others={1: 1}, L=[(6000.0, -1.0)]),  # A,B : Y
        dict(sublattice=1, pair=(0, 1), others={0: 0}, L=[(4000.0,)]),      # A : X,Y
    ],
)


def check(tag, tdb, comps, phase_name, our_phase, points, Ys, T=1000.0):
    open(os.path.join(HERE, "_v.tdb"), "w").write(tdb)
    db = Database(os.path.join(HERE, "_v.tdb"))
    print(f"\n{tag}  (T={T} K)")
    worst = 0.0
    for pt, Y in zip(points, Ys):
        res = calculate(db, comps, phase_name, T=T, P=101325,
                        points=np.array([pt], dtype=float), output="GM")
        gpc = float(res.GM.values.squeeze())
        gours = our_phase.gibbs(Y, T)
        d = abs(gpc - gours)
        worst = max(worst, d)
        print(f"  Y={Y}  pycalphad={gpc:12.4f}  ours={gours:12.4f}  |d|={d:.2e}")
    print(f"  worst |d| = {worst:.2e} J/mol  -> {'PASS' if worst < 1e-4 else 'FAIL'}")


if __name__ == "__main__":
    # case 1: points are [y_A, y_B]
    p1 = [[0.8, 0.2], [0.5, 0.5], [0.2, 0.8]]
    Y1 = [[[0.8, 0.2]], [[0.5, 0.5]], [[0.2, 0.8]]]
    check("case 1: (A,B)1", TDB1, ["A", "B"], "SOL", PHASE1, p1, Y1)

    # case 2: points are [y_A, y_B, y_X, y_Y]
    p2 = [[0.7, 0.3, 0.6, 0.4], [0.5, 0.5, 0.5, 0.5], [0.25, 0.75, 0.9, 0.1]]
    Y2 = [[[0.7, 0.3], [0.6, 0.4]], [[0.5, 0.5], [0.5, 0.5]], [[0.25, 0.75], [0.9, 0.1]]]
    check("case 2: (A,B)1(X,Y)2 reciprocal", TDB2, ["A", "B", "X", "Y"], "REC",
          PHASE2, p2, Y2)
