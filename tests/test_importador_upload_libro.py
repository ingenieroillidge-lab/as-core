"""Extremo a extremo por la API: subir un libro tipo Hincha debe leer 'Datos', no 'Resumen' (base temporal)."""
import io, os, sys, tempfile
_tmp = tempfile.mkdtemp(); _repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _repo); sys.path.insert(0, os.path.join(_repo, 'tests')); os.chdir(_tmp)
from werkzeug.security import generate_password_hash
import app as appmod
from database import ejecutar_query
from test_lector_libro import _libro_tipo_hincha

ejecutar_query("INSERT INTO negocios (id, nombre) VALUES (601, 'Empresa Prueba')")
ejecutar_query("INSERT INTO usuarios (negocio_id, username, password_hash, role) VALUES (601, 'adm', ?, 'ADMIN')", (generate_password_hash('Clave123'),))


def _cliente():
    c = appmod.app.test_client()
    assert c.post('/login', data={'username': 'adm', 'password': 'Clave123'}).status_code == 302
    return c


def test_subida_elige_hoja_de_datos_y_mapea_columnas():
    c = _cliente()
    r = c.post('/api/importador/cargar', data={'file': (io.BytesIO(_libro_tipo_hincha()), 'seguimiento.xlsx')},
               content_type='multipart/form-data')
    j = r.get_json()
    assert r.status_code == 200 and j['ok'], j
    assert j['libro']['hoja_usada'] == 'Datos' and j['libro']['hoja_sugerida'] == 'Datos'
    heads = j['info']['headers']
    assert heads[:3] == ['Lote', 'Equipo', 'Talla'] and 'Estado analítico' not in heads
    campos = {m['columna_excel']: m['campo_propuesto'] for m in j['propuesta_mapeo']}
    assert campos['Cliente'] == 'cliente_nombre' and campos['Lote'] == 'codigo_lote'


def test_usuario_puede_elegir_otra_hoja():
    c = _cliente()
    r = c.post('/api/importador/cargar', data={'hoja': 'Caja', 'file': (io.BytesIO(_libro_tipo_hincha()), 'seguimiento.xlsx')},
               content_type='multipart/form-data')
    assert r.get_json()['libro']['hoja_usada'] == 'Caja'


if __name__ == '__main__':
    test_subida_elige_hoja_de_datos_y_mapea_columnas(); print('OK subida')
    test_usuario_puede_elegir_otra_hoja(); print('OK hoja elegida')
    print('UPLOAD LIBRO: TODAS LAS PRUEBAS PASARON')
