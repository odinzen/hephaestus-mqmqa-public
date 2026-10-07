/* 3D views over the engine's vis3d functions (src/vis3d.h), for a Web Worker or Node.
 *
 * The engine is single-threaded: one module instance per worker. The build grows its
 * memory (ALLOW_MEMORY_GROWTH), which replaces the heap buffer, so no typed-array view
 * survives an engine call: every read makes a fresh view at the returned address and
 * copies it out with slice(). The mesh is for seeing; numbers a user reads come from
 * fresh engine calls (hull.assemblage, liquidusPoint), never from the mesh.
 */
(function (root) {
  'use strict';

  function withString(M, s, fn) {
    const n = M.lengthBytesUTF8(s) + 1, p = M._malloc(n);
    M.stringToUTF8(s, p, n);
    try { return fn(p); } finally { M._free(p); }
  }

  function engineError(M, what, rc) {
    return new Error(what + ': ' + M.UTF8ToString(M._mqmqa_db_error()) + (rc !== undefined ? ' (code ' + rc + ')' : ''));
  }

  function loadDatabase(M, text) {
    const db = withString(M, text, p => M._mqmqa_db_read_string(p));
    if (!db) throw engineError(M, 'database');
    return db;
  }

  // Copies of every mesh array, taken after the call that filled the mesh.
  function readMesh(M, mesh) {
    const nv = M._vis3d_mesh_n_vert(mesh), nt = M._vis3d_mesh_n_tri(mesh);
    const np = M._vis3d_mesh_n_patch(mesh), nl = M._vis3d_mesh_n_line(mesh);
    const nlp = M._vis3d_mesh_n_line_pts(mesh);
    const f32 = (p, n) => new Float32Array(M.HEAPF32.buffer, p, n).slice();
    const f64 = (p, n) => new Float64Array(M.HEAPF64.buffer, p, n).slice();
    const i32 = (p, n) => new Int32Array(M.HEAP32.buffer, p, n).slice();
    const labels = [];
    for (let k = 0; k < M._vis3d_mesh_n_label(mesh); k++) labels.push(M.UTF8ToString(M._vis3d_mesh_label(mesh, k)));
    const sp = M._vis3d_mesh_scalar(mesh);
    return {
      pos: f32(M._vis3d_mesh_pos(mesh), nv * 3),
      comp: f64(M._vis3d_mesh_comp(mesh), nv * 3),
      temp: f64(M._vis3d_mesh_temp(mesh), nv),
      scalar: sp ? f32(sp, nv) : null,
      tri: new Uint32Array(M.HEAPU32.buffer, M._vis3d_mesh_tri(mesh), nt * 3).slice(),
      patchStart: i32(M._vis3d_mesh_patch_start(mesh), np + 1),
      patchPhase: i32(M._vis3d_mesh_patch_phase(mesh), np),
      linePos: f32(M._vis3d_mesh_line_pos(mesh), nlp * 3),
      lineStart: i32(M._vis3d_mesh_line_start(mesh), nl + 1),
      labels,
    };
  }

  function meshCall(M, what, call) {
    const mesh = M._vis3d_mesh_new();
    if (!mesh) throw new Error(what + ': out of memory');
    try {
      const rc = call(mesh);
      if (rc !== 0) throw engineError(M, what, rc);
      return readMesh(M, mesh);
    } finally {
      M._vis3d_mesh_delete(mesh);   // one arena, one free
    }
  }

  const phaseList = o => (o.phases || []).join(',');

  function section(M, db, o) {
    return withString(M, phaseList(o), pl => meshCall(M, 'section', mesh =>
      M._vis3d_section_js(db, pl, o.T, o.latticeN || 60, o.xTol || 1e-3, o.seed || 0,
                          o.maxRefine || 32, o.zPerKelvin || 1e-3, mesh)));
  }

  function liquidus(M, db, o) {
    const nTemps = o.nTemps || Math.max(3, Math.ceil((o.tHi - o.tLo) / 25) + 1);
    return withString(M, phaseList(o), pl => meshCall(M, 'liquidus surface', mesh =>
      M._vis3d_liquidus_surface_js(db, pl, o.latticeN || 30, nTemps, o.tLo, o.tHi,
                                   o.xTol || 1e-3, o.tTol || 1.0, o.zPerKelvin || 1e-3, mesh)));
  }

  function gibbs(M, db, o) {
    return withString(M, phaseList(o), pl => meshCall(M, 'Gibbs surfaces', mesh =>
      M._vis3d_gibbs_surfaces_js(db, pl, o.T, o.relative ? 1 : 0, o.latticeN || 30,
                                 o.xTol || 1e-3, o.zPerJoule || 1e-5, mesh)));
  }

  // The refined equilibrium at one temperature, for exact readouts; free() when done.
  function hull(M, db, o) {
    const h = withString(M, phaseList(o), pl =>
      M._vis3d_hull_build_js(db, pl, o.T, o.xTol || 1e-3, o.seed || 0, o.maxRefine || 32));
    if (!h) throw engineError(M, 'hull');
    const names = [];
    for (let k = 0; k < M._vis3d_hull_num_phases(h); k++) names.push(M.UTF8ToString(M._vis3d_hull_phase_name(h, k)));
    return {
      T: o.T,
      assemblage(x2, x3) {
        const ph = M._malloc(8 * 4), am = M._malloc(8 * 8), cp = M._malloc(16 * 8);
        try {
          const m = M._vis3d_hull_assemblage(h, x2, x3, ph, am, cp, 8);
          if (m < 0) throw engineError(M, 'assemblage', m);
          const out = [];
          for (let k = 0; k < m; k++)
            out.push({ phase: names[M.getValue(ph + 4 * k, 'i32')], amount: M.getValue(am + 8 * k, 'double'),
                       x2: M.getValue(cp + 16 * k, 'double'), x3: M.getValue(cp + 16 * k + 8, 'double') });
          return out;
        } finally { M._free(ph); M._free(am); M._free(cp); }
      },
      gibbs(x2, x3) { return M._vis3d_hull_gibbs(h, x2, x3); },
      free() { M._vis3d_hull_free(h); },
    };
  }

  function liquidusPoint(M, db, x2, x3, o) {
    const nTemps = o.nTemps || Math.max(3, Math.ceil((o.tHi - o.tLo) / 25) + 1);
    const T = M._malloc(8), name = M._malloc(64);
    try {
      const rc = withString(M, phaseList(o), pl => M._vis3d_liquidus_point_js(
        db, pl, x2, x3, nTemps, o.tLo, o.tHi, o.xTol || 1e-3, o.tTol || 0.1, T, name, 64));
      if (rc !== 0) throw engineError(M, 'liquidus point', rc);
      return { T: M.getValue(T, 'double'), primary: M.UTF8ToString(name) };
    } finally { M._free(T); M._free(name); }
  }

  // The buffers a mesh owns, for postMessage transfer lists.
  function transferables(mesh) {
    return ['pos', 'comp', 'temp', 'scalar', 'tri', 'patchStart', 'patchPhase', 'linePos', 'lineStart']
      .filter(k => mesh[k]).map(k => mesh[k].buffer);
  }

  const api = { loadDatabase, section, liquidus, gibbs, hull, liquidusPoint, readMesh, transferables };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Vis3D = api;
})(typeof self !== 'undefined' ? self : this);
