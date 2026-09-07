"""Run the Al-Zn ZPF MCMC (Option-2 fit: liquidus from Massalski). Writes the
posterior trace to output/trace.npy. Upgraded with Mey (1993) calorimetry later."""
import yaml
from espei.espei_script import get_run_settings, run_espei

with open("espei_input.yaml") as f:
    settings = get_run_settings(yaml.safe_load(f))
run_espei(settings)
print("MCMC done; trace at output/trace.npy")
