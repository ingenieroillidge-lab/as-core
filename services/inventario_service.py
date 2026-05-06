from datetime import datetime
from database import ejecutar_query


def registrar_movimiento(insumo_id, tipo, cantidad, referencia, usuario_id=None):
    """
    Registra cualquier flujo de inventario con trazabilidad de usuario.
    """
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    ejecutar_query(
        """INSERT INTO movimientos_inventario
           (fecha, insumo_id, tipo, cantidad, referencia, usuario_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (fecha, insumo_id, tipo, cantidad, referencia, usuario_id)
    )

    operador = "+" if tipo == 'entrada' else "-"
    ejecutar_query(
        f"UPDATE inventario SET stock_actual = stock_actual {operador} ? WHERE id=?",
        (cantidad, insumo_id)
    )

def reponer_stock_por_presentacion(insumo_id, cantidad_presentaciones, usuario_id=None):
    res = ejecutar_query("SELECT cantidad_presentacion FROM inventario WHERE id=?", (insumo_id,), fetch=True)
    if not res: return False
    factor = res[0][0]
    cantidad_base = cantidad_presentaciones * factor
    registrar_movimiento(insumo_id, 'entrada', cantidad_base, f"Compra {cantidad_presentaciones} pres.", usuario_id)
    return True

def actualizar_costo_insumo(insumo_id, costo_pres, cant_pres):
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cb = costo_pres / cant_pres if cant_pres > 0 else 0
    ejecutar_query("UPDATE inventario SET costo_presentacion=?, cantidad_presentacion=?, costo_unitario_base=? WHERE id=?", (costo_pres, cant_pres, cb, insumo_id))
    ejecutar_query("INSERT INTO historial_costos (insumo_id, fecha, costo_unitario) VALUES (?, ?, ?)", (insumo_id, fecha, cb))

def obtener_inventario():
    return ejecutar_query("SELECT id, codigo, nombre, unidad_base, stock_actual, stock_minimo, costo_unitario_base, costo_presentacion, cantidad_presentacion, stock_inicial FROM inventario", fetch=True)

def obtener_flujo_inventario(mes=None):
    if not mes: mes = datetime.now().strftime("%Y-%m")
    insumos = ejecutar_query("SELECT id, nombre, unidad_base, stock_inicial, stock_actual FROM inventario", fetch=True)
    
    reporte = []
    for i_id, nombre, unidad, s_ini, s_act in insumos:
        res_e = ejecutar_query("SELECT SUM(cantidad) FROM movimientos_inventario WHERE insumo_id=? AND tipo='entrada' AND fecha LIKE ?", (i_id, f"{mes}%"), fetch=True)
        entradas = res_e[0][0] or 0
        res_s = ejecutar_query("SELECT SUM(cantidad) FROM movimientos_inventario WHERE insumo_id=? AND tipo='salida' AND fecha LIKE ?", (i_id, f"{mes}%"), fetch=True)
        salidas = res_s[0][0] or 0
        reporte.append({"nombre": nombre, "unidad": unidad, "inicial": s_ini, "entradas": entradas, "salidas": salidas, "final": s_act})
    return reporte