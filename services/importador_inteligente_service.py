import json
import uuid
import time
import hashlib
from datetime import datetime
from database import ejecutar_query, ejecutar_query_many, transaccion, insertar_con_id
import services.cartera_service as cartera_service

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


def parse_money(val):
    if not val:
        return 0.0
    try:
        clean = str(val).replace('$', '').replace(',', '').strip()
        return float(clean) if clean else 0.0
    except Exception:
        return 0.0


def calcular_hash_contenido(filas_matriz):
    """Genera SHA-256 del contenido del archivo para detectar importaciones duplicadas."""
    contenido = json.dumps(filas_matriz, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(contenido.encode('utf-8')).hexdigest()


def inferir_granularidad_costos(filas_datos, mapeo_usuario):
    """
    Analiza las muestras para inferir si 'costo_total' representa costo unitario final o costo total del lote.
    """
    coincidencias_unitario = 0
    coincidencias_lote = 0
    total_evaluados = 0

    col_origen = next((col for col, campo in mapeo_usuario.items() if campo == 'costo_unitario_origen'), None)
    col_tasa = next((col for col, campo in mapeo_usuario.items() if campo == 'tasa_cambio'), None)
    col_local = next((col for col, campo in mapeo_usuario.items() if campo == 'costo_unitario_local'), None)
    col_envio = next((col for col, campo in mapeo_usuario.items() if campo == 'costo_envio'), None)
    col_total = next((col for col, campo in mapeo_usuario.items() if campo == 'costo_total'), None)
    col_cant = next((col for col, campo in mapeo_usuario.items() if campo == 'cantidad'), None)

    for r in filas_datos[:30]:
        total = parse_money(r.get(col_total)) if col_total else 0.0
        local = parse_money(r.get(col_local)) if col_local else 0.0
        envio = parse_money(r.get(col_envio)) if col_envio else 0.0
        cant = parse_money(r.get(col_cant)) if col_cant else 1.0
        if cant <= 0: cant = 1.0

        if not total or total == 0:
            continue
        total_evaluados += 1

        # Test 1: ¿local + envío ≈ total? → total es unitario final
        if local > 0 and abs((local + envio) - total) <= 2.0:
            coincidencias_unitario += 1
        # Test 2: ¿total / cantidad ≈ local? → total es por lote completo
        elif cant > 1 and local > 0 and abs((total / cant) - local) <= 2.0:
            coincidencias_lote += 1

    if total_evaluados == 0:
        return "POR_UNIDAD", ["No se detectaron campos de costo total compitiendo; se asume costo por unidad."]

    ratio_unitario = coincidencias_unitario / total_evaluados
    ratio_lote = coincidencias_lote / total_evaluados

    if ratio_unitario >= 0.7:
        return "POR_UNIDAD", [
            f"En {coincidencias_unitario}/{total_evaluados} filas analizadas: costo local + envío ≈ costo total.",
            "Se interpreta que 'Costo Total' representa el costo unitario final (puesto en destino)."
        ]
    elif ratio_lote >= 0.7:
        return "POR_LOTE", [
            f"En {coincidencias_lote}/{total_evaluados} filas analizadas: costo total / cantidad ≈ costo local.",
            "Se interpreta que 'Costo Total' representa el costo del lote completo."
        ]
    else:
        return "AMBIGUO", [
            f"Evaluación de costos: {coincidencias_unitario} filas sugieren costo unitario, {coincidencias_lote} sugieren lote.",
            "Se recomienda confirmar si el Costo Total es por unidad o por pedido/lote."
        ]


def determinar_tipo_fila(mapped_data):
    """
    Determina qué tipo de operación representa una fila:
    COMPRA_Y_VENTA | SOLO_COMPRA | SOLO_VENTA | REGISTRO_HISTORICO
    """
    tiene_costos = any(mapped_data.get(c) for c in [
        'costo_unitario_origen', 'costo_unitario_local', 'costo_total'
    ])
    tiene_precio_venta = bool(mapped_data.get('precio_venta'))
    tiene_cliente = bool(mapped_data.get('cliente_nombre'))

    if tiene_costos and (tiene_precio_venta or tiene_cliente):
        return "COMPRA_Y_VENTA"
    elif tiene_costos and not tiene_precio_venta:
        return "SOLO_COMPRA"
    elif tiene_precio_venta and not tiene_costos:
        return "SOLO_VENTA"
    else:
        return "REGISTRO_HISTORICO"


# ══════════════════════════════════════════════════════════════════
# ETAPA 1: CARGA Y STAGING CON DETECCIÓN DE DUPLICADOS Y FILTRADO
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

    params_staging = []
    muestras = []
    fila_num_real = 0

    for idx, row in enumerate(filas_datos):
        dict_row = {}
        tiene_datos = False
        for orig_idx, h in headers_info:
            val = str(row[orig_idx]).strip() if orig_idx < len(row) and row[orig_idx] is not None else ""
            if val.lower() in ("none", "nan", ""):
                val = ""
            dict_row[h] = val
            if val:
                tiene_datos = True

        # Filtrar filas completamente vacías
        if not tiene_datos:
            continue

        # Filtrar filas que son resúmenes/totales al final del Excel
        primer_val = (dict_row.get(headers[0]) or "").upper().strip()
        if primer_val in ("TOTAL", "SUBTOTAL", "GRAN TOTAL", "SUMA", "TOTALES", "PROMEDIO"):
            continue

        fila_num_real += 1

        if len(muestras) < 5:
            muestras.append(dict_row)

        params_staging.append((
            negocio_id, batch_id, fila_num_real,
            json.dumps(dict_row, ensure_ascii=False),
            fecha_creacion
        ))

    if not params_staging:
        return False, "No se encontraron filas con datos válidos en el archivo", None

    # Calcular hash basado en las filas útiles filtradas (coincide exactamente con el hash de procesar)
    filas_matriz_utiles = [json.loads(p[3]) for p in params_staging]
    hash_archivo = calcular_hash_contenido(filas_matriz_utiles)

    # Verificar si este archivo ya fue importado anteriormente
    imp_previa = ejecutar_query(
        "SELECT undo_token, fecha, total_registros, estado FROM auditoria_importaciones WHERE negocio_id=? AND hash_archivo=? ORDER BY id DESC LIMIT 1",
        (negocio_id, hash_archivo), fetch=True
    )
    importacion_previa = None
    if imp_previa and len(imp_previa) > 0 and len(imp_previa[0]) >= 4:
        importacion_previa = {
            "undo_token": imp_previa[0][0],
            "fecha": imp_previa[0][1],
            "total_registros": imp_previa[0][2],
            "estado": imp_previa[0][3]
        }

    sql_insert = """INSERT INTO importaciones_staging 
                    (negocio_id, batch_id, fila_num, datos_raw_json, estado_validacion, fecha_creacion)
                    VALUES (?, ?, ?, ?, 'PENDIENTE', ?)"""
    ejecutar_query_many(sql_insert, params_staging)

    res_info = {
        "batch_id": batch_id,
        "nombre_archivo": nombre_archivo,
        "headers": headers,
        "total_registros": len(params_staging),
        "muestras": muestras,
        "hash_archivo": hash_archivo,
        "importacion_previa": importacion_previa
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
        #    No depende del nombre del encabezado; inspecciona los DATOS reales.
        if not match_campo and muestras:
            val_muestras = [str(m.get(h, '')).strip() for m in muestras if m.get(h)]
            
            if val_muestras:
                # ── 4a. ¿Predominantemente texto no numérico ni fecha? ──
                es_textual = all(
                    not v.replace('.', '').replace(',', '').replace('$', '').replace('-', '').replace(' ', '').isdigit() and
                    not (len(v) == 10 and v.count('-') == 2)
                    for v in val_muestras
                )
                
                # ── 4b. ¿Predominantemente numérico? ──
                es_numerico = all(
                    v.replace('.', '').replace(',', '').replace('$', '').replace('-', '').replace(' ', '').isdigit()
                    for v in val_muestras
                ) if val_muestras else False
                
                # ── 4c. ¿Valores de tipo estado? (patrones booleanos/binarios/workflow) ──
                #    Estados reales: Sí/No, Activo/Inactivo, Pagado/Pendiente, Entregado/En tránsito.
                #    No confundir con nombres de producto de baja cardinalidad (Napoli, Barcelona, Italia).
                vals_unicos = set(v.lower() for v in val_muestras)
                avg_len = sum(len(v) for v in vals_unicos) / max(len(vals_unicos), 1)
                estado_keywords = {"si", "no", "sí", "activo", "inactivo", "pagado", "pendiente",
                                   "entregado", "cancelado", "en transito", "en tránsito", "devuelto",
                                   "completado", "procesando", "aprobado", "rechazado", "vendido",
                                   "disponible", "agotado", "reservado", "true", "false", "yes"}
                tiene_patron_estado = any(v in estado_keywords for v in vals_unicos)
                es_estado = es_textual and len(vals_unicos) <= 2 and tiene_patron_estado
                # Alternativa: estados binarios muy cortos (ej: "ok", "a", "b"), pero solo con 5+ muestras y longitud promedio <= 5
                if not es_estado and es_textual and len(val_muestras) >= 5 and len(vals_unicos) <= 2 and avg_len <= 5:
                    es_estado = True

                no_hay_producto_todavia = 'nombre_producto' not in destinos_usados

                if es_textual and tiene_atributos_vecinos and no_hay_producto_todavia and not es_estado:
                    # Primera columna textual no-estado con vecinos de atributo → probable identidad de producto
                    match_campo = "nombre_producto"
                    confianza = "MEDIA"
                    motivos.append(f"Valores de muestra textuales ({', '.join(val_muestras[:3])}) en presencia de atributos/variantes vecinos.")
                    motivos.append("Hipótesis contextual: posible identidad del producto o catálogo (IA propone, humano autoriza).")

                elif es_estado:
                    # Columna con pocos valores únicos textuales → probable estado/clasificación
                    match_campo = "IGNORAR"
                    confianza = "MEDIA"
                    motivos.append(f"Valores categóricos detectados ({', '.join(sorted(vals_unicos)[:4])}). Posible estado o clasificación.")
                    motivos.append("Se recomienda revisar si corresponde a un estado de pago, operación, inventario u otro.")

                elif es_numerico and not match_campo:
                    # Numérico sin coincidencia previa → probable campo derivado/calculable
                    match_campo = "campo_calculado"
                    confianza = "MEDIA"
                    motivos.append(f"Valores numéricos ({', '.join(val_muestras[:3])}) sin coincidencia semántica directa.")
                    motivos.append("Se interpreta como campo derivado o calculable. Se usará para validación, no como fuente de verdad.")

        # 5. Detectar variante conocida (por nombre de encabezado)
        if not match_campo:
            if h_norm in VARIANT_HINTS or any(v in h_norm for v in VARIANT_HINTS if len(v) > 2):
                match_campo = "variante"
                confianza = "ALTA"
                motivos.append("El encabezado corresponde a una dimensión de variante inventariable (talla, color, presentación).")

        # 6. Detectar atributo conocido (por nombre de encabezado)
        if not match_campo:
            if h_norm in ATTRIBUTE_HINTS or any(a in h_norm for a in ATTRIBUTE_HINTS if len(a) > 2):
                match_campo = "atributo"
                confianza = "MEDIA"
                motivos.append("El encabezado corresponde a una característica descriptiva del producto (marca, modelo, material).")

        # 7. Fallback final
        if not match_campo:
            match_campo = "IGNORAR"
            if not muestras:
                motivos.append("No se dispone de datos de muestra para evaluación contextual. Se recomienda revisión manual.")
            else:
                motivos.append("No se encontró coincidencia semántica ni patrón contextual en los datos de muestra.")

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
# ETAPA 4: SIMULACIÓN DE IMPORTACIÓN PRE-CONFIRMACIÓN
# ══════════════════════════════════════════════════════════════════

def simular_importacion(batch_id, negocio_id, mapeo_usuario, granularidad_costos="POR_UNIDAD"):
    """
    Calcula exactamente el impacto de la importación antes de ejecutar la transacción atómica.
    """
    registros_staging = ejecutar_query(
        "SELECT fila_num, datos_raw_json FROM importaciones_staging WHERE batch_id=? AND negocio_id=? ORDER BY fila_num ASC",
        (batch_id, negocio_id), fetch=True
    ) or []

    if not registros_staging:
        return False, "No hay datos en staging para simular", None

    productos_procesados = set()
    productos_nuevos = set()
    clientes_nuevos = set()
    lotes_con_costo = 0
    lotes_sin_costo = 0
    ventas_con_costo = 0
    ventas_sin_costo = 0

    total_inversion = 0.0
    total_ingresos = 0.0
    total_cartera = 0.0
    total_abonos = 0.0

    prods_exist = ejecutar_query("SELECT LOWER(nombre) FROM productos WHERE negocio_id=?", (negocio_id,), fetch=True) or []
    prods_exist_set = {p[0] for p in prods_exist if p and p[0]}

    clis_exist = ejecutar_query("SELECT LOWER(nombre) FROM clientes WHERE negocio_id=?", (negocio_id,), fetch=True) or []
    clis_exist_set = {c[0] for c in clis_exist if c and c[0]}

    tipos_filas_cnt = {"COMPRA_Y_VENTA": 0, "SOLO_COMPRA": 0, "SOLO_VENTA": 0, "REGISTRO_HISTORICO": 0}

    for fila_num, raw_json in registros_staging:
        raw_row = json.loads(raw_json)
        mapped = {campo: raw_row.get(col, "").strip() for col, campo in mapeo_usuario.items() if campo and campo != "IGNORAR"}

        nombre_prod = (mapped.get('nombre_producto') or '').strip()
        if not nombre_prod:
            continue

        tipo_fila = determinar_tipo_fila(mapped)
        tipos_filas_cnt[tipo_fila] = tipos_filas_cnt.get(tipo_fila, 0) + 1

        key_p = nombre_prod.lower()
        productos_procesados.add(key_p)
        if key_p not in prods_exist_set:
            productos_nuevos.add(key_p)

        cli_nombre = (mapped.get('cliente_nombre') or '').strip()
        if cli_nombre and cli_nombre.lower() not in clis_exist_set:
            clientes_nuevos.add(cli_nombre.lower())

        cant = parse_money(mapped.get('cantidad')) or 1.0
        precio_v = parse_money(mapped.get('precio_venta'))
        costo_origen = parse_money(mapped.get('costo_unitario_origen'))
        tasa_cambio = parse_money(mapped.get('tasa_cambio'))
        costo_local = parse_money(mapped.get('costo_unitario_local'))
        costo_envio = parse_money(mapped.get('costo_envio'))
        costo_total_imp = parse_money(mapped.get('costo_total'))
        deuda_val = parse_money(mapped.get('saldo_pendiente'))
        abono_val = parse_money(mapped.get('abono_monto'))

        # Calcular costo unitario de adquisición
        if granularidad_costos == "POR_LOTE" and cant > 1 and costo_total_imp > 0:
            costo_adq = costo_total_imp / cant
        elif costo_total_imp > 0:
            costo_adq = costo_total_imp
        elif costo_local > 0:
            costo_adq = costo_local + costo_envio
        elif costo_origen > 0 and tasa_cambio > 0:
            costo_adq = (costo_origen * tasa_cambio) + costo_envio
        else:
            costo_adq = 0.0

        if tipo_fila in ("COMPRA_Y_VENTA", "SOLO_COMPRA"):
            if costo_adq > 0:
                lotes_con_costo += 1
                total_inversion += (costo_adq * cant)
            else:
                lotes_sin_costo += 1

        if tipo_fila in ("COMPRA_Y_VENTA", "SOLO_VENTA"):
            total_ingresos += (precio_v * cant)
            total_cartera += deuda_val
            total_abonos += abono_val

            if costo_adq > 0:
                ventas_con_costo += 1
            else:
                ventas_sin_costo += 1

    utilidad_estimada = total_ingresos - total_inversion

    return True, "Simulación generada", {
        "batch_id": batch_id,
        "total_filas": len(registros_staging),
        "productos_totales": len(productos_procesados),
        "productos_nuevos": len(productos_nuevos),
        "clientes_nuevos": len(clientes_nuevos),
        "lotes_a_crear": lotes_con_costo + lotes_sin_costo,
        "lotes_con_costo": lotes_con_costo,
        "lotes_sin_costo": lotes_sin_costo,
        "ventas_a_crear": ventas_con_costo + ventas_sin_costo,
        "ventas_con_costo": ventas_con_costo,
        "ventas_sin_costo": ventas_sin_costo,
        "total_inversion": total_inversion,
        "total_ingresos": total_ingresos,
        "utilidad_estimada": utilidad_estimada,
        "margen_estimado_pct": (utilidad_estimada / total_ingresos * 100.0) if total_ingresos > 0 else 0.0,
        "total_cartera": total_cartera,
        "total_abonos": total_abonos,
        "desglose_operaciones": tipos_filas_cnt
    }


# ══════════════════════════════════════════════════════════════════
# ETAPA 5: PROCESAMIENTO APROBADO CON TRANSACCIÓN ATÓMICA COMPLETA
# ══════════════════════════════════════════════════════════════════

def procesar_importacion_aprobada(batch_id, negocio_id, usuario_id, mapeo_usuario, autorizaciones=None, granularidad_costos="POR_UNIDAD"):
    """
    Confirmación transaccional atómica multi-módulo (BEGIN ... COMMIT/ROLLBACK).
    Si cualquier paso falla, se ejecuta ROLLBACK automático y no persiste ningún registro.
    Soporta trazabilidad mediante importacion_id (undo_token) en todas las tablas.
    """
    registros_staging = ejecutar_query(
        "SELECT fila_num, datos_raw_json FROM importaciones_staging WHERE batch_id=? AND negocio_id=? ORDER BY fila_num ASC",
        (batch_id, negocio_id), fetch=True
    ) or []

    if not registros_staging:
        return False, "No se encontraron datos para procesar", None

    undo_token = f"UNDO-{uuid.uuid4().hex[:12].upper()}"
    fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Recuperar hash de archivo si fue guardado en autorizaciones o calcularlo desde staging
    hash_archivo = None
    if autorizaciones and isinstance(autorizaciones, dict):
        hash_archivo = autorizaciones.get('hash_archivo')

    if not hash_archivo and registros_staging:
        filas_matriz_staging = [json.loads(r[1]) for r in registros_staging if r and r[1]]
        hash_archivo = calcular_hash_contenido(filas_matriz_staging)

    creados_info = {
        "productos": [], "atributos": [], "inventario": [],
        "compras": [], "lotes": [], "ventas": [],
        "clientes": [], "abonos": [], "movimientos": []
    }
    procesados = 0

    try:
        with transaccion() as (cursor, ph, is_pg):
            productos_cache = {}   # key_lower → pid
            clientes_cache = {}    # key_lower → cli_id
            inventario_cache = {}  # key_lower → inv_id

            for fila_num, raw_json in registros_staging:
                raw_row = json.loads(raw_json)
                mapped = {campo: raw_row.get(col, "").strip() for col, campo in mapeo_usuario.items() if campo and campo != "IGNORAR"}

                nombre_prod = (mapped.get('nombre_producto') or '').strip()
                if not nombre_prod:
                    continue

                tipo_fila = determinar_tipo_fila(mapped)

                cant = parse_money(mapped.get('cantidad')) or 1.0
                precio_v = parse_money(mapped.get('precio_venta'))
                costo_origen = parse_money(mapped.get('costo_unitario_origen'))
                tasa_cambio = parse_money(mapped.get('tasa_cambio'))
                costo_local = parse_money(mapped.get('costo_unitario_local'))
                costo_envio = parse_money(mapped.get('costo_envio'))
                costo_total_imp = parse_money(mapped.get('costo_total'))
                cli_nombre = (mapped.get('cliente_nombre') or '').strip()
                deuda_val = parse_money(mapped.get('saldo_pendiente'))
                abono_val = parse_money(mapped.get('abono_monto'))
                fecha_v = mapped.get('fecha_operacion') or datetime.now().strftime("%Y-%m-%d")
                if len(fecha_v) == 10:
                    fecha_v = f"{fecha_v} 12:00:00"

                # Calcular costo de adquisición unitario
                if granularidad_costos == "POR_LOTE" and cant > 1 and costo_total_imp > 0:
                    costo_adq = costo_total_imp / cant
                elif costo_total_imp > 0:
                    costo_adq = costo_total_imp
                elif costo_local > 0:
                    costo_adq = costo_local + costo_envio
                elif costo_origen > 0 and tasa_cambio > 0:
                    costo_adq = (costo_origen * tasa_cambio) + costo_envio
                else:
                    costo_adq = 0.0

                # ── 1. PRODUCTO (tipo_producto = 'COMERCIALIZADO') ──
                key_p = nombre_prod.lower()
                if key_p in productos_cache:
                    pid = productos_cache[key_p]
                else:
                    cursor.execute(
                        f"SELECT id FROM productos WHERE LOWER(nombre)=LOWER({ph}) AND negocio_id={ph}",
                        (nombre_prod, negocio_id)
                    )
                    exist_p = cursor.fetchone()
                    if exist_p:
                        pid = exist_p[0]
                        if autorizaciones and autorizaciones.get('actualizar_precios') and precio_v > 0:
                            cursor.execute(
                                f"UPDATE productos SET precio={ph} WHERE id={ph} AND negocio_id={ph}",
                                (precio_v, pid, negocio_id)
                            )
                    else:
                        categoria = (mapped.get('categoria') or '').strip() or None
                        subcategoria = (mapped.get('subcategoria') or '').strip() or None
                        pid = insertar_con_id(cursor,
                            f"""INSERT INTO productos 
                                (negocio_id, nombre, precio, tipo_producto, categoria, subcategoria, importacion_id)
                                VALUES ({ph}, {ph}, {ph}, 'COMERCIALIZADO', {ph}, {ph}, {ph})""",
                            (negocio_id, nombre_prod, precio_v, categoria, subcategoria, undo_token),
                            ph, is_pg)
                        creados_info["productos"].append(pid)
                    productos_cache[key_p] = pid

                # ── 2. ATRIBUTOS Y VARIANTES EN PRODUCTO_ATRIBUTOS ──
                for col_excel, campo_target in mapeo_usuario.items():
                    if campo_target in ("atributo", "variante"):
                        val = raw_row.get(col_excel, "").strip()
                        if val:
                            attr_id = insertar_con_id(cursor,
                                f"""INSERT INTO producto_atributos 
                                    (negocio_id, producto_id, nombre_atributo, valor_atributo, tipo, importacion_id)
                                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})""",
                                (negocio_id, pid, col_excel, val, campo_target.upper(), undo_token),
                                ph, is_pg)
                            creados_info["atributos"].append(attr_id)

                # ── 3. INVENTARIO + PRODUCTO_INSUMO + COMPRAS + LOTES ──
                inv_id = None
                lote_id = None

                if tipo_fila in ("COMPRA_Y_VENTA", "SOLO_COMPRA"):
                    if key_p in inventario_cache:
                        inv_id = inventario_cache[key_p]
                        # Incrementar stock
                        cursor.execute(
                            f"UPDATE inventario SET stock_actual = stock_actual + {ph} WHERE id={ph} AND negocio_id={ph}",
                            (cant, inv_id, negocio_id)
                        )
                    else:
                        cursor.execute(
                            f"SELECT id FROM inventario WHERE LOWER(nombre)=LOWER({ph}) AND negocio_id={ph}",
                            (nombre_prod, negocio_id)
                        )
                        exist_inv = cursor.fetchone()
                        if exist_inv:
                            inv_id = exist_inv[0]
                            cursor.execute(
                                f"UPDATE inventario SET stock_actual = stock_actual + {ph} WHERE id={ph} AND negocio_id={ph}",
                                (cant, inv_id, negocio_id)
                            )
                        else:
                            codigo_inv = (mapped.get('codigo_sku') or '').strip() or None
                            inv_id = insertar_con_id(cursor,
                                f"""INSERT INTO inventario 
                                    (negocio_id, nombre, stock_actual, codigo, costo_unitario_base, importacion_id)
                                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})""",
                                (negocio_id, nombre_prod, cant, codigo_inv, costo_adq, undo_token),
                                ph, is_pg)
                            creados_info["inventario"].append(inv_id)
                        inventario_cache[key_p] = inv_id

                    # ── Enlace Producto ↔ Inventario via producto_insumo (tipo_relacion='PRODUCTO_DIRECTO') ──
                    cursor.execute(
                        f"SELECT id FROM producto_insumo WHERE producto_id={ph} AND insumo_id={ph} AND negocio_id={ph}",
                        (pid, inv_id, negocio_id)
                    )
                    if not cursor.fetchone():
                        insertar_con_id(cursor,
                            f"""INSERT INTO producto_insumo 
                                (negocio_id, producto_id, insumo_id, cantidad_usada, tipo_relacion)
                                VALUES ({ph}, {ph}, {ph}, 1.0, 'PRODUCTO_DIRECTO')""",
                            (negocio_id, pid, inv_id),
                            ph, is_pg)

                    # ── Compra y Lote de adquisición ──
                    codigo_lote = f"IMP-{undo_token[-6:]}-F{fila_num}"
                    costo_total_lote = costo_adq * cant

                    compra_id = insertar_con_id(cursor,
                        f"""INSERT INTO compras_entradas 
                            (negocio_id, fecha_compra, proveedor, insumo_id, codigo_lote, 
                             cantidad_comprada, costo_unitario_compra, costo_total_compra, importacion_id, usuario_id)
                            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})""",
                        (negocio_id, fecha_v, cli_nombre or "Proveedor Importación", inv_id, codigo_lote,
                         cant, costo_adq, costo_total_lote, undo_token, usuario_id),
                        ph, is_pg)
                    creados_info["compras"].append(compra_id)

                    lote_id = insertar_con_id(cursor,
                        f"""INSERT INTO lotes_inventario 
                            (negocio_id, compra_id, insumo_id, codigo_lote, fecha_compra, 
                             cantidad_inicial, cantidad_disponible, costo_unitario, proveedor, estado, importacion_id)
                            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 'ACTIVO', {ph})""",
                        (negocio_id, compra_id, inv_id, codigo_lote, fecha_v[:10],
                         cant, cant, costo_adq, cli_nombre or "Proveedor Importación", undo_token),
                        ph, is_pg)
                    creados_info["lotes"].append(lote_id)

                    # Movimiento de entrada del lote
                    mov_e_id = insertar_con_id(cursor,
                        f"""INSERT INTO movimientos_lote 
                            (negocio_id, lote_id, fecha, tipo, cantidad, costo_unitario_lote, costo_subtotal, referencia, usuario_id)
                            VALUES ({ph}, {ph}, {ph}, 'ENTRADA', {ph}, {ph}, {ph}, {ph}, {ph})""",
                        (negocio_id, lote_id, fecha_v, cant, costo_adq, costo_total_lote, f"Importación {undo_token}", usuario_id),
                        ph, is_pg)
                    creados_info["movimientos"].append(mov_e_id)

                # ── 4. CLIENTE ──
                cli_id = None
                if cli_nombre:
                    key_c = cli_nombre.lower()
                    if key_c in clientes_cache:
                        cli_id = clientes_cache[key_c]
                    else:
                        cursor.execute(
                            f"SELECT id FROM clientes WHERE LOWER(nombre)=LOWER({ph}) AND negocio_id={ph}",
                            (cli_nombre, negocio_id)
                        )
                        exist_c = cursor.fetchone()
                        if exist_c:
                            cli_id = exist_c[0]
                        else:
                            cli_id = insertar_con_id(cursor,
                                f"INSERT INTO clientes (negocio_id, nombre, importacion_id) VALUES ({ph}, {ph}, {ph})",
                                (negocio_id, cli_nombre, undo_token), ph, is_pg)
                            creados_info["clientes"].append(cli_id)
                        clientes_cache[key_c] = cli_id

                # ── 5. REGISTRO DE VENTA ──
                if tipo_fila in ("COMPRA_Y_VENTA", "SOLO_VENTA"):
                    costo_venta_total = (costo_adq * cant) if tipo_fila == "COMPRA_Y_VENTA" else 0.0
                    metodo_pago = "CRÉDITO" if deuda_val > 0 else "Efectivo"
                    total_venta = precio_v * cant

                    vid = insertar_con_id(cursor,
                        f"""INSERT INTO ventas 
                            (negocio_id, fecha, producto_id, cantidad, total, metodo_pago, 
                             costo_historico_total, precio_historico_unitario, usuario_id,
                             cliente_nombre, cliente_id, saldo_pendiente, importacion_id)
                            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})""",
                        (negocio_id, fecha_v, pid, cant, total_venta, metodo_pago,
                         costo_venta_total, precio_v, usuario_id,
                         cli_nombre or None, cli_id, deuda_val, undo_token),
                        ph, is_pg)
                    creados_info["ventas"].append(vid)
                    procesados += 1

                    # Si fue COMPRA_Y_VENTA, la venta consume la existencia recién ingresada
                    if tipo_fila == "COMPRA_Y_VENTA" and inv_id and lote_id:
                        cursor.execute(
                            f"UPDATE inventario SET stock_actual = stock_actual - {ph} WHERE id={ph} AND negocio_id={ph}",
                            (cant, inv_id, negocio_id)
                        )
                        cursor.execute(
                            f"""UPDATE lotes_inventario 
                                SET cantidad_disponible = cantidad_disponible - {ph},
                                    estado = CASE WHEN (cantidad_disponible - {ph}) <= 0.0001 THEN 'AGOTADO' ELSE 'ACTIVO' END
                                WHERE id={ph} AND negocio_id={ph}""",
                            (cant, cant, lote_id, negocio_id)
                        )

                        mov_s_id = insertar_con_id(cursor,
                            f"""INSERT INTO movimientos_lote 
                                (negocio_id, lote_id, fecha, tipo, cantidad, costo_unitario_lote, costo_subtotal, referencia, venta_id, usuario_id)
                                VALUES ({ph}, {ph}, {ph}, 'SALIDA_VENTA', {ph}, {ph}, {ph}, {ph}, {ph}, {ph})""",
                            (negocio_id, lote_id, fecha_v, cant, costo_adq, costo_venta_total, f"Venta #{vid} (Importación {undo_token})", vid, usuario_id),
                            ph, is_pg)
                        creados_info["movimientos"].append(mov_s_id)

                    # Abono inicial si aplica
                    if abono_val > 0 and vid:
                        abono_id = insertar_con_id(cursor,
                            f"""INSERT INTO abonos_cartera 
                                (negocio_id, venta_id, fecha, monto, metodo_pago, usuario_id, observacion)
                                VALUES ({ph}, {ph}, {ph}, {ph}, 'Efectivo', {ph}, 'Abono cargado por Importador Inteligente')""",
                            (negocio_id, vid, fecha_v, abono_val, usuario_id),
                            ph, is_pg)
                        creados_info["abonos"].append(abono_id)

            # ── 6. MEMORIA DE MAPEO ──
            insertar_con_id(cursor,
                f"INSERT INTO mapeos_importacion (negocio_id, nombre_mapeo, estructura_columnas_json, fecha_creacion) VALUES ({ph}, 'Mapeo Aprobado Tenant', {ph}, {ph})",
                (negocio_id, json.dumps(mapeo_usuario, ensure_ascii=False), fecha_hoy),
                ph, is_pg)

            # ── 7. AUDITORÍA CON UNDO TOKEN Y HASH ARCHIVO ──
            insertar_con_id(cursor,
                f"""INSERT INTO auditoria_importaciones 
                    (negocio_id, usuario_id, fecha, undo_token, nombre_archivo, 
                     total_registros, creados_json, hash_archivo, estado)
                    VALUES ({ph}, {ph}, {ph}, {ph}, 'Importación Excel Empresarial', {ph}, {ph}, {ph}, 'COMPLETADO')""",
                (negocio_id, usuario_id, fecha_hoy, undo_token, procesados,
                 json.dumps(creados_info, ensure_ascii=False), hash_archivo),
                ph, is_pg)

        # COMMIT AUTOMÁTICO AL SALIR DEL BLOQUE CONTEXTUAL
        print(f"[IMPORTADOR ÉXITO ATÓMICO] Transacción atómica ejecutada con éxito. undo_token={undo_token}")
        return True, f"¡Importación exitosa! Se procesaron {procesados} registros en una única transacción atómica.", {
            "undo_token": undo_token,
            "procesados": procesados,
            "resumen": creados_info
        }

    except Exception as e_trans:
        print(f"[IMPORTADOR ERROR ATÓMICO - ROLLBACK EJECUTADO] {e_trans}")
        return False, f"Error en el procesamiento (ROLLBACK automático ejecutado, 0 registros creados): {str(e_trans)}", None


# ══════════════════════════════════════════════════════════════════
# ETAPA 6: REVERSIÓN ASISTIDA E INTELIGENTE
# ══════════════════════════════════════════════════════════════════

def revertir_importacion(undo_token, negocio_id, usuario_id):
    """
    Reversión inteligente:
    1. Si no hay operaciones posteriores → Reversión completa (elimina todos los registros de la importación).
    2. Si existen operaciones posteriores de esos productos → Reversión asistida (elimina ventas/lotes de la importación, preserva productos/clientes).
    """
    audit = ejecutar_query(
        "SELECT id, creados_json, estado FROM auditoria_importaciones WHERE undo_token=? AND negocio_id=?",
        (undo_token, negocio_id), fetch=True
    )
    if not audit or len(audit) == 0 or len(audit[0]) < 3:
        return False, "Token de reversión no encontrado o ya fue revertido", None

    a_id, creados_json, estado = audit[0]
    if estado in ('REVERTIDO', 'REVERTIDO_PARCIAL'):
        return False, f"Esta importación ya fue revertida anteriormente (estado: {estado})", None

    creados = json.loads(creados_json) if creados_json else {}
    prods_creados = creados.get('productos', [])

    # Comprobar si existen ventas posteriores de estos productos que NO sean de esta importación
    tiene_ops_posteriores = False
    if prods_creados:
        ph_list = ", ".join(["?"] * len(prods_creados))
        params_check = [negocio_id, undo_token] + prods_creados
        query_check = f"SELECT COUNT(*) FROM ventas WHERE negocio_id=? AND (importacion_id IS NULL OR importacion_id != ?) AND producto_id IN ({ph_list})"
        res_ops = ejecutar_query(query_check, params_check, fetch=True)
        if res_ops and res_ops[0][0] > 0:
            tiene_ops_posteriores = True

    try:
        with transaccion() as (cursor, ph, is_pg):
            # Eliminar abonos de la importación
            cursor.execute(
                f"DELETE FROM abonos_cartera WHERE venta_id IN (SELECT id FROM ventas WHERE importacion_id={ph} AND negocio_id={ph}) AND negocio_id={ph}",
                (undo_token, negocio_id, negocio_id)
            )
            # Eliminar movimientos de lote de la importación
            cursor.execute(
                f"DELETE FROM movimientos_lote WHERE (referencia LIKE {ph} OR venta_id IN (SELECT id FROM ventas WHERE importacion_id={ph})) AND negocio_id={ph}",
                (f"%{undo_token}%", undo_token, negocio_id)
            )
            # Eliminar ventas de la importación
            cursor.execute(f"DELETE FROM ventas WHERE importacion_id={ph} AND negocio_id={ph}", (undo_token, negocio_id))
            # Eliminar lotes de la importación
            cursor.execute(f"DELETE FROM lotes_inventario WHERE importacion_id={ph} AND negocio_id={ph}", (undo_token, negocio_id))
            # Eliminar compras de la importación
            cursor.execute(f"DELETE FROM compras_entradas WHERE importacion_id={ph} AND negocio_id={ph}", (undo_token, negocio_id))
            # Eliminar atributos de la importación
            cursor.execute(f"DELETE FROM producto_atributos WHERE importacion_id={ph} AND negocio_id={ph}", (undo_token, negocio_id))

            if not tiene_ops_posteriores:
                # Reversión COMPLETA: eliminar también enlaces, inventario y productos creados
                cursor.execute(f"DELETE FROM producto_insumo WHERE producto_id IN (SELECT id FROM productos WHERE importacion_id={ph}) AND negocio_id={ph}", (undo_token, negocio_id))
                cursor.execute(f"DELETE FROM inventario WHERE importacion_id={ph} AND negocio_id={ph}", (undo_token, negocio_id))
                cursor.execute(f"DELETE FROM productos WHERE importacion_id={ph} AND negocio_id={ph}", (undo_token, negocio_id))
                cursor.execute(f"DELETE FROM clientes WHERE importacion_id={ph} AND negocio_id={ph}", (undo_token, negocio_id))
                cursor.execute(f"UPDATE auditoria_importaciones SET estado='REVERTIDO' WHERE id={ph}", (a_id,))
                msg = f"Importación {undo_token} revertida completamente. Se eliminaron todos los registros generados."
            else:
                # Reversión ASISTIDA: conservar productos/clientes que tienen ventas manuales posteriores
                cursor.execute(f"UPDATE auditoria_importaciones SET estado='REVERTIDO_PARCIAL' WHERE id={ph}", (a_id,))
                msg = f"Importación {undo_token} revertida (asistida). Se eliminaron las ventas y lotes de la importación, pero se conservaron los productos y clientes por tener operaciones posteriores."

        return True, msg, {"undo_token": undo_token, "modo": "COMPLETO" if not tiene_ops_posteriores else "PARCIAL"}

    except Exception as e_rev:
        return False, f"Error al revertir la importación: {str(e_rev)}", None

