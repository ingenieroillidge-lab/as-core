import json
import uuid
import time
from datetime import datetime
from database import ejecutar_query, ejecutar_query_many
import services.ventas_service as ventas_service
import services.cartera_service as cartera_service
import services.inventario_service as inventario_service

# ══════════════════════════════════════════════════════════════════
# NÚCLEO SEMÁNTICO UNIVERSAL
# ══════════════════════════════════════════════════════════════════

SEMANTIC_CORE = {
    # ── Identidad del producto o servicio ──
    "nombre_producto": [
        "PRODUCTO", "DESCRIPCION", "ITEM", "NOMBRE", "ARTICULO",
        "SERVICIO", "REFERENCIA PRODUCTO", "NOMBRE PRODUCTO"
    ],
    "codigo_sku": [
        "CODIGO", "SKU", "REF", "REFERENCIA", "BARCODE", "EAN",
        "PLU", "CODIGO INTERNO", "ID PRODUCTO"
    ],
    "categoria": [
        "CATEGORIA", "TIPO", "TIPO PRODUCTO", "FAMILY", "GRUPO",
        "LINEA", "DIVISION", "DEPARTAMENTO", "CLASIFICACION"
    ],
    "subcategoria": [
        "SUBCATEGORIA", "SUBTIPO", "SUBGRUPO", "SEGMENTO", "SUBLINEA"
    ],

    # ── Costos y precios ──
    "costo_unitario_origen": [
        "US", "USD", "COSTO USD", "COSTO UNITARIO USD", "PRECIO COMPRA USD",
        "UNIT USD", "COSTO EUR", "COSTO ORIGEN", "COSTO UNITARIO ORIGEN"
    ],
    "tasa_cambio": [
        "PRECIO US", "PRECIO USD", "TASA", "TASA CAMBIO", "TRM",
        "CAMBIO USD", "EXCHANGE RATE", "TRM EUR", "TASA CONVERSION"
    ],
    "costo_unitario_local": [
        "COSTO UNITARIO", "COSTO COP", "COSTO UNITARIO (COP)", "COSTO BASE COP",
        "UNIT COP", "COSTO UNITARIO LOCAL", "COSTO BASE"
    ],
    "costo_envio": [
        "COSTO DE ENVIO", "COSTO ENVIO", "FLETE", "ENVIO", "FLETES",
        "SHIPPING", "LOGISTICA", "COSTO LOGISTICO", "TRANSPORTE"
    ],
    "costo_total": [
        "COSTO TOTAL", "COSTO TOTAL ADQUISICION", "TOTAL COP", "TOTAL COST",
        "COSTO ADQUISICION", "COSTO NETO"
    ],
    "precio_venta": [
        "PRECIO VENTA", "PRECIO DE VENTA", "PRECIO VENTA (COP)", "PVP",
        "PRICE", "PRECIO UNITARIO", "PRECIO AL PUBLICO"
    ],

    # ── Cantidades ──
    "cantidad": [
        "CANTIDAD", "UNIDADES", "CANTIDAD DE UNIDADES", "UNIDADES COMPRADAS",
        "QTY", "STOCK", "EXISTENCIAS", "INVENTARIO"
    ],

    # ── Cliente y cartera ──
    "cliente_nombre": [
        "CLIENTE", "CLIENTES", "CUSTOMER", "COMPRADOR", "NOMBRE CLIENTE",
        "DESTINATARIO", "RAZON SOCIAL"
    ],
    "saldo_pendiente": [
        "DEUDAS POR COBRAR", "DEUDAS", "CARTERA", "SALDO PENDIENTE",
        "POR COBRAR", "DEUDA", "CUENTA POR COBRAR", "SALDO"
    ],
    "abono_monto": [
        "PAGOS/ABONOS", "PAGOS", "ABONOS", "ABONO", "PAGO",
        "PAGO RECIBIDO", "RECAUDO"
    ],

    # ── Fechas ──
    "fecha_operacion": [
        "FECHA", "FECHA COMPRA", "FECHA PEDIDO", "DATE",
        "FECHA OPERACION", "FECHA VENTA", "FECHA REGISTRO"
    ],
    "fecha_recepcion": [
        "FECHA DE LLEGADA", "FECHA LLEGADA", "FECHA RECEPCION",
        "ARRIVAL DATE", "FECHA ENTREGA", "FECHA INGRESO"
    ],

    # ── Campos derivados ──
    "campo_calculado": [
        "UTILIDAD", "PROFIT", "MARGEN", "PORCENTAJE DE GANANCIA",
        "GANANCIA", "DIAS EN TRANSITO", "DIAS TRANSITO", "TRANSIT DAYS",
        "RENTABILIDAD", "ROI", "PORCENTAJE", "INVERSION POR PEDIDO",
        "VENDIDO HASTA LA FECHA", "GANANCIA POR PEDIDO", "DINERO EN CAJA"
    ],
}

SINGLETON_FIELDS = {
    "nombre_producto", "codigo_sku", "precio_venta", 
    "cliente_nombre", "saldo_pendiente", "abono_monto", 
    "fecha_operacion", "fecha_recepcion"
}

ATTRIBUTE_HINTS = [
    "JUGADOR", "EDICION", "PLAYER", "TEMPORADA",
    "MARCA", "BRAND", "FABRICANTE",
    "MODELO", "MODEL", "VERSION",
    "MATERIAL", "COMPOSICION", "ACABADO",
    "ORIGEN", "PAIS", "PROCEDENCIA",
    "PESO", "DIMENSIONES", "CAPACIDAD",
    "CILINDRAJE", "POTENCIA", "VOLTAJE",
]

VARIANT_HINTS = [
    "TALLA", "SIZE", "VARIANTE",
    "COLOR", "COLOUR",
    "MEDIDA", "PRESENTACION", "EMPAQUE",
    "SABOR", "FRAGANCIA", "DENSIDAD",
]

CAMPO_LABELS = {
    "IGNORAR": "🚫 No importar",
    "nombre_producto": "📦 Nombre del producto o servicio",
    "codigo_sku": "🔖 Código / SKU / Referencia",
    "categoria": "📂 Categoría",
    "subcategoria": "📁 Subcategoría",
    "atributo": "🏷️ Atributo del producto",
    "variante": "🔀 Variante (talla, color, medida...)",
    "costo_unitario_origen": "💵 Costo unitario (moneda origen)",
    "tasa_cambio": "💱 Tasa de cambio",
    "costo_unitario_local": "💰 Costo unitario (moneda local)",
    "costo_envio": "🚚 Costo logístico / envío",
    "costo_total": "📦 Costo total de adquisición",
    "precio_venta": "🏷️ Precio de venta",
    "cantidad": "🔢 Cantidad / Unidades",
    "cliente_nombre": "👤 Cliente",
    "saldo_pendiente": "💳 Cuenta por cobrar / Deuda",
    "abono_monto": "💵 Pago / Abono recibido",
    "fecha_operacion": "📅 Fecha de operación",
    "fecha_recepcion": "📦 Fecha de recepción",
    "campo_calculado": "📊 Campo derivado — usar para validación",
}


# ══════════════════════════════════════════════════════════════════
# ETAPA 1: CARGA Y STAGING
# ══════════════════════════════════════════════════════════════════

def crear_lote_staging(negocio_id, nombre_archivo, filas_matriz):
    if not filas_matriz or len(filas_matriz) < 1:
        return False, "El archivo no contiene filas de datos", None

    batch_id = f"BATCH-{uuid.uuid4().hex[:12].upper()}"
    fecha_creacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    raw_headers = [str(c).strip() for c in filas_matriz[0]]
    headers_info = []
    headers = []
    for orig_idx, h in enumerate(raw_headers):
        if h:
            headers_info.append((orig_idx, h))
            headers.append(h)

    if not headers:
        return False, "El archivo no contiene encabezados válidos en la primera fila", None

    filas_datos = filas_matriz[1:]

    muestras = []
    for idx, row in enumerate(filas_datos[:5]):
        dict_row = {}
        for orig_idx, h in headers_info:
            dict_row[h] = str(row[orig_idx]).strip() if orig_idx < len(row) and row[orig_idx] is not None else ""
        muestras.append(dict_row)

    params_staging = []
    for idx, row in enumerate(filas_datos):
        dict_row = {}
        for orig_idx, h in headers_info:
            dict_row[h] = str(row[orig_idx]).strip() if orig_idx < len(row) and row[orig_idx] is not None else ""

        params_staging.append((
            negocio_id, batch_id, idx + 1,
            json.dumps(dict_row, ensure_ascii=False),
            fecha_creacion
        ))

    sql_insert = """INSERT INTO importaciones_staging 
                    (negocio_id, batch_id, fila_num, datos_raw_json, estado_validacion, fecha_creacion)
                    VALUES (?, ?, ?, ?, 'PENDIENTE', ?)"""
    ejecutar_query_many(sql_insert, params_staging)

    res_info = {
        "batch_id": batch_id,
        "nombre_archivo": nombre_archivo,
        "headers": headers,
        "total_registros": len(filas_datos),
        "muestras": muestras
    }
    return True, "Archivo cargado en staging con éxito", res_info


# ══════════════════════════════════════════════════════════════════
# ETAPA 2: MOTOR HEURÍSTICO UNIVERSAL Y CONTEXTUAL CON EXPLICABILIDAD
# ══════════════════════════════════════════════════════════════════

def proponer_mapeo_heuristico(headers, negocio_id, muestras=None):
    """
    Motor heurístico contextual:
    Evalúa encabezado + muestra de valores + columnas vecinas + tipo de dato.
    Devuelve propuesta con nivel de confianza y motivos explícitos.
    """
    mem_res = ejecutar_query(
        "SELECT estructura_columnas_json FROM mapeos_importacion WHERE negocio_id=? ORDER BY id DESC LIMIT 1",
        (negocio_id,), fetch=True
    )
    mapeo_guardado = {}
    if mem_res and len(mem_res) > 0 and len(mem_res[0]) > 0 and mem_res[0][0]:
        try:
            mapeo_guardado = json.loads(mem_res[0][0])
        except Exception:
            mapeo_guardado = {}

    muestras = muestras or []
    headers_upper = [h.upper().strip() for h in headers]

    # Detectar presencia de atributos/variantes en el conjunto
    tiene_atributos_vecinos = any(
        any(hint in h for hint in ATTRIBUTE_HINTS + VARIANT_HINTS) 
        for h in headers_upper
    )

    propuesta = []
    destinos_usados = {}

    for h in headers:
        h_norm = h.upper().strip()
        motivos = []

        # 1. Memoria guardada del tenant
        if h in mapeo_guardado:
            campo_mem = mapeo_guardado[h]
            motivos.append("Recuperado de la memoria de importaciones anteriores de tu empresa.")
            propuesta.append({
                "columna_excel": h,
                "campo_propuesto": campo_mem,
                "confianza": "ALTA",
                "origen": "MEMORIA_TENANT",
                "nombre_atributo": h if campo_mem in ("atributo", "variante") else None,
                "label": CAMPO_LABELS.get(campo_mem, campo_mem),
                "motivos": motivos,
                "es_calculado": campo_mem == "campo_calculado"
            })
            destinos_usados[campo_mem] = destinos_usados.get(campo_mem, 0) + 1
            continue

        match_campo = None
        confianza = "NINGUNA"

        # 2. Coincidencia exacta con SEMANTIC_CORE
        for campo, sinonimos in SEMANTIC_CORE.items():
            if h_norm in sinonimos:
                match_campo = campo
                confianza = "ALTA"
                motivos.append(f"Coincidencia exacta de encabezado con el concepto '{CAMPO_LABELS.get(campo, campo)}'.")
                break

        # 3. Coincidencia parcial con SEMANTIC_CORE
        if not match_campo:
            for campo, sinonimos in SEMANTIC_CORE.items():
                if any(len(s) > 2 and s in h_norm for s in sinonimos):
                    match_campo = campo
                    confianza = "MEDIA"
                    motivos.append(f"El encabezado contiene términos compatibles con '{CAMPO_LABELS.get(campo, campo)}'.")
                    break

        # 4. Evaluación Contextual Genérica (Valores de muestra + Tipo de dato + Contexto de dataset)
        if not match_campo:
            val_muestras = [str(m.get(h, '')).strip() for m in muestras if m.get(h)]
            
            # Comprobar si los valores de la columna son predominantemente texto (no números, no fechas)
            es_textual = len(val_muestras) > 0 and all(
                not v.replace('.', '').replace(',', '').replace('$', '').replace('-', '').isdigit() and
                not (len(v) == 10 and v.count('-') == 2)
                for v in val_muestras
            )

            # Comprobar si aún no se ha identificado una columna principal de nombre_producto
            no_hay_producto_todavia = 'nombre_producto' not in destinos_usados

            if es_textual and tiene_atributos_vecinos and no_hay_producto_todavia:
                match_campo = "nombre_producto"
                confianza = "MEDIA"
                motivos.append("Valores de muestra predominantemente textuales en presencia de atributos/variantes vecinos en el archivo.")
                motivos.append("Hipótesis contextual: Se infiere como la identidad principal del producto o catálogo (IA propone, humano autoriza).")

        # 5. Detectar variante conocida
        if not match_campo:
            if h_norm in VARIANT_HINTS or any(v in h_norm for v in VARIANT_HINTS if len(v) > 2):
                match_campo = "variante"
                confianza = "ALTA"
                motivos.append("El encabezado corresponde a una dimensión de variante inventariable (talla, color, presentación).")

        # 6. Detectar atributo conocido
        if not match_campo:
            if h_norm in ATTRIBUTE_HINTS or any(a in h_norm for a in ATTRIBUTE_HINTS if len(a) > 2):
                match_campo = "atributo"
                confianza = "MEDIA"
                motivos.append("El encabezado corresponde a una característica descriptiva del producto (marca, modelo, material, jugador).")

        # 7. Si no se reconoce nada
        if not match_campo:
            match_campo = "IGNORAR"
            motivos.append("No se encontró coincidencia semántica evidente en el diccionario universal.")

        nombre_attr = h if match_campo in ("atributo", "variante") else None

        # Moneda concreta detectada para UX
        label_dinamica = CAMPO_LABELS.get(match_campo, match_campo)
        if match_campo == "costo_unitario_origen":
            if "US" in h_norm or "USD" in h_norm:
                label_dinamica = "💵 Costo unitario — USD"
            elif "EUR" in h_norm:
                label_dinamica = "💶 Costo unitario — EUR"
        elif match_campo == "tasa_cambio":
            if "US" in h_norm or "USD" in h_norm:
                label_dinamica = "💱 Tasa de cambio — USD → COP"
        elif match_campo == "costo_unitario_local":
            label_dinamica = "💰 Costo unitario — COP"

        propuesta.append({
            "columna_excel": h,
            "campo_propuesto": match_campo,
            "confianza": confianza,
            "origen": "HEURISTICA_CONTEXTUAL",
            "nombre_atributo": nombre_attr,
            "label": label_dinamica,
            "motivos": motivos,
            "es_calculado": match_campo == "campo_calculado"
        })

        destinos_usados[match_campo] = destinos_usados.get(match_campo, 0) + 1

    return propuesta


# ══════════════════════════════════════════════════════════════════
# ETAPA 3: PREVALIDACIÓN BATCH (SIN N+1)
# ══════════════════════════════════════════════════════════════════

def conciliar_y_prevalidar(batch_id, negocio_id, mapeo_usuario):
    t_start = time.time()
    print(f"[PREVALIDAR] Leyendo staging batch_id={batch_id}")

    registros_staging = ejecutar_query(
        "SELECT id, fila_num, datos_raw_json FROM importaciones_staging WHERE batch_id=? AND negocio_id=? ORDER BY fila_num ASC",
        (batch_id, negocio_id), fetch=True
    ) or []

    if not registros_staging:
        return False, "No se encontraron registros en la capa de staging", None

    productos_existentes = ejecutar_query(
        "SELECT id, nombre, precio, categoria, subcategoria, variante FROM productos WHERE negocio_id=?",
        (negocio_id,), fetch=True
    ) or []
    prod_map = {}
    for p in productos_existentes:
        key = (p[1] or '').strip().lower()
        prod_map[key] = {"id": p[0], "nombre": p[1], "precio": p[2], "categoria": p[3], "subcategoria": p[4], "variante": p[5]}

    clientes_existentes = ejecutar_query(
        "SELECT id, nombre FROM clientes WHERE negocio_id=?",
        (negocio_id,), fetch=True
    ) or []
    cli_set = {(c[1] or '').strip().lower() for c in clientes_existentes}

    total_validos = 0
    total_advertencias = 0
    total_errores = 0
    productos_nuevos = []
    diferencias_detectadas = []
    resumen_filas = []
    update_params = []

    for s_id, fila_num, raw_json in registros_staging:
        raw_row = json.loads(raw_json)
        mapped_data = {}
        for col_excel, campo_target in mapeo_usuario.items():
            if campo_target and campo_target != "IGNORAR":
                mapped_data[campo_target] = raw_row.get(col_excel, "").strip()

        errs = []
        advs = []

        # ── Cantidad ──
        cant_str = mapped_data.get('cantidad', '')
        try:
            cant_val = float(cant_str) if cant_str else 1.0
        except Exception:
            cant_val = 1.0
            advs.append("No se identificó cantidad explícita; se asumió 1.0 unidad.")

        # ── Validación multimoneda ──
        origen_str = mapped_data.get('costo_unitario_origen', '')
        tasa_str = mapped_data.get('tasa_cambio', '')
        local_str = mapped_data.get('costo_unitario_local', '')

        if origen_str and tasa_str and local_str:
            try:
                v_origen = float(origen_str.replace('$', '').replace(',', '').strip())
                v_tasa = float(tasa_str.replace('$', '').replace(',', '').strip())
                v_local = float(local_str.replace('$', '').replace(',', '').strip())

                calc_local = v_origen * v_tasa
                if abs(calc_local - v_local) > 1.0:
                    advs.append(
                        f"🧮 Discrepancia multimoneda: {v_origen} × {v_tasa} = ${calc_local:,.0f}, "
                        f"pero el archivo reporta ${v_local:,.0f}."
                    )
            except Exception:
                pass

        # ── Conciliación de producto ──
        nombre_prod = (mapped_data.get('nombre_producto') or '').strip()
        key_p = nombre_prod.lower()

        if nombre_prod:
            if key_p in prod_map:
                p_exist = prod_map[key_p]
                precio_imp_str = mapped_data.get('precio_venta', '')
                if precio_imp_str:
                    try:
                        precio_imp = float(precio_imp_str.replace('$', '').replace(',', '').strip())
                        if p_exist['precio'] and abs(p_exist['precio'] - precio_imp) > 0.01:
                            diferencias_detectadas.append({
                                "fila": fila_num,
                                "producto": p_exist['nombre'],
                                "campo": "Precio de Venta",
                                "existente": p_exist['precio'],
                                "importado": precio_imp
                            })
                            advs.append(
                                f"Diferencia de precio: '{p_exist['nombre']}' "
                                f"actual ${p_exist['precio']:,.0f} vs importado ${precio_imp:,.0f}."
                            )
                    except Exception:
                        pass
            else:
                productos_nuevos.append({"nombre": nombre_prod})

        estado_row = "VALIDO"
        if errs:
            estado_row = "ERROR"
            total_errores += 1
        elif advs:
            estado_row = "ADVERTENCIA"
            total_advertencias += 1
        else:
            total_validos += 1

        update_params.append((
            estado_row,
            json.dumps(errs, ensure_ascii=False),
            json.dumps(advs, ensure_ascii=False),
            s_id
        ))

        resumen_filas.append({
            "fila": fila_num,
            "estado": estado_row,
            "datos": mapped_data,
            "errores": errs,
            "advertencias": advs
        })

    t_conciliacion = time.time() - t_start
    ejecutar_query_many(
        "UPDATE importaciones_staging SET estado_validacion=?, errores_json=?, advertencias_json=? WHERE id=?",
        update_params
    )

    t_total = time.time() - t_start

    resumen = {
        "batch_id": batch_id,
        "total_registros": len(registros_staging),
        "validos": total_validos,
        "advertencias": total_advertencias,
        "errores": total_errores,
        "productos_nuevos": productos_nuevos,
        "diferencias_detectadas": diferencias_detectadas,
        "detalles_filas": resumen_filas[:50],
        "tiempo_ms": int(t_total * 1000)
    }

    return True, "Prevalidación completada", resumen


# ══════════════════════════════════════════════════════════════════
# ETAPA 4: PROCESAMIENTO APROBADO CON MULTI-ATRIBUTOS
# ══════════════════════════════════════════════════════════════════

def procesar_importacion_aprobada(batch_id, negocio_id, usuario_id, mapeo_usuario, autorizaciones=None):
    """
    Confirmación transaccional multi-módulo.
    Soporta múltiples columnas asignadas a 'atributo' y 'variante'.
    Cada columna conserva su encabezado como nombre_atributo en producto_atributos.
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

        if not nombre_prod:
            continue

        try:
            precio_v = float(str(mapped.get('precio_venta', 0)).replace('$', '').replace(',', '').strip())
        except Exception:
            precio_v = 0.0

        try:
            costo_local = float(str(mapped.get('costo_unitario_local', 0)).replace('$', '').replace(',', '').strip())
        except Exception:
            costo_local = 0.0

        # 1. PRODUCTO (nombre limpio)
        p_res = ejecutar_query(
            "SELECT id FROM productos WHERE LOWER(nombre)=LOWER(?) AND negocio_id=?",
            (nombre_prod, negocio_id), fetch=True
        )
        if p_res and len(p_res) > 0 and len(p_res[0]) > 0:
            pid = p_res[0][0]
            if autorizaciones and autorizaciones.get('actualizar_precios') and precio_v > 0:
                ejecutar_query("UPDATE productos SET precio=? WHERE id=? AND negocio_id=?", (precio_v, pid, negocio_id))
        else:
            categoria = (mapped.get('categoria') or '').strip()
            subcategoria = (mapped.get('subcategoria') or '').strip()
            ejecutar_query(
                "INSERT INTO productos (negocio_id, nombre, precio, tipo_producto, categoria, subcategoria) VALUES (?, ?, ?, 'TRANSFORMADO', ?, ?)",
                (negocio_id, nombre_prod, precio_v, categoria or None, subcategoria or None)
            )
            pid_r = ejecutar_query(
                "SELECT id FROM productos WHERE nombre=? AND negocio_id=? ORDER BY id DESC LIMIT 1",
                (nombre_prod, negocio_id), fetch=True
            )
            pid = pid_r[0][0] if (pid_r and len(pid_r) > 0 and len(pid_r[0]) > 0) else 1
            creados_info["productos"].append(pid)

        # 2. ATRIBUTOS Y VARIANTES MULTI-COLUMNA EN TABLA SEPARADA
        for col_excel, campo_target in mapeo_usuario.items():
            if campo_target in ("atributo", "variante"):
                val = raw_row.get(col_excel, "").strip()
                if val:
                    ejecutar_query(
                        "INSERT INTO producto_atributos (negocio_id, producto_id, nombre_atributo, valor_atributo, tipo) VALUES (?, ?, ?, ?, ?)",
                        (negocio_id, pid, col_excel, val, campo_target.upper())
                    )

        # 3. CARTERA Y CLIENTE
        cli_nombre = (mapped.get('cliente_nombre') or '').strip()
        deuda_val = float(str(mapped.get('saldo_pendiente', 0)).replace('$', '').replace(',', '').strip() or 0)
        abono_val = float(str(mapped.get('abono_monto', 0)).replace('$', '').replace(',', '').strip() or 0)

        if cli_nombre:
            cartera_service.crear_o_actualizar_cliente(cli_nombre, negocio_id)
            creados_info["clientes"].append(cli_nombre)

        # 4. REGISTRO DE VENTA / VENTA A CRÉDITO
        cant = float(str(mapped.get('cantidad', 1)).strip() or 1.0)
        metodo = "CRÉDITO" if deuda_val > 0 else "Efectivo"
        fecha_v = mapped.get('fecha_operacion') or datetime.now().strftime("%Y-%m-%d")

        ok_v, res_v = ventas_service.registrar_venta(pid, cant, metodo, usuario_id, negocio_id, fecha_custom=fecha_v)
        if ok_v:
            procesados += 1
            v_res = ejecutar_query("SELECT id FROM ventas WHERE negocio_id=? ORDER BY id DESC LIMIT 1", (negocio_id,), fetch=True)
            if v_res and len(v_res) > 0 and len(v_res[0]) > 0:
                vid = v_res[0][0]
                creados_info["ventas"].append(vid)
                if cli_nombre or deuda_val > 0:
                    ejecutar_query(
                        "UPDATE ventas SET cliente_nombre=?, saldo_pendiente=? WHERE id=? AND negocio_id=?",
                        (cli_nombre, deuda_val, vid, negocio_id)
                    )
                if abono_val > 0:
                    cartera_service.registrar_abono(vid, abono_val, "Efectivo (Importación)", usuario_id, negocio_id, observacion="Abono cargado por Importador Inteligente")
                    creados_info["abonos"].append(vid)

    # Memoria de mapeo
    ejecutar_query(
        "INSERT INTO mapeos_importacion (negocio_id, nombre_mapeo, estructura_columnas_json, fecha_creacion) VALUES (?, 'Mapeo Aprobado Tenant', ?, ?)",
        (negocio_id, json.dumps(mapeo_usuario, ensure_ascii=False), fecha_hoy)
    )

    # Auditoría
    ejecutar_query(
        """INSERT INTO auditoria_importaciones 
           (negocio_id, usuario_id, fecha, undo_token, nombre_archivo, total_registros, creados_json, estado)
           VALUES (?, ?, ?, ?, 'Importación Excel Empresarial', ?, ?, 'COMPLETADO')""",
        (negocio_id, usuario_id, fecha_hoy, undo_token, procesados, json.dumps(creados_info, ensure_ascii=False))
    )

    return True, f"¡Importación exitosa! Se procesaron {procesados} registros.", {"undo_token": undo_token, "resumen": creados_info}


# ══════════════════════════════════════════════════════════════════
# ETAPA 5: REVERSIÓN ASISTIDA
# ══════════════════════════════════════════════════════════════════

def revertir_importacion(undo_token, negocio_id, usuario_id):
    audit = ejecutar_query(
        "SELECT id, creados_json, estado FROM auditoria_importaciones WHERE undo_token=? AND negocio_id=?",
        (undo_token, negocio_id), fetch=True
    )
    if not audit or len(audit) == 0 or len(audit[0]) < 3:
        return False, "Token de reversión no encontrado o ya fue revertido"

    a_id, creados_json, estado = audit[0]

    if estado == 'REVERTIDO':
        return False, "Esta importación ya había sido revertida previamente"

    creados = json.loads(creados_json) if creados_json else {}
    ventas_creadas = creados.get('ventas', [])

    for vid in ventas_creadas:
        ventas_service.eliminar_venta(vid, negocio_id, usuario_id)

    ejecutar_query("UPDATE auditoria_importaciones SET estado='REVERTIDO' WHERE id=?", (a_id,))

    return True, f"Importación {undo_token} revertida exitosamente. Se restituyó la información."
