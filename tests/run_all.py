"""Ejecuta cada prueba del contrato en AISLAMIENTO: carpeta temporal y base SQLite nueva.
Nunca toca as_platform.db. Solo usa la librería estándar (sin pytest).

Uso:  python tests/run_all.py            (todas)
      python tests/run_all.py seguridad  (solo las que contengan el texto)
Código de salida 5 dentro de una prueba = omitida (falta un archivo externo, etc.).
"""
import glob, os, subprocess, sys, tempfile, time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIMEOUT = 240


def correr(script):
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, PYTHONPATH=RAIZ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        # Base nueva con todas las tablas (el cwd temporal hace que as_platform.db sea nueva)
        subprocess.run([sys.executable, "-c", "import database; database.crear_tablas()"],
                       cwd=tmp, env=env, capture_output=True, timeout=TIMEOUT)
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, script], cwd=tmp, env=env,
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT)
            return r.returncode, (r.stdout + r.stderr), time.time() - t0
        except subprocess.TimeoutExpired:
            return 124, "TIMEOUT", time.time() - t0


def main():
    filtro = sys.argv[1] if len(sys.argv) > 1 else ""
    scripts = sorted(p for p in glob.glob(os.path.join(RAIZ, "tests", "test_*.py")) if filtro in os.path.basename(p))
    fallos = 0
    for s in scripts:
        code, out, seg = correr(s)
        estado = {0: "OK   ", 5: "SKIP "}.get(code, "FALLA")
        print(f"{estado} {os.path.basename(s):<46} {seg:5.1f}s")
        if code not in (0, 5):
            fallos += 1
            print("      " + "\n      ".join(out.strip().splitlines()[-12:]))
    print(f"\n{len(scripts) - fallos}/{len(scripts)} pruebas sin fallo.")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
