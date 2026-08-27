# MLIP-for-solids validation against measured olivine calorimetry

This is the honesty check on the MLIP mixing energies used for the CEF solid solutions
(clinopyroxene, spinel). Those excesses are computed from a foundation MLIP because no open
Fe-Mg mixing calorimetry exists for those joins. Olivine is the control: its Fe-Mg mixing
enthalpy **is** measured, so running the identical method on olivine and comparing to
experiment bounds the systematic error of the whole approach.

## The control datum

Wood & Kleppa 1981 (solution calorimetry), forsterite-fayalite:

    Hxs = X_Fe * X_Mg * (2000 + 2000 * X_Fe) cal/mol formula
        = RK  L0 = 12552, L1 = 4184 J/mol   (positive - mixing is slightly unfavourable)

H_mix = +1961 / +3138 / +2746 J/mol at x_Fe = 0.25 / 0.50 / 0.75. Positive and of order a
few kJ - the opposite sign from the spinel result, which makes it a strong, independent test.

## Method (identical to spinel and clinopyroxene)

Forsterite cell (COD 1572966, 28 atoms, 8 M-sites). Mg->Fe orderings on the M-sites are
relaxed (cell + positions, 0 GPa) and averaged; H_mix(x) is taken per (Mg,Fe)2SiO4 formula
as a difference against the two endmembers, so any constant MLIP offset cancels. Two
foundation models were run through the same script (`mlip_mix.py`, `mlip_mix_orb.py`).

## Result

Six foundation MLIPs were run through the identical script. Measured RK: L0 = 12552, L1 = 4184
(H_mix = +3138 J/mol at x = 0.5), ranked by RMS against it:

| model | RK L0 | H_mix @ 0.5 | RMS vs measured | verdict |
|-------|-------|-------------|-----------------|---------|
| **SevenNet-0** (MPtrj) | 9746 | +3168 | **861** | reproduces the measurement |
| **TensorNet** (MatPES-PBE) | 16845 | +4994 | 1134 | right sign, slight over |
| **ORB v2** | 6338 | +2092 | 1398 | right sign, under |
| MACE-MPA-0 | 1170 | +1013 | 2563 | weak, spurious -L1 |
| MatterSim v1.0.0-5M | -136 | +71 | 2675 | ideal-biased |
| CHGNet 0.4.2 | -14308 | -2888 | 5693 | wrong sign |
| M3GNet (MatPES-PBE) | 58804 | +15503 | 9907 | ~5x over |

MACE runs in a separate `mlip-mace` conda env: its cached checkpoints fail to unpickle under
this env's e3nn 0.6.0 (shared with MatterSim, so not downgradable in place). The `mlip-mace`
clone pins e3nn 0.4.4, under which MACE-MPA-0 loads. It landed mid-pack (RMS 2563), not with
the three good models.

The six models **span both signs and an order of magnitude** for a join measured at +3 kJ
(from -2888 to +15503 at x = 0.5). Foundation MLIPs disagree enormously on Fe-Mg cation mixing;
model choice dominates the answer. **Three models get the sign right and bracket the
measurement** - ORB under, SevenNet almost exact, TensorNet slightly over - while the other
three fail in three different directions. **SevenNet-0 is the model of record** (RMS 861,
essentially reproducing Wood & Kleppa); ORB and TensorNet are the corroborating bracket.
MatterSim (ideal-biased), CHGNet (wrong sign) and M3GNet (5x over) are excluded.

The configurational (statistical) noise is small (per-ordering spread <= a few meV/formula);
the error that matters is systematic model bias, and it is large and model-dependent.

## Does passing olivine certify a model on other joins? No.

The same four viable models (the three good + MatterSim) were run on the two joins the
database actually needs, where no calorimetry exists to check them:

**Spinel MgAl2O4-FeAl2O4, A-site Fe-Mg (RK L0, L1 J/mol per formula):**

| model | L0 | L1 | sign |
|-------|----|----|------|
| SevenNet-0 | -14915 | +3085 | negative |
| TensorNet | -9949 | +5761 | negative |
| MatterSim | -3411 | -2373 | negative |
| ORB v2 | +6953 | +6093 | **positive** |

The two best olivine models both say **strongly negative**; ORB (3rd best on olivine) flips
**positive**. Spread ~22 kJ on L0. Passing the olivine control did **not** make the models
agree here - it did not even fix the sign. The magnitude is essentially unconstrained.

**Clinopyroxene diopside-hedenbergite, M1 Fe-Mg:**

| model | L0 | L1 |
|-------|----|----|
| SevenNet-0 | +1259 | -10121 |
| MatterSim | -576 | ~0 |
| TensorNet | -1843 | -6913 |
| ORB v2 | -5440 | +199 |

Here the models **cluster near zero** (L0 spread -5.4 to +1.3 kJ) - di-hed is **near-ideal**,
which is the robust conclusion regardless of model. The wild, inconsistent L1 values show the
composition dependence is not resolved by any model.

## Resolution (what actually goes in the database)

1. **The MLIP-for-solids method is validated in principle** - SevenNet reproduces the measured
   olivine excess (RMS 861). But **no single model is reliable on an unmeasured join**, and
   passing one measured join does not certify a model on a chemically different one. The honest
   error bar on any single-MLIP solid-solution excess is **~+/-10-15 kJ on L0** (spinel spread),
   set by inter-model disagreement, not by configurational noise.

2. There is a **regime split**: the models that capture the large positive olivine excess
   (SevenNet, TensorNet) over-state the small spinel/cpx excesses; MatterSim, which biases to
   ideal, is closest for the near-ideal joins. No model is right in both regimes.

3. **Clinopyroxene: near-ideal** is robust across all models - shipped as a small excess,
   low impact on equilibrium.

4. **Spinel: sign leans negative (favourable), magnitude unconstrained.** Every model, both
   signs, gives complete Fe-Mg miscibility with no gap above ~1000 K (ORB's +6953 would open a
   gap only below ~420 K), so the **slag-relevant phase behaviour is model-independent** even
   though L0 is not.

5. **Decision: spinel and cpx ship IDEAL (no excess term).** With no measurement to arbitrate,
   no model agreement (spinel), and a direct test showing the cpx excess moves the
   CaO-FeO-MgO-SiO2 liquidus by <= 20 K with no phase change, a nonzero excess is not earned.
   Shipping ideal avoids an unconstrained parameter while keeping the supported claim - complete
   Fe-Mg miscibility, no gap at slag temperatures - which every model agrees on. The `_mlip/`
   scripts and this study are retained as the basis for the choice and as the drop-in harness for
   a future DFT or measured excess. Verified: the ideal SUBL blocks reproduce pycalphad to 1e-6
   and match the analytic ideal-mixing Gibbs to < 0.1 J/mol (tests updated accordingly).
