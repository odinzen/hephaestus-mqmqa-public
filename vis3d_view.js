/* The 3D phase-space card: the liquidus surface over the composition triangle (height is
 * temperature), a temperature plane, and the exact isothermal section drawn in it. The
 * engine runs in its own Web Workers (vis3d_worker.js); this module only draws. The mesh is
 * for seeing: every number the card prints comes from a fresh engine call at that point. */
import * as THREE from 'three';
import { OrbitControls } from './vendor/three/OrbitControls.js';

const card = document.getElementById('vis3dcard');
if (card) init();

function init() {
  const $ = id => document.getElementById(id);
  const wrap = $('v3-wrap'), status = $('v3-status'), read = $('v3-read'), legend = $('v3-legend');
  const sysSel = $('v3-sys'), tIn = $('v3-t'), tOut = $('v3-tval'), startBtn = $('v3-go');
  const clipBox = $('v3-clip');
  const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const tLab = T => (typeof window.tLabel === 'function') ? window.tLabel(T) : T.toFixed(0) + ' K';
  const tSym = () => (typeof window.tSym === 'function') ? window.tSym() : 'K';
  const kToU = K => (typeof window.kToU === 'function') ? window.kToU(K) : K;
  const pretty = s => s.split('+').map(p => p.startsWith('FEO') || p.startsWith('CAO-') ? 'Liquid'
    : p.charAt(0) + p.slice(1).toLowerCase().replace(/_/g, ' ')).join(' + ');

  const SYSTEMS = {
    slag: { dat: './FeO-MgO-SiO2-combined.dat', corners: ['FeO', 'MgO', 'SiO₂'], tLo: 1300, tHi: 3200, tDef: 1873 },
    cas: { dat: './CaO-Al2O3-SiO2.dat', corners: ['CaO', 'AlO₁.₅', 'SiO₂'], tLo: 1300, tHi: 3300, tDef: 1873 },
  };
  const H = 1.0;                                   // prism height for the temperature window
  let sys = SYSTEMS.slag, zpk = H / (sys.tHi - sys.tLo);

  // ---- two workers, each with its own engine and each running one calculation at a time:
  // the surface engine takes the minute-long liquidus, the other answers sections and clicks
  let nextId = 1;
  const pending = new Map(), workers = {};
  function workerFor(which) {
    if (!workers[which]) {
      const w = new Worker('./vis3d_worker.js');
      w.onmessage = ev => {
        const r = ev.data, p = pending.get(r.id);
        if (!p) return;
        pending.delete(r.id);
        r.ok ? p.resolve(r) : p.reject(new Error(r.error));
      };
      w.onerror = e => { for (const p of pending.values()) p.reject(new Error(e.message || 'worker failed')); pending.clear(); };
      workers[which] = w;
    }
    return workers[which];
  }
  function ask(cmd, args, which = 'quick') {
    const w = workerFor(which), id = nextId++;
    return new Promise((resolve, reject) => { pending.set(id, { resolve, reject }); w.postMessage({ id, cmd, args }); });
  }
  const started = () => Object.keys(workers).length > 0;
  // A restart must not wait behind the minute-long runs it replaces: the engine cannot be
  // interrupted mid-call, so the old workers are terminated and fresh ones take over.
  const SUPERSEDED = 'superseded';
  function dropWorkers() {
    for (const k of Object.keys(workers)) { workers[k].terminate(); delete workers[k]; }
    for (const p of pending.values()) p.reject(new Error(SUPERSEDED));
    pending.clear();
  }

  const datText = {};   // fetched once per page load; reload the page to pick up a rebuilt file
  async function loadText(path) {
    if (!(path in datText)) {
      let res;
      try {
        res = await fetch(path);
      } catch (e) {
        throw new Error('could not reach the local web server for ' + path.slice(2) + '; is it still running?');
      }
      if (!res.ok) throw new Error(path.slice(2) + ': server answered ' + res.status);
      datText[path] = await res.text();
    }
    return datText[path];
  }

  // ---- results kept in this browser: a finished mesh is stored under the hash of the
  // database text and of the engine build, so a rebuilt file or engine never reuses an old one
  const cacheDb = new Promise(resolve => {
    try {
      const r = indexedDB.open('hmqmqa-vis3d', 1);
      r.onupgradeneeded = () => r.result.createObjectStore('meshes');
      r.onsuccess = () => resolve(r.result);
      r.onerror = () => resolve(null);
    } catch (e) { resolve(null); }
  });
  async function cacheGet(key) {
    const db = await cacheDb;
    if (!db || !key) return null;
    return new Promise(resolve => {
      try {
        const r = db.transaction('meshes').objectStore('meshes').get(key);
        r.onsuccess = () => resolve(r.result || null);
        r.onerror = () => resolve(null);
      } catch (e) { resolve(null); }
    });
  }
  async function cachePut(key, value) {
    const db = await cacheDb;
    if (!db || !key) return;
    try { db.transaction('meshes', 'readwrite').objectStore('meshes').put(value, key); } catch (e) { /* storage full or off */ }
  }
  async function digest(text) {
    try {
      const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
      return [...new Uint8Array(b)].slice(0, 12).map(x => x.toString(16).padStart(2, '0')).join('');
    } catch (e) { return null; }
  }
  let engineHash = null;
  async function engineVersion() {
    if (engineHash === null) {
      try { engineHash = await digest(await (await fetch('./hephaestus.js')).text()) || ''; } catch (e) { engineHash = ''; }
    }
    return engineHash;
  }
  let datHash = '';
  const cacheKey = (cmd, args) => (engineHash && datHash) ? [engineHash, datHash, cmd, JSON.stringify(args)].join('|') : null;

  // ---- the scene -------------------------------------------------------------------
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  } catch (e) {
    wrap.innerHTML = '<p class="tern-note">This browser cannot draw WebGL, so the 3D view is off. ' +
      'The 2D diagrams above show the same results.</p>';
    startBtn.disabled = true;
    return;
  }
  renderer.localClippingEnabled = true;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  wrap.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(32, 1, 0.01, 50);
  camera.up.set(0, 0, 1);
  camera.position.set(0.1, -1.85, 1.3);             // front, looking up the SiO2 apex
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0.5, 0.32, 0.4);
  controls.update();
  scene.add(new THREE.HemisphereLight(0xffffff, 0x404040, 1.6));
  const sun = new THREE.DirectionalLight(0xffffff, 1.4);
  sun.position.set(1.5, -1, 3);
  scene.add(sun);
  const world = new THREE.Group();                 // engine coordinates, shifted so tLo sits at 0
  scene.add(world);

  const overlay = cls => { const d = document.createElement('div'); d.className = cls; wrap.appendChild(d); return d; };
  const cornerDivs = [0, 1, 2].map(() => overlay('v3-corner'));
  const CORNERS = [new THREE.Vector3(0, 0, 0), new THREE.Vector3(1, 0, 0), new THREE.Vector3(0.5, Math.sqrt(3) / 2, 0)];

  // ---- temperature axis: round values in the page's unit, labelled on whichever vertical
  // edge is furthest left on screen, so the scale stays readable as the view turns
  let tickDivs = [], tickZ = [];
  const axisTitle = overlay('v3-axis-title');
  function axisTicks() {
    const lo = kToU(sys.tLo), hi = kToU(sys.tHi), toK = sys.tLo - lo;   // K and degC differ by an offset
    const step = [100, 200, 250, 400, 500, 1000].find(s => (hi - lo) / s <= 6) || 1000;
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push({ v, z: (v + toK - sys.tLo) * zpk });
    return out;
  }

  let frame = null;
  function drawFrame() {
    if (frame) scene.remove(frame);
    const c = new THREE.Color(css('--muted') || '#888'), pts = [];
    const b = CORNERS, t = CORNERS.map(v => v.clone().setZ(H));
    for (let k = 0; k < 3; k++) {
      pts.push(b[k], b[(k + 1) % 3], t[k], t[(k + 1) % 3], b[k], t[k]);
    }
    // short outward ticks on every vertical edge at each labelled temperature
    const ticks = axisTicks(), mid = new THREE.Vector3(0.5, Math.sqrt(3) / 6, 0);
    for (const v of CORNERS) {
      const out = v.clone().sub(mid).setZ(0).normalize().multiplyScalar(0.03);
      for (const { z } of ticks) pts.push(v.clone().setZ(z), v.clone().add(out).setZ(z));
    }
    frame = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color: c, transparent: true, opacity: 0.6 }));
    scene.add(frame);
    tickDivs.forEach(d => d.remove());
    tickDivs = ticks.map(({ v }) => { const d = overlay('v3-axis'); d.textContent = Math.round(v); return d; });
    tickZ = ticks.map(t => t.z);
    axisTitle.textContent = 'Temperature (' + tSym() + ')';
  }

  function resize() {
    const w = wrap.clientWidth, h = Math.min(Math.round(w * 0.78), 600);
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    render();
  }
  function render() {
    renderer.render(scene, camera);
    const w = renderer.domElement.clientWidth, h = renderer.domElement.clientHeight;
    const screen = v => { const p = v.clone().project(camera); return [(p.x + 1) / 2 * w, (1 - p.y) / 2 * h]; };
    CORNERS.forEach((v, k) => {
      const [x, y] = screen(v);
      cornerDivs[k].style.left = x + 'px';
      cornerDivs[k].style.top = y + 'px';
      cornerDivs[k].textContent = sys.corners[k];
    });
    const edge = CORNERS.reduce((a, v) => screen(v.clone().setZ(H / 2))[0] < screen(a.clone().setZ(H / 2))[0] ? v : a);
    let minX = Infinity, sumY = 0;
    tickDivs.forEach((d, k) => {
      const [x, y] = screen(edge.clone().setZ(tickZ[k]));
      d.style.left = x + 'px'; d.style.top = y + 'px';
      minX = Math.min(minX, x); sumY += y;
    });
    // the title sits left of the leftmost tick label, so a slanted, foreshortened edge seen
    // from above cannot push the numbers under it
    pins.forEach(p => {
      const [x, y] = screen(world.localToWorld(p.pos.clone()));
      p.label.style.left = x + 'px'; p.label.style.top = y + 'px';
    });
    axisTitle.style.left = minX + 'px';
    axisTitle.style.top = (tickDivs.length ? sumY / tickDivs.length : screen(edge.clone().setZ(H / 2))[1]) + 'px';
  }
  controls.addEventListener('change', render);
  new ResizeObserver(resize).observe(wrap);
  if (typeof window.onTUnit === 'function') window.onTUnit(() => { tOut.textContent = tLab(+tIn.value); drawFrame(); render(); });

  // ---- colours: one per phase, a field of several phases blends its members ----------
  const PALETTE = ['#e07b39', '#3fa66b', '#b35fc6', '#d9b23a', '#39a9b5', '#d0587e', '#7f8c3a',
                   '#8a6d52', '#6f7fd6', '#c96f4a', '#4f9e9e', '#5b8def'];
  const LIQ_COLOUR = '#c9d3dc';
  const phaseColour = new Map();
  const isLiquid = p => p.includes('LIQUID');
  function colourOfPhase(p) {
    if (isLiquid(p)) return new THREE.Color(LIQ_COLOUR);
    if (!phaseColour.has(p)) phaseColour.set(p, PALETTE[phaseColour.size % PALETTE.length]);
    return new THREE.Color(phaseColour.get(p));
  }
  const colours = { clear() { phaseColour.clear(); } };
  function colourOf(lab) {
    const parts = lab.split('+'), c = new THREE.Color(0, 0, 0);
    parts.forEach(p => { const k = colourOfPhase(p); c.r += k.r / parts.length; c.g += k.g / parts.length; c.b += k.b / parts.length; });
    if (parts.length === 3) c.multiplyScalar(0.8);        // three-phase fields a shade darker
    return '#' + c.getHexString();
  }
  const hidden = new Set();

  // ---- meshes from the worker -------------------------------------------------------
  const clipPlane = new THREE.Plane(new THREE.Vector3(0, 0, -1), 0);
  let liquidus = null, section = null, plane = null;

  function meshFrom(r, opacity, clip) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(r.pos, 3));
    g.setIndex(new THREE.BufferAttribute(r.tri, 1));
    // one draw group per phase field; seams are duplicated per patch in the engine, so the
    // normals never average across a boundary and the crease stays sharp
    const mats = [];
    for (let p = 0; p < r.patchPhase.length; p++) {
      g.addGroup(r.patchStart[p] * 3, (r.patchStart[p + 1] - r.patchStart[p]) * 3, p);
      const lab = r.labels[r.patchPhase[p]];
      const m = new THREE.MeshStandardMaterial({ color: colourOf(lab), side: THREE.DoubleSide,
        transparent: opacity < 1, opacity, roughness: 0.75, metalness: 0,
        clippingPlanes: clip ? [clipPlane] : [] });
      m.userData.label = lab;
      m.visible = !hidden.has(lab);
      mats.push(m);
    }
    g.computeVertexNormals();
    const mesh = new THREE.Mesh(g, mats);
    const lines = new THREE.LineSegments(
      new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(r.linePos, 3)),
      new THREE.LineBasicMaterial({ color: new THREE.Color(css('--ink') || '#222'), clippingPlanes: clip ? [clipPlane] : [] }));
    const grp = new THREE.Group();
    grp.add(mesh, lines);
    grp.userData = { mesh, result: r };
    return grp;
  }

  function setLegend() {
    legend.innerHTML = '';
    const labs = new Set();
    [liquidus, section].forEach(o => o && o.userData.result.labels.forEach(l => labs.add(l)));
    for (const lab of labs) {
      const s = document.createElement('span');
      s.className = 'v3-chip' + (hidden.has(lab) ? ' off' : '');
      s.innerHTML = '<i style="background:' + colourOf(lab) + '"></i>' + pretty(lab);
      s.title = 'Show or hide this field';
      s.onclick = () => {
        hidden.has(lab) ? hidden.delete(lab) : hidden.add(lab);
        [liquidus, section].forEach(o => o && o.userData.mesh.material.forEach(m => { if (m.userData.label === lab) m.visible = !hidden.has(lab); }));
        setLegend(); render();
      };
      legend.appendChild(s);
    }
  }

  function setPlane(T) {
    const z = (T - sys.tLo) * zpk;
    clipPlane.constant = z;
    if (!plane) {
      const g = new THREE.BufferGeometry().setFromPoints(CORNERS);
      g.setIndex([0, 1, 2]);
      plane = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ color: new THREE.Color(css('--brand') || '#2a9d4f'),
        transparent: true, opacity: 0.18, side: THREE.DoubleSide, depthWrite: false }));
      scene.add(plane);
    }
    plane.position.z = z;
    render();
  }

  // ---- saved points: every click is numbered on the plot and listed under the card, the
  // same comparison list the 2D calculators keep; its row fills in when the engine answers
  const histEl = $('v3-hist'), pins = [];
  function renderPins() {
    if (typeof window.renderCalcHist === 'function') window.renderCalcHist(histEl, pins.map(p => p.txt), clearPins);
  }
  function addPin(q) {
    const marker = new THREE.Mesh(new THREE.SphereGeometry(0.018, 16, 12),
      new THREE.MeshBasicMaterial({ color: new THREE.Color(css('--pointer') || '#ff3b3b'), depthTest: false }));
    marker.renderOrder = 10;
    marker.position.copy(q.pos);
    world.add(marker);
    const pin = { n: pins.length + 1, q, pos: q.pos.clone(), marker, label: overlay('v3-pin'), txt: comp(q) + '  |  queued' };
    pin.label.textContent = pin.n;
    pins.push(pin);
    renderPins(); render();
    return pin;
  }
  function clearPins() {
    pins.forEach(p => { world.remove(p.marker); p.marker.geometry.dispose(); p.marker.material.dispose(); p.label.remove(); });
    pins.length = 0;
    clicks.length = 0;
    renderPins(); render(); showWaiting();
  }

  // ---- the queue, shown in the card: each engine line says what it is running and what waits.
  // Waiting requests of one kind replace each other, so only the newest slider position and the
  // newest click are ever computed.
  let generation = 0, sectionT = NaN, sysKey = sysSel.value;
  const lane = { surface: { now: '', next: '' }, quick: { now: '', next: '' } };
  // One line: running work first, then what is queued. A narrow window cuts it with an
  // ellipsis, and the full text is on hover.
  function renderStatus() {
    const bits = [lane.surface, lane.quick].map(l => l.now + (l.next ? ', ' + l.next : '')).filter(Boolean);
    status.textContent = status.title = bits.join('  ·  ');
  }
  function say(which, text) { lane[which].now = text; renderStatus(); }

  // The engine reports nothing mid-call, so the countdown is how long the same job took last
  // time in this browser; the first run uses typical times.
  const EST_DEFAULT = { section: 15, point: 15, coarse: 180, refined: 600 };
  const estKey = job => 'v3-est:' + sysKey + ':' + job;
  function estimate(job) {
    try { const v = +localStorage.getItem(estKey(job)); if (v > 0) return v; } catch (e) { /* storage off */ }
    return EST_DEFAULT[job];
  }
  function remember(job, seconds) {
    try { localStorage.setItem(estKey(job), seconds.toFixed(1)); } catch (e) { /* storage off */ }
  }
  const fmt = s => s < 90 ? Math.max(1, Math.round(s)) + ' s' : Math.round(s / 60) + ' min';
  const timers = {};
  function sayTimed(which, text, job) {
    clearInterval(timers[which]);
    const est = estimate(job), t0 = Date.now();
    const tick = () => {
      const run = (Date.now() - t0) / 1000, left = est - run;
      say(which, text + ': ' + (left > 1 ? 'about ' + fmt(left) + ' left' : fmt(run) + ', longer than usual'));
    };
    tick();
    timers[which] = setInterval(tick, 1000);
  }
  function sayDone(which, text) { clearInterval(timers[which]); say(which, text); }
  function stopTimers() { Object.values(timers).forEach(clearInterval); }

  // -- the sections-and-points engine: one job at a time. Every click is recorded, so clicks
  // queue in order; slider moves keep only the newest position. Clicks go ahead of a section.
  const want = { section: null };
  const clicks = [];
  let quickLoop = 0;
  const comp = q => sys.corners.map((c, k) => c + ' ' + [q.x1, q.x2, q.x3][k].toFixed(3)).join(', ');
  function showWaiting() {
    const w = [];
    if (clicks.length) w.push(clicks.length + (clicks.length > 1 ? ' clicks' : ' click'));
    if (want.section !== null) w.push('section at ' + tLab(want.section));
    lane.quick.next = w.length ? 'queued: ' + w.join(', then ') : '';
    renderStatus();
  }
  function wantQuick(kind, payload) {
    if (kind === 'point') clicks.push(payload); else want[kind] = payload;
    showWaiting();
    return pumpQuick();
  }
  async function pumpQuick() {
    if (quickLoop === generation) return;            // this start's loop is already draining
    const gen = quickLoop = generation;
    try {
      while (gen === generation) {
        const kind = clicks.length ? 'point' : want.section !== null ? 'section' : null;
        if (!kind) break;
        const payload = kind === 'point' ? clicks.shift() : want.section;
        if (kind === 'section') want.section = null;
        showWaiting();
        try {
          await (kind === 'section' ? computeSection(payload, gen) : computePoint(payload, gen));
        } catch (e) {
          if (e.message !== SUPERSEDED && gen === generation) sayDone('quick', 'Stopped: ' + e.message);
        }
      }
    } finally {
      if (quickLoop === gen) quickLoop = 0;
    }
  }

  let lastSectionNote = '';
  async function computeSection(T, gen) {
    const args = { T, latticeN: 40, zPerKelvin: zpk };
    let r = await cacheGet(cacheKey('section', args)), cached = !!r;
    if (!r) {
      sayTimed('quick', 'Section at ' + tLab(T), 'section');
      r = await ask('section', args);
      if (gen !== generation) return;
      remember('section', r.seconds);
      cachePut(cacheKey('section', args), r);
    }
    if (gen !== generation) return;
    if (section) world.remove(section);
    section = meshFrom(r.mesh, 0.97, false);
    sectionT = T;
    world.add(section);
    setLegend(); render();
    lastSectionNote = 'Section at ' + tLab(T) + (cached ? ' ready (saved)' : ' ready (' + fmt(r.seconds) + ')');
    sayDone('quick', lastSectionNote);
  }

  async function computePoint(pin, gen) {
    const q = pin.q;
    sayTimed('quick', 'Reading point ' + pin.n, 'point');
    const t0 = Date.now(), lines = [comp(q)];
    try {
      if (!q.onSection) {
        const lp = await ask('liquidusPoint', { x2: q.x2, x3: q.x3, tLo: sys.tLo, tHi: sys.tHi, tTol: 0.1 });
        if (gen !== generation) return;
        lines.push('liquidus ' + tLab(lp.T) + ', first to crystallize: ' + pretty(lp.primary));
      }
      const T = isNaN(sectionT) ? +tIn.value : sectionT;   /* the temperature drawn in the plane */
      const a = await ask('assemblage', { T, x2: q.x2, x3: q.x3 });
      if (gen !== generation) return;
      lines.push('at ' + tLab(T) + ': ' + a.phases.map(p => pretty(p.phase) + ' ' + (100 * p.amount).toFixed(1) + '%').join(' + '));
    } catch (e) {
      if (e.message !== SUPERSEDED) { pin.txt = comp(q) + '  |  ' + e.message; renderPins(); }
      throw e;
    }
    pin.txt = lines.join('  |  ');
    read.textContent = 'Point ' + pin.n + ': ' + pin.txt;
    renderPins();
    remember('point', (Date.now() - t0) / 1000);
    sayDone('quick', lastSectionNote || 'Point read');
  }

  // -- the surface engine: coarse, then refined; the finest result already saved is shown first
  // and only the steps beyond it are computed
  async function computeLiquidus(gen) {
    const steps = [{ latticeN: 12, xTol: 5e-3, label: 'coarse' }, { latticeN: 24, xTol: 2e-3, label: 'refined' }];
    const argsOf = s => ({ tLo: sys.tLo, tHi: sys.tHi, nTemps: Math.ceil((sys.tHi - sys.tLo) / 50) + 1,
      latticeN: s.latticeN, xTol: s.xTol, zPerKelvin: zpk });
    const show = (r, s, cached) => {
      if (liquidus) world.remove(liquidus);
      liquidus = meshFrom(r.mesh, 0.9, clipBox.checked);
      world.add(liquidus);
      setLegend(); render();
      return 'Surface ready, ' + s.label + (cached ? ' (saved)' : ' (' + fmt(r.seconds) + ')');
    };
    let first = 0;
    for (let i = steps.length - 1; i >= 0; i--) {
      const hit = await cacheGet(cacheKey('liquidus', argsOf(steps[i])));
      if (gen !== generation) return;
      if (hit) { sayDone('surface', show(hit, steps[i], true)); first = i + 1; break; }
    }
    for (let i = first; i < steps.length; i++) {
      const s = steps[i];
      lane.surface.next = steps.slice(i + 1).map(n => n.label + ' next (about ' + fmt(estimate(n.label)) + ')').join(', ');
      sayTimed('surface', 'Surface step ' + (i + 1) + ' of ' + steps.length, s.label);
      const r = await ask('liquidus', argsOf(s), 'slow');
      if (gen !== generation) return;
      remember(s.label, r.seconds);
      cachePut(cacheKey('liquidus', argsOf(s)), r);
      lane.surface.next = '';
      sayDone('surface', show(r, s, false));
    }
  }

  async function start() {
    const gen = ++generation;
    dropWorkers();
    stopTimers();
    want.section = null; clearPins();
    sysKey = sysSel.value;
    sys = SYSTEMS[sysKey];
    zpk = H / (sys.tHi - sys.tLo);
    world.position.z = -sys.tLo * zpk;
    tIn.min = sys.tLo; tIn.max = sys.tHi; tIn.value = sys.tDef; tOut.textContent = tLab(sys.tDef);
    [liquidus, section].forEach(o => o && world.remove(o));
    liquidus = section = null;
    colours.clear(); hidden.clear();
    lane.surface = { now: '', next: '' }; lane.quick = { now: '', next: '' }; lastSectionNote = ''; sectionT = NaN;
    drawFrame(); setPlane(sys.tDef); setLegend();
    read.textContent = '';
    try {
      say('quick', 'Loading the database…');
      const text = await loadText(sys.dat);
      [datHash] = await Promise.all([digest(text), engineVersion()]);
      await Promise.all([ask('load', { text }, 'quick'), ask('load', { text }, 'slow')]);
      if (gen !== generation) return;
      await Promise.all([wantQuick('section', sys.tDef), computeLiquidus(gen)]);
    } catch (e) {
      if (gen === generation) { stopTimers(); lane.quick = { now: '', next: '' }; say('surface', 'Stopped: ' + e.message); }
    }
  }

  startBtn.addEventListener('click', start);
  sysSel.addEventListener('change', () => { if (started()) start(); });
  tIn.addEventListener('input', () => { tOut.textContent = tLab(+tIn.value); setPlane(+tIn.value); });
  tIn.addEventListener('change', () => { if (started()) wantQuick('section', +tIn.value); });
  clipBox.addEventListener('change', () => {
    renderer.clippingPlanes = [];
    if (liquidus) liquidus.children.forEach(obj => [].concat(obj.material).forEach(m => {
      m.clippingPlanes = clipBox.checked ? [clipPlane] : []; m.needsUpdate = true; }));
    render();
  });

  // ---- reading a point: hover shows the mesh, click asks the engine -------------------
  const ray = new THREE.Raycaster(), ptr = new THREE.Vector2();
  function hit(ev) {
    const r = renderer.domElement.getBoundingClientRect();
    ptr.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ptr, camera);
    ray.params.Line.threshold = 0;
    const targets = [section, liquidus].filter(Boolean).map(o => o.userData.mesh);
    const hits = ray.intersectObjects(targets, false).filter(h => {
      const m = Array.isArray(h.object.material) ? h.object.material[h.face.materialIndex] : h.object.material;
      if (!m.visible) return false;
      const planes = m.clippingPlanes || [];
      return planes.every(p => p.distanceToPoint(h.point) >= 0);
    });
    if (!hits.length) return null;
    const h = hits[0], p = world.worldToLocal(h.point.clone());
    const x3 = p.y / (Math.sqrt(3) / 2), x2 = p.x - x3 / 2, T = p.z / zpk;
    const onSection = section && h.object === section.userData.mesh;
    return { x2, x3, x1: 1 - x2 - x3, T: onSection ? sectionT : T, onSection, pos: p };
  }
  let dragged = false;
  renderer.domElement.addEventListener('pointerdown', () => { dragged = false; });
  renderer.domElement.addEventListener('pointermove', ev => {
    if (ev.buttons) { dragged = true; return; }
    const q = hit(ev);
    if (q) read.textContent = comp(q) + (q.onSection ? '' : '  |  surface ' + tLab(q.T) + ' (from the mesh; click for the engine)');
  });
  renderer.domElement.addEventListener('click', ev => {
    if (dragged || !started()) return;
    const q = hit(ev);
    if (!q) return;
    const pin = addPin(q);
    read.textContent = 'Point ' + pin.n + ' queued for the engine: ' + comp(q);
    wantQuick('point', pin);
  });

  drawFrame(); setPlane(sys.tDef); resize();
}
