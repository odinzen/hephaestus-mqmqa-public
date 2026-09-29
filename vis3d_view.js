/* The 3D phase-space card: the liquidus surface over the composition triangle (height is
 * temperature), a temperature plane, and the exact isothermal section drawn in it. The
 * engine runs in its own Web Worker (vis3d_worker.js); this module only draws. The mesh is
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
  const pretty = s => s.split('+').map(p => p.startsWith('FEO') || p.startsWith('CAO-') ? 'Liquid'
    : p.charAt(0) + p.slice(1).toLowerCase().replace(/_/g, ' ')).join(' + ');

  const SYSTEMS = {
    slag: { dat: './FeO-MgO-SiO2-combined.dat', corners: ['FeO', 'MgO', 'SiO\u2082'], tLo: 1300, tHi: 3200, tDef: 1873 },
    cas: { dat: './CaO-Al2O3-SiO2.dat', corners: ['CaO', 'AlO\u2081.\u2085', 'SiO\u2082'], tLo: 1300, tHi: 3300, tDef: 1873 },
  };
  const H = 1.0;                                   // prism height for the temperature window
  let sys = SYSTEMS.slag, zpk = H / (sys.tHi - sys.tLo);

  // ---- two workers, each with its own engine: the engine is single-threaded, so the
  // minute-long liquidus runs in one while sections and point readouts answer from the other
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

  const cornerDivs = [0, 1, 2].map(() => {
    const d = document.createElement('div');
    d.className = 'v3-corner';
    wrap.appendChild(d);
    return d;
  });
  const CORNERS = [new THREE.Vector3(0, 0, 0), new THREE.Vector3(1, 0, 0), new THREE.Vector3(0.5, Math.sqrt(3) / 2, 0)];

  let frame = null;
  function drawFrame() {
    if (frame) scene.remove(frame);
    const c = new THREE.Color(css('--muted') || '#888'), pts = [];
    const b = CORNERS, t = CORNERS.map(v => v.clone().setZ(H));
    for (let k = 0; k < 3; k++) {
      pts.push(b[k], b[(k + 1) % 3], t[k], t[(k + 1) % 3], b[k], t[k]);
    }
    frame = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color: c, transparent: true, opacity: 0.6 }));
    scene.add(frame);
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
    CORNERS.forEach((v, k) => {
      const p = v.clone().project(camera);
      cornerDivs[k].style.left = ((p.x + 1) / 2 * w) + 'px';
      cornerDivs[k].style.top = ((1 - p.y) / 2 * h) + 'px';
      cornerDivs[k].textContent = sys.corners[k];
    });
  }
  controls.addEventListener('change', render);
  new ResizeObserver(resize).observe(wrap);

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

  // ---- the work: the section and the liquidus run side by side, each in its worker ---
  let generation = 0, sectionT = NaN;
  const parts = { section: '', liquidus: '' };
  function say(which, text) {
    parts[which] = text;
    status.textContent = [parts.section, parts.liquidus].filter(Boolean).join('  \u00b7  ');
  }
  async function computeSection(T, gen) {
    say('section', 'Computing the exact section at ' + tLab(T) + '\u2026');
    const r = await ask('section', { T, latticeN: 40, zPerKelvin: zpk });
    if (gen !== generation) return;
    if (section) world.remove(section);
    section = meshFrom(r.mesh, 0.97, false);
    sectionT = T;
    world.add(section);
    setLegend(); render();
    say('section', 'Section at ' + tLab(T) + ' in ' + r.seconds.toFixed(1) + ' s');
  }

  async function computeLiquidus(gen) {
    const steps = [{ latticeN: 12, xTol: 5e-3, label: 'coarse' }, { latticeN: 24, xTol: 2e-3, label: 'refined' }];
    for (const s of steps) {
      say('liquidus', 'computing the ' + s.label + ' liquidus surface (' + s.latticeN +
        ' divisions), about a minute; you can rotate and read points meanwhile\u2026');
      const r = await ask('liquidus', { tLo: sys.tLo, tHi: sys.tHi, nTemps: Math.round((sys.tHi - sys.tLo) / 50) + 1,
        latticeN: s.latticeN, xTol: s.xTol, zPerKelvin: zpk }, 'slow');
      if (gen !== generation) return;
      if (liquidus) world.remove(liquidus);
      liquidus = meshFrom(r.mesh, 0.9, clipBox.checked);
      world.add(liquidus);
      setLegend(); render();
      say('liquidus', 'liquidus surface (' + s.label + ', ' + s.latticeN + ' divisions) in ' + r.seconds.toFixed(0) + ' s');
    }
  }

  async function start() {
    const gen = ++generation;
    sys = SYSTEMS[sysSel.value];
    zpk = H / (sys.tHi - sys.tLo);
    world.position.z = -sys.tLo * zpk;
    tIn.min = sys.tLo; tIn.max = sys.tHi; tIn.value = sys.tDef; tOut.textContent = tLab(sys.tDef);
    [liquidus, section].forEach(o => o && world.remove(o));
    liquidus = section = null;
    colours.clear(); hidden.clear();
    parts.section = parts.liquidus = ''; sectionT = NaN;
    drawFrame(); setPlane(sys.tDef); setLegend();
    read.textContent = '';
    try {
      say('section', 'Loading the database into the engine\u2026');
      const text = await (await fetch(sys.dat)).text();
      await Promise.all([ask('load', { text }, 'quick'), ask('load', { text }, 'slow')]);
      await Promise.all([computeSection(sys.tDef, gen), computeLiquidus(gen)]);
    } catch (e) {
      if (gen === generation) say('liquidus', 'the engine stopped: ' + e.message);
    }
  }

  startBtn.addEventListener('click', start);
  sysSel.addEventListener('change', () => { if (started()) start(); });
  tIn.addEventListener('input', () => { tOut.textContent = tLab(+tIn.value); setPlane(+tIn.value); });
  tIn.addEventListener('change', () => {
    if (!started()) return;
    computeSection(+tIn.value, generation).catch(e => say('section', 'The engine stopped: ' + e.message));
  });
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
    return { x2, x3, x1: 1 - x2 - x3, T: onSection ? sectionT : T, onSection };
  }
  const comp = q => sys.corners.map((c, k) => c + ' ' + [q.x1, q.x2, q.x3][k].toFixed(3)).join(', ');
  let dragged = false;
  renderer.domElement.addEventListener('pointerdown', () => { dragged = false; });
  renderer.domElement.addEventListener('pointermove', ev => {
    if (ev.buttons) { dragged = true; return; }
    const q = hit(ev);
    if (q) read.textContent = comp(q) + (q.onSection ? '' : '  |  surface ' + tLab(q.T) + ' (from the mesh; click for the engine)');
  });
  renderer.domElement.addEventListener('click', async ev => {
    if (dragged || !started()) return;
    const q = hit(ev);
    if (!q) return;
    read.textContent = comp(q) + '  |  asking the engine\u2026';
    try {
      const lines = [comp(q)];
      if (!q.onSection) {
        const lp = await ask('liquidusPoint', { x2: q.x2, x3: q.x3, tLo: sys.tLo, tHi: sys.tHi, tTol: 0.1 });
        lines.push('liquidus ' + tLab(lp.T) + ', first to crystallize: ' + pretty(lp.primary));
      }
      const T = isNaN(sectionT) ? +tIn.value : sectionT;   /* the temperature drawn in the plane */
      const a = await ask('assemblage', { T, x2: q.x2, x3: q.x3 });
      lines.push('at ' + tLab(T) + ': ' + a.phases.map(p => pretty(p.phase) + ' ' + (100 * p.amount).toFixed(1) + '%').join(' + '));
      read.textContent = lines.join('  |  ');
    } catch (e) {
      read.textContent = comp(q) + '  |  ' + e.message;
    }
  });

  drawFrame(); setPlane(sys.tDef); resize();
}
