"""Pull the 25 C formation Gibbs energies the wet-slag phases need out of the Cemdata18 accepted
manuscript (Lothenbach et al. 2019, Cem. Concr. Res. 115, 472, doi:10.1016/j.cemconres.2018.04.018)
and the Table 2 solubility products into cemdata18_dfG.csv, with the PDF page and the manuscript line number of each row, so nothing is
retyped. Tables 1 and 4 of the manuscript; run once (the PDF lives in the local trove, not in git).

    python extract_cemdata18.py
"""
import csv
import re
from pathlib import Path

import pypdf

PDF = Path(r"C:/Users/busta/Code/odinzen_assessment_workspace/assets/local-archive/oxide-slag/references/"
           r"Lothenbach_2019_CemConcrRes115_472_Cemdata18_accepted-ms.pdf")
OUT = Path(__file__).resolve().parent / "cemdata18_dfG.csv"

# our name: (row label as printed, CaO, Al2O3, SiO2, MgO, H2O) in oxide units per formula
ROWS = {
    "Portlandite_C18": ("CH (portlandite)", 1, 0, 0, 0, 1),
    "Gibbsite_C18": ("Al(OH)3(gibbsite)", 0, 0.5, 0, 0, 1.5),
    "Al(OH)3(mic)": ("Al(OH)3(mic)", 0, 0.5, 0, 0, 1.5),
    "Quartz_C18": ("SiO2 (quartz)", 0, 0, 1, 0, 0),
    "SiO2(am)_C18": ("SiO2 (am)", 0, 0, 1, 0, 0),
    "C3AH6": ("C3AH6", 3, 1, 0, 0, 6),
    "C3AS0.41H5.18": ("C3AS0.41H5.18", 3, 1, 0.41, 0, 5.18),
    "C3AS0.84H4.32": ("C3AS0.84H4.32", 3, 1, 0.84, 0, 4.32),
    "C4AH19": ("C4AH19", 4, 1, 0, 0, 19),
    "C4AH13": ("C4AH13", 4, 1, 0, 0, 13),
    "C2AH7.5": ("C2AH7.5", 2, 1, 0, 0, 7.5),
    "CAH10": ("CAH10", 1, 1, 0, 0, 10),
    "Straetlingite": ("C2ASH8", 2, 1, 1, 0, 8),
    "MSH_0.75": ("M1.5S2H2.5", 0, 0, 2, 1.5, 2.5),
    "MSH_1.5": ("M1.5SH2.5", 0, 0, 1, 1.5, 2.5),
    "CSH_Tob": ("Tob: C0.83SH1.3", 0.83, 0, 1, 0, 1.3),
    "CSH_Jen": ("Jen: C1.67SH2.1", 1.67, 0, 1, 0, 2.1),
    # anhydrous clinker phases: the cross-check against our own solids
    "Lime_C18": ("C (lime)", 1, 0, 0, 0, 0),
    "C3S_C18": ("C3S", 3, 0, 1, 0, 0),
    "C2S_C18": ("C2S", 2, 0, 1, 0, 0),
    "C3A_C18": ("C3A", 3, 1, 0, 0, 0),
    "CA_C18": ("CA", 1, 1, 0, 0, 0),
    "CA2_C18": ("CA2", 1, 2, 0, 0, 0),
}
NUM = r"(-?\d+(?:\.\d+)?)"


def main():
    reader = pypdf.PdfReader(str(PDF))
    found, dfh_s = {}, {}
    for ipage, page in enumerate(reader.pages, start=1):
        if ipage not in (4, 5, 6, 19, 20):          # Table 1 runs over pp. 4-6, Table 4 is on p. 19
            continue
        for line in (page.extract_text() or "").splitlines():
            s = line.strip()
            for name, (label, *_rest) in ROWS.items():
                if name in found:
                    continue
                # the label, optional footnote marks, then dfG in kJ; dfH (kJ) and S (J/K) follow
                m = re.match(re.escape(label) + r"[\s*a-z,]*?\s+" + NUM + r"\s", s + " ")
                if m:
                    ln = re.search(r"\s(\d{2,4})\s*$", s)
                    found[name] = (float(m.group(1)) * 1000.0, ipage, ln.group(1) if ln else "")
                    hs = re.match(re.escape(label) + r"[\s*a-z,]*?\s+" + NUM + r"\s+" + NUM + r"[a-z]?\s+" + NUM, s)
                    if hs:
                        dfh_s[name] = (float(hs.group(2)) * 1000.0, float(hs.group(3)))
    # CSHQ endmembers (Table 4, pp. 19-20; Kulik 2011): the label carries "Ca/Si=" and a formula, so
    # match on the endmember name and take the first number after the formula
    CSHQ = {"CSHQ_TobH": ("TobH", 2 / 3, 1, 1.5), "CSHQ_TobD": ("TobD", 5 / 6, 2 / 3, 11 / 6),
            "CSHQ_JenH": ("JenH", 4 / 3, 1, 13 / 6), "CSHQ_JenD": ("JenD", 1.5, 2 / 3, 2.5)}
    for ipage in (19, 20):
        for line in (reader.pages[ipage - 1].extract_text() or "").splitlines():
            s = line.strip()
            for name, (tag, ca, si, h2o) in CSHQ.items():
                m = re.match(tag + r"\s+Ca/Si\s*=\s*[\d.]+:\s*\S+\s+" + NUM + r"\s+" + NUM + r"\s+" + NUM, s)
                if m and name not in found:
                    ln = re.search(r"\s(\d{3})\s*$", s)
                    found[name] = (float(m.group(1)) * 1000.0, ipage, ln.group(1) if ln else "")
                    dfh_s[name] = (float(m.group(2)) * 1000.0, float(m.group(3)))
                    ROWS[name] = (tag, ca, 0, si, 0, h2o)
    # Table 2 (manuscript lines 247-320, pp. 6-7): log KS0 at 25 C, same row labels where they exist
    T2 = {"Portlandite_C18": "CH", "Gibbsite_C18": "Al(OH)3(gibbsite)", "Al(OH)3(mic)": "Al(OH)3(mic)",
          "Quartz_C18": "SiO2(quartz)", "SiO2(am)_C18": "SiO2(am)", "C3AH6": "C3AH6",
          "C3AS0.41H5.18": "C3AS0.41H5.18", "C3AS0.84H4.32": "C3AS0.84H4.32", "C4AH19": "C4AH19",
          "C4AH13": "C4AH13", "C2AH7.5": "C2AH7.5", "CAH10": "CAH10", "Straetlingite": "C2ASH8",
          "MSH_0.75": "M1.5S2H2.5", "MSH_1.5": "M1.5SH2.5"}
    logks0 = {}
    for ipage in (6, 7):
        for line in (reader.pages[ipage - 1].extract_text() or "").splitlines():
            s = line.strip()
            ln = re.search(r"\s(\d{3})\s*$", s)
            if not ln or not 247 <= int(ln.group(1)) <= 320:
                continue
            for name, label in T2.items():
                m = re.match(re.escape(label) + r"[\s*]*?\s+" + NUM + r"[\s*]", s + " ")
                if m and name not in logks0:
                    logks0[name] = (float(m.group(1)), ln.group(1))
    missing = [n for n in ROWS if n not in found] + [n for n in T2 if n not in logks0]
    if missing:
        raise SystemExit(f"rows not found in the PDF text: {missing}")
    with OUT.open("w", newline="", encoding="ascii") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "label", "CaO", "Al2O3", "SiO2", "MgO", "H2O", "dfG_J", "pdf_page", "ms_line",
                    "logKs0_table2", "table2_ms_line", "dfH_J", "S_JK"])
        for name, (label, *ox) in ROWS.items():
            g, pg, ln = found[name]
            k, kl = logks0.get(name, ("", ""))
            h, s = (f"{v:.1f}" for v in dfh_s[name]) if name in dfh_s else ("", "")
            w.writerow([name, label, *ox, f"{g:.1f}", pg, ln, k, kl, h, s])
    print(f"wrote {OUT.name}: {len(found)} rows")
    for name, (g, pg, ln) in found.items():
        print(f"  {name:16s} {g / 1000:11.2f} kJ  p{pg} l{ln}")


if __name__ == "__main__":
    main()
