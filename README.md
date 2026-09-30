# AS Platform (as-core)

SaaS ERP y financiero multi-tenant para micro y pequeñas empresas (Flask, SQLite/PostgreSQL).

## Ejecutar
```
pip install -r requirements.txt
cp .env.example .env        # y define SECRET_KEY
python app.py               # FLASK_DEBUG=1 solo en desarrollo
```

## Pruebas
```
python tests/run_all.py             # todas, cada una con una base SQLite temporal nueva
python tests/run_all.py seguridad   # solo las que contengan "seguridad"
python -m unittest discover -s tests -p "test_suite.py" -v   # mismo resultado, formato unittest
pytest tests/test_suite.py          # si tienes pytest (conftest.py evita importar los scripts sueltos)
```
Las pruebas **nunca** tocan `as_platform.db`. `test_importador_excel_real_266` se omite si no
defines `AS_EXCEL_266` con la ruta de un Excel real (datos de clientes: no se suben al repositorio).
El CI (GitHub Actions) ejecuta lo mismo en cada pull request.
