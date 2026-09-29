"""3D phase-space views over the C module in src/vis3d.h.

The mesh is for seeing; numbers come from the engine. Every array is copied out of the
C arena into numpy before the arena is freed, so nothing here keeps a pointer into
engine memory.

Composition is the cation fractions (x1, x2, x3) of the liquid's three cations, in the
liquid's own order; `hull.phase_names` and `Section.labels` name what was found.
"""
from dataclasses import dataclass

import numpy as np

from ._abi import _ffi, _lib
from ._database import Database

_ffi.cdef(
    """
    typedef struct {
        int32_t n_vert, n_tri, n_patch, n_line_pts, n_line;
        float *pos; double *comp; double *temp; float *scalar; uint32_t *tri;
        int32_t *patch_start; int32_t *patch_phase; float *line_pos; int32_t *line_start;
        int32_t n_label; char (*label)[64];
        void *arena;
    } VisMesh;
    typedef struct {
        int32_t lattice_n, n_temps; double t_lo, t_hi; double x_tol, t_tol, z_per_kelvin;
        uint32_t seed; int32_t max_refine;
    } VisOptions;
    void vis3d_default_options(VisOptions *opt);
    int vis3d_section(const void *db, const char *const *phases, int n_phases, double T,
                      const VisOptions *opt, VisMesh *out);
    void vis3d_bary_to_xy(double x2, double x3, double *X, double *Y);
    void vis3d_free(VisMesh *m);
    double vis3d_liquid_gibbs(const void *db, int phase, double T, double x2, double x3,
                              double *X_out);
    void *vis3d_hull_build(const void *db, const char *const *phases, int n_phases, double T,
                           const VisOptions *opt);
    void vis3d_hull_free(void *h);
    int vis3d_hull_passes(const void *h);
    double vis3d_hull_last_shift(const void *h);
    int vis3d_hull_num_points(const void *h);
    double vis3d_hull_max_comp_err(const void *h);
    int vis3d_hull_num_phases(const void *h);
    const char *vis3d_hull_phase_name(const void *h, int k);
    int vis3d_hull_point(const void *h, int i, double *x2, double *x3, double *g,
                         double *comp_err);
    int vis3d_hull_num_facets(const void *h);
    const int *vis3d_hull_facets(const void *h);
    double vis3d_hull_gibbs(const void *h, double x2, double x3);
    int vis3d_hull_section(const void *h, const VisOptions *opt, VisMesh *out);
    int vis3d_lower_hull(const double *pts, int n, int *facets, int max_facets);
    int vis3d_liquidus_surface(const void *db, const char *const *phases, int n_phases,
                               const VisOptions *opt, VisMesh *out);
    int vis3d_liquidus_point(const void *db, const char *const *phases, int n_phases,
                             const VisOptions *opt, double x2, double x3, double *T,
                             char *primary, int primary_len);
    int vis3d_hull_assemblage(const void *h, double x2, double x3, int *phase_out,
                              double *amt_out, double *comp_out, int max_out);
    """,
    override=True,
)


class Vis3DError(RuntimeError):
    """The engine refused or could not converge; the message says why."""


def _error():
    return _ffi.string(_lib.mqmqa_db_error()).decode()


def _options(lattice_n, x_tol, seed, max_refine, z_per_kelvin, t_lo=None, t_hi=None,
             n_temps=None, t_tol=None):
    o = _ffi.new("VisOptions *")
    _lib.vis3d_default_options(o)
    if t_lo is not None:
        o.t_lo = t_lo
    if t_hi is not None:
        o.t_hi = t_hi
    if n_temps is not None:
        o.n_temps = n_temps
    if t_tol is not None:
        o.t_tol = t_tol
    if lattice_n is not None:
        o.lattice_n = lattice_n
    if x_tol is not None:
        o.x_tol = x_tol
    if seed is not None:
        o.seed = seed
    if max_refine is not None:
        o.max_refine = max_refine
    if z_per_kelvin is not None:
        o.z_per_kelvin = z_per_kelvin
    return o


def _phase_args(phases):
    if phases is None:
        return _ffi.NULL, 0, []
    keep = [_ffi.new("char[]", p.encode()) for p in phases]
    return _ffi.new("const char *[]", keep), len(keep), keep


def _handle(db):
    return db._db if isinstance(db, Database) else db


def bary_to_xy(x2, x3):
    X = _ffi.new("double *"); Y = _ffi.new("double *")
    _lib.vis3d_bary_to_xy(x2, x3, X, Y)
    return X[0], Y[0]


def liquid_gibbs(db, phase, T, x2, x3):
    """Minimum liquid Gibbs energy per mole of cations at (x2, x3), and the quadruplet
    fractions reaching it."""
    p = db.phase_index(phase) if isinstance(phase, str) else phase
    X = _ffi.new("double[16]")
    g = _lib.vis3d_liquid_gibbs(_handle(db), p, float(T), float(x2), float(x3), X)
    if g != g:
        raise Vis3DError(_error() or f"the liquid minimization did not converge at "
                                      f"x2 = {x2!r}, x3 = {x3!r}, T = {T} K")
    return g, np.array([X[q] for q in range(6)])


class Hull:
    """The deterministic, tangency-refined equilibrium hull at one temperature."""

    def __init__(self, db, T, phases=None, x_tol=None, seed=None, max_refine=None):
        self._db = db   # keep the database alive as long as the hull reads it
        arr, n, self._keep = _phase_args(phases)
        o = _options(None, x_tol, seed, max_refine, None)
        h = _lib.vis3d_hull_build(_handle(db), arr, n, float(T), o)
        if h == _ffi.NULL:
            raise Vis3DError(_error())
        self._h = _ffi.gc(h, _lib.vis3d_hull_free)
        self.T = float(T)

    @property
    def passes(self):
        return _lib.vis3d_hull_passes(self._h)

    @property
    def last_shift(self):
        return _lib.vis3d_hull_last_shift(self._h)

    @property
    def num_points(self):
        return _lib.vis3d_hull_num_points(self._h)

    @property
    def max_comp_err(self):
        return _lib.vis3d_hull_max_comp_err(self._h)

    @property
    def phase_names(self):
        return [_ffi.string(_lib.vis3d_hull_phase_name(self._h, k)).decode()
                for k in range(_lib.vis3d_hull_num_phases(self._h))]

    def points(self):
        """Samples as arrays: x2, x3, g (per mole of cations), phase index, comp error."""
        n = self.num_points
        out = np.empty((n, 5))
        x2 = _ffi.new("double *"); x3 = _ffi.new("double *"); g = _ffi.new("double *")
        e = _ffi.new("double *")
        for i in range(n):
            k = _lib.vis3d_hull_point(self._h, i, x2, x3, g, e)
            out[i] = (x2[0], x3[0], g[0], k, e[0])
        return out

    def facets(self):
        nf = _lib.vis3d_hull_num_facets(self._h)
        return _copy(_lib.vis3d_hull_facets(self._h), "int *", nf * 3, np.int32, (nf, 3))

    def section(self, lattice_n=None, x_tol=None, z_per_kelvin=None):
        """The isothermal section of this hull (see `section`)."""
        o = _options(lattice_n, x_tol, None, None, z_per_kelvin)
        m = _ffi.new("VisMesh *")
        return _take_mesh(m, _lib.vis3d_hull_section(self._h, o, m), self.T)

    def gibbs(self, x2, x3):
        """Equilibrium Gibbs energy per mole of cations at bulk (x2, x3)."""
        return _lib.vis3d_hull_gibbs(self._h, float(x2), float(x3))

    def assemblage(self, x2, x3):
        """[(phase, amount, x2, x3), ...] at bulk (x2, x3); a phase on both sides of a
        miscibility gap appears twice."""
        ph = _ffi.new("int[8]"); am = _ffi.new("double[8]"); cp = _ffi.new("double[16]")
        m = _lib.vis3d_hull_assemblage(self._h, float(x2), float(x3), ph, am, cp, 8)
        if m < 0:
            raise Vis3DError(_error())
        names = self.phase_names
        return [(names[ph[k]], am[k], cp[2 * k], cp[2 * k + 1]) for k in range(m)]


@dataclass
class Section:
    T: float
    pos: np.ndarray          # (n_vert, 3) float32: X, Y, z
    comp: np.ndarray         # (n_vert, 3): x1, x2, x3
    temp: np.ndarray         # (n_vert,)
    tri: np.ndarray          # (n_tri, 3) uint32
    patch_start: np.ndarray  # (n_patch + 1,)
    patch_phase: np.ndarray  # (n_patch,) label index
    line_pos: np.ndarray     # (n_line_pts, 3) float32
    line_start: np.ndarray   # (n_line + 1,)
    labels: list

    @property
    def tri_label(self):
        """Label index of every triangle (one label per triangle by construction)."""
        out = np.empty(len(self.tri), dtype=np.int32)
        for p in range(len(self.patch_phase)):
            out[self.patch_start[p]:self.patch_start[p + 1]] = self.patch_phase[p]
        return out


def _copy(ptr, ctype, count, dtype, shape=None):
    if count == 0:
        return np.zeros(shape if shape else (0,), dtype=dtype)
    a = np.frombuffer(_ffi.buffer(_ffi.cast(ctype, ptr), count * np.dtype(dtype).itemsize),
                      dtype=dtype).copy()
    return a.reshape(shape) if shape else a


def lower_hull(pts):
    """Lower-hull facets (index triples) of an (n, 3) array of (x, y, g), every orientation
    decided exactly."""
    P = np.ascontiguousarray(pts, dtype=np.float64)
    cap = 6 * len(P) + 64
    F = _ffi.new("int[]", 3 * cap)
    nf = _lib.vis3d_lower_hull(_ffi.cast("double *", P.ctypes.data), len(P), F, cap)
    if nf < 0:
        raise Vis3DError("lower hull failed (fewer than four points, or all coplanar)")
    return _copy(F, "int *", nf * 3, np.int32, (nf, 3))


def section(db, T, phases=None, lattice_n=None, x_tol=None, seed=None, max_refine=None,
            z_per_kelvin=None):
    """Exact phase regions of the isothermal section at T, one patch per phase field."""
    arr, n, keep = _phase_args(phases)
    o = _options(lattice_n, x_tol, seed, max_refine, z_per_kelvin)
    m = _ffi.new("VisMesh *")
    return _take_mesh(m, _lib.vis3d_section(_handle(db), arr, n, float(T), o, m), T)


def _liquidus_options(t_lo, t_hi, n_temps, lattice_n, x_tol, t_tol, max_refine, z_per_kelvin):
    if n_temps is None:
        n_temps = max(3, int(round((t_hi - t_lo) / 25.0)) + 1)   # levels about 25 K apart
    return _options(lattice_n, x_tol, None, max_refine, z_per_kelvin, t_lo, t_hi, n_temps, t_tol)


def liquidus_point(db, x2, x3, t_lo, t_hi, phases=None, n_temps=None, x_tol=None, t_tol=None,
                   max_refine=None):
    """(T_liquidus in K, primary phase) of one bulk composition."""
    arr, n, keep = _phase_args(phases)
    o = _liquidus_options(t_lo, t_hi, n_temps, None, x_tol, t_tol, max_refine, None)
    T = _ffi.new("double *")
    name = _ffi.new("char[64]")
    rc = _lib.vis3d_liquidus_point(_handle(db), arr, n, o, float(x2), float(x3), T, name, 64)
    if rc != 0:
        raise Vis3DError(f"{_error()} (code {rc})")
    return T[0], _ffi.string(name).decode()


def liquidus_surface(db, t_lo, t_hi, phases=None, n_temps=None, lattice_n=None, x_tol=None,
                     t_tol=None, max_refine=None, z_per_kelvin=None):
    """The liquidus surface: one patch per primary-phase field, field boundaries as lines.
    `temp` holds each vertex's liquidus temperature."""
    arr, n, keep = _phase_args(phases)
    o = _liquidus_options(t_lo, t_hi, n_temps, lattice_n, x_tol, t_tol, max_refine, z_per_kelvin)
    m = _ffi.new("VisMesh *")
    return _take_mesh(m, _lib.vis3d_liquidus_surface(_handle(db), arr, n, o, m), None)


def _take_mesh(m, rc, T):
    if rc != 0:
        raise Vis3DError(f"{_error()} (code {rc})")
    try:
        nv, nt, np_, nl = m.n_vert, m.n_tri, m.n_patch, m.n_line
        return Section(
            T=float(T) if T is not None else float("nan"),
            pos=_copy(m.pos, "float *", nv * 3, np.float32, (nv, 3)),
            comp=_copy(m.comp, "double *", nv * 3, np.float64, (nv, 3)),
            temp=_copy(m.temp, "double *", nv, np.float64),
            tri=_copy(m.tri, "uint32_t *", nt * 3, np.uint32, (nt, 3)),
            patch_start=_copy(m.patch_start, "int32_t *", np_ + 1, np.int32),
            patch_phase=_copy(m.patch_phase, "int32_t *", np_, np.int32),
            line_pos=_copy(m.line_pos, "float *", m.n_line_pts * 3, np.float32, (m.n_line_pts, 3)),
            line_start=_copy(m.line_start, "int32_t *", nl + 1, np.int32),
            labels=[_ffi.string(m.label[k]).decode() for k in range(m.n_label)],
        )
    finally:
        _lib.vis3d_free(m)
