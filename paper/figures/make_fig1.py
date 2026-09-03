"""Regenerate fig1_architecture.png (greyscale, serif, no baked caption)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"]})

FIG_W, FIG_H = 11.0, 7.2
fig, ax = plt.subplots(figsize=(FIG_W, FIG_H), dpi=600)
ax.set_xlim(0, 100)
ax.set_ylim(0, 66)
ax.axis("off")


def box(x, y, w, h, title, lines, face="#ececec", dashed=False, title_size=15, size=13.5):
    p = FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.6,rounding_size=1.2",
        facecolor=face, edgecolor="black",
        linewidth=1.4, linestyle=(0, (4, 3)) if dashed else "solid",
    )
    ax.add_patch(p)
    cy = y + h - 2.6
    ax.text(x + w / 2, cy, title, ha="center", va="center", fontsize=title_size, fontweight="bold")
    for ln in lines:
        cy -= 3.4
        ax.text(x + w / 2, cy, ln, ha="center", va="center", fontsize=size)
    return (x + w / 2, y, x + w / 2, y + h, x, x + w)  # cx, bottom, cx, top, left, right


def arrow(x1, y1, x2, y2, dashed=False, both=False):
    a = FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle="<->" if both else "->",
        mutation_scale=22, linewidth=1.6, color="black",
        linestyle=(0, (4, 3)) if dashed else "solid",
    )
    ax.add_patch(a)


# top row
b_files = box(2, 51, 44, 12, "Database files: .dat / .tdb / .utdb",
              ["ChemSage · Thermo-Calc · unified dialect",
               "MQMQA liquids, CEF solids, stoichiometric"], size=12.5)
b_dbb = box(53, 51, 38, 12, "dbbuild (Python)",
            ["measured data + fitted excess", "written as a valid ChemSage file"])

# center core
b_core = box(12, 29, 58, 13, "C core (C99, no dependencies)",
             ["auto-detecting reader · MQMQA + CEF Gibbs energy",
              "Inden magnetic model · liquid equilibrium minimizer"], size=12.5)
b_pyc = box(78, 30, 20, 11, "pycalphad", ["independent oracle,", "machine precision"], dashed=True,
            title_size=14, size=12.5)

# bottom row
b_nat = box(2, 5, 28, 12, "Native library",
            ["embed from C or any", "language with a C FFI"])
b_py = box(36, 5, 28, 12, "Python package (cffi)",
           ["scripting · fitting", "multiphase hull · sections"])
b_wasm = box(70, 5, 28, 12, "WebAssembly",
             ["zero-install browser app,", "fully client-side"])

# arrows: inputs to core
arrow(24, 50.3, 36, 43)
arrow(72, 50.3, 56, 43)
# core to outputs
arrow(22, 28.3, 16, 18)
arrow(42, 28.3, 50, 18)
arrow(62, 28.3, 84, 18)
# oracle
arrow(70.9, 35.5, 77.2, 35.5, dashed=True, both=True)

fig.savefig("fig1_architecture.png", bbox_inches="tight", facecolor="white")
print("fig1_architecture.png written")
