"""The teaching notebooks run start to finish on the current engine."""
from pathlib import Path

import pytest

nbformat = pytest.importorskip("nbformat")
nbclient = pytest.importorskip("nbclient")

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = sorted((ROOT / "notebooks").glob("*/*.ipynb"))


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.stem)
def test_notebook_runs(path):
    nb = nbformat.read(path, as_version=4)
    nbclient.NotebookClient(nb, timeout=900, kernel_name="python3",
                            resources={"metadata": {"path": str(path.parent)}}).execute()
