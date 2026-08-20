import json
from database import ejecutar_query
from datetime import datetime

def registrar_compra_lote(insumo_id, codigo_lote, cantidad, costo_unitario, negocio_id, usuario_id, fecha_vencimiento=None, proveedor="", numero_factura="", observaciones="", fecha_compra=None):
    try:
        cantidad = float(cantidad)
        costo_unitario = float(costo_unitario)
        if cantidad <= 0 or costo_unitario < 0:
            return False, "La cantidad comprada debe ser mayor a cero y el costo no puede ser negativo."

        codigo_lote = (codigo_lote or '').strip()
        if not codigo_lote:
            codigo_lote = f"LOT-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        if fecha_compra and str(fecha_compra).strip():
            f_compra = str(fecha_compra).strip()
            if len(f_compra) == 10:
                f_compra = f"{f_compra} 12:00:00"
        else:
            f_compra = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        costo_total = cantidad * costo_unitario

        # 1. Registrar Transacción de Compra / Entrada
        ejecutar_query(
            """INSERT INTO compras_entradas (negocio_id, fecha_compra, proveedor, numero_factura, insumo_id, codigo_lote, cantidad_comprada, costo_unitario_compra, costo_total_compra, fecha_vencimiento, observaciones, usuario_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (negocio_id, f_compra, proveedor, numero_factura, insumo_id, codigo_lote, cantidad, costo_unitario, costo_total, fecha_vencimiento, observaciones, usuario_id)
        )

        c_res = ejecutar_query("SELECT id FROM compras_entradas WHERE negocio_id=? ORDER BY id DESC LIMIT 1", (negocio_id,), fetch=True)
        compra_id = c_res[0][0] if c_res else None

        # 2. Registrar el Lote en Almacén
        ejecutar_query(
            """INSERT INTO lotes_inventario (negocio_id, compra_id, insumo_id, codigo_lote, fecha_compra, fecha_vencimiento, cantidad_inicial, cantidad_disponible, costo_unitario, proveedor, numero_factura, estado)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVO')""",
            (negocio_id, compra_id, insumo_id, codigo_lote, f_compra[:10], fecha_vencimiento, cantidad, cantidad, costo_unitario, proveedor, numero_factura)
        )

        l_res = ejecutar_query("SELECT id FROM lotes_inventario WHERE negocio_id=? ORDER BY id DESC LIMIT 1", (negocio_id,), fetch=True)
        lote_id = l_res[0][0] if l_res else None

        # 3. Movimiento de Entrada
        if lote_id:
            ejecutar_query(
                """INSERT INTO movimientos_lote (negocio_id, lote_id, fecha, tipo, cantidad, costo_unitario_lote, costo_subtotal, referencia, usuario_id)
                   VALUES (?, ?, ?, 'ENTRADA', ?, ?, ?, 'Compra de Inventario', ?)""",
                (negocio_id, lote_id, f_compra, cantidad, costo_unitario, costo_total, usuario_id)
            )

        # 4. Actualizar Consolidado de Inventario (Única fuente de verdad)
        sincronizar_stock_consolidado(insumo_id, negocio_id)

        return True, {"compra_id": compra_id, "lote_id": lote_id, "codigo_lote": codigo_lote}
    except Exception as e:
        return False, f"Error al registrar compra y lote: {str(e)}"

def sincronizar_stock_consolidado(insumo_id, negocio_id):
    try:
        res = ejecutar_query(
            "SELECT SUM(cantidad_disponible) FROM lotes_inventario WHERE insumo_id=? AND negocio_id=? AND estado='ACTIVO'",
            (insumo_id, negocio_id), fetch=True
        )
        total_lotes = res[0][0] or 0.0 if res else 0.0

        ejecutar_query(
            "UPDATE inventario SET stock_actual=? WHERE id=? AND negocio_id=?",
            (total_lotes, insumo_id, negocio_id)
        )
    except Exception as e:
        print(f"Error sincronizando stock consolidado: {e}")

def consumir_lotes_insumo(insumo_id, cantidad_necesaria, negocio_id, venta_id=None, usuario_id=None):
    try:
        cantidad_necesaria = float(cantidad_necesaria)
        if cantidad_necesaria <= 0:
            return True, 0.0, []

        # Configuración del negocio
        conf_res = ejecutar_query(
            "SELECT metodo_salida_lotes, bloquear_lotes_vencidos FROM configuracion_negocio WHERE negocio_id=?",
            (negocio_id,), fetch=True
        )
        metodo = conf_res[0][0] if conf_res and conf_res[0][0] else 'FEFO'
        bloquear_vencidos = conf_res[0][1] if conf_res and conf_res[0][1] else 'SI'

        # Obtener lotes activos
        lotes_raw = ejecutar_query(
            """SELECT id, codigo_lote, fecha_compra, fecha_vencimiento, cantidad_disponible, costo_unitario
               FROM lotes_inventario
               WHERE insumo_id=? AND negocio_id=? AND estado='ACTIVO' AND cantidad_disponible > 0.0001""",
            (insumo_id, negocio_id), fetch=True
        ) or []

        if not lotes_raw:
            # Fallback costo del inventario general si no hay lotes registrados
            inv_res = ejecutar_query("SELECT costo_unitario_base FROM inventario WHERE id=? AND negocio_id=?", (insumo_id, negocio_id), fetch=True)
            costo_base = inv_res[0][0] if inv_res else 0.0
            return True, costo_base * cantidad_necesaria, []

        hoy_str = datetime.now().strftime("%Y-%m-%d")

        # Filtrar o advertir lotes vencidos
        lotes = []
        for l in lotes_raw:
            l_id, l_cod, l_fc, l_fv, l_cant, l_cost = l
            es_vencido = bool(l_fv and str(l_fv).strip() and str(l_fv).strip() < hoy_str)
            if es_vencido and bloquear_vencidos == 'SI':
                continue
            lotes.append({
                "id": l_id, "codigo": l_cod, "fecha_compra": l_fc or '',
                "fecha_vencimiento": l_fv or '', "disponible": float(l_cant),
                "costo_unitario": float(l_cost), "es_vencido": es_vencido
            })

        # Regla de Ordenación FEFO / FIFO
        if metodo == 'FEFO':
            # FEFO: 1º con vencimiento por fecha_vencimiento ASC, 2º sin vencimiento por fecha_compra ASC
            def fefo_key(l):
                has_fv = 0 if (l['fecha_vencimiento'] and l['fecha_vencimiento'].strip()) else 1
                fv_str = l['fecha_vencimiento'] if has_fv == 0 else '9999-99-99'
                fc_str = l['fecha_compra'] or '9999-99-99'
                return (has_fv, fv_str, fc_str)

            lotes.sort(key=fefo_key)
        else:
            # FIFO: fecha_compra ASC
            lotes.sort(key=lambda l: l['fecha_compra'] or '9999-99-99')

        # Procesar consumo secuencial
        restante = cantidad_necesaria
        costo_total_consumido = 0.0
        trace_lotes = []
        fecha_mov = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for l in lotes:
            if restante <= 0.00001:
                break

            cant_a_tomar = min(l['disponible'], restante)
            costo_subtotal = cant_a_tomar * l['costo_unitario']

            nuevo_disp = l['disponible'] - cant_a_tomar
            nuevo_estado = 'AGOTADO' if nuevo_disp <= 0.0001 else 'ACTIVO'

            # Actualizar lote
            ejecutar_query(
                "UPDATE lotes_inventario SET cantidad_disponible=?, estado=? WHERE id=? AND negocio_id=?",
                (nuevo_disp, nuevo_estado, l['id'], negocio_id)
            )

            # Registrar movimiento del lote
            ejecutar_query(
                """INSERT INTO movimientos_lote (negocio_id, lote_id, fecha, tipo, cantidad, costo_unitario_lote, costo_subtotal, referencia, venta_id, usuario_id)
                   VALUES (?, ?, ?, 'SALIDA_VENTA', ?, ?, ?, ?, ?, ?)""",
                (negocio_id, l['id'], fecha_mov, cant_a_tomar, l['costo_unitario'], costo_subtotal, f"Venta #{venta_id}" if venta_id else "Consumo Venta", venta_id, usuario_id)
            )

            costo_total_consumido += costo_subtotal
            restante -= cant_a_tomar
            trace_lotes.append({
                "lote_id": l['id'],
                "codigo_lote": l['codigo'],
                "cantidad_tomada": cant_a_tomar,
                "costo_unitario": l['costo_unitario'],
                "costo_subtotal": costo_subtotal
            })

        # Sincronizar stock consolidado
        sincronizar_stock_consolidado(insumo_id, negocio_id)

        return True, costo_total_consumido, trace_lotes
    except Exception as e:
        print(f"Error en consumos de lotes: {e}")
        return False, 0.0, []

def obtener_lotes(negocio_id, insumo_id=None, estado_filtro=None):
    try:
        query = """
            SELECT l.id, l.insumo_id, i.nombre as insumo_nombre, l.codigo_lote, l.fecha_compra,
                   l.fecha_vencimiento, l.cantidad_inicial, l.cantidad_disponible, l.costo_unitario,
                   l.proveedor, l.numero_factura, l.estado
            FROM lotes_inventario l
            LEFT JOIN inventario i ON l.insumo_id = i.id
            WHERE l.negocio_id=?
        """
        params = [negocio_id]

        if insumo_id:
            query += " AND l.insumo_id=?"
            params.append(insumo_id)

        if estado_filtro:
            query += " AND l.estado=?"
            params.append(estado_filtro)

        query += " ORDER BY l.id DESC"
        res = ejecutar_query(query, params, fetch=True) or []

        hoy_str = datetime.now().strftime("%Y-%m-%d")

        out = []
        for x in res:
            l_id, i_id, i_nom, cod, fc, fv, cant_i, cant_d, cost, prov, fact, est = x
            es_vencido = bool(fv and fv.strip() and fv.strip() < hoy_str and cant_d > 0.001)

            out.append({
                "id": l_id, "insumo_id": i_id, "insumo": i_nom or "Insumo",
                "codigo_lote": cod, "fecha_compra": fc or '', "fecha_vencimiento": fv or 'Sin vencimiento',
                "cantidad_inicial": cant_i, "cantidad_disponible": cant_d,
                "costo_unitario": cost, "costo_total_disponible": cant_d * cost,
                "proveedor": prov or 'N/A', "numero_factura": fact or 'N/A',
                "estado": est, "es_vencido": es_vencido
            })
        return out
    except Exception as e:
        print(f"Error obteniendo lotes: {e}")
        return []

def guardar_configuracion_informe(negocio_id, nombre_informe, tipo_objeto, columnas, filtros, agrupacion=None):
    try:
        nombre_informe = (nombre_informe or '').strip()
        if not nombre_informe:
            return False, "El nombre del informe es obligatorio."

        col_str = json.dumps(columnas) if isinstance(columnas, (list, dict)) else str(columnas)
        fil_str = json.dumps(filtros) if isinstance(filtros, (list, dict)) else str(filtros)
        agr_str = json.dumps(agrupacion) if agrupacion else ""
        fecha_creacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        ejecutar_query(
            """INSERT INTO informes_guardados (negocio_id, nombre_informe, tipo_objeto, columnas_json, filtros_json, agrupacion_json, fecha_creacion)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (negocio_id, nombre_informe, tipo_objeto, col_str, fil_str, agr_str, fecha_creacion)
        )
        return True, "Configuración de informe guardada con éxito."
    except Exception as e:
        return False, f"Error al guardar informe: {str(e)}"

def obtener_informes_guardados(negocio_id):
    try:
        res = ejecutar_query(
            "SELECT id, nombre_informe, tipo_objeto, columnas_json, filtros_json, agrupacion_json, fecha_creacion FROM informes_guardados WHERE negocio_id=? ORDER BY id DESC",
            (negocio_id,), fetch=True
        ) or []

        out = []
        for x in res:
            out.append({
                "id": x[0],
                "nombre": x[1],
                "tipo_objeto": x[2],
                "columnas": json.loads(x[3]) if x[3] else [],
                "filtros": json.loads(x[4]) if x[4] else {},
                "agrupacion": json.loads(x[5]) if x[5] else {},
                "fecha_creacion": x[6]
            })
        return out
    except Exception as e:
        print(f"Error obteniendo informes guardados: {e}")
        return []

def reagrupar_lotes_post_cargue(negocio_id, criterio):
    """
    Reagrupa los lotes de inventario post-cargue según el criterio seleccionado por el emprendedor.
    Criterios: 'FECHA_TRM', 'PEDIDO_NUM', 'FECHA_PROVEEDOR', 'MES_COMPRA', 'PROVEEDOR', 'INDIVIDUAL', 'MASTER_UNICO'
    """
    try:
        crit = (criterio or 'FECHA_TRM').strip().upper()
        rows = ejecutar_query(
            "SELECT id, fecha_compra, proveedor, importacion_id FROM lotes_inventario WHERE negocio_id=?",
            (negocio_id,), fetch=True
        ) or []

        for r in rows:
            lid, fcomp, prov, imp_id = r[0], r[1] or '', r[2] or 'PROV', r[3] or 'IMP'
            f_clean = fcomp[:10] if fcomp else 'FECHA'
            m_clean = fcomp[:7] if fcomp else 'MES'

            if crit == 'PEDIDO_NUM':
                new_code = f"PED-{imp_id[-6:]}" if imp_id else f"PED-{f_clean}"
            elif crit == 'FECHA_PROVEEDOR':
                p_clean = prov.replace(' ', '_')[:8].upper()
                new_code = f"LOT-{f_clean}-{p_clean}"
            elif crit == 'MES_COMPRA':
                new_code = f"LOT-{m_clean}"
            elif crit == 'PROVEEDOR':
                p_clean = prov.replace(' ', '_')[:12].upper()
                new_code = f"LOT-PROV-{p_clean}"
            elif crit == 'INDIVIDUAL':
                new_code = f"LOTE-{lid}"
            elif crit == 'MASTER_UNICO':
                new_code = f"IMP-{imp_id[-6:]}" if imp_id else "LOTE-MAESTRO"
            else:
                # FECHA_TRM
                new_code = f"IMP-{imp_id[-6:]}" if imp_id else f"LOT-{f_clean}"

            ejecutar_query(
                "UPDATE lotes_inventario SET codigo_lote=? WHERE id=? AND negocio_id=?",
                (new_code, lid, negocio_id)
            )

        return True, "Lotes reagrupados correctamente en la base de datos."
    except Exception as e:
        print(f"Error en reagrupar_lotes_post_cargue: {e}")
        return False, str(e)

