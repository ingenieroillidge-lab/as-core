"""Integridad financiera de ventas: abono inicial una sola vez, contado con cliente, stock con lotes."""
import os, sys, tempfile
_tmp = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(_tmp)
from werkzeug.security import generate_password_hash
import app as appmod
from database import ejecutar_query
import services.ventas_service as vs
import services.lotes_service as ls

NEG = 601
ejecutar_query("INSERT INTO negocios (id, nombre) VALUES (?, 'Emp')", (NEG,))
ejecutar_query("INSERT INTO usuarios (id, negocio_id, username, password_hash, role) VALUES (9601, ?, 'adm', ?, 'ADMIN')", (NEG, generate_password_hash('Clave123')))
ejecutar_query("INSERT INTO productos (negocio_id, nombre, precio) VALUES (?, 'Camisa', 100000)", (NEG,))
PID = ejecutar_query("SELECT id FROM productos WHERE negocio_id=?", (NEG,), fetch=True)[0][0]


def cli():
    c = appmod.app.test_client()
    assert c.post('/login', data={'username': 'adm', 'password': 'Clave123'}).status_code == 302
    return c


def venta(v_id):
    return ejecutar_query("SELECT total, saldo_pendiente, estado_pago, metodo_pago FROM ventas WHERE id=?", (v_id,), fetch=True)[0]


def ultima():
    return ejecutar_query("SELECT MAX(id) FROM ventas WHERE negocio_id=?", (NEG,), fetch=True)[0][0]


def test_abono_inicial_se_descuenta_una_vez():
    c = cli()
    r = c.post('/api/ventas', json={'producto_id': PID, 'cantidad': 1, 'metodo_pago': 'Nequi', 'cliente_nombre': 'Ana', 'abono_inicial': 40000})
    assert r.status_code == 200, r.data
    total, saldo, estado, _ = venta(ultima())
    assert (total, saldo, estado) == (100000, 60000, 'PARCIAL'), (total, saldo, estado)
    ab = ejecutar_query("SELECT monto, metodo_pago FROM abonos_cartera WHERE venta_id=?", (ultima(),), fetch=True)
    assert ab == [(40000.0, 'Nequi')], ab   # método real, no inventado


def test_abono_con_credito_no_inventa_metodo():
    c = cli()
    c.post('/api/ventas', json={'producto_id': PID, 'cantidad': 1, 'metodo_pago': 'CRÉDITO', 'cliente_nombre': 'Beto', 'abono_inicial': 100000})
    total, saldo, estado, _ = venta(ultima())
    assert saldo == 0 and estado == 'PAGADO'
    ab = ejecutar_query("SELECT metodo_pago FROM abonos_cartera WHERE venta_id=?", (ultima(),), fetch=True)
    assert ab == [('NO_ESPECIFICADO',)], ab


def test_contado_con_cliente_queda_pagado():
    c = cli()
    c.post('/api/ventas', json={'producto_id': PID, 'cantidad': 1, 'metodo_pago': 'Efectivo', 'cliente_nombre': 'Carla'})
    total, saldo, estado, _ = venta(ultima())
    assert estado == 'PAGADO' and not saldo, (saldo, estado)


def test_credito_sin_abono_queda_pendiente():
    c = cli()
    c.post('/api/ventas', json={'producto_id': PID, 'cantidad': 2, 'metodo_pago': 'CRÉDITO', 'cliente_nombre': 'Dani'})
    total, saldo, estado, _ = venta(ultima())
    assert (total, saldo, estado) == (200000, 200000, 'PENDIENTE')


def test_stock_con_lotes_se_descuenta_una_vez_y_se_restituye():
    ejecutar_query("INSERT INTO configuracion_negocio (negocio_id, maneja_lotes) VALUES (?, 1)", (NEG,)) or \
        ejecutar_query("UPDATE configuracion_negocio SET maneja_lotes=1 WHERE negocio_id=?", (NEG,))
    ejecutar_query("INSERT INTO inventario (negocio_id, nombre, stock_actual, unidad_base, costo_unitario_base) VALUES (?, 'Tela', 10, 'm', 5)", (NEG,))
    ins = ejecutar_query("SELECT id FROM inventario WHERE negocio_id=? AND nombre='Tela'", (NEG,), fetch=True)[0][0]
    ejecutar_query("INSERT INTO lotes_inventario (negocio_id, insumo_id, codigo_lote, fecha_compra, cantidad_inicial, cantidad_disponible, costo_unitario) VALUES (?, ?, 'L1', '2026-01-01', 10, 10, 5)", (NEG, ins))
    ejecutar_query("INSERT INTO productos (negocio_id, nombre, precio) VALUES (?, 'Polo', 50000)", (NEG,))
    pid2 = ejecutar_query("SELECT id FROM productos WHERE nombre='Polo' AND negocio_id=?", (NEG,), fetch=True)[0][0]
    ejecutar_query("INSERT INTO producto_insumo (negocio_id, producto_id, insumo_id, cantidad_usada) VALUES (?, ?, ?, 1)", (NEG, pid2, ins))
    ok, _, vid = vs.registrar_venta_con_id(pid2, 3, 'Efectivo', 9601, NEG)
    assert ok
    stock = ejecutar_query("SELECT stock_actual FROM inventario WHERE id=?", (ins,), fetch=True)[0][0]
    lote = ejecutar_query("SELECT cantidad_disponible FROM lotes_inventario WHERE insumo_id=?", (ins,), fetch=True)[0][0]
    assert stock == 7 and lote == 7, (stock, lote)
    ok, _ = vs.eliminar_venta(vid, NEG, 9601)
    assert ok
    stock = ejecutar_query("SELECT stock_actual FROM inventario WHERE id=?", (ins,), fetch=True)[0][0]
    lote, est = ejecutar_query("SELECT cantidad_disponible, estado FROM lotes_inventario WHERE insumo_id=?", (ins,), fetch=True)[0]
    assert stock == 10 and lote == 10 and est == 'ACTIVO', (stock, lote, est)


def test_venta_que_agota_lote_y_se_elimina_reactiva_lote():
    ins = ejecutar_query("SELECT id FROM inventario WHERE negocio_id=? AND nombre='Tela'", (NEG,), fetch=True)[0][0]
    pid2 = ejecutar_query("SELECT id FROM productos WHERE nombre='Polo' AND negocio_id=?", (NEG,), fetch=True)[0][0]
    ok, _, vid = vs.registrar_venta_con_id(pid2, 10, 'Efectivo', 9601, NEG)
    assert ok
    assert ejecutar_query("SELECT estado FROM lotes_inventario WHERE insumo_id=?", (ins,), fetch=True)[0][0] == 'AGOTADO'
    vs.eliminar_venta(vid, NEG, 9601)
    assert ejecutar_query("SELECT estado FROM lotes_inventario WHERE insumo_id=?", (ins,), fetch=True)[0][0] == 'ACTIVO'


def test_recaudo_sale_de_saldos_no_del_metodo_de_pago():
    import services.financiero_service as fs
    import services.cartera_service as cs
    nid = 602
    ejecutar_query("INSERT INTO negocios (id, nombre) VALUES (?, 'E2')", (nid,))
    # Venta 100.000 pagada con Nequi de contado; venta 100.000 con abono 40.000; venta 100.000 fiada con descuento de 60.000
    F = "2026-03-10 12:00:00"
    for tot, met, saldo, est in [(100000, 'Nequi', 0, 'PAGADO'), (100000, 'Efectivo', 60000, 'PARCIAL'), (100000, 'CRÉDITO', 100000, 'PENDIENTE')]:
        ejecutar_query("INSERT INTO ventas (negocio_id, fecha, total, cantidad, metodo_pago, costo_historico_total, saldo_pendiente, estado_pago) VALUES (?,?,?,1,?,0,?,?)", (nid, F, tot, met, saldo, est))
    ids = [r[0] for r in ejecutar_query("SELECT id FROM ventas WHERE negocio_id=? ORDER BY id", (nid,), fetch=True)]
    ejecutar_query("INSERT INTO abonos_cartera (negocio_id, venta_id, fecha, monto, metodo_pago) VALUES (?,?,?,?,?)", (nid, ids[1], F, 40000, 'Efectivo'))
    ejecutar_query("INSERT INTO abonos_cartera (negocio_id, venta_id, fecha, monto, metodo_pago) VALUES (?,?,?,?,?)", (nid, ids[2], F, 60000, 'DESCUENTO_COMERCIAL'))
    v = fs.ventas_con_cobro_inmediato(nid)
    # venta 2: saldo 60.000 + abono 40.000 => nada cobrado al vender (el dinero llegó como abono); venta 3: saldo 100.000 + 60.000 capado al total
    assert [round(x["cobrado_en_venta"]) for x in v] == [100000, 0, 0], v
    assert cs.obtener_resumen_cartera(nid, "2026-03")["recaudo_mes"] == 140000   # 100.000 contado + 40.000 abono; el descuento no es caja
    cierre = fs.realizar_cierre_caja(nid, "2026-03-10")
    assert cierre["total"] == 140000, cierre


def test_ranking_de_productos_del_tablero_no_queda_vacio():
    import services.financiero_service as fs
    r = fs.obtener_tablero_ejecutivo_completo(NEG, periodo='TODO', comparar_anterior=False)
    assert r.get('ok'), r
    rank = r.get('ranking_productos') or r.get('productos', {}).get('ranking') or []
    assert rank, list(r.keys())


if __name__ == '__main__':
    for n, f in list(globals().items()):
        if n.startswith('test_'):
            f(); print('OK', n)
    print('INTEGRIDAD DE VENTAS: TODAS LAS PRUEBAS PASARON')
