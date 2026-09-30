import sys
import os
sys.path.insert(0, '.')

from database import conectar, ejecutar_query

import services.ventas_service as ventas_service
import services.inventario_service as inventario_service

def run_tests():
    print("--- INICIANDO TEST DE ELIMINACIÓN DE VENTAS Y PERMISOS ---")
    nid = 9999
    uid_admin = 100
    uid_vendedor = 200

    # Clean setup
    ejecutar_query("DELETE FROM productos WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM inventario WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM ventas WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM producto_insumo WHERE negocio_id=?", (nid,))

    # 1. Crear insumo con stock inicial 100
    ejecutar_query(
        "INSERT INTO inventario (negocio_id, nombre, unidad_base, stock_actual, stock_inicial) VALUES (?, 'Carne Test', 'gr', 100, 100)",
        (nid,)
    )
    insumo_res = ejecutar_query("SELECT id FROM inventario WHERE negocio_id=? AND nombre='Carne Test'", (nid,), fetch=True)
    insumo_id = insumo_res[0][0]

    # 2. Crear producto que usa 10gr de Carne por unidad
    ejecutar_query("INSERT INTO productos (negocio_id, nombre, precio) VALUES (?, 'Burguer Test', 10000)", (nid,))
    prod_res = ejecutar_query("SELECT id FROM productos WHERE negocio_id=? AND nombre='Burguer Test'", (nid,), fetch=True)
    prod_id = prod_res[0][0]

    ejecutar_query("INSERT INTO producto_insumo (producto_id, insumo_id, cantidad_usada, negocio_id) VALUES (?, ?, 10, ?)", (prod_id, insumo_id, nid))

    # 3. Registrar venta de 2 hamburguesas (debe descontar 20gr -> stock pasa a 80gr)
    ok_v, res_v = ventas_service.registrar_venta(prod_id, 2, 'Efectivo', uid_vendedor, nid)
    assert ok_v, f"Falló registro de venta: {res_v}"

    stock_post = ejecutar_query("SELECT stock_actual FROM inventario WHERE id=?", (insumo_id,), fetch=True)[0][0]
    print(f"Stock post venta (esperado 80): {stock_post}")
    assert stock_post == 80, f"Stock incorrecto: {stock_post}"

    venta_res = ejecutar_query("SELECT id FROM ventas WHERE negocio_id=?", (nid,), fetch=True)
    venta_id = venta_res[0][0]

    # 4. Eliminar venta (debe reintegrar 20gr -> stock regresa a 100gr)
    ok_del, msg_del = ventas_service.eliminar_venta(venta_id, nid, uid_admin)
    assert ok_del, f"Falló eliminación de venta: {msg_del}"

    stock_restaurado = ejecutar_query("SELECT stock_actual FROM inventario WHERE id=?", (insumo_id,), fetch=True)[0][0]
    print(f"Stock post eliminación (esperado 100): {stock_restaurado}")
    assert stock_restaurado == 100, f"Reversión de stock incorrecta: {stock_restaurado}"

    # Cleanup
    ejecutar_query("DELETE FROM productos WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM inventario WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM ventas WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM producto_insumo WHERE negocio_id=?", (nid,))

    print("--- SUCCESS: TODOS LOS TESTS DE ELIMINACION Y REINTEGRO PASARON SATISFACTORIAMENTE ---")

if __name__ == '__main__':
    run_tests()

