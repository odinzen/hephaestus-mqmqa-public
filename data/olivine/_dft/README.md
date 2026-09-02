# Olivine Fe-Mg mixing: DFT control (proof of method)

Purpose: establish, on the one join with real calorimetry, that **DFT with the olivine control
reproduces the measured mixing enthalpy** where foundation MLIPs did not (see
`../_mlip/VALIDATION.md`, a 22 kJ inter-model spread). If DFT hits Wood & Kleppa 1981 here, the
DFT-with-control protocol is the validated upgrade path for any join whose excess actually moves
a deliverable - not these two (spinel/cpx were shown immaterial and are shipped ideal), but the
next one that matters.

## Target datum

Wood & Kleppa 1981 solution calorimetry, forsterite-fayalite: RK L0 = 12552, L1 = 4184 J/mol,
i.e. H_mix = +3138 J/mol formula at x_Fe = 0.5 (positive, slightly unfavourable).

## Method

- **Engine:** Quantum ESPRESSO 6.7 (`pw.x`), run locally in WSL on the 14-core i7-1370P
  (mpirun, 14 ranks). Not Sol - this is a bounded local job by design.
- **Cell:** the same 28-atom forsterite framework as the MLIP runs (COD 1572966, Mg8Si4O16 =
  4 formula units). x=0 forsterite, x=1 fayalite (all M -> Fe), x=0.5 one ordering (4 of 8
  M-sites -> Fe). Every structure uses the **same k-mesh and cutoffs**, so basis and k-point
  errors cancel in the mixing-enthalpy difference - the same difference trick used for the MLIPs.
- **Pseudopotentials:** pslibrary 1.0.0 PBE PAW, one self-consistent set for all four elements
  (`Fe.pbe-spn-kjpaw`, `Mg.pbe-spnl-kjpaw`, `Si.pbe-n-kjpaw`, `O.pbe-n-kjpaw`), in `pseudo/`.
- **Functional / spin:** PBE, spin-polarized (nspin=2), Fe initialized high-spin FM
  (starting_magnetization 0.5). PBE first, deliberately no +U knob for the first proof.
- **Numerics:** ecutwfc 60 Ry, ecutrho 480 Ry, Gaussian smearing 0.01 Ry, k-mesh 2x1x2,
  conv_thr 1e-7, full cell+ion relaxation (`vc-relax`, BFGS).
- **Mixing enthalpy:** H_mix(0.5) = [E(x50) - 1/2 E(fa) - 1/2 E(fo)] / 4 formulas, Ry -> J/mol.

## Reproduce

    python gen_inputs.py                       # writes runs/*/pw.in (needs ASE)
    wsl bash run_all.sh                         # runs the three vc-relax jobs
    python analyze.py                           # H_mix vs Wood-Kleppa

## Scope and honest limits

- One ordering at x=0.5 (not a full configurational average) and moderate cutoffs/k: this is a
  proof of method, not a production excess. The difference-cancellation makes H_mix far better
  converged than the absolute energies, but a production value would add orderings, raise
  cutoffs to the SSSP-recommended Fe values, and test +U / r2SCAN sensitivity.
- PBE (no +U): Fe2+ oxide energetics carry a known functional error; for the Fe<->Mg exchange
  (both octahedral) much cancels in the difference. +U and r2SCAN are the documented next checks
  if the PBE number misses Wood-Kleppa.
- FM alignment (real fayalite is AFM below 65 K, paramagnetic at the calorimetry T); consistent
  collinear treatment across fa and the mixed cell is the pragmatic choice for the difference.

## Result (2026-08-28)

All three converged (fayalite 26 BFGS steps, ~10 h; magnetism correct: fayalite 32 muB =
4 muB/Fe high-spin FM, x=0.5 16 muB). Per formula:

| x_Fe | DFT PBE H_mix | Wood-Kleppa |
|------|---------------|-------------|
| 0.5  | **-4742 J/mol** | +3138 J/mol |

E(fo) = -1988.20969, E(fa) = -3488.70871, E(x50) = -2738.47365 Ry.

**Plain PBE gets the sign wrong** and misses by ~7.9 kJ - worse than the olivine-validated
MLIPs (SevenNet +3168, ORB +2092). The proof-of-method conclusion is the honest one: naive DFT
does NOT automatically beat a good foundation MLIP. The two caveats both bit - bare PBE
mis-describes Fe2+ 3d energetics (olivine work needs PBE+U or r2SCAN/hybrid), and a single
Fe4Mg4 ordering carries ordering energy rather than the measured random-mixing enthalpy (needs
SQS / multi-ordering averaging). A DFT campaign that actually arbitrates these excesses requires
+U or meta-GGA plus configurational averaging; each functional is ~an overnight run at this cell
size. Until then, SevenNet remains the best single tool, which is why spinel/cpx ship ideal.

## Follow-up: PBE+U and SQS (2026-09-01)

The two caveats were tested directly.

- **PBE+U (U = 4 eV on Fe 3d) fixes the sign.** A single x=0.5 ordering went from -4742 (bare PBE)
  to **+16100** J/mol - correct sign, but ~5x over the measured +3138, because that one clustered
  ordering carries ordering energy, not random-mixing enthalpy.
- **Ordering bias confirmed.** Alternate SevenNet-relaxed orderings, re-relaxed at DFT+U, sat far
  lower (~+800 J/mol), straddling the measurement instead of sitting 5x high. So the overshoot was
  the single-ordering artifact, exactly as expected.
- **SQS attempt.** An 8-site special quasirandom structure (nearest and next-nearest shells matched
  to random) was built and run at U=4 to get one clean random-mixing value. The from-scratch SCF
  plateaued at ~1e-5 and never reached 1e-7 - the known magnetic-oxide + LDA+U convergence
  pathology (eigenvalues not fully converged capping the accuracy). It was not pushed further.

**Conclusion.** DFT+U with proper random mixing gets the sign and the order of magnitude right, but
pinning the exact value needs a tuned U (a U scan), an SQS, and configurational averaging - a
multi-overnight campaign per functional. SevenNet reproduces +3138 out of the box, so it is the
reference model for the solid-solution excesses. The MLIP excesses for the ship-ideal joins
(spinel, clinopyroxene, orthopyroxene) are in `../../solidsolutions/RESULTS.md`.
