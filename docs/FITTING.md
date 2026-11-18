# Fitting databases in Hephaestus

Design note for the database fitter. Status: design, nothing implemented yet.

## What it does

Fits the excess parameters of a database to measured data and reports how well the data
determine each one. It runs in the browser on the same engine that computes the diagrams, so
the fitted file and the calculation can never disagree, and the data stay on the user's machine.

It follows the method of ESPEI (Bocklund et al., MRS Communications 9 (2019) 618-627,
doi:10.1557/mrc.2019.59): parameters are chosen first, by fitting candidate models to
thermochemical data and scoring them, and then all parameters are fitted together to every kind
of data, phase boundaries included, with Markov chain Monte Carlo giving their uncertainty.
ESPEI fits the compound energy formalism through pycalphad and has no MQMQA. This fitter is
written for the MQMQA first and the compound energy formalism second.

## Provenance

Written from the ESPEI paper above, ESPEI's documentation (`docs/input_data.rst` and
`docs/design.rst` in ESPEI 0.9.1, read 2026-11-14) and the published methods cited below.
ESPEI's source code is not opened, so ESPEI can serve as an independent check on alloy fits where
both tools apply. If that changes, it is recorded here, in NOTICE and in the commit.

## Data

ESPEI's dataset JSON is read as documented, so an existing ESPEI dataset loads unchanged:
energies in J/mol of atoms, mole fractions, kelvin, pascal; `output` names the quantity; `values`
has shape (P, T, points); `reference`, `comment`, `weight` and `tags` keep their meaning.

Supported outputs, in the order they are built:

1. `ACR_<component>`: activity in a single phase at a stated composition, with ESPEI's
   `reference_state` block.
2. `HM_MIX`: enthalpy of mixing of a phase at a stated composition.
3. `ZPF`: phase-boundary data, with ESPEI's phase-region layout including `null` compositions.

One documented extension: for oxide and salt systems a component may be a compound written as a
formula (`"FEO"`, `"SIO2"`, `"MGCL2"`), and compositions are mole fractions of those compounds.
Element-based files are untouched by this.

ESPEI's non-equilibrium thermochemical data (known site fractions) has no MQMQA counterpart,
because the quadruplet distribution of an MQMQA liquid is always relaxed. Such data is accepted
for compound-energy-formalism phases only.

## Stage 1: choosing the parameters

For each binary of the phase, a list of candidate excess models of increasing size: for the
MQMQA, the Q-code terms with exponents (0,0), then (1,0) and (0,1), then higher, each with or
without a temperature term; for the compound energy formalism, L0, L0+L1, and so on. Each
candidate is fitted to that binary's thermochemical data and scored by the corrected Akaike
information criterion (Hurvich and Tsai, Biometrika 76 (1989) 297-307,
doi:10.1093/biomet/76.2.297), which charges for every added parameter. The lowest score wins.

ESPEI fits its candidates by linear least squares, which works because the compound energy
formalism is linear in its parameters at fixed site fractions. The MQMQA is not: changing an
excess term moves the quadruplet distribution. Each candidate is therefore fitted by
Levenberg-Marquardt through the engine's equilibrium, and the temperature terms are fitted as the
parameter's values at the lowest and highest data temperatures, which removes the near-collinearity
of the a and b terms (the same device `dbbuild.fit_binary_excess` uses).

## Stage 2: fitting everything, with uncertainty

All chosen parameters, every binary and any ternary term, are fitted together to all the data.
Each point contributes a Gaussian log-likelihood with the standard deviation the dataset states,
or a default per quantity, scaled by the dataset weight. Phase-boundary points use the
zero-phase-fraction driving force of Bocklund et al. (2019): the target hyperplane is set by the
phases with stated compositions, and each phase's distance from it is the error.

The posterior is sampled with the affine-invariant ensemble sampler (Goodman and Weare,
Communications in Applied Mathematics and Computational Science 5 (2010) 65-80,
doi:10.2140/camcos.2010.5.65), the algorithm behind emcee (Foreman-Mackey et al., Publications of
the Astronomical Society of the Pacific 125 (2013) 306-312, doi:10.1086/670067). Priors are normal
distributions centred on the stage-1 values and wide enough to stay out of the way. In the browser
each Web Worker runs its own chain with its own seed, and the chains are pooled after burn-in.

Output: the fitted database file, each parameter's mean, standard deviation and correlations,
the samples, and any calculated diagram drawn with a band from posterior samples.

## Where the code goes

- `src/fit.c`, `src/fit.h`: dataset reading (JSON), the observation table, residuals and
  likelihoods through the engine, Levenberg-Marquardt, the score, and the sampler. One
  implementation for Python and the browser.
- Engine additions: list a database's free parameters and set their values in memory, so a fit
  does not rewrite and reread a file for every trial.
- `python/mqmqa/fit.py`: thin wrapper and the tests' entry point.
- `web/fit_worker.js` and a Fit panel in `web/index.html`.

## How it is checked

- Plant and recover: data computed from known parameters, with and without noise, must give back
  those parameters within the reported uncertainty.
- Stage 1 against `dbbuild.fit_binary_excess` on the same binary data.
- ESPEI on a compound-energy-formalism binary where both tools apply.
- The held-out literature test (`validation/literature`) for databases refitted with it.
