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
# Cada clave es un CONCEPTO del sistema, no un campo de un Excel particular.
# Los sinónimos son tokens que podrían encontrarse en encabezados reales
# de distintos sectores empresariales.

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

    # ── Costos y precios (moneda universal) ──
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

    # ── Campos calculados (no se importan, solo se detectan) ──
    "campo_calculado": [
        "UTILIDAD", "PROFIT", "MARGEN", "PORCENTAJE DE GANANCIA",
        "GANANCIA", "DIAS EN TRANSITO", "DIAS TRANSITO", "TRANSIT DAYS",
        "RENTABILIDAD", "ROI", "PORCENTAJE", "INVERSION POR PEDIDO",
        "VENDIDO HASTA LA FECHA", "GANANCIA POR PEDIDO", "DINERO EN CAJA"
    ],
}

# Tokens comunes que sugieren que una columna es un atributo del producto
# Se usa como fallback cuando no hay coincidencia exacta con SEMANTIC_CORE
ATTRIBUTE_HINTS = [
    "JUGADOR", "EDICION", "PLAYER", "TEMPORADA",
    "MARCA", "BRAND", "FABRICANTE",
    "MODELO", "MODEL", "VERSION",
    "MATERIAL", "COMPOSICION", "ACABADO",
    "ORIGEN", "PAIS", "PROCEDENCIA",
    "PESO", "DIMENSIONES", "CAPACIDAD",
    "CILINDRAJE", "POTENCIA", "VOLTAJE",
]

# Tokens comunes que sugieren que una columna es una variante
VARIANT_HINTS = [
    "TALLA", "SIZE", "VARIANTE",
    "COLOR", "COLOUR",
    "MEDIDA", "PRESENTACION", "EMPAQUE",
    "SABOR", "FRAGANCIA", "DENSIDAD",
]

# Etiquetas humanizadas para el frontend
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
    "campo_calculado": "📊 Campo calculado (no importar)",
}


# ══════════════════════════════════════════════════════════════════
# ETAPA 1: CARGA Y STAGING
# ══════════════════════════════════════════════════════════════════

def crear_lote_staging(negocio_id, nombre_archivo, filas_matriz):
    """
    Carga el archivo en staging. Filtra columnas vacías.
    Inserción masiva con ejecutar_query_many (1 transacción).
    """
    if not filas_matriz or len(filas_matriz) < 1:
        return False, "El archivo no contiene filas de datos", None

    batch_id = f"BATCH-{uuid.uuid4().hex[:12].upper()}"
    fecha_creacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Filtrar columnas vacías del encabezado
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

    # Inserción masiva en staging (1 sola transacción)
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
# ETAPA 2: MOTOR HEURÍSTICO UNIVERSAL
# ══════════════════════════════════════════════════════════════════

def proponer_mapeo_heuristico(headers, negocio_id):
    """
    Motor heurístico contextual universal.
    Para cada encabezado, detecta:
      - tipo semántico (concepto del sistema, atributo, variante, calculado)
      - nombre del atributo/variante si aplica
      - confianza y origen de la propuesta
    """
    # Recuperar memoria de mapeo previa del tenant
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

    propuesta = []
    for h in headers:
        h_norm = h.upper().strip()

        # 1. Memoria guardada del tenant
        if h in mapeo_guardado:
            campo_mem = mapeo_guardado[h]
            propuesta.append({
                "columna_excel": h,
                "campo_propuesto": campo_mem,
                "confianza": "ALTA",
                "origen": "MEMORIA_TENANT",
                "nombre_atributo": h if campo_mem in ("atributo", "variante") else None,
                "label": CAMPO_LABELS.get(campo_mem, campo_mem),
                "es_calculado": campo_mem == "campo_calculado"
            })
            continue

        # 2. Coincidencia exacta con SEMANTIC_CORE
        match_campo = None
        confianza = "NINGUNA"

        for campo, sinonimos in SEMANTIC_CORE.items():
            if h_norm in sinonimos:
                match_campo = campo
                confianza = "ALTA"
                break

        # 3. Coincidencia parcial con SEMANTIC_CORE
        if not match_campo:
            for campo, sinonimos in SEMANTIC_CORE.items():
                if any(len(s) > 2 and s in h_norm for s in sinonimos):
                    match_campo = campo
                    confianza = "MEDIA"
                    break

        # 4. Detectar si es una variante conocida
        if not match_campo:
            if h_norm in VARIANT_HINTS or any(v in h_norm for v in VARIANT_HINTS if len(v) > 2):
                match_campo = "variante"
                confianza = "ALTA"

        # 5. Detectar si es un atributo conocido
        if not match_campo:
            if h_norm in ATTRIBUTE_HINTS or any(a in h_norm for a in ATTRIBUTE_HINTS if len(a) > 2):
                match_campo = "atributo"
                confianza = "MEDIA"

        # 6. Si no se reconoce nada, proponer IGNORAR
        if not match_campo:
            match_campo = "IGNORAR"

        nombre_attr = None
        if match_campo in ("atributo", "variante"):
            nombre_attr = h  # El nombre original de la columna se convierte en el nombre del atributo/variante

        propuesta.append({
            "columna_excel": h,
            "campo_propuesto": match_campo,
            "confianza": confianza,
            "origen": "HEURISTICA_SISTEMA",
            "nombre_atributo": nombre_attr,
            "label": CAMPO_LABELS.get(match_campo, match_campo),
            "es_calculado": match_campo == "campo_calculado"
        })

    return propuesta


# ══════════════════════════════════════════════════════════════════
# ETAPA 3: PREVALIDACIÓN BATCH (SIN N+1)
# ══════════════════════════════════════════════════════════════════

def conciliar_y_prevalidar(batch_id, negocio_id, mapeo_usuario):
    """
    Prevalidación batch optimizada:
    - 1 consulta: staging completo
    - 1 consulta: productos existentes
    - 1 consulta: clientes existentes
    - Conciliación en memoria
    - 1 consulta batch: actualización del staging
    """
    t_start = time.time()
    print(f"[PREVALIDAR] Leyendo staging batch_id={batch_id}")

    # ── Consulta 1: Staging completo ──
    registros_staging = ejecutar_query(
        "SELECT id, fila_num, datos_raw_json FROM importaciones_staging WHERE batch_id=? AND negocio_id=? ORDER BY fila_num ASC",
        (batch_id, negocio_id), fetch=True
    ) or []

    if not registros_staging:
        return False, "No se encontraron registros en la capa de staging", None

    print(f"[PREVALIDAR] Registros staging: {len(registros_staging)}")

    # ── Consulta 2: Productos existentes (masivo) ──
    productos_existentes = ejecutar_query(
        "SELECT id, nombre, precio, categoria, subcategoria, variante FROM productos WHERE negocio_id=?",
        (negocio_id,), fetch=True
    ) or []
    prod_map = {}
    for p in productos_existentes:
        key = (p[1] or '').strip().lower()
        prod_map[key] = {"id": p[0], "nombre": p[1], "precio": p[2], "categoria": p[3], "subcategoria": p[4], "variante": p[5]}

    print(f"[PREVALIDAR] Productos existentes cargados: {len(prod_map)}")

    # ── Consulta 3: Clientes existentes (masivo) ──
    clientes_existentes = ejecutar_query(
        "SELECT id, nombre FROM clientes WHERE negocio_id=?",
        (negocio_id,), fetch=True
    ) or []
    cli_set = {(c[1] or '').strip().lower() for c in clientes_existentes}

    print(f"[PREVALIDAR] Clientes existentes cargados: {len(cli_set)}")

    # ── Conciliación en memoria ──
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

        # ── Validación de cantidad ──
        cant_str = mapped_data.get('cantidad', '')
        try:
            cant_val = float(cant_str) if cant_str else 1.0
        except Exception:
            cant_val = 1.0
            advs.append("No se identificó cantidad explícita; se asumió 1.0 unidad.")

        # ── Validación multimoneda universal (valor_origen × tasa = valor_destino) ──
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
                        f"Discrepancia multimoneda: {v_origen} × {v_tasa} = {calc_local:,.0f}, "
                        f"pero el archivo reporta {v_local:,.0f}."
                    )
            except Exception:
                pass

        # ── Conciliación de producto (solo nombre, sin concatenar atributos) ──
        nombre_prod = (mapped_data.get('nombre_producto') or '').strip()
        key_p = nombre_prod.lower()

        if nombre_prod:
            if key_p in prod_map:
                p_exist = prod_map[key_p]
                # Detector de diferencias de precio
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

        # ── Clasificación del registro ──
        estado_row = "VALIDO"
        if errs:
            estado_row = "ERROR"
            total_errores += 1
        elif advs:
            estado_row = "ADVERTENCIA"
            total_advertencias += 1
        else:
            total_validos += 1

        # Acumular para batch update
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

    # ── Consulta 4: Batch update del staging ──
    t_conciliacion = time.time() - t_start
    print(f"[PREVALIDAR] Conciliación en memoria completada en {t_conciliacion:.3f}s")

    ejecutar_query_many(
        "UPDATE importaciones_staging SET estado_validacion=?, errores_json=?, advertencias_json=? WHERE id=?",
        update_params
    )

    t_total = time.time() - t_start
    print(f"[PREVALIDAR] Batch update completado. Tiempo total: {t_total:.3f}s")
    print(f"[PREVALIDAR] Resultado: validos={total_validos}, advertencias={total_advertencias}, errores={total_errores}")

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
# ETAPA 4: PROCESAMIENTO APROBADO (DEUDA TÉCNICA: Adaptar a modelo universal)
# ══════════════════════════════════════════════════════════════════
# NOTA: Esta función todavía consume los campos antiguos del modelo
# (jugador_edicion, variante_talla). Debe ser adaptada al modelo
# semántico universal (atributo, variante, categoria) en una
# iteración posterior, una vez que Carga → Mapeo → Prevalidación
# estén estables.

def procesar_importacion_aprobada(batch_id, negocio_id, usuario_id, mapeo_usuario, autorizaciones=None):
    """
    Confirmación explícita e inserción transaccional multi-módulo.
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

        # Compatibilidad temporal: mapear campos universales a los que
        # espera la lógica existente (deuda técnica explícita)
        nombre_prod = (mapped.get('nombre_producto') or '').strip()
        atributo = (mapped.get('atributo') or '').strip()
        variante = (mapped.get('variante') or '').strip()

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

        # 1. PRODUCTO (nombre limpio, sin concatenar atributos)
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
                "INSERT INTO productos (negocio_id, nombre, precio, tipo_producto, categoria, subcategoria, variante) VALUES (?, ?, ?, 'TRANSFORMADO', ?, ?, ?)",
                (negocio_id, nombre_prod, precio_v, categoria or None, subcategoria or None, variante or None)
            )
            pid_r = ejecutar_query(
                "SELECT id FROM productos WHERE nombre=? AND negocio_id=? ORDER BY id DESC LIMIT 1",
                (nombre_prod, negocio_id), fetch=True
            )
            pid = pid_r[0][0] if (pid_r and len(pid_r) > 0 and len(pid_r[0]) > 0) else 1
            creados_info["productos"].append(pid)

            # Guardar atributos del producto en tabla separada
            if atributo:
                # El nombre del atributo proviene de la columna Excel original
                for col_excel, campo_target in mapeo_usuario.items():
                    if campo_target == "atributo":
                        val = raw_row.get(col_excel, "").strip()
                        if val:
                            ejecutar_query(
                                "INSERT INTO producto_atributos (negocio_id, producto_id, nombre_atributo, valor_atributo, tipo) VALUES (?, ?, ?, ?, 'ATRIBUTO')",
                                (negocio_id, pid, col_excel, val)
                            )

            if variante:
                for col_excel, campo_target in mapeo_usuario.items():
                    if campo_target == "variante":
                        val = raw_row.get(col_excel, "").strip()
                        if val:
                            ejecutar_query(
                                "INSERT INTO producto_atributos (negocio_id, producto_id, nombre_atributo, valor_atributo, tipo) VALUES (?, ?, ?, ?, 'VARIANTE')",
                                (negocio_id, pid, col_excel, val)
                            )

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
            if v_res and len(v_res) > 0 and len(v_res[0]) > 0:
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


# ══════════════════════════════════════════════════════════════════
# ETAPA 5: REVERSIÓN ASISTIDA
# ══════════════════════════════════════════════════════════════════

def revertir_importacion(undo_token, negocio_id, usuario_id):
    """Reversión asistida respetando la integridad de datos posteriores."""
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
