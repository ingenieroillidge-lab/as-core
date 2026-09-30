"""Envoltorio unittest/pytest: una prueba por cada script del contrato, cada una en AISLAMIENTO
(base SQLite temporal, ver run_all.py). Sirve con:

    python -m unittest discover -s tests -p "test_suite.py" -v
    pytest tests/test_suite.py            (si tienes pytest; conftest.py evita importar los scripts sueltos)
"""
import glob
import os
import unittest

from run_all import RAIZ, correr


class ContratoTests(unittest.TestCase):
    pass


def _crear(script):
    def prueba(self):
        codigo, salida, _ = correr(script)
        if codigo == 5:
            self.skipTest("omitida (falta un recurso externo)")
        self.assertEqual(codigo, 0, "\n".join(salida.strip().splitlines()[-15:]))
    return prueba


for _ruta in sorted(glob.glob(os.path.join(RAIZ, "tests", "test_*.py"))):
    _nombre = os.path.basename(_ruta)
    if _nombre != "test_suite.py":
        setattr(ContratoTests, _nombre[:-3], _crear(_ruta))

if __name__ == "__main__":
    unittest.main()
