/* The 3D views' own engine instance. The engine is single-threaded by design, so it lives
 * in this worker alone; the page never calls it while the worker does. Requests run one at
 * a time in arrival order, and every reply carries the request's id. Meshes go back as
 * transferred buffers: ownership moves to the page, nothing is copied. */
importScripts('hephaestus.js?v=b96085caacdc', 'vis3d_engine.js');

let M = null, db = 0;
const hulls = new Map();   // readout hulls by temperature, freed when the database changes
let queue = Promise.resolve();

function freeHulls() { for (const h of hulls.values()) h.free(); hulls.clear(); }

async function handle(msg) {
  if (!M) M = await Hephaestus();
  const a = msg.args || {};
  switch (msg.cmd) {
    case 'load':
      freeHulls();
      if (db) { M._mqmqa_db_free(db); db = 0; }
      db = Vis3D.loadDatabase(M, a.text);
      return { ok: true };
    case 'section': case 'liquidus': case 'gibbs': {
      if (!db) throw new Error('no database loaded');
      const t0 = Date.now();
      const mesh = Vis3D[msg.cmd](M, db, a);
      return { ok: true, mesh, seconds: (Date.now() - t0) / 1000, transfer: Vis3D.transferables(mesh) };
    }
    case 'assemblage': {
      if (!db) throw new Error('no database loaded');
      const key = a.T + '|' + (a.phases || []).join(',');
      if (!hulls.has(key)) hulls.set(key, Vis3D.hull(M, db, a));
      const h = hulls.get(key);
      return { ok: true, phases: h.assemblage(a.x2, a.x3), G: h.gibbs(a.x2, a.x3) };
    }
    case 'liquidusPoint':
      if (!db) throw new Error('no database loaded');
      return { ok: true, ...Vis3D.liquidusPoint(M, db, a.x2, a.x3, a) };
    default:
      throw new Error('unknown command ' + msg.cmd);
  }
}

self.onmessage = ev => {
  const msg = ev.data;
  queue = queue.then(async () => {
    try {
      const r = await handle(msg);
      const transfer = r.transfer || [];
      delete r.transfer;
      self.postMessage({ id: msg.id, ...r }, transfer);
    } catch (e) {
      self.postMessage({ id: msg.id, ok: false, error: String(e && e.message || e) });
    }
  });
};
