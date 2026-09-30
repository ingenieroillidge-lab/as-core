from datetime import datetime
from database import ejecutar_query, transaccion, insertar_con_id
import services.inventario_service as inventario_service
import services.lotes_service as lotes_service

def registrar_venta(producto_id, cantidad_vendida, metodo_pago, usuario_id, negocio_id, fecha_custom=None):
    """Compatibilidad: devuelve (ok, total | mensaje)."""
    ok, r, _vid = registrar_venta_con_id(producto_id, cantidad_vendida, metodo_pago, usuario_id, negocio_id, fecha_custom)
    return ok, r


def registrar_venta_con_id(producto_id, cantidad_vendida, metodo_pago, usuario_id, negocio_id, fecha_custom=None):
    """Devuelve (ok, total | mensaje, venta_id). El id viene del propio INSERT (sin 'ORDER BY id DESC LIMIT 1')."""
    if not cantidad_vendida or float(cantidad_vendida) <= 0:
        return False, "La cantidad debe ser mayor a cero", None
    if fecha_custom and str(fecha_custom).strip():
        fecha = str(fecha_custom).strip()
        if len(fecha) == 10:
            fecha = f"{fecha} 12:00:00"
    else:
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Obtener datos del producto (Filtrado por negocio)
    res = ejecutar_query("SELECT nombre, precio FROM productos WHERE id=? AND negocio_id=?", (producto_id, negocio_id), fetch=True)
    if not res: return False, "Producto no encontrado o no pertenece a su empresa", None
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
        return False, "Stock insuficiente: " + ", ".join(insumos_insuficientes), None

    # 4. Procesar transacción con Multi-tenancy
    try:
        # Insertar venta inicial y obtener su id en la misma operación
        with transaccion() as (cur, ph, is_pg):
            venta_id = insertar_con_id(
                cur,
                """INSERT INTO ventas (negocio_id, fecha, producto_id, cantidad, total, metodo_pago, costo_historico_total, precio_historico_unitario, usuario_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (negocio_id, fecha, producto_id, cantidad_vendida, total_ingreso, metodo_pago, costo_total_momento, precio_actual, usuario_id),
                ph, is_pg)

        # Si maneja lotes, consumir secuencialmente por FEFO/FIFO
        if maneja_lotes == 1:
            costo_lotes_total = 0.0
            for insumo_id, cant_desc in items_a_descontar:
                ok, c_costo, traza = lotes_service.consumir_lotes_insumo(insumo_id, cant_desc, negocio_id, venta_id=venta_id, usuario_id=usuario_id)
                if ok:
                    costo_lotes_total += c_costo
                inventario_service.registrar_movimiento(insumo_id, 'salida', cant_desc, f"Venta #{venta_id} {nombre_prod}", usuario_id, negocio_id, ajustar_stock=not traza)  # con lotes el stock ya se sincronizó
            
            # Actualizar venta con el costo histórico exacto asignado por lotes
            ejecutar_query("UPDATE ventas SET costo_historico_total=? WHERE id=? AND negocio_id=?", (costo_lotes_total, venta_id, negocio_id))
        else:
            for insumo_id, cant_desc in items_a_descontar:
                inventario_service.registrar_movimiento(
                    insumo_id, 'salida', cant_desc, f"Venta {nombre_prod}", usuario_id, negocio_id
                )

        return True, total_ingreso, venta_id
    except Exception as e:
        return False, f"Error en la transacción: {str(e)}", None

def eliminar_venta(venta_id, negocio_id, usuario_id):
    """
    Elimina una venta almacenada y reintegra el stock correspondiente al inventario.
    Solo debe ser invocado por administradores del negocio.
    """
    try:
        # 1. Obtener la venta
        res = ejecutar_query(
            "SELECT producto_id, cantidad FROM ventas WHERE id=? AND negocio_id=?",
            (venta_id, negocio_id), fetch=True
        )
        if not res:
            return False, "Venta no encontrada o no pertenece a la empresa"

        producto_id, cantidad_vendida = res[0]

        # 2. Obtener receta para reintegrar stock
        insumos_receta = ejecutar_query(
            """SELECT i.id, ri.cantidad_usada 
               FROM producto_insumo ri 
               JOIN inventario i ON ri.insumo_id = i.id 
               WHERE ri.producto_id = ? AND ri.negocio_id = ?""",
            (producto_id, negocio_id), fetch=True
        ) or []

        movs_lote = ejecutar_query(
            "SELECT lote_id, cantidad FROM movimientos_lote WHERE venta_id=? AND negocio_id=?",
            (venta_id, negocio_id), fetch=True
        ) or []

        # Con lotes, el stock se reconstruye desde los lotes (evita sumar dos veces); sin lotes, se reintegra por receta.
        for i_id, cant_receta in insumos_receta:
            cant_reintegrar = cant_receta * cantidad_vendida
            inventario_service.registrar_movimiento(
                i_id, 'entrada', cant_reintegrar, f"Reversión / Anulación Venta #{venta_id}", usuario_id, negocio_id,
                ajustar_stock=not movs_lote
            )

        # 3. Revertir lotes (y reactivar los que quedaron AGOTADO)
        insumos_lote = set()
        for lote_id, cant_lote in movs_lote:
            ejecutar_query(
                "UPDATE lotes_inventario SET cantidad_disponible = cantidad_disponible + ?, estado='ACTIVO' WHERE id=? AND negocio_id=?",
                (cant_lote, lote_id, negocio_id)
            )
            r = ejecutar_query("SELECT insumo_id FROM lotes_inventario WHERE id=? AND negocio_id=?", (lote_id, negocio_id), fetch=True)
            if r: insumos_lote.add(r[0][0])
        if movs_lote:
            ejecutar_query("DELETE FROM movimientos_lote WHERE venta_id=? AND negocio_id=?", (venta_id, negocio_id))
            for ins in insumos_lote:
                lotes_service.sincronizar_stock_consolidado(ins, negocio_id)

        # 4. Eliminar abonos de cartera asociados a la venta si existen
        ejecutar_query("DELETE FROM abonos_cartera WHERE venta_id=? AND negocio_id=?", (venta_id, negocio_id))

        # 5. Eliminar la venta
        ejecutar_query("DELETE FROM ventas WHERE id=? AND negocio_id=?", (venta_id, negocio_id))

        return True, "Venta eliminada exitosamente y stock reintegrado al inventario"
    except Exception as e:
        return False, f"Error al eliminar la venta: {str(e)}"

def modificar_venta(venta_id, negocio_id, usuario_id, datos):
    """
    Modifica una venta existente. Permite actualizar método de pago, fecha, total, observaciones o cantidad.
    Solo disponible para administradores del negocio.
    """
    try:
        res = ejecutar_query(
            "SELECT id, producto_id, cantidad, total FROM ventas WHERE id=? AND negocio_id=?",
            (venta_id, negocio_id), fetch=True
        )
        if not res:
            return False, "Venta no encontrada"

        _, p_id_actual, cant_actual, total_actual = res[0]

        metodo_pago = datos.get('metodo_pago')
        fecha = datos.get('fecha')
        nueva_cant = float(datos.get('cantidad', cant_actual))
        nuevo_total = float(datos.get('total', total_actual))
        observacion = datos.get('observacion')
        cliente_nombre = datos.get('cliente_nombre')

        # Ajuste de inventario si cambia la cantidad
        if nueva_cant != cant_actual:
            diferencia = nueva_cant - cant_actual
            insumos_receta = ejecutar_query(
                "SELECT insumo_id, cantidad_usada FROM producto_insumo WHERE producto_id=? AND negocio_id=?",
                (p_id_actual, negocio_id), fetch=True
            ) or []

            for i_id, cant_receta in insumos_receta:
                cant_ajuste = abs(diferencia) * cant_receta
                if diferencia > 0:
                    inventario_service.registrar_movimiento(
                        i_id, 'salida', cant_ajuste, f"Ajuste Venta #{venta_id} (+cant)", usuario_id, negocio_id
                    )
                else:
                    inventario_service.registrar_movimiento(
                        i_id, 'entrada', cant_ajuste, f"Ajuste Venta #{venta_id} (-cant)", usuario_id, negocio_id
                    )

        campos = ["cantidad = ?", "total = ?"]
        params = [nueva_cant, nuevo_total]

        if metodo_pago:
            campos.append("metodo_pago = ?")
            params.append(metodo_pago)
        if fecha:
            campos.append("fecha = ?")
            params.append(fecha)
        if observacion is not None:
            campos.append("observacion = ?")
            params.append(observacion)
        if cliente_nombre is not None:
            campos.append("cliente_nombre = ?")
            params.append(cliente_nombre)

        params.extend([venta_id, negocio_id])
        query_sql = f"UPDATE ventas SET {', '.join(campos)} WHERE id=? AND negocio_id=?"
        ejecutar_query(query_sql, params)

        return True, "Venta actualizada exitosamente"
    except Exception as e:
        return False, f"Error al modificar la venta: {str(e)}"