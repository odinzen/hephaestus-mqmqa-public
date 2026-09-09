"""Reference XTDB reader + 3rd-generation (Einstein/GEIN + two-state liquid) evaluator.
Prototype/spec for the C port in src/xtdb.c. Parses a real XTDB file and assembles endmember
and phase Gibbs energies; the LNTH Einstein term is weighted by the atom count of the formula
unit (so a compound recovers its full 3R-per-atom heat capacity)."""
import os, re, math, xml.etree.ElementTree as ET
R = 8.31451

def parse(path):
    root = ET.parse(path).getroot()
    tp = {}            # TPfun Id -> list of (expr, hiT)  (piecewise)
    for e in root.findall('TPfun'):
        ranges = [(e.get('Expr'), float(e.get('HighT','1e9')))]
        for tr in e.findall('Trange'):
            ranges.append((tr.get('Expr'), float(tr.get('HighT','1e9'))))
        tp[e.get('Id')] = (float(e.get('LowT','0')), ranges)
    params = {}        # (kind, phase, config) -> expr ; kind in G/LNTH/GD
    for e in root.findall('Parameter'):
        m = re.match(r'(\w+)\(([^,]+),([^;]+);(\d+)\)', e.get('Id'))
        kind, phase, consts, deg = m.group(1), m.group(2), m.group(3), m.group(4)
        params[(kind, phase, consts, deg)] = e.get('Expr')
    phases = {}
    for e in root.findall('Phase'):
        amend = e.find('AmendPhase')
        sub = e.find('Sublattices')
        mult, con = [], []
        if sub is not None:
            mult = [float(x) for x in sub.get('Multiplicities').split()]
            con = [None] * len(mult)
            for c in sub.findall('Constituents'):
                con[int(c.get('Sublattice')) - 1] = c.get('List').split()
        phases[e.get('Id')] = {
            'twostate': (amend is not None and 'LIQ2STATE' in (amend.get('Models') or '')),
            'mult': mult, 'con': con}
    return tp, params, phases

def make_eval(tp):
    memo = {}
    def GEIN(theta, T): return 1.5*R*theta + 3*R*T*math.log(1 - math.exp(-theta/T))
    def prep(expr):
        s = expr.strip().rstrip(';').strip()
        s = re.sub(r'\bLN\(', 'log(', s); s = re.sub(r'\bEXP\(', 'exp(', s)
        return s
    def val_tpfun(name, T):
        key=(name,T)
        if key in memo: return memo[key]
        lowT, ranges = tp[name]
        expr = ranges[0][0]
        for ex, hi in ranges:
            expr = ex
            if T <= hi: break
        v = ev(expr, T); memo[key]=v; return v
    class NS(dict):
        def __init__(self, T): super().__init__(); self.T=T
        def __missing__(self, k):
            if k in tp: return val_tpfun(k, self.T)
            raise KeyError(k)
    def ev(expr, T):
        ns = NS(T)
        ns.update({'T':T,'P':1e5,'log':math.log,'exp':math.exp,
                   'GEIN':(lambda th, _T=T: GEIN(th,_T))})
        return eval(prep(expr), {'__builtins__':{}}, ns)
    return ev

def _natoms(phases, phase, consts):
    """Real atoms per formula unit of an endmember (site multiplicities of non-VA constituents).
    The LNTH Einstein term is weighted by this, so a compound gets its full 3R-per-atom Cp."""
    mult = phases[phase].get('mult') or []
    parts = consts.split(':')
    n = sum(mult[s] for s, c in enumerate(parts) if s < len(mult) and c != 'VA')
    return n if n > 0 else 1.0


def endmember_G(tp, params, phases, phase, consts, T):
    """Total 3rd-gen endmember Gibbs: G_expr + N_atoms*GEIN(exp(LNTH)) [+ two-state via GD]."""
    ev = make_eval(tp)
    g = ev(params[('G', phase, consts, '0')], T)
    lnth = params.get(('LNTH', phase, consts, '0'))
    if lnth is not None:
        theta = math.exp(ev(lnth, T))
        g += _natoms(phases, phase, consts) * (1.5*R*theta + 3*R*T*math.log(1 - math.exp(-theta/T)))
    if phases[phase]['twostate']:
        gd = params.get(('GD', phase, consts, '0'))
        if gd is not None:
            dG = ev(gd, T)
            g += -R*T*math.log(1 + math.exp(-dG/(R*T)))
    return g

def _atoms(c): return 0.0 if c == 'VA' else 1.0

def _endmember_am(tp, params, phases, phase, consts, T):
    """Amorphous endmember (G + GEIN, WITHOUT the phase-level two-state term)."""
    ev = make_eval(tp)
    g = ev(params[('G', phase, consts, '0')], T)
    lnth = params.get(('LNTH', phase, consts, '0'))
    if lnth is not None:
        theta = math.exp(ev(lnth, T))
        g += _natoms(phases, phase, consts) * (1.5*R*theta + 3*R*T*math.log(1 - math.exp(-theta/T)))
    return g

def phase_G(tp, params, phases, phase, B, xB, T):
    """Gibbs per mole of atoms at overall mole fraction xB of element B. Mirrors the C
    xtdb_phase_gibbs: CEF reference + ideal entropy + Redlich-Kister excess + two-state.
    Returns (G, fixed_xB) where fixed_xB is the stoichiometric composition or None."""
    ev = make_eval(tp)
    ph = phases[phase]; mult, con = ph['mult'], ph['con']
    smix = next((s for s in range(len(con)) if len(con[s]) > 1), None)

    def xB_of_y(y):
        aB = atot = 0.0
        for s in range(len(con)):
            for i, c in enumerate(con[s]):
                yi = (y if i == 0 else 1 - y) if s == smix else 1.0
                atot += mult[s] * yi * _atoms(c)
                if c == B: aB += mult[s] * yi * _atoms(c)
        return aB / atot if atot else 0.0

    if smix is None:
        y, fixed = 1.0, xB_of_y(1.0)
    else:
        lo, hi, fixed = 1e-9, 1 - 1e-9, None
        flo = xB_of_y(lo) - xB
        if (xB_of_y(hi) - xB) * flo > 0: return None, None      # xB out of range
        for _ in range(100):
            m = 0.5*(lo+hi)
            if (xB_of_y(m) - xB) * flo <= 0: hi = m
            else: lo = m
        y = 0.5*(lo+hi)

    Y = [[(y if i == 0 else 1-y) if s == smix else 1.0 for i in range(len(con[s]))]
         for s in range(len(con))]

    ref = 0.0
    import itertools
    for idx in itertools.product(*[range(len(con[s])) for s in range(len(con))]):
        prod = 1.0
        cs = ':'.join(con[s][idx[s]] for s in range(len(con)))
        for s in range(len(con)): prod *= Y[s][idx[s]]
        if prod > 0: ref += prod * _endmember_am(tp, params, phases, phase, cs, T)

    ideal = sum(R*T*mult[s]*Y[s][i]*math.log(Y[s][i])
                for s in range(len(con)) for i in range(len(con[s])) if Y[s][i] > 0)

    excess = 0.0
    for (kind, php, cons, deg), expr in params.items():
        if kind != 'G' or php != phase or ',' not in cons: continue
        subl = cons.split(':')
        smix2 = next((s for s in range(len(subl)) if ',' in subl[s]), None)
        if smix2 is None: continue
        ci, cj = subl[smix2].split(',')
        try: ii, jj = con[smix2].index(ci), con[smix2].index(cj)
        except ValueError: continue
        yi, yj = Y[smix2][ii], Y[smix2][jj]
        excess += yi*yj*ev(expr, T)*(yi-yj)**int(deg)

    atot = sum(mult[s]*Y[s][i]*_atoms(con[s][i])
               for s in range(len(con)) for i in range(len(con[s])))
    G = (ref + ideal + excess) / (atot if atot else 1.0)

    if ph['twostate'] and smix is not None:
        dG = sum(Y[smix][i]*ev(params[('GD', phase, con[smix][i], '0')], T)
                 for i in range(len(con[smix])) if ('GD', phase, con[smix][i], '0') in params)
        G += -R*T*math.log(1 + math.exp(-dG/(R*T)))
    return G, fixed

if __name__ == '__main__':
    # default to the repository's own CC-BY transcription (data/xtdb/AlC.xtdb); the GPL
    # reference file (AlC-database.XTDB) is a local-only validation copy, not shipped.
    import sys
    _here = os.path.dirname(os.path.abspath(__file__))
    _default = os.path.join(_here, '..', 'xtdb', 'AlC.xtdb')
    path = sys.argv[1] if len(sys.argv) > 1 else (_default if os.path.exists(_default) else 'AlC-database.XTDB')
    tp, params, phases = parse(path)
    print('parsed:', len(tp), 'TPfuns,', len(params), 'parameters,', len(phases), 'phases')
    print('two-state phases:', [p for p in phases if phases[p]['twostate']])
    # validate pure-Al melting FROM THE PARSED FILE: G(LIQUID,AL) == G(FCC_A1,AL:VA)
    f = lambda T: endmember_G(tp,params,phases,'LIQUID','AL',T) - endmember_G(tp,params,phases,'FCC_A1','AL:VA',T)
    lo,hi=700.,1100.
    for _ in range(80):
        m=0.5*(lo+hi)
        if f(lo)*f(m)<=0: hi=m
        else: lo=m
    Tm=0.5*(lo+hi)
    print(f'pure-Al melting from parsed XTDB: {Tm:.2f} K  (target 933.47)')
    # graphite reference sanity: G(GRAPHITE,C) finite and Cp physical at 298
    gG = endmember_G(tp,params,phases,'GRAPHITE','C',298.15)
    Cp = -298.15*(endmember_G(tp,params,phases,'GRAPHITE','C',298.16)-2*gG+endmember_G(tp,params,phases,'GRAPHITE','C',298.14))/0.01**2
    print(f'G(GRAPHITE,C,298.15) = {gG:.1f} J/mol ; Cp = {Cp:.2f} J/mol/K  (graphite Cp exp ~8.5)')
