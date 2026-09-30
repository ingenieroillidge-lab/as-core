"""pytest: los scripts test_*.py sueltos ejecutan código al importarse (y usarían la base del cwd).
Solo se recolecta test_suite.py, que los corre aislados en subprocesos."""
import glob
import os

_aqui = os.path.dirname(os.path.abspath(__file__))
collect_ignore = [os.path.basename(p) for p in glob.glob(os.path.join(_aqui, "test_*.py"))
                  if os.path.basename(p) != "test_suite.py"]
