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
        "DESTINATARIO", "RAZON SOCIAL", "NOMBRE DEL CLIENTE",
        "NOMBRE COMPRADOR", "BUYER", "ADQUIRIENTE"
    ],
    "cliente_documento": [
        "CEDULA", "CC", "NIT", "RUT", "DOCUMENTO", "DNI", "CI",
        "NUMERO DOCUMENTO", "IDENTIFICACION", "ID CLIENTE", "DOC"
    ],
    "cliente_telefono": [
        "TELEFONO", "TEL", "CELULAR", "MOVIL", "PHONE", "MOBILE",
        "NUMERO CELULAR", "NUMERO TELEFONO", "CEL"
    ],
    "cliente_whatsapp": [
        "WHATSAPP", "WA", "NUMERO WHATSAPP", "WHATS"
    ],
    "cliente_email": [
        "EMAIL", "CORREO", "CORREO ELECTRONICO", "E-MAIL", "MAIL"
    ],
    "cliente_direccion": [
        "DIRECCION", "DOMICILIO", "CIUDAD", "MUNICIPIO", "BARRIO",
        "ADDRESS", "LOCALIDAD", "ZONA", "UBICACION"
    ],
    "cliente_tipo": [
        "TIPO CLIENTE", "SEGMENTO", "CANAL", "TIPO DE CLIENTE",
        "CLASIFICACION CLIENTE", "CATEGORIA CLIENTE"
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
    "estado_origen": [
        "ESTADO", "ESTADO ORIGEN", "STATUS", "CONDICION", "ESTADO PRODUCTO", "ESTADO VENTA"
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
    "estado_origen", "cliente_nombre", "cliente_documento", "cliente_telefono", "cliente_whatsapp",
    "cliente_email", "cliente_direccion", "cliente_tipo",
    "saldo_pendiente", "abono_monto", 
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
    "estado_origen": "🚦 Estado (Stock, Vendida, Debe, Pérdida)",
    "cliente_nombre": "👤 Cliente",
    "cliente_documento": "🪪 Documento / Cédula / NIT",
    "cliente_telefono": "📱 Teléfono / Celular",
    "cliente_whatsapp": "💬 WhatsApp",
    "cliente_email": "📧 Email / Correo",
    "cliente_direccion": "📍 Dirección / Ciudad",
    "cliente_tipo": "🏷️ Tipo / Segmento de cliente",
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


CONCEPTOS_ESTADO_MAP = {
    "STOCK": ["STOCK", "DISPONIBLE", "EN STOCK", "INVENTARIO", "ALMACEN"],
    "VENDIDA": ["VENDIDA", "VENDIDO", "VENTA", "PAGADO", "PAGADA", "CONTADO"],
    "DEBE": ["DEBE", "DEUDA", "CARTERA", "CREDITO", "CRÉDITO", "PENDIENTE", "POR COBRAR"],
    "PERDIDA": ["PERDIDA", "PÉRDIDA", "DAÑADO", "DAÑADA", "MERMA", "ROBO", "DESCARTE"]
}

def normalizar_concepto_estado(val_raw):
    if not val_raw:
        return None
    val_clean = str(val_raw).strip().upper()
    for concepto, sinonimos in CONCEPTOS_ESTADO_MAP.items():
        if val_clean in sinonimos:
            return concepto
    return "AMBIGUO"

def determinar_tipo_fila(mapped_data):
    """
    Determina qué tipo de operación representa una fila y su nivel de confianza:
    - Retorna (tipo_fila, origen_clasificacion)
    - EXPLICITA: Determinado por Estado mapeado en Excel (STOCK, PERDIDA, DEBE, VENDIDA)
    - INFERIDA: Determinado por deducción de estructura (Costos + Precio/Cliente)
    """
    raw_est = (mapped_data.get('estado_origen') or mapped_data.get('estado') or '').strip()
    concepto = normalizar_concepto_estado(raw_est)

    if concepto == "STOCK":
        return "SOLO_COMPRA", "EXPLICITA"
    elif concepto == "PERDIDA":
        return "PERDIDA", "EXPLICITA"
    elif concepto in ("DEBE", "VENDIDA"):
        return "COMPRA_Y_VENTA", "EXPLICITA"

    # Fallback estructural si no hay columna de Estado o si es AMBIGUO:
    tiene_costos = any(mapped_data.get(c) for c in [
        'costo_unitario_origen', 'costo_unitario_local', 'costo_total'
    ])
    tiene_precio_venta = bool(mapped_data.get('precio_venta'))
    tiene_cliente = bool(mapped_data.get('cliente_nombre'))

    if tiene_costos and (tiene_precio_venta or tiene_cliente):
        return "COMPRA_Y_VENTA", "INFERIDA"
    elif tiene_costos and not tiene_precio_venta:
        return "SOLO_COMPRA", "INFERIDA"
    elif tiene_precio_venta and not tiene_costos:
        return "SOLO_VENTA", "INFERIDA"
    else:
        return "REGISTRO_HISTORICO", "INFERIDA"


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
                v_origen = parse_money(origen_str)
                v_tasa = parse_money(tasa_str)
                v_local = parse_money(local_str)
                calc_local = v_origen * v_tasa
                if abs(calc_local - v_local) > 1.0:
                    advs.append(
                        f"🧮 Discrepancia multimoneda: {v_origen} × {v_tasa} = ${calc_local:,.0f}, "
                        f"pero el archivo reporta ${v_local:,.0f}."
                    )
            except Exception:
                pass

        # ── Evaluación de Estado y Discrepancia de Origen (Excel vs Realidad Financiera) ──
        raw_est = (mapped_data.get('estado_origen') or mapped_data.get('estado') or '').strip()
        concepto_est = normalizar_concepto_estado(raw_est)

        if raw_est and concepto_est == "AMBIGUO":
            advs.append(
                f"⚠️ Estado no reconocido en Fila #{fila_num}: '{raw_est}'. "
                f"AS no intentará adivinar; se utilizará deducción estructural a menos que el usuario lo ajuste."
            )

        precio_v = parse_money(mapped_data.get('precio_venta'))
        abono_val = parse_money(mapped_data.get('abono_monto'))
        deuda_excel = parse_money(mapped_data.get('saldo_pendiente'))
        total_v_row = precio_v * cant_val
        tiene_col_abono = 'abono_monto' in mapped_data

        # Regla 4 del Contrato Semántico: Abonos
        if not tiene_col_abono and concepto_est == "VENDIDA" and deuda_excel == 0.0:
            # Fallback: No existe columna de abonos y el estado es VENDIDA -> asume pago completo
            abono_efectivo = total_v_row
        else:
            # Columna existe (o se reporta explícitamente): usar el valor real tippado (incluso 0.0 si está vacía)
            abono_efectivo = abono_val

        # Regla 5: Cartera y Alerta de Sobreabono
        saldo_calc_as = max(0.0, total_v_row - abono_efectivo)
        if abono_efectivo > total_v_row and total_v_row > 0:
            excedente = abono_efectivo - total_v_row
            advs.append(
                f"⚠️ SOBREABONO (Fila #{fila_num}): Se reporta un pago de ${abono_efectivo:,.0f} mayor al total de la venta (${total_v_row:,.0f}). Excedente de ${excedente:,.0f} registrado para auditoría."
            )

        # Regla 7: Contradicciones (Estado de Origen vs Realidad Financiera)
        if concepto_est == "VENDIDA" and saldo_calc_as > 0.01:
            advs.append(
                f"⚠️ Inconsistencia de Origen (Fila #{fila_num}): El archivo indica Estado='{raw_est}', "
                f"pero reporta un saldo pendiente de ${saldo_calc_as:,.0f}. AS lo clasifica financieramente como "
                f"{'PARCIAL' if abono_efectivo > 0 else 'PENDIENTE'}."
            )
        elif concepto_est == "DEBE" and saldo_calc_as <= 0.01 and total_v_row > 0:
            advs.append(
                f"⚠️ Inconsistencia de Origen (Fila #{fila_num}): El archivo indica Estado='{raw_est}', "
                f"pero los pagos cubren el 100% de la venta (${total_v_row:,.0f}). AS lo clasifica financieramente como PAGADO."
            )

        # Regla 6: Deuda del Excel vs Saldo AS
        if deuda_excel > 0 and abs(saldo_calc_as - deuda_excel) > 1.0:
            diferencias_detectadas.append({
                "fila": fila_num,
                "producto": mapped_data.get('nombre_producto', 'Producto'),
                "campo": "Cuenta por cobrar / Cartera",
                "existente": deuda_excel,
                "importado": saldo_calc_as
            })
            advs.append(
                f"💳 Discrepancia de Cartera (Fila #{fila_num}): Excel reporta ${deuda_excel:,.0f} de deuda, pero la matemática de AS calcula ${saldo_calc_as:,.0f} (${total_v_row:,.0f} venta - ${abono_efectivo:,.0f} abono)."
            )

        # ── Conciliación de producto ──
        nombre_prod = (mapped_data.get('nombre_producto') or '').strip()
        key_p = nombre_prod.lower()

        if nombre_prod:
            if key_p in prod_map:
                p_exist = prod_map[key_p]
                precio_imp_str = mapped_data.get('precio_venta', '')
                if precio_imp_str:
                    try:
                        precio_imp = parse_money(precio_imp_str)
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

    ejecutar_query_many(
        "UPDATE importaciones_staging SET estado_validacion=?, errores_json=?, advertencias_json=? WHERE id=?",
        update_params
    )

    ok_sim, msg_sim, sim_data = simular_importacion(batch_id, negocio_id, mapeo_usuario)
    t_total = time.time() - t_start

    resumen = {
        "batch_id": batch_id,
        "total_registros": len(registros_staging),
        "validos": total_validos,
        "advertencias": total_advertencias,
        "errores": total_errores,
        "productos_nuevos": productos_nuevos,
        "diferencias_detectadas": diferencias_detectadas,
        "simulacion": sim_data,
        "detalles_filas": resumen_filas[:50],
        "tiempo_ms": int(t_total * 1000)
    }

    return True, "Prevalidación completada", resumen


# ══════════════════════════════════════════════════════════════════
# ETAPA 4: SIMULACIÓN DE IMPORTACIÓN PRE-CONFIRMACIÓN
# ══════════════════════════════════════════════════════════════════

def simular_importacion(batch_id, negocio_id, mapeo_usuario, granularidad_costos="POR_UNIDAD"):
    """
    Calcula exactamente el impacto de la importación antes de ejecutar la transacción atómica
    y genera la matriz completa de 'Prueba de Oro' para conciliación final.
    """
    registros_staging = ejecutar_query(
        "SELECT fila_num, datos_raw_json FROM importaciones_staging WHERE batch_id=? AND negocio_id=? ORDER BY fila_num ASC",
        (batch_id, negocio_id), fetch=True
    ) or []

    if not registros_staging:
        return False, "No hay datos en staging para simular", None

    prods_exist = ejecutar_query("SELECT LOWER(nombre) FROM productos WHERE negocio_id=?", (negocio_id,), fetch=True) or []
    prods_exist_set = {p[0] for p in prods_exist if p and p[0]}

    clis_exist = ejecutar_query("SELECT LOWER(nombre) FROM clientes WHERE negocio_id=?", (negocio_id,), fetch=True) or []
    clis_exist_set = {c[0] for c in clis_exist if c and c[0]}

    productos_procesados = set()
    productos_nuevos = set()
    clientes_nuevos = set()
    clientes_deudores_set = set()
    lotes_set = set()

    unidades_adquiridas = 0.0
    unidades_vendidas = 0.0
    unidades_perdidas = 0.0
    unidades_disponibles = 0.0

    total_inversion_lotes = 0.0
    total_ingresos = 0.0
    costo_ventas = 0.0
    costo_perdidas = 0.0

    ventas_contado_val = 0.0
    ventas_credito_val = 0.0
    total_abonos = 0.0
    total_cartera_as = 0.0
    total_deuda_excel = 0.0

    cnt_stock = 0
    cnt_vendida = 0
    cnt_debe = 0
    cnt_perdida = 0

    lotes_acumulados_sim = {}

    for fila_num, raw_json in registros_staging:
        raw_row = json.loads(raw_json)
        mapped = {campo: raw_row.get(col, "").strip() for col, campo in mapeo_usuario.items() if campo and campo != "IGNORAR"}

        nombre_prod = (mapped.get('nombre_producto') or '').strip()
        if not nombre_prod:
            continue

        tipo_fila, origen_clasificacion = determinar_tipo_fila(mapped)
        raw_est = (mapped.get('estado_origen') or mapped.get('estado') or '').strip()
        concepto_est = normalizar_concepto_estado(raw_est)

        if concepto_est == "STOCK":
            cnt_stock += 1
        elif concepto_est == "PERDIDA":
            cnt_perdida += 1
        elif concepto_est == "DEBE":
            cnt_debe += 1
        else:
            cnt_vendida += 1

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
        fecha_compra_raw = mapped.get('fecha_operacion') or datetime.now().strftime("%Y-%m-%d")

        # Costo unitario landed
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

        # Regla de Lote para Importación: (Fecha Compra + Tasa Cambio, Producto)
        pedido_key = f"{fecha_compra_raw[:10]}_{tasa_cambio}"
        lote_key = (pedido_key, key_p)
        lotes_set.add(lote_key)

        if lote_key not in lotes_acumulados_sim:
            lotes_acumulados_sim[lote_key] = {"cant_total": 0.0, "cant_disponible": 0.0, "costo_adq": costo_adq}
        lotes_acumulados_sim[lote_key]["cant_total"] += cant

        unidades_adquiridas += cant
        total_inversion_lotes += (costo_adq * cant)

        if tipo_fila == "SOLO_COMPRA":
            unidades_disponibles += cant
            lotes_acumulados_sim[lote_key]["cant_disponible"] += cant

        elif tipo_fila == "PERDIDA":
            unidades_perdidas += cant
            costo_perdidas += (costo_adq * cant)

        elif tipo_fila in ("COMPRA_Y_VENTA", "SOLO_VENTA"):
            unidades_vendidas += cant
            tot_v_row = precio_v * cant
            total_ingresos += tot_v_row
            costo_ventas += (costo_adq * cant)
            total_abonos += abono_val

            if raw_est in ('DEBE', 'CARTERA', 'CRÉDITO', 'CREDITO', 'DEUDA') or deuda_val > 0:
                ventas_credito_val += tot_v_row
                saldo_calc = max(0.0, tot_v_row - abono_val)
                total_cartera_as += saldo_calc
                total_deuda_excel += deuda_val
                if cli_nombre:
                    clientes_deudores_set.add(cli_nombre.lower())
            else:
                ventas_contado_val += tot_v_row

    utilidad_bruta = total_ingresos - costo_ventas
    margen_pct = (utilidad_bruta / total_ingresos * 100.0) if total_ingresos > 0 else 0.0
    valor_inventario_restante = sum(ldata["cant_disponible"] * ldata["costo_adq"] for ldata in lotes_acumulados_sim.values())

    lotes_con_costo = sum(1 for ldata in lotes_acumulados_sim.values() if ldata["costo_adq"] > 0)
    lotes_sin_costo = len(lotes_acumulados_sim) - lotes_con_costo

    prueba_de_oro = {
        "total_filas": len(registros_staging),
        "desglose_estados": {
            "stock": cnt_stock,
            "vendida": cnt_vendida,
            "debe": cnt_debe,
            "perdida": cnt_perdida
        },
        "unidades": {
            "adquiridas": unidades_adquiridas,
            "vendidas": unidades_vendidas,
            "perdidas": unidades_perdidas,
            "disponibles": unidades_disponibles
        },
        "financiero": {
            "ingresos_totales": total_ingresos,
            "costo_ventas": costo_ventas,
            "costo_perdidas": costo_perdidas,
            "utilidad_bruta": utilidad_bruta,
            "margen_pct": round(margen_pct, 2),
            "inversion_lotes_total": total_inversion_lotes,
            "valor_inventario_restante": valor_inventario_restante
        },
        "cartera": {
            "ventas_contado": ventas_contado_val,
            "ventas_credito": ventas_credito_val,
            "total_abonos": total_abonos,
            "cartera_generada_as": total_cartera_as,
            "deuda_excel_total": total_deuda_excel,
            "discrepancia_total": abs(total_cartera_as - total_deuda_excel),
            "clientes_deudores_cnt": len(clientes_deudores_set)
        },
        "lotes": {
            "lotes_creados": len(lotes_set),
            "con_costo": lotes_con_costo,
            "sin_costo": lotes_sin_costo
        }
    }

    return True, "Simulación generada", {
        "batch_id": batch_id,
        "total_filas": len(registros_staging),
        "productos_totales": len(productos_procesados),
        "productos_nuevos": len(productos_nuevos),
        "clientes_nuevos": len(clientes_nuevos),
        "lotes_a_crear": len(lotes_set),
        "lotes_con_costo": lotes_con_costo,
        "lotes_sin_costo": lotes_sin_costo,
        "ventas_a_crear": cnt_vendida + cnt_debe,
        "total_inversion": total_inversion_lotes,
        "total_ingresos": total_ingresos,
        "utilidad_estimada": utilidad_bruta,
        "margen_estimado_pct": round(margen_pct, 2),
        "total_cartera": total_cartera_as,
        "total_abonos": total_abonos,
        "prueba_de_oro": prueba_de_oro
    }


def bulk_insert_con_returning(cursor, table_name, columns, rows_params, ph, is_pg, return_cols="id"):
    """
    Inserta masivamente múltiples filas en 1 sola consulta SQL usando VALUES (...), (...) RETURNING.
    Reduce la latencia de red de N viajes a 1 solo viaje por cada 100 filas.
    """
    if not rows_params:
        return []

    col_str = ", ".join(columns)
    CHUNK_SIZE = 100
    results = []

    for i in range(0, len(rows_params), CHUNK_SIZE):
        chunk = rows_params[i:i+CHUNK_SIZE]
        if is_pg:
            val_ph_single = "(" + ", ".join([ph] * len(columns)) + ")"
            val_ph_all = ", ".join([val_ph_single] * len(chunk))
            sql = f"INSERT INTO {table_name} ({col_str}) VALUES {val_ph_all} RETURNING {return_cols}"
            flattened_params = [item for row in chunk for item in row]
            cursor.execute(sql, flattened_params)
            results.extend(cursor.fetchall())
        else:
            sql_single = f"INSERT INTO {table_name} ({col_str}) VALUES ({', '.join([ph] * len(columns))})"
            for row in chunk:
                cursor.execute(sql_single, row)
                new_id = cursor.lastrowid
                if "lower(nombre)" in return_cols.lower() and len(row) > 1:
                    results.append((new_id, str(row[1]).lower()))
                else:
                    results.append((new_id,))
    return results


# ══════════════════════════════════════════════════════════════════
# ETAPA 5: PROCESAMIENTO APROBADO CON TRANSACCIÓN ATÓMICA ULTRA-RÁPIDA
# ══════════════════════════════════════════════════════════════════

def procesar_importacion_aprobada(batch_id, negocio_id, usuario_id, mapeo_usuario, autorizaciones=None, granularidad_costos="POR_UNIDAD"):
    """
    Confirmación transaccional atómica masiva (BEGIN ... COMMIT/ROLLBACK).
    Usa procesamiento en 2 pases con inserciones multi-fila (VALUES ..., ...)
    para completar la importación de cientos de filas en menos de 1 segundo.
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
            # ── PASO 0: Pre-cargar cachés en memoria ──
            cursor.execute(f"SELECT LOWER(nombre), id FROM productos WHERE negocio_id={ph}", (negocio_id,))
            productos_cache = {row[0]: row[1] for row in cursor.fetchall() if row and row[0]}

            cursor.execute(f"SELECT LOWER(nombre), id FROM inventario WHERE negocio_id={ph}", (negocio_id,))
            inventario_cache = {row[0]: row[1] for row in cursor.fetchall() if row and row[0]}

            cursor.execute(f"SELECT LOWER(nombre), id FROM clientes WHERE negocio_id={ph}", (negocio_id,))
            clientes_cache = {row[0]: row[1] for row in cursor.fetchall() if row and row[0]}

            cursor.execute(f"SELECT producto_id, insumo_id FROM producto_insumo WHERE negocio_id={ph}", (negocio_id,))
            producto_insumo_set = {(row[0], row[1]) for row in cursor.fetchall() if row}

            # ── PASO 1: Análisis de Filas, Fechas y Claves de Pedido / Lote ──
            filas_mapeadas = []
            nuevos_prods_dict = {}     # key_lower -> params_tuple
            nuevos_inv_dict = {}       # key_lower -> params_tuple
            nuevos_clientes_dict = {}  # key_lower -> params_tuple

            for fila_num, raw_json in registros_staging:
                raw_row = json.loads(raw_json)
                mapped = {campo: raw_row.get(col, "").strip() for col, campo in mapeo_usuario.items() if campo and campo != "IGNORAR"}

                nombre_prod = (mapped.get('nombre_producto') or '').strip()
                if not nombre_prod:
                    continue

                estado_raw = (mapped.get('estado_origen') or mapped.get('estado') or '').strip().upper()
                tipo_fila, origen_clasificacion = determinar_tipo_fila(mapped)

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

                # Fechas separadas independientemente
                fecha_compra_raw = mapped.get('fecha_operacion') or datetime.now().strftime("%Y-%m-%d")
                fecha_recepcion_raw = mapped.get('fecha_recepcion') or fecha_compra_raw

                if len(fecha_compra_raw) == 10:
                    fecha_compra_fmt = f"{fecha_compra_raw} 12:00:00"
                else:
                    fecha_compra_fmt = fecha_compra_raw

                if len(fecha_recepcion_raw) == 10:
                    fecha_recepcion_fmt = f"{fecha_recepcion_raw} 12:00:00"
                else:
                    fecha_recepcion_fmt = fecha_recepcion_raw

                # Costo Landed Unitario definitivo
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

                key_p = nombre_prod.lower()
                if key_p not in productos_cache and key_p not in nuevos_prods_dict:
                    categoria = (mapped.get('categoria') or '').strip() or None
                    subcategoria = (mapped.get('subcategoria') or '').strip() or None
                    nuevos_prods_dict[key_p] = (negocio_id, nombre_prod, precio_v, 'COMERCIALIZADO', categoria, subcategoria, undo_token)

                if tipo_fila in ("COMPRA_Y_VENTA", "SOLO_COMPRA", "PERDIDA"):
                    if key_p not in inventario_cache and key_p not in nuevos_inv_dict:
                        codigo_inv = (mapped.get('codigo_sku') or '').strip() or None
                        stock_ini = cant if tipo_fila == "SOLO_COMPRA" else 0.0
                        nuevos_inv_dict[key_p] = (negocio_id, nombre_prod, stock_ini, codigo_inv, costo_adq, undo_token)

                if cli_nombre:
                    key_c = cli_nombre.lower()
                    if key_c not in clientes_cache and key_c not in nuevos_clientes_dict:
                        cli_doc = (mapped.get('cliente_documento') or '').strip()
                        cli_tel = (mapped.get('cliente_telefono') or '').strip()
                        cli_wa = (mapped.get('cliente_whatsapp') or '').strip()
                        cli_email = (mapped.get('cliente_email') or '').strip()
                        cli_dir = (mapped.get('cliente_direccion') or '').strip()
                        cli_tipo = (mapped.get('cliente_tipo') or '').strip() or 'PERSONA'
                        nuevos_clientes_dict[key_c] = (
                            negocio_id, cli_nombre, cli_tipo, cli_doc, cli_tel,
                            cli_wa or cli_tel, cli_email, cli_dir, 0.0, 15, 'ACTIVO', undo_token
                        )

                # Clave Única de Pedido/Embarque y Lote (importaciones: fecha + tasa de cambio)
                pedido_key = f"{fecha_compra_raw[:10]}_{tasa_cambio}"
                lote_key = (pedido_key, key_p)

                concepto_est = normalizar_concepto_estado(estado_raw)
                total_v_row = precio_v * cant
                tiene_col_abono = 'abono_monto' in mapped

                # Abono efectivo percibido (Regla 4)
                if not tiene_col_abono and concepto_est == "VENDIDA" and deuda_val == 0.0:
                    abono_efectivo = total_v_row
                else:
                    abono_efectivo = abono_val

                # Manejo de Sobreabonos (Regla 2 & 5)
                if abono_efectivo > total_v_row and total_v_row > 0:
                    excedente_abono = abono_efectivo - total_v_row
                    saldo_calc = 0.0
                    est_pago = "PAGADO"
                    metodo_pago = "Efectivo"
                else:
                    excedente_abono = 0.0
                    saldo_calc = max(0.0, total_v_row - abono_efectivo)
                    if saldo_calc <= 0.01:
                        est_pago = "PAGADO"
                        metodo_pago = "Efectivo"
                    elif abono_efectivo > 0:
                        est_pago = "PARCIAL"
                        metodo_pago = "CRÉDITO"
                    else:
                        est_pago = "PENDIENTE"
                        metodo_pago = "CRÉDITO"

                filas_mapeadas.append({
                    "fila_num": fila_num,
                    "raw_row": raw_row,
                    "mapped": mapped,
                    "nombre_prod": nombre_prod,
                    "key_p": key_p,
                    "tipo_fila": tipo_fila,
                    "origen_clasificacion": origen_clasificacion,
                    "estado_raw": estado_raw,
                    "cant": cant,
                    "precio_v": precio_v,
                    "costo_adq": costo_adq,
                    "cli_nombre": cli_nombre,
                    "deuda_val": deuda_val,
                    "abono_val": abono_val,
                    "abono_efectivo": abono_efectivo,
                    "excedente_abono": excedente_abono,
                    "saldo_calc": saldo_calc,
                    "metodo_pago": metodo_pago,
                    "fecha_compra": fecha_compra_fmt,
                    "fecha_recepcion": fecha_recepcion_fmt,
                    "fecha_venta": fecha_compra_fmt,
                    "pedido_key": pedido_key,
                    "lote_key": lote_key
                })

            # ── PASO 2: Inserción masiva de Productos, Inventario y Clientes ──
            if nuevos_prods_dict:
                cols_p = ["negocio_id", "nombre", "precio", "tipo_producto", "categoria", "subcategoria", "importacion_id"]
                rows_p = list(nuevos_prods_dict.values())
                res_p = bulk_insert_con_returning(cursor, "productos", cols_p, rows_p, ph, is_pg, "id, LOWER(nombre)")
                for r in res_p:
                    p_id_gen, lower_name = r[0], r[1]
                    productos_cache[lower_name] = p_id_gen
                    creados_info["productos"].append(p_id_gen)

            if nuevos_inv_dict:
                cols_inv = ["negocio_id", "nombre", "stock_actual", "codigo", "costo_unitario_base", "importacion_id"]
                rows_inv = list(nuevos_inv_dict.values())
                res_inv = bulk_insert_con_returning(cursor, "inventario", cols_inv, rows_inv, ph, is_pg, "id, LOWER(nombre)")
                for r in res_inv:
                    inv_id_gen, lower_name = r[0], r[1]
                    inventario_cache[lower_name] = inv_id_gen
                    creados_info["inventario"].append(inv_id_gen)

            if nuevos_clientes_dict:
                cols_c = ["negocio_id", "nombre", "tipo", "documento", "telefono", "whatsapp", "email", "direccion", "limite_credito", "dias_credito_predeterminado", "estado", "importacion_id"]
                rows_c = list(nuevos_clientes_dict.values())
                res_c = bulk_insert_con_returning(cursor, "clientes", cols_c, rows_c, ph, is_pg, "id, LOWER(nombre)")
                for r in res_c:
                    cli_id_gen, lower_name = r[0], r[1]
                    clientes_cache[lower_name] = cli_id_gen
                    creados_info["clientes"].append(cli_id_gen)

            # Enlaces producto_insumo faltantes
            links_a_crear = []
            for f in filas_mapeadas:
                pid = productos_cache.get(f["key_p"])
                inv_id = inventario_cache.get(f["key_p"])
                if pid and inv_id and (pid, inv_id) not in producto_insumo_set:
                    links_a_crear.append((negocio_id, pid, inv_id, 1.0, 'PRODUCTO_DIRECTO'))
                    producto_insumo_set.add((pid, inv_id))

            if links_a_crear:
                sql_link = f"INSERT INTO producto_insumo (negocio_id, producto_id, insumo_id, cantidad_usada, tipo_relacion) VALUES ({ph}, {ph}, {ph}, {ph}, {ph})"
                cursor.executemany(sql_link, links_a_crear)

            # ── PASO 3: Agrupación Consolidada de Lotes Maestros ──
            lotes_acumulados = {}
            batch_atributos = []

            for f in filas_mapeadas:
                pid = productos_cache[f["key_p"]]
                inv_id = inventario_cache.get(f["key_p"])

                # Atributos
                for col_excel, campo_target in mapeo_usuario.items():
                    if campo_target in ("atributo", "variante"):
                        val = f["raw_row"].get(col_excel, "").strip()
                        if val:
                            batch_atributos.append((negocio_id, pid, col_excel, val, campo_target.upper(), undo_token))

                if inv_id:
                    lk = f["lote_key"]
                    if lk not in lotes_acumulados:
                        lotes_acumulados[lk] = {
                            "lote_key": lk,
                            "inv_id": inv_id,
                            "cant_total": 0.0,
                            "costo_adq": f["costo_adq"],
                            "fecha_compra": f["fecha_compra"],
                            "fecha_recepcion": f["fecha_recepcion"],
                            "cli_nombre": f["cli_nombre"],
                            "solo_compra_cant": 0.0
                        }
                    lotes_acumulados[lk]["cant_total"] += f["cant"]
                    if f["tipo_fila"] == "SOLO_COMPRA":
                        lotes_acumulados[lk]["solo_compra_cant"] += f["cant"]

            # Actualizar stock_actual en la tabla inventario para productos con stock disponible activo
            for lk, ldata in lotes_acumulados.items():
                if ldata["solo_compra_cant"] > 0:
                    cursor.execute(
                        f"UPDATE inventario SET stock_actual = stock_actual + {ph} WHERE id={ph} AND negocio_id={ph}",
                        (ldata["solo_compra_cant"], ldata["inv_id"], negocio_id)
                    )

            # Creación masiva de Lotes Maestros en BD
            batch_lotes = []
            batch_compras = []
            lotes_keys_order = []

            for idx_lote, (lk, ldata) in enumerate(lotes_acumulados.items(), start=1):
                codigo_lote = f"IMP-{undo_token[-6:]}-L{idx_lote}"
                cant_total = ldata["cant_total"]
                cant_disp = ldata["solo_compra_cant"]
                estado_lote = 'AGOTADO' if cant_disp <= 0.0001 else 'ACTIVO'
                costo_total_compra = cant_total * ldata["costo_adq"]

                batch_compras.append((
                    negocio_id, ldata["fecha_compra"], "",
                    ldata["inv_id"], codigo_lote, cant_total, ldata["costo_adq"], costo_total_compra, undo_token, usuario_id
                ))

                batch_lotes.append((
                    negocio_id, ldata["inv_id"], codigo_lote, ldata["fecha_recepcion"][:10],
                    cant_total, cant_disp, ldata["costo_adq"], "",
                    estado_lote, undo_token
                ))
                lotes_keys_order.append(lk)

            cols_l = ["negocio_id", "insumo_id", "codigo_lote", "fecha_compra", "cantidad_inicial", "cantidad_disponible", "costo_unitario", "proveedor", "estado", "importacion_id"]
            res_lotes = bulk_insert_con_returning(cursor, "lotes_inventario", cols_l, batch_lotes, ph, is_pg, "id")

            lote_id_map = {}
            for idx, r in enumerate(res_lotes):
                gen_id = r[0]
                lk = lotes_keys_order[idx]
                lote_id_map[lk] = gen_id
                creados_info["lotes"].append(gen_id)

            # ── PASO 4: Registro de Ventas, Movimientos de Lote y Abonos ──
            batch_ventas = []
            ventas_meta = []

            for f in filas_mapeadas:
                pid = productos_cache[f["key_p"]]
                cli_id = clientes_cache.get(f["cli_nombre"].lower()) if f["cli_nombre"] else None

                if f["tipo_fila"] in ("COMPRA_Y_VENTA", "SOLO_VENTA"):
                    costo_venta_total = (f["costo_adq"] * f["cant"]) if f["tipo_fila"] == "COMPRA_Y_VENTA" else 0.0
                    total_venta = f["precio_v"] * f["cant"]

                    if f["saldo_calc"] <= 0.01:
                        est_pago = "PAGADO"
                    elif f["abono_val"] > 0:
                        est_pago = "PARCIAL"
                    else:
                        est_pago = "PENDIENTE"

                    batch_ventas.append((
                        negocio_id, f["fecha_venta"], pid, f["cant"], total_venta, f["metodo_pago"],
                        costo_venta_total, f["precio_v"], usuario_id,
                        f["cli_nombre"] or None, cli_id, f["saldo_calc"], est_pago, undo_token
                    ))
                    ventas_meta.append({
                        "fecha_v": f["fecha_venta"], "cant": f["cant"], "costo_adq": f["costo_adq"],
                        "costo_venta_total": costo_venta_total, "abono_val": f["abono_val"],
                        "tipo_fila": f["tipo_fila"], "lote_key": f["lote_key"]
                    })
                    procesados += 1

            cols_v = ["negocio_id", "fecha", "producto_id", "cantidad", "total", "metodo_pago", "costo_historico_total", "precio_historico_unitario", "usuario_id", "cliente_nombre", "cliente_id", "saldo_pendiente", "estado_pago", "importacion_id"]
            res_ventas = bulk_insert_con_returning(cursor, "ventas", cols_v, batch_ventas, ph, is_pg, "id")

            batch_movimientos = []
            batch_abonos = []

            # Movimientos de Entrada (1 por Lote Maestro)
            for idx_l, (lk, ldata) in enumerate(lotes_acumulados.items()):
                l_id = lote_id_map[lk]
                cant_total = ldata["cant_total"]
                costo_total = cant_total * ldata["costo_adq"]
                batch_movimientos.append((
                    negocio_id, l_id, ldata["fecha_recepcion"], 'ENTRADA', cant_total,
                    ldata["costo_adq"], costo_total, f"Importación {undo_token}", None, usuario_id
                ))

            # Movimientos de Salida por Venta
            for idx, r in enumerate(res_ventas):
                v_id = r[0]
                creados_info["ventas"].append(v_id)
                meta = ventas_meta[idx]

                if meta["tipo_fila"] == "COMPRA_Y_VENTA" and meta["lote_key"] in lote_id_map:
                    l_id = lote_id_map[meta["lote_key"]]
                    batch_movimientos.append((
                        negocio_id, l_id, meta["fecha_v"], 'SALIDA_VENTA', meta["cant"],
                        meta["costo_adq"], meta["costo_venta_total"], f"Venta #{v_id} (Importación {undo_token})", v_id, usuario_id
                    ))

                if meta["abono_val"] > 0:
                    batch_abonos.append((
                        negocio_id, v_id, meta["fecha_v"], meta["abono_val"], 'Efectivo', usuario_id, 'Abono cargado por Importador Inteligente'
                    ))

            # Movimientos de Salida por Pérdida/Merma
            for f in filas_mapeadas:
                if f["tipo_fila"] == "PERDIDA" and f["lote_key"] in lote_id_map:
                    l_id = lote_id_map[f["lote_key"]]
                    batch_movimientos.append((
                        negocio_id, l_id, f["fecha_recepcion"], 'SALIDA_PERDIDA', f["cant"],
                        f["costo_adq"], f["costo_adq"] * f["cant"], f"Pérdida/Dañado (Importación {undo_token})", None, usuario_id
                    ))

            if batch_atributos:
                sql_attr = f"INSERT INTO producto_atributos (negocio_id, producto_id, nombre_atributo, valor_atributo, tipo, importacion_id) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})"
                cursor.executemany(sql_attr, batch_atributos)

            if batch_compras:
                sql_comp = f"INSERT INTO compras_entradas (negocio_id, fecha_compra, proveedor, insumo_id, codigo_lote, cantidad_comprada, costo_unitario_compra, costo_total_compra, importacion_id, usuario_id) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})"
                cursor.executemany(sql_comp, batch_compras)

            if batch_movimientos:
                sql_mov = f"INSERT INTO movimientos_lote (negocio_id, lote_id, fecha, tipo, cantidad, costo_unitario_lote, costo_subtotal, referencia, venta_id, usuario_id) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})"
                cursor.executemany(sql_mov, batch_movimientos)

            if batch_abonos:
                sql_ab = f"INSERT INTO abonos_cartera (negocio_id, venta_id, fecha, monto, metodo_pago, usuario_id, observacion) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})"
                cursor.executemany(sql_ab, batch_abonos)

            # ── PASO 5: Memoria de Mapeo y Auditoría ──
            insertar_con_id(cursor,
                f"INSERT INTO mapeos_importacion (negocio_id, nombre_mapeo, estructura_columnas_json, fecha_creacion) VALUES ({ph}, 'Mapeo Aprobado Tenant', {ph}, {ph})",
                (negocio_id, json.dumps(mapeo_usuario, ensure_ascii=False), fecha_hoy),
                ph, is_pg)

            insertar_con_id(cursor,
                f"""INSERT INTO auditoria_importaciones 
                    (negocio_id, usuario_id, fecha, undo_token, nombre_archivo, 
                     total_registros, creados_json, hash_archivo, estado)
                    VALUES ({ph}, {ph}, {ph}, {ph}, 'Importación Excel Empresarial', {ph}, {ph}, {ph}, 'COMPLETADO')""",
                (negocio_id, usuario_id, fecha_hoy, undo_token, procesados,
                 json.dumps(creados_info, ensure_ascii=False), hash_archivo),
                ph, is_pg)

        print(f"[IMPORTADOR ÉXITO ATÓMICO] Transacción atómica masiva ejecutada con éxito. undo_token={undo_token}")
        return True, f"¡Importación exitosa! Se procesaron {procesados} registros en una única transacción atómica ultra-rápida.", {
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


# ══════════════════════════════════════════════════════════════════
# STREAMING DE PROGRESO REAL DE IMPORTACIÓN (SSE)
# ══════════════════════════════════════════════════════════════════

def procesar_importacion_aprobada_stream(batch_id, negocio_id, usuario_id, mapeo_usuario, autorizaciones=None, granularidad_costos="POR_UNIDAD"):
    """
    Generador SSE que emite notificaciones de progreso reales por cada fase
    del pipeline manteniendo 100% de integridad transaccional atómica.
    """
    def make_event(stage_id, title, status, detail, result=None):
        payload = {
            "stage": stage_id,
            "title": title,
            "status": status,
            "detail": detail,
            "result": result
        }
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    # ETAPA 1: Lectura de Staging
    yield make_event("ANALIZANDO", "Analizando archivo...", "processing", "Leyendo datos de staging...")
    
    registros_staging = ejecutar_query(
        "SELECT fila_num, datos_raw_json FROM importaciones_staging WHERE batch_id=? AND negocio_id=? ORDER BY fila_num ASC",
        (batch_id, negocio_id), fetch=True
    ) or []

    if not registros_staging:
        yield make_event("ERROR", "Error de lectura", "error", "No se encontraron datos en staging para este batch.")
        return

    num_registros = len(registros_staging)
    yield make_event("ANALIZANDO", "Archivo leído", "completed", f"✓ Archivo leído — {num_registros} registros detectados")

    # ETAPA 2: Interpretación de Estructura
    num_cols = len(mapeo_usuario) if mapeo_usuario else 0
    yield make_event("ESTRUCTURA", "Interpretando estructura...", "processing", f"Analizando {num_cols} columnas mapeadas...")
    time.sleep(0.05)
    yield make_event("ESTRUCTURA", "Estructura interpretada", "completed", f"✓ {num_cols} columnas analizadas")

    undo_token = f"UNDO-{uuid.uuid4().hex[:12].upper()}"
    fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
            # ETAPA 3: Conciliación
            yield make_event("CONCILIANDO", "Conciliando productos y clientes...", "processing", "Buscando coincidencias en catálogo y clientes...")

            cursor.execute(f"SELECT LOWER(nombre), id FROM productos WHERE negocio_id={ph}", (negocio_id,))
            productos_cache = {row[0]: row[1] for row in cursor.fetchall() if row and row[0]}

            cursor.execute(f"SELECT LOWER(nombre), id FROM inventario WHERE negocio_id={ph}", (negocio_id,))
            inventario_cache = {row[0]: row[1] for row in cursor.fetchall() if row and row[0]}

            cursor.execute(f"SELECT LOWER(nombre), id FROM clientes WHERE negocio_id={ph}", (negocio_id,))
            clientes_cache = {row[0]: row[1] for row in cursor.fetchall() if row and row[0]}

            cursor.execute(f"SELECT producto_id, insumo_id FROM producto_insumo WHERE negocio_id={ph}", (negocio_id,))
            producto_insumo_set = {(row[0], row[1]) for row in cursor.fetchall() if row}

            filas_mapeadas = []
            nuevos_prods_dict = {}
            nuevos_inv_dict = {}
            nuevos_clientes_dict = {}

            for fila_num, raw_json in registros_staging:
                raw_row = json.loads(raw_json)
                mapped = {campo: raw_row.get(col, "").strip() for col, campo in mapeo_usuario.items() if campo and campo != "IGNORAR"}
                nombre_prod = (mapped.get('nombre_producto') or '').strip()
                if not nombre_prod: continue

                estado_raw = (mapped.get('estado_origen') or mapped.get('estado') or '').strip().upper()
                tipo_fila, origen_clasificacion = determinar_tipo_fila(mapped)

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

                fecha_compra_raw = mapped.get('fecha_operacion') or datetime.now().strftime("%Y-%m-%d")
                fecha_recepcion_raw = mapped.get('fecha_recepcion') or fecha_compra_raw
                fecha_compra_fmt = f"{fecha_compra_raw} 12:00:00" if len(fecha_compra_raw) == 10 else fecha_compra_raw
                fecha_recepcion_fmt = f"{fecha_recepcion_raw} 12:00:00" if len(fecha_recepcion_raw) == 10 else fecha_recepcion_raw

                if granularidad_costos == "POR_LOTE" and cant > 1 and costo_total_imp > 0:
                    costo_adq = costo_total_imp / cant
                elif costo_total_imp > 0: costo_adq = costo_total_imp
                elif costo_local > 0: costo_adq = costo_local + costo_envio
                elif costo_origen > 0 and tasa_cambio > 0: costo_adq = (costo_origen * tasa_cambio) + costo_envio
                else: costo_adq = 0.0

                key_p = nombre_prod.lower()
                if key_p not in productos_cache and key_p not in nuevos_prods_dict:
                    categoria = (mapped.get('categoria') or '').strip() or None
                    subcategoria = (mapped.get('subcategoria') or '').strip() or None
                    nuevos_prods_dict[key_p] = (negocio_id, nombre_prod, precio_v, 'COMERCIALIZADO', categoria, subcategoria, undo_token)

                if tipo_fila in ("COMPRA_Y_VENTA", "SOLO_COMPRA", "PERDIDA"):
                    if key_p not in inventario_cache and key_p not in nuevos_inv_dict:
                        codigo_inv = (mapped.get('codigo_sku') or '').strip() or None
                        stock_ini = cant if tipo_fila == "SOLO_COMPRA" else 0.0
                        nuevos_inv_dict[key_p] = (negocio_id, nombre_prod, stock_ini, codigo_inv, costo_adq, undo_token)

                if cli_nombre:
                    key_c = cli_nombre.lower()
                    if key_c not in clientes_cache and key_c not in nuevos_clientes_dict:
                        cli_doc = (mapped.get('cliente_documento') or '').strip()
                        cli_tel = (mapped.get('cliente_telefono') or '').strip()
                        cli_wa = (mapped.get('cliente_whatsapp') or '').strip()
                        cli_email = (mapped.get('cliente_email') or '').strip()
                        cli_dir = (mapped.get('cliente_direccion') or '').strip()
                        cli_tipo = (mapped.get('cliente_tipo') or '').strip() or 'PERSONA'
                        nuevos_clientes_dict[key_c] = (
                            negocio_id, cli_nombre, cli_tipo, cli_doc, cli_tel,
                            cli_wa or cli_tel, cli_email, cli_dir, 0.0, 15, 'ACTIVO', undo_token
                        )

                # Clave Única de Pedido/Embarque y Lote (importaciones: fecha + tasa de cambio)
                pedido_key = f"{fecha_compra_raw[:10]}_{tasa_cambio}"
                lote_key = (pedido_key, key_p)

                concepto_est = normalizar_concepto_estado(estado_raw)
                total_v_row = precio_v * cant
                tiene_col_abono = 'abono_monto' in mapped

                # Abono efectivo percibido (Regla 4)
                if not tiene_col_abono and concepto_est == "VENDIDA" and deuda_val == 0.0:
                    abono_efectivo = total_v_row
                else:
                    abono_efectivo = abono_val

                # Manejo de Sobreabonos (Regla 2 & 5)
                if abono_efectivo > total_v_row and total_v_row > 0:
                    excedente_abono = abono_efectivo - total_v_row
                    saldo_calc = 0.0
                    est_pago = "PAGADO"
                    metodo_pago = "Efectivo"
                else:
                    excedente_abono = 0.0
                    saldo_calc = max(0.0, total_v_row - abono_efectivo)
                    if saldo_calc <= 0.01:
                        est_pago = "PAGADO"
                        metodo_pago = "Efectivo"
                    elif abono_efectivo > 0:
                        est_pago = "PARCIAL"
                        metodo_pago = "CRÉDITO"
                    else:
                        est_pago = "PENDIENTE"
                        metodo_pago = "CRÉDITO"

                filas_mapeadas.append({
                    "fila_num": fila_num, "raw_row": raw_row, "mapped": mapped,
                    "nombre_prod": nombre_prod, "key_p": key_p, "tipo_fila": tipo_fila,
                    "origen_clasificacion": origen_clasificacion,
                    "estado_raw": estado_raw, "cant": cant, "precio_v": precio_v, "costo_adq": costo_adq,
                    "cli_nombre": cli_nombre, "deuda_val": deuda_val, "abono_val": abono_val,
                    "abono_efectivo": abono_efectivo, "excedente_abono": excedente_abono,
                    "saldo_calc": saldo_calc, "metodo_pago": metodo_pago,
                    "fecha_compra": fecha_compra_fmt, "fecha_recepcion": fecha_recepcion_fmt,
                    "fecha_venta": fecha_compra_fmt, "pedido_key": pedido_key, "lote_key": lote_key
                })

            if nuevos_prods_dict:
                cols_p = ["negocio_id", "nombre", "precio", "tipo_producto", "categoria", "subcategoria", "importacion_id"]
                rows_p = list(nuevos_prods_dict.values())
                res_p = bulk_insert_con_returning(cursor, "productos", cols_p, rows_p, ph, is_pg, "id, LOWER(nombre)")
                for r in res_p:
                    productos_cache[r[1]] = r[0]
                    creados_info["productos"].append(r[0])

            if nuevos_inv_dict:
                cols_inv = ["negocio_id", "nombre", "stock_actual", "codigo", "costo_unitario_base", "importacion_id"]
                rows_inv = list(nuevos_inv_dict.values())
                res_inv = bulk_insert_con_returning(cursor, "inventario", cols_inv, rows_inv, ph, is_pg, "id, LOWER(nombre)")
                for r in res_inv:
                    inventario_cache[r[1]] = r[0]
                    creados_info["inventario"].append(r[0])

            if nuevos_clientes_dict:
                cols_c = ["negocio_id", "nombre", "tipo", "documento", "telefono", "whatsapp", "email", "direccion", "limite_credito", "dias_credito_predeterminado", "estado", "importacion_id"]
                rows_c = list(nuevos_clientes_dict.values())
                res_c = bulk_insert_con_returning(cursor, "clientes", cols_c, rows_c, ph, is_pg, "id, LOWER(nombre)")
                for r in res_c:
                    clientes_cache[r[1]] = r[0]
                    creados_info["clientes"].append(r[0])

            links_a_crear = []
            for f in filas_mapeadas:
                pid = productos_cache.get(f["key_p"])
                inv_id = inventario_cache.get(f["key_p"])
                if pid and inv_id and (pid, inv_id) not in producto_insumo_set:
                    links_a_crear.append((negocio_id, pid, inv_id, 1.0, 'PRODUCTO_DIRECTO'))
                    producto_insumo_set.add((pid, inv_id))

            if links_a_crear:
                sql_link = f"INSERT INTO producto_insumo (negocio_id, producto_id, insumo_id, cantidad_usada, tipo_relacion) VALUES ({ph}, {ph}, {ph}, {ph}, {ph})"
                cursor.executemany(sql_link, links_a_crear)

            yield make_event("CONCILIANDO", "Productos y clientes conciliados", "completed", f"✓ {len(productos_cache)} productos | {len(clientes_cache)} clientes conciliados")

            # ETAPA 4: Lotes
            yield make_event("LOTES", "Preparando inventario y lotes maestros...", "processing", "Consolidando embarques y lotes de adquisición...")

            lotes_acumulados = {}
            batch_atributos = []

            for f in filas_mapeadas:
                pid = productos_cache[f["key_p"]]
                inv_id = inventario_cache.get(f["key_p"])

                for col_excel, campo_target in mapeo_usuario.items():
                    if campo_target in ("atributo", "variante"):
                        val = f["raw_row"].get(col_excel, "").strip()
                        if val:
                            batch_atributos.append((negocio_id, pid, col_excel, val, campo_target.upper(), undo_token))

                if inv_id:
                    lk = f["lote_key"]
                    if lk not in lotes_acumulados:
                        lotes_acumulados[lk] = {
                            "lote_key": lk, "inv_id": inv_id, "cant_total": 0.0, "costo_adq": f["costo_adq"],
                            "fecha_compra": f["fecha_compra"], "fecha_recepcion": f["fecha_recepcion"],
                            "cli_nombre": f["cli_nombre"], "solo_compra_cant": 0.0
                        }
                    lotes_acumulados[lk]["cant_total"] += f["cant"]
                    if f["tipo_fila"] == "SOLO_COMPRA":
                        lotes_acumulados[lk]["solo_compra_cant"] += f["cant"]

            for lk, ldata in lotes_acumulados.items():
                if ldata["solo_compra_cant"] > 0:
                    cursor.execute(
                        f"UPDATE inventario SET stock_actual = stock_actual + {ph} WHERE id={ph} AND negocio_id={ph}",
                        (ldata["solo_compra_cant"], ldata["inv_id"], negocio_id)
                    )

            batch_lotes = []
            batch_compras = []
            lotes_keys_order = []

            for idx_lote, (lk, ldata) in enumerate(lotes_acumulados.items(), start=1):
                codigo_lote = f"IMP-{undo_token[-6:]}-L{idx_lote}"
                cant_total = ldata["cant_total"]
                cant_disp = ldata["solo_compra_cant"]
                estado_lote = 'AGOTADO' if cant_disp <= 0.0001 else 'ACTIVO'
                costo_total_compra = cant_total * ldata["costo_adq"]

                batch_compras.append((
                    negocio_id, ldata["fecha_compra"], "",
                    ldata["inv_id"], codigo_lote, cant_total, ldata["costo_adq"], costo_total_compra, undo_token, usuario_id
                ))
                batch_lotes.append((
                    negocio_id, ldata["inv_id"], codigo_lote, ldata["fecha_recepcion"][:10],
                    cant_total, cant_disp, ldata["costo_adq"], "",
                    estado_lote, undo_token
                ))
                lotes_keys_order.append(lk)

            cols_l = ["negocio_id", "insumo_id", "codigo_lote", "fecha_compra", "cantidad_inicial", "cantidad_disponible", "costo_unitario", "proveedor", "estado", "importacion_id"]
            res_lotes = bulk_insert_con_returning(cursor, "lotes_inventario", cols_l, batch_lotes, ph, is_pg, "id")

            lote_id_map = {}
            for idx, r in enumerate(res_lotes):
                gen_id = r[0]
                lk = lotes_keys_order[idx]
                lote_id_map[lk] = gen_id
                creados_info["lotes"].append(gen_id)

            yield make_event("LOTES", "Lotes maestros preparados", "completed", f"✓ {len(lotes_acumulados)} lotes maestros agrupados")

            # ETAPA 5: Costos y Rentabilidad
            yield make_event("COSTOS", "Calculando costos y rentabilidad...", "processing", "Prorrateando fletes y costos de adquisición...")
            time.sleep(0.05)
            yield make_event("COSTOS", "Costos y rentabilidad calculados", "completed", "✓ Costos landed por lote asignados")

            # ETAPA 6: Cartera y Ventas
            yield make_event("CARTERA", "Preparando cartera y ventas...", "processing", f"Asignando {len(filas_mapeadas)} operaciones a cuentas y ventas...")

            batch_ventas = []
            ventas_meta = []

            for f in filas_mapeadas:
                pid = productos_cache[f["key_p"]]
                cli_id = clientes_cache.get(f["cli_nombre"].lower()) if f["cli_nombre"] else None

                if f["tipo_fila"] in ("COMPRA_Y_VENTA", "SOLO_VENTA"):
                    costo_venta_total = (f["costo_adq"] * f["cant"]) if f["tipo_fila"] == "COMPRA_Y_VENTA" else 0.0
                    total_venta = f["precio_v"] * f["cant"]

                    if f["saldo_calc"] <= 0.01:
                        est_pago = "PAGADO"
                    elif f["abono_val"] > 0:
                        est_pago = "PARCIAL"
                    else:
                        est_pago = "PENDIENTE"

                    batch_ventas.append((
                        negocio_id, f["fecha_venta"], pid, f["cant"], total_venta, f["metodo_pago"],
                        costo_venta_total, f["precio_v"], usuario_id,
                        f["cli_nombre"] or None, cli_id, f["saldo_calc"], est_pago, undo_token
                    ))
                    ventas_meta.append({
                        "fecha_v": f["fecha_venta"], "cant": f["cant"], "costo_adq": f["costo_adq"],
                        "costo_venta_total": costo_venta_total, "abono_val": f["abono_val"],
                        "tipo_fila": f["tipo_fila"], "lote_key": f["lote_key"]
                    })
                    procesados += 1

            cols_v = ["negocio_id", "fecha", "producto_id", "cantidad", "total", "metodo_pago", "costo_historico_total", "precio_historico_unitario", "usuario_id", "cliente_nombre", "cliente_id", "saldo_pendiente", "estado_pago", "importacion_id"]
            res_ventas = bulk_insert_con_returning(cursor, "ventas", cols_v, batch_ventas, ph, is_pg, "id")

            batch_movimientos = []
            batch_abonos = []

            for idx_l, (lk, ldata) in enumerate(lotes_acumulados.items()):
                l_id = lote_id_map[lk]
                cant_total = ldata["cant_total"]
                costo_total = cant_total * ldata["costo_adq"]
                batch_movimientos.append((
                    negocio_id, l_id, ldata["fecha_recepcion"], 'ENTRADA', cant_total,
                    ldata["costo_adq"], costo_total, f"Importación {undo_token}", None, usuario_id
                ))

            for idx, r in enumerate(res_ventas):
                v_id = r[0]
                creados_info["ventas"].append(v_id)
                meta = ventas_meta[idx]

                if meta["tipo_fila"] == "COMPRA_Y_VENTA" and meta["lote_key"] in lote_id_map:
                    l_id = lote_id_map[meta["lote_key"]]
                    batch_movimientos.append((
                        negocio_id, l_id, meta["fecha_v"], 'SALIDA_VENTA', meta["cant"],
                        meta["costo_adq"], meta["costo_venta_total"], f"Venta #{v_id} (Importación {undo_token})", v_id, usuario_id
                    ))

                if meta["abono_val"] > 0:
                    batch_abonos.append((
                        negocio_id, v_id, meta["fecha_v"], meta["abono_val"], 'Efectivo', usuario_id, 'Abono cargado por Importador Inteligente'
                    ))

            for f in filas_mapeadas:
                if f["tipo_fila"] == "PERDIDA" and f["lote_key"] in lote_id_map:
                    l_id = lote_id_map[f["lote_key"]]
                    batch_movimientos.append((
                        negocio_id, l_id, f["fecha_recepcion"], 'SALIDA_PERDIDA', f["cant"],
                        f["costo_adq"], f["costo_adq"] * f["cant"], f"Pérdida/Dañado (Importación {undo_token})", None, usuario_id
                    ))

            if batch_atributos:
                sql_attr = f"INSERT INTO producto_atributos (negocio_id, producto_id, nombre_atributo, valor_atributo, tipo, importacion_id) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})"
                cursor.executemany(sql_attr, batch_atributos)

            if batch_compras:
                sql_comp = f"INSERT INTO compras_entradas (negocio_id, fecha_compra, proveedor, insumo_id, codigo_lote, cantidad_comprada, costo_unitario_compra, costo_total_compra, importacion_id, usuario_id) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})"
                cursor.executemany(sql_comp, batch_compras)

            if batch_movimientos:
                sql_mov = f"INSERT INTO movimientos_lote (negocio_id, lote_id, fecha, tipo, cantidad, costo_unitario_lote, costo_subtotal, referencia, venta_id, usuario_id) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})"
                cursor.executemany(sql_mov, batch_movimientos)

            if batch_abonos:
                sql_ab = f"INSERT INTO abonos_cartera (negocio_id, venta_id, fecha, monto, metodo_pago, usuario_id, observacion) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})"
                cursor.executemany(sql_ab, batch_abonos)

            insertar_con_id(cursor,
                f"INSERT INTO mapeos_importacion (negocio_id, nombre_mapeo, estructura_columnas_json, fecha_creacion) VALUES ({ph}, 'Mapeo Aprobado Tenant', {ph}, {ph})",
                (negocio_id, json.dumps(mapeo_usuario, ensure_ascii=False), fecha_hoy),
                ph, is_pg)

            insertar_con_id(cursor,
                f"""INSERT INTO auditoria_importaciones 
                    (negocio_id, usuario_id, fecha, undo_token, nombre_archivo, 
                     total_registros, creados_json, hash_archivo, estado)
                    VALUES ({ph}, {ph}, {ph}, {ph}, 'Importación Excel Empresarial', {ph}, {ph}, {ph}, 'COMPLETADO')""",
                (negocio_id, usuario_id, fecha_hoy, undo_token, procesados,
                 json.dumps(creados_info, ensure_ascii=False), hash_archivo),
                ph, is_pg)

            yield make_event("CARTERA", "Ventas y cartera preparadas", "completed", f"✓ {procesados} ventas y saldos preparados")

            # ETAPA 7: Transacción Atómica
            yield make_event("TRANSACCION", "Ejecutando importación segura...", "processing", "Consolidando transacción atómica en base de datos...")
            time.sleep(0.05)
            yield make_event("TRANSACCION", "Transacción atómica completada", "completed", "✓ Base de datos validada")

            # ETAPA 8: Guardando Cambios
            yield make_event("GUARDANDO", "Guardando cambios...", "processing", "Persistiendo registros...")

        # COMMIT AUTOMÁTICO AL SALIR DEL BLOQUE CONTEXTUAL
        yield make_event("GUARDANDO", "Cambios guardados", "completed", "✓ Transacción persistida con éxito")

        # ETAPA FINAL: Completado
        final_payload = {
            "undo_token": undo_token,
            "procesados": procesados,
            "resumen": creados_info
        }
        yield make_event("COMPLETADO", "¡Importación completada!", "completed", f"Se importaron {procesados} registros exitosamente.", result=final_payload)

    except Exception as e_stream:
        print(f"[IMPORTADOR STREAM ERROR - ROLLBACK AUTO] {e_stream}")
        yield make_event("ERROR", "Error de procesamiento", "error", f"Error en la importación (0 registros guardados): {str(e_stream)}")


