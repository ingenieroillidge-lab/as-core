from datetime import datetime
from database import ejecutar_query

def registrar_movimiento(insumo_id, tipo, cantidad, referencia, usuario_id, negocio_id):
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Validar que el insumo pertenece al negocio
    res = ejecutar_query("SELECT id FROM inventario WHERE id=? AND negocio_id=?", (insumo_id, negocio_id), fetch=True)
    if not res: return False

    ejecutar_query(
        """INSERT INTO movimientos_inventario
           (negocio_id, fecha, insumo_id, tipo, cantidad, referencia, usuario_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (negocio_id, fecha, insumo_id, tipo, cantidad, referencia, usuario_id)
    )

    operador = "+" if tipo == 'entrada' else "-"
    ejecutar_query(
        f"UPDATE inventario SET stock_actual = stock_actual {operador} ? WHERE id=? AND negocio_id=?",
        (cantidad, insumo_id, negocio_id)
    )
    return True

def obtener_inventario(negocio_id):
    return ejecutar_query("SELECT id, codigo, nombre, unidad_base, stock_actual, 0, costo_unitario_base, 0, cantidad_presentacion, 0 FROM inventario WHERE negocio_id=?", (negocio_id,), fetch=True)

def obtener_flujo_inventario(negocio_id, mes=None):
    if not mes: mes = datetime.now().strftime("%Y-%m")
    insumos = ejecutar_query("SELECT id, nombre, unidad_base, 0, stock_actual FROM inventario WHERE negocio_id=?", (negocio_id,), fetch=True)
    
    reporte = []
    for i_id, nombre, unidad, s_ini, s_act in insumos:
        res_e = ejecutar_query("SELECT SUM(cantidad) FROM movimientos_inventario WHERE insumo_id=? AND tipo='entrada' AND fecha LIKE ? AND negocio_id=?", (i_id, f"{mes}%", negocio_id), fetch=True)
        entradas = res_e[0][0] or 0
        res_s = ejecutar_query("SELECT SUM(cantidad) FROM movimientos_inventario WHERE insumo_id=? AND tipo='salida' AND fecha LIKE ? AND negocio_id=?", (i_id, f"{mes}%", negocio_id), fetch=True)
        salidas = res_s[0][0] or 0
        reporte.append({"nombre": nombre, "unidad": unidad, "inicial": 0, "entradas": entradas, "salidas": salidas, "final": s_act})
    return reporte