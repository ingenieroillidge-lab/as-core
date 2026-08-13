from datetime import datetime
from database import ejecutar_query
import services.inventario_service as inventario_service
import services.lotes_service as lotes_service

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

    # Verificar si el negocio maneja lotes
    conf_lotes = ejecutar_query("SELECT maneja_lotes FROM configuracion_negocio WHERE negocio_id=?", (negocio_id,), fetch=True)
    maneja_lotes = conf_lotes[0][0] if conf_lotes and conf_lotes[0][0] else 0

    # 2. Obtener receta (Filtrado por negocio)
    insumos_receta = ejecutar_query(
        """SELECT i.id, i.nombre, i.stock_actual, ri.cantidad_usada, i.unidad_base 
           FROM producto_insumo ri 
           JOIN inventario i ON ri.insumo_id = i.id 
           WHERE ri.producto_id = ? AND ri.negocio_id = ?""",
        (producto_id, negocio_id), fetch=True
    )
    
    # 3. Validar Stock y Calcular Costo Real por Lotes
    costo_total_momento = 0.0
    items_a_descontar = []
    insumos_insuficientes = []

    for i_id, i_nombre, stock_actual, cant_receta, unidad in insumos_receta:
        cant_necesaria = cant_receta * cantidad_vendida
        if stock_actual < cant_necesaria:
            falta = cant_necesaria - stock_actual
            insumos_insuficientes.append(f"{i_nombre} (Faltan {falta:.2f} {unidad})")
        
        items_a_descontar.append((i_id, cant_necesaria))

        if maneja_lotes != 1:
            res_c = ejecutar_query("SELECT costo_unitario_base FROM inventario WHERE id=? AND negocio_id=?", (i_id, negocio_id), fetch=True)
            costo_unit = res_c[0][0] if res_c else 0
            costo_total_momento += costo_unit * cant_necesaria

    if insumos_insuficientes:
        return False, "Stock insuficiente: " + ", ".join(insumos_insuficientes)

    # 4. Procesar transacción con Multi-tenancy
    try:
        # Insertar venta inicial
        ejecutar_query(
            """INSERT INTO ventas (negocio_id, fecha, producto_id, cantidad, total, metodo_pago, costo_historico_total, precio_historico_unitario, usuario_id) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (negocio_id, fecha, producto_id, cantidad_vendida, total_ingreso, metodo_pago, costo_total_momento, precio_actual, usuario_id)
        )

        v_res = ejecutar_query("SELECT id FROM ventas WHERE negocio_id=? ORDER BY id DESC LIMIT 1", (negocio_id,), fetch=True)
        venta_id = v_res[0][0] if v_res else None

        # Si maneja lotes, consumir secuencialmente por FEFO/FIFO
        if maneja_lotes == 1:
            costo_lotes_total = 0.0
            for insumo_id, cant_desc in items_a_descontar:
                ok, c_costo, _ = lotes_service.consumir_lotes_insumo(insumo_id, cant_desc, negocio_id, venta_id=venta_id, usuario_id=usuario_id)
                if ok:
                    costo_lotes_total += c_costo
                inventario_service.registrar_movimiento(insumo_id, 'salida', cant_desc, f"Venta #{venta_id} {nombre_prod}", usuario_id, negocio_id)
            
            # Actualizar venta con el costo histórico exacto asignado por lotes
            ejecutar_query("UPDATE ventas SET costo_historico_total=? WHERE id=? AND negocio_id=?", (costo_lotes_total, venta_id, negocio_id))
        else:
            for insumo_id, cant_desc in items_a_descontar:
                inventario_service.registrar_movimiento(
                    insumo_id, 'salida', cant_desc, f"Venta {nombre_prod}", usuario_id, negocio_id
                )

        return True, total_ingreso
    except Exception as e:
        return False, f"Error en la transacción: {str(e)}"