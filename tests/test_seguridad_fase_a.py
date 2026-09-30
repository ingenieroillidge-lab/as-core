"""Pruebas de la Fase A (seguridad). Usan una base temporal: no tocan as_platform.db."""
import os, sys, tempfile

_tmp = tempfile.mkdtemp()
_repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _repo)
os.chdir(_tmp)  # database.py abre "as_platform.db" relativo al cwd

from werkzeug.security import generate_password_hash
import app as appmod
from database import ejecutar_query

ejecutar_query("INSERT INTO negocios (id, nombre) VALUES (501, 'Empresa A')")
ejecutar_query("INSERT INTO usuarios (negocio_id, username, password_hash, role) VALUES (501, 'admin_a', ?, 'ADMIN')", (generate_password_hash('ClaveAdmin1'),))
ejecutar_query("INSERT INTO usuarios (negocio_id, username, password_hash, role) VALUES (501, 'oper_a', ?, 'OPERADOR')", (generate_password_hash('ClaveOper1'),))


def cliente(user, pw):
    c = appmod.app.test_client()
    r = c.post('/login', data={'username': user, 'password': pw})
    assert r.status_code == 302, f"login de {user} falló ({r.status_code})"
    return c


def test_admin_no_puede_crear_super():
    c = cliente('admin_a', 'ClaveAdmin1')
    r = c.post('/api/usuarios', json={'username': 'hacker', 'password': 'x12345', 'role': 'SUPER'})
    assert r.status_code == 400, r.status_code
    r = c.post('/api/usuarios', json={'username': 'ok_oper', 'password': 'x12345', 'role': 'OPERADOR'})
    assert r.status_code == 200, r.status_code
    n = ejecutar_query("SELECT COUNT(*) FROM usuarios WHERE role='SUPER'", fetch=True)[0][0]
    assert n == 0


def test_login_ya_no_acepta_texto_plano():
    ejecutar_query("INSERT INTO usuarios (negocio_id, username, password, password_hash, role) VALUES (501, 'legacy', 'plano123', ?, 'OPERADOR')", (generate_password_hash('otra-clave'),))
    c = appmod.app.test_client()
    r = c.post('/login', data={'username': 'legacy', 'password': 'plano123'})
    assert r.status_code == 200, "el texto plano no debe iniciar sesión"


def test_migracion_hashea_y_borra_texto_plano():
    ejecutar_query("INSERT INTO usuarios (negocio_id, username, password, role) VALUES (501, 'solo_plano', 'miClave9', 'OPERADOR')")
    assert appmod.migrar_passwords_planas() >= 1
    fila = ejecutar_query("SELECT password, password_hash FROM usuarios WHERE username='solo_plano'", fetch=True)[0]
    assert fila[0] is None and fila[1]
    cliente('solo_plano', 'miClave9')
    assert appmod.migrar_passwords_planas() == 0  # idempotente


def test_operador_no_puede_purgar_ni_deshacer():
    c = cliente('oper_a', 'ClaveOper1')
    assert c.post('/api/importador/purgar').status_code == 403
    assert c.post('/api/importador/deshacer/xyz').status_code == 403
    assert c.delete('/api/costos-fijos/1').status_code == 403


def test_google_sheets_rechaza_urls_no_google():
    c = cliente('admin_a', 'ClaveAdmin1')
    for u in ['file:///etc/passwd', 'http://169.254.169.254/latest/meta-data/', 'https://evil.com/docs.google.com/spreadsheets/d/' + 'a' * 25]:
        r = c.post('/api/importar/google-sheets', json={'url': u})
        assert r.status_code == 400, (u, r.status_code)


def test_secret_key_no_es_la_antigua():
    assert appmod.app.secret_key != "as_platform_high_conversion_2024"
    assert appmod.app.config['SESSION_COOKIE_HTTPONLY'] is True


if __name__ == '__main__':
    for n, f in list(globals().items()):
        if n.startswith('test_'):
            f(); print('OK', n)
    print('FASE A: TODAS LAS PRUEBAS PASARON')
