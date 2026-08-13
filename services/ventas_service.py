from datetime import datetime
from database import ejecutar_query
import services.inventario_service as inventario_service

def registrar_venta(producto_id, cantidad_vendida, metodo_pago, usuario_id, negocio_id, fecha_custom=None):
    if fecha_custom and str(fecha_custom).strip():
        fecha = str(fecha_custom).strip()
        if len(fecha) == 10:
            fecha = f"{fecha} 12:00:00"
    else:
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Obtener datos del producto (Filtrado por negocio)
    res = ejecutar_query("SELECT nombre, precio FROM productos WHERE id=? AND negocio_id=?", (producto_id, negocio_id), fetch=True)
    if not res: return False, "Producto no encontrado o no pertenece a su empresa"
    nombre_prod, precio_actual = res[0]
    total_ingreso = precio_actual * cantidad_vendida

    # 2. Obtener receta (Filtrado por negocio)
    insumos_receta = ejecutar_query(
        """SELECT i.id, i.nombre, i.stock_actual, ri.cantidad_usada, i.unidad_base 
           FROM producto_insumo ri 
           JOIN inventario i ON ri.insumo_id = i.id 
           WHERE ri.producto_id = ? AND ri.negocio_id = ?""",
        (producto_id, negocio_id), fetch=True
    )
    
    # 3. Validar Stock y Calcular Costo
    costo_total_momento = 0
    items_a_descontar = []
    insumos_insuficientes = []

    for i_id, i_nombre, stock_actual, cant_receta, unidad in insumos_receta:
        cant_necesaria = cant_receta * cantidad_vendida
        if stock_actual < cant_necesaria:
            falta = cant_necesaria - stock_actual
            insumos_insuficientes.append(f"{i_nombre} (Faltan {falta:.2f} {unidad})")
        
        res_c = ejecutar_query("SELECT costo_unitario_base FROM inventario WHERE id=? AND negocio_id=?", (i_id, negocio_id), fetch=True)
        costo_unit = res_c[0][0] if res_c else 0
        costo_total_momento += costo_unit * cant_necesaria
        items_a_descontar.append((i_id, cant_necesaria))

    if insumos_insuficientes:
        return False, "Stock insuficiente: " + ", ".join(insumos_insuficientes)

    # 4. Procesar transacción con Multi-tenancy
    try:
        ejecutar_query(
            """INSERT INTO ventas (negocio_id, fecha, producto_id, cantidad, total, metodo_pago, costo_historico_total, precio_historico_unitario, usuario_id) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (negocio_id, fecha, producto_id, cantidad_vendida, total_ingreso, metodo_pago, costo_total_momento, precio_actual, usuario_id)
        )

        for insumo_id, cant_desc in items_a_descontar:
            inventario_service.registrar_movimiento(
                insumo_id, 'salida', cant_desc, f"Venta {nombre_prod}", usuario_id, negocio_id
            )

        return True, total_ingreso
    except Exception as e:
        return False, f"Error en la transacción: {str(e)}"