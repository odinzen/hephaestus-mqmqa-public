import warnings; warnings.filterwarnings('ignore')
from ase.io import read
import glob, os
here=os.path.dirname(os.path.abspath(__file__))
for f in sorted(glob.glob(os.path.join(here,'cif','*.cif'))):
    b=os.path.basename(f)
    try:
        a=read(f); sym=a.get_chemical_symbols()
        print(f"{b:42s} -> {a.get_chemical_formula():16s} atoms={len(a):3d} Mg={sym.count('Mg')} Fe={sym.count('Fe')} Ca={sym.count('Ca')} Al={sym.count('Al')}")
    except Exception as e:
        print(b,'ERROR:',repr(e))
