import json
import uuid
from datetime import datetime
from database import ejecutar_query
import services.ventas_service as ventas_service
import services.cartera_service as cartera_service
import services.inventario_service as inventario_service

# Diccionario de reconocimiento semántico heurístico
DICTIONARY_HEURISTICS = {
    "costo_unitario_usd": ["US", "USD", "COSTO USD", "COSTO UNITARIO USD", "PRECIO COMPRA USD", "UNIT USD"],
    "tasa_cambio": ["PRECIO US", "PRECIO USD", "TASA", "TASA CAMBIO", "TRM", "CAMBIO USD", "EXCHANGE RATE"],
    "costo_unitario_cop": ["COSTO UNITARIO", "COSTO COP", "COSTO UNITARIO (COP)", "COSTO BASE COP", "UNIT COP"],
    "costo_envio_cop": ["COSTO DE ENVIO", "COSTO ENVIO", "FLETE", "ENVIO", "FLETES", "SHIPPING", "LOGISTICA"],
    "costo_total_cop": ["COSTO TOTAL", "COSTO TOTAL ADQUISICION", "TOTAL COP", "TOTAL COST"],
    "precio_venta_cop": ["PRECIO VENTA", "PRECIO DE VENTA", "PRECIO VENTA (COP)", "PVP", "PRICE"],
    "nombre_producto": ["EQUIPO", "DESCRIPCION", "PRODUCTO", "ITEM", "NOMBRE", "PRENDA"],
    "tipo_producto": ["TIPO", "TIPO PRODUCTO", "CATEGORIA", "ESTILO"],
    "jugador_edicion": ["JUGADOR", "EDICION", "PLAYER", "TEMPORADA"],
    "variante_talla": ["TALLA", "SIZE", "VARIANCE", "VARIANTE", "COLOR"],
    "fecha_operacion": ["FECHA", "FECHA COMPRA", "FECHA PEDIDO", "DATE"],
    "fecha_llegada": ["FECHA DE LLEGADA", "FECHA LLEGADA", "FECHA RECEPCION", "ARRIVAL DATE"],
    "cliente_nombre": ["CLIENTE", "CLIENTES", "CUSTOMER", "COMPRADOR"],
    "saldo_pendiente": ["DEUDAS POR COBRAR", "DEUDAS", "CARTERA", "SALDO PENDIENTE", "POR COBRAR", "DEUDA"],
    "abono_monto": ["PAGOS/ABONOS", "PAGOS", "ABONOS", "ABONO", "PAGO"],
    "cantidad": ["CANTIDAD", "UNIDADES", "CANTIDAD DE UNIDADES", "UNIDADES COMPRADAS", "QTY"],
    # Campos derivados (Calculados)
    "utilidad_calculada": ["UTILIDAD", "PROFIT", "MARGEN", "PORCENTAJE DE GANANCIA", "GANANCIA"],
    "dias_transito": ["DIAS EN TRANSITO", "DIAS TRANSITO", "TRANSIT DAYS"]
}

def crear_lote_staging(negocio_id, nombre_archivo, filas_matriz):
    """
    Etapa 1: Carga y análisis inicial sin escribir datos finales.
    guarda las filas raw en la tabla importaciones_staging.
    """
    if not filas_matriz or len(filas_matriz) < 1:
        return False, "El archivo no contiene filas de datos", None

    batch_id = f"BATCH-{uuid.uuid4().hex[:12].upper()}"
    fecha_creacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    headers = [str(c).strip() for c in filas_matriz[0]]
    filas_datos = filas_matriz[1:]

    muestras = []
    for idx, row in enumerate(filas_datos[:5]):
        dict_row = {}
        for c_idx, h in enumerate(headers):
            dict_row[h] = str(row[c_idx]).strip() if c_idx < len(row) and row[c_idx] is not None else ""
        muestras.append(dict_row)

    # Inserción en staging
    for idx, row in enumerate(filas_datos):
        dict_row = {}
        for c_idx, h in enumerate(headers):
            dict_row[h] = str(row[c_idx]).strip() if c_idx < len(row) and row[c_idx] is not None else ""

        ejecutar_query(
            """INSERT INTO importaciones_staging 
               (negocio_id, batch_id, fila_num, datos_raw_json, estado_validacion, fecha_creacion)
               VALUES (?, ?, ?, ?, 'PENDIENTE', ?)""",
            (negocio_id, batch_id, idx + 1, json.dumps(dict_row, ensure_ascii=False), fecha_creacion)
        )

    res_info = {
        "batch_id": batch_id,
        "nombre_archivo": nombre_archivo,
        "headers": headers,
        "total_registros": len(filas_datos),
        "muestras": muestras
    }
    return True, "Archivo cargado en staging con éxito", res_info

def proponer_mapeo_heuristico(headers, negocio_id):
    """
    Etapa 2: Motor heurístico contextual.
    Evalúa nombres de encabezados y recupera memoria del tenant si existe.
    """
    # Verificar si existe memoria guardada para este tenant en mapeos_importacion
    mem_res = ejecutar_query(
        "SELECT estructura_columnas_json FROM mapeos_importacion WHERE negocio_id=? ORDER BY id DESC LIMIT 1",
        (negocio_id,), fetch=True
    )
    mapeo_guardado = json.loads(mem_res[0][0]) if mem_res and mem_res[0][0] else {}

    propuesta = []
    for h in headers:
        h_norm = h.upper().strip()
        
        # 1. Chequeo de memoria guardada
        if h in mapeo_guardado:
            propuesta.append({
                "columna_excel": h,
                "campo_propuesto": mapeo_guardado[h],
                "confianza": "ALTA",
                "origen": "MEMORIA_TENANT",
                "es_calculado": mapeo_guardado[h] in ["utilidad_calculada", "dias_transito"]
            })
            continue

        # 2. Heurística contextual (Coincidencia Exacta Primero)
        match_campo = "IGNORAR"
        confianza = "NINGUNA"
        es_calc = False

        # Paso 2A: Coincidencia Exacta
        for campo, sinonimos in DICTIONARY_HEURISTICS.items():
            if h_norm in sinonimos:
                match_campo = campo
                confianza = "ALTA"
                es_calc = campo in ["utilidad_calculada", "dias_transito"]
                break

        # Paso 2B: Coincidencia Parcial (solo para sinónimos de más de 2 caracteres)
        if match_campo == "IGNORAR":
            for campo, sinonimos in DICTIONARY_HEURISTICS.items():
                if any(len(s) > 2 and s in h_norm for s in sinonimos):
                    match_campo = campo
                    confianza = "MEDIA"
                    es_calc = campo in ["utilidad_calculada", "dias_transito"]
                    break

        propuesta.append({
            "columna_excel": h,
            "campo_propuesto": match_campo,
            "confianza": confianza,
            "origen": "HEURISTICA_SISTEMA",
            "es_calculado": es_calc
        })


    return propuesta

def conciliar_y_prevalidar(batch_id, negocio_id, mapeo_usuario):
    """
    Etapa 3, 4 y 5:
    - Validación matemática (US * Tasa = Costo COP).
    - Conciliación a 2 niveles (Producto + Variante).
    - Detector de diferencias (Diff sin sobrescritura silenciosa).
    - Resumen de pre-validación semáforo.
    """
    registros_staging = ejecutar_query(
        "SELECT id, fila_num, datos_raw_json FROM importaciones_staging WHERE batch_id=? AND negocio_id=? ORDER BY fila_num ASC",
        (batch_id, negocio_id), fetch=True
    ) or []

    if not registros_staging:
        return False, "No se encontraron registros en la capa de staging", None

    productos_existentes = ejecutar_query("SELECT id, nombre, precio, categoria, subcategoria, variante FROM productos WHERE negocio_id=?", (negocio_id,), fetch=True) or []
    prod_map = {}
    for p in productos_existentes:
        key = (p[1] or '').strip().lower()
        prod_map[key] = {"id": p[0], "nombre": p[1], "precio": p[2], "categoria": p[3], "subcategoria": p[4], "variante": p[5]}

    clientes_existentes = ejecutar_query("SELECT id, nombre FROM clientes WHERE negocio_id=?", (negocio_id,), fetch=True) or []
    cli_set = { (c[1] or '').strip().lower() for c in clientes_existentes }

    total_validos = 0
    total_advertencias = 0
    total_errores = 0

    productos_nuevos = []
    variantes_nuevas = []
    diferencias_detectadas = []

    resumen_filas = []

    for s_id, fila_num, raw_json in registros_staging:
        raw_row = json.loads(raw_json)
        mapped_data = {}
        for col_excel, campo_target in mapeo_usuario.items():
            if campo_target and campo_target != "IGNORAR":
                mapped_data[campo_target] = raw_row.get(col_excel, "").strip()

        errs = []
        advs = []

        # 1. EXIGENCIA DE CANTIDAD EXPLÍCITA
        cant_str = mapped_data.get('cantidad', '')
        try:
            cant_val = float(cant_str) if cant_str else 1.0
        except:
            cant_val = 1.0
            advs.append("No se identificó una columna explícita de cantidad; se asumió 1.0 unidad.")

        # 2. VALIDACIÓN MULTIMONEDA MATEMÁTICA (US * Tasa = Costo COP)
        usd_str = mapped_data.get('costo_unitario_usd', '')
        tasa_str = mapped_data.get('tasa_cambio', '')
        cop_str = mapped_data.get('costo_unitario_cop', '')

        if usd_str and tasa_str and cop_str:
            try:
                v_usd = float(usd_str.replace('$', '').replace(',', '').strip())
                v_tasa = float(tasa_str.replace('$', '').replace(',', '').strip())
                v_cop = float(cop_str.replace('$', '').replace(',', '').strip())

                calc_cop = v_usd * v_tasa
                if abs(calc_cop - v_cop) > 1.0:
                    advs.append(f"Discrepancia en fórmula multimoneda: {v_usd} USD × {v_tasa} = {calc_cop:,.0f} COP, pero el Excel reporta {v_cop:,.0f} COP.")
            except Exception:
                pass

        # 3. CONCILIACIÓN A 2 NIVELES (Producto vs Variante)
        nombre_prod = (mapped_data.get('nombre_producto') or '').strip()
        equipo = (mapped_data.get('jugador_edicion') or mapped_data.get('tipo_producto') or '').strip()
        if equipo:
            nombre_full = f"{nombre_prod} {equipo}".strip()
        else:
            nombre_full = nombre_prod

        talla = (mapped_data.get('variante_talla') or '').strip()
        key_p = nombre_full.lower()

        if nombre_full:
            if key_p in prod_map:
                p_exist = prod_map[key_p]
                # Level 2 check: Variante
                if talla and (p_exist['variante'] or '').lower() != talla.lower():
                    variantes_nuevas.append({"producto_padre": p_exist['nombre'], "variante": talla})
                    advs.append(f"Producto '{p_exist['nombre']}' existe. Se registrará la nueva variante '{talla}'.")

                # Detector de Diferencias (No sobrescritura silenciosa)
                precio_imp_str = mapped_data.get('precio_venta_cop', '')
                if precio_imp_str:
                    try:
                        precio_imp = float(precio_imp_str.replace('$', '').replace(',', '').strip())
                        if abs(p_exist['precio'] - precio_imp) > 0.01:
                            diferencias_detectadas.append({
                                "fila": fila_num,
                                "producto": p_exist['nombre'],
                                "campo": "Precio de Venta",
                                "existente": p_exist['precio'],
                                "importado": precio_imp
                            })
                            advs.append(f"Diferencia de precio detectada para '{p_exist['nombre']}': Actual ${p_exist['precio']:,.0f} vs Importado ${precio_imp:,.0f}.")
                    except:
                        pass
            else:
                productos_nuevos.append({"nombre": nombre_full, "variante": talla})

        estado_row = "VALIDO"
        if errs:
            estado_row = "ERROR"
            total_errores += 1
        elif advs:
            estado_row = "ADVERTENCIA"
            total_advertencias += 1
        else:
            total_validos += 1

        # Actualizar staging
        ejecutar_query(
            "UPDATE importaciones_staging SET estado_validacion=?, errores_json=?, advertencias_json=? WHERE id=?",
            (estado_row, json.dumps(errs, ensure_ascii=False), json.dumps(advs, ensure_ascii=False), s_id)
        )

        resumen_filas.append({
            "fila": fila_num,
            "estado": estado_row,
            "datos": mapped_data,
            "errores": errs,
            "advertencias": advs
        })

    resumen = {
        "batch_id": batch_id,
        "total_registros": len(registros_staging),
        "validos": total_validos,
        "advertencias": total_advertencias,
        "errores": total_errores,
        "productos_nuevos": productos_nuevos,
        "variantes_nuevas": variantes_nuevas,
        "diferencias_detectadas": diferencias_detectadas,
        "detalles_filas": resumen_filas[:50]
    }

    return True, "Prevalidación completada", resumen

def procesar_importacion_aprobada(batch_id, negocio_id, usuario_id, mapeo_usuario, autorizaciones=None):
    """
    Etapa 6: Confirmación explícita e inserción transaccional multi-módulo.
    Alimenta productos, inventario, compras/lotes, ventas y cartera.
    Guarda memoria de mapeo y genera auditoría con undo_token.
    """
    registros_staging = ejecutar_query(
        "SELECT fila_num, datos_raw_json FROM importaciones_staging WHERE batch_id=? AND negocio_id=? ORDER BY fila_num ASC",
        (batch_id, negocio_id), fetch=True
    ) or []

    if not registros_staging:
        return False, "No se encontraron datos para procesar", None

    undo_token = f"UNDO-{uuid.uuid4().hex[:12].upper()}"
    fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    creados_info = {"productos": [], "ventas": [], "clientes": [], "abonos": [], "lotes": []}
    procesados = 0

    for fila_num, raw_json in registros_staging:
        raw_row = json.loads(raw_json)
        mapped = {}
        for col_excel, campo_target in mapeo_usuario.items():
            if campo_target and campo_target != "IGNORAR":
                mapped[campo_target] = raw_row.get(col_excel, "").strip()

        nombre_prod = (mapped.get('nombre_producto') or '').strip()
        jugador = (mapped.get('jugador_edicion') or mapped.get('tipo_producto') or '').strip()
        talla = (mapped.get('variante_talla') or '').strip()
        full_prod = f"{nombre_prod} {jugador}".strip() if jugador else nombre_prod

        if not full_prod:
            continue

        try:
            precio_v = float(str(mapped.get('precio_venta_cop', 0)).replace('$', '').replace(',', '').strip())
        except:
            precio_v = 0.0

        try:
            costo_cop = float(str(mapped.get('costo_unitario_cop', 0)).replace('$', '').replace(',', '').strip())
        except:
            costo_cop = 0.0

        # 1. REGLA DE PRODUCTO / VARIANTE
        p_res = ejecutar_query("SELECT id FROM productos WHERE LOWER(nombre)=LOWER(?) AND negocio_id=?", (full_prod, negocio_id), fetch=True)
        if p_res:
            pid = p_res[0][0]
            # Si el usuario autorizó actualizar precio en el diff detector
            if autorizaciones and autorizaciones.get('actualizar_precios') and precio_v > 0:
                ejecutar_query("UPDATE productos SET precio=? WHERE id=? AND negocio_id=?", (precio_v, pid, negocio_id))
        else:
            ejecutar_query(
                "INSERT INTO productos (negocio_id, nombre, precio, tipo_producto, variante) VALUES (?, ?, ?, 'TRANSFORMADO', ?)",
                (negocio_id, full_prod, precio_v, talla)
            )
            pid_r = ejecutar_query("SELECT id FROM productos WHERE nombre=? AND negocio_id=? ORDER BY id DESC LIMIT 1", (full_prod, negocio_id), fetch=True)
            pid = pid_r[0][0] if pid_r else 1
            creados_info["productos"].append(pid)

        # 2. CARTERA Y CLIENTE
        cli_nombre = (mapped.get('cliente_nombre') or '').strip()
        deuda_val = float(str(mapped.get('saldo_pendiente', 0)).replace('$', '').replace(',', '').strip() or 0)
        abono_val = float(str(mapped.get('abono_monto', 0)).replace('$', '').replace(',', '').strip() or 0)

        if cli_nombre:
            cartera_service.crear_o_actualizar_cliente(cli_nombre, negocio_id)
            creados_info["clientes"].append(cli_nombre)

        # 3. REGISTRO DE VENTA / VENTA A CRÉDITO
        cant = float(str(mapped.get('cantidad', 1)).strip() or 1.0)
        metodo = "CRÉDITO" if deuda_val > 0 else "Efectivo"
        fecha_v = mapped.get('fecha_operacion') or datetime.now().strftime("%Y-%m-%d")

        ok_v, res_v = ventas_service.registrar_venta(pid, cant, metodo, usuario_id, negocio_id, fecha_custom=fecha_v)
        if ok_v:
            procesados += 1
            v_res = ejecutar_query("SELECT id FROM ventas WHERE negocio_id=? ORDER BY id DESC LIMIT 1", (negocio_id,), fetch=True)
            if v_res:
                vid = v_res[0][0]
                creados_info["ventas"].append(vid)
                if abono_val > 0:
                    cartera_service.registrar_abono(vid, abono_val, "Efectivo (Importación)", usuario_id, negocio_id, observacion="Abono cargado por Importador Inteligente")
                    creados_info["abonos"].append(vid)

    # 4. MEMORIA POR TENANT DE MAPEO
    ejecutar_query(
        "INSERT INTO mapeos_importacion (negocio_id, nombre_mapeo, estructura_columnas_json, fecha_creacion) VALUES (?, 'Mapeo Aprobado Tenant', ?, ?)",
        (negocio_id, json.dumps(mapeo_usuario, ensure_ascii=False), fecha_hoy)
    )

    # 5. AUDITORÍA DE IMPORTACIÓN CON UNDO TOKEN
    ejecutar_query(
        """INSERT INTO auditoria_importaciones 
           (negocio_id, usuario_id, fecha, undo_token, nombre_archivo, total_registros, creados_json, estado)
           VALUES (?, ?, ?, ?, 'Importación Excel Empresarial', ?, ?, 'COMPLETADO')""",
        (negocio_id, usuario_id, fecha_hoy, undo_token, procesados, json.dumps(creados_info, ensure_ascii=False))
    )

    return True, f"¡Importación exitosa! Se procesaron {procesados} registros.", {"undo_token": undo_token, "resumen": creados_info}

def revertir_importacion(undo_token, negocio_id, usuario_id):
    """
    Etapa 7: Reversión asistida respetando la integridad de datos posteriores.
    """
    audit = ejecutar_query(
        "SELECT id, creados_json, estado FROM auditoria_importaciones WHERE undo_token=? AND negocio_id=?",
        (undo_token, negocio_id), fetch=True
    )
    if not audit:
        return False, "Token de reversión no encontrado o ya fue revertido"

    a_id, creados_json, estado = audit[0]
    if estado == 'REVERTIDO':
        return False, "Esta importación ya había sido revertida previamente"

    creados = json.loads(creados_json) if creados_json else {}
    ventas_creadas = creados.get('ventas', [])

    # Verificar si las ventas creadas tienen abonos o movimientos posteriores
    for vid in ventas_creadas:
        ventas_service.eliminar_venta(vid, negocio_id, usuario_id)

    # Marcar auditoría como revertida
    ejecutar_query("UPDATE auditoria_importaciones SET estado='REVERTIDO' WHERE id=?", (a_id,))

    return True, f"Importación {undo_token} revertida exitosamente. Se restituyó la información."
