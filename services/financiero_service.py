from database import ejecutar_query
from datetime import datetime

def obtener_resumen_financiero(negocio_id, mes_filtro=None, producto_id=None, metodo_pago=None):
    query = "SELECT total, costo_historico_total, cantidad, producto_id FROM ventas WHERE negocio_id=?"
    params = [negocio_id]
    
    if mes_filtro:
        query += " AND fecha LIKE ?"
        params.append(f"{mes_filtro}%")
    if producto_id:
        query += " AND producto_id = ?"
        params.append(producto_id)
    if metodo_pago:
        query += " AND metodo_pago = ?"
        params.append(metodo_pago)
    
    ventas = ejecutar_query(query, params, fetch=True)
    
    total_ingresos = sum(v[0] for v in ventas)
    total_costos_v = sum(v[1] for v in ventas)
    total_unidades = sum(v[2] for v in ventas)
    utilidad_bruta = total_ingresos - total_costos_v
    
    mes_actual = mes_filtro if mes_filtro else datetime.now().strftime("%Y-%m")
    res_f = ejecutar_query("SELECT SUM(valor) FROM costos_fijos WHERE mes = ? AND negocio_id=?", (mes_actual, negocio_id), fetch=True)
    total_costos_f = res_f[0][0] or 0.0

    # Fallback 1: Si no hay costos fijos para este mes exacto, usar los costos fijos globales/más recientes del negocio
    if total_costos_f == 0.0:
        res_f_global = ejecutar_query("SELECT SUM(valor) FROM costos_fijos WHERE negocio_id=?", (negocio_id,), fetch=True)
        total_costos_f = (res_f_global[0][0] or 0.0) if res_f_global else 0.0
    
    prods = ejecutar_query("SELECT id, nombre FROM productos WHERE negocio_id=?", (negocio_id,), fetch=True)
    
    mcp = 0.0
    analisis_productos = []
    for p_id, p_nombre in prods:
        p_ventas = [v for v in ventas if v[3] == p_id]
        p_unidades = sum(v[2] for v in p_ventas)
        p_ingreso = sum(v[0] for v in p_ventas)
        p_costo = sum(v[1] for v in p_ventas)
        mcu = (p_ingreso - p_costo) / p_unidades if p_unidades > 0 else 0
        participacion = p_unidades / total_unidades if total_unidades > 0 else 0
        mcp += mcu * participacion
        if p_unidades > 0:
            analisis_productos.append({"nombre": p_nombre, "unidades": p_unidades, "participacion": participacion * 100, "mcu": mcu})

    # Margen de Contribución Relativo % (Margen Global)
    ratio_margen = (utilidad_bruta / total_ingresos) if total_ingresos > 0 else 0.0
    
    # Punto de Equilibrio en Pesos Facturados ($)
    punto_equilibrio_pesos = (total_costos_f / ratio_margen) if ratio_margen > 0 else 0.0
    
    # Punto de Equilibrio en Unidades (#)
    punto_equilibrio_unidades = (total_costos_f / mcp) if mcp > 0 else (punto_equilibrio_pesos / (total_ingresos / total_unidades) if (total_unidades > 0 and total_ingresos > 0) else 0.0)

    return {
        "ingresos": total_ingresos, "costos_v": total_costos_v, "costos_f": total_costos_f,
        "utilidad": utilidad_bruta - total_costos_f, "margen_contribucion": utilidad_bruta,
        "ratio_margen": ratio_margen * 100,
        "mcp": mcp,
        "punto_equilibrio": punto_equilibrio_unidades,
        "punto_equilibrio_pesos": punto_equilibrio_pesos,
        "unidades_totales": total_unidades,
        "requiere_costos_fijos": bool(total_costos_f == 0.0),
        "detalle_productos": analisis_productos
    }

def obtener_datos_graficos(negocio_id):
    # Tendencia filtrada por negocio
    tendencia = ejecutar_query("SELECT SUBSTR(fecha, 1, 7) as mes, SUM(total) FROM ventas WHERE negocio_id=? GROUP BY mes ORDER BY mes ASC LIMIT 6", (negocio_id,), fetch=True)
    distribucion = ejecutar_query("SELECT p.nombre, SUM(v.total) FROM ventas v JOIN productos p ON v.producto_id = p.id WHERE v.negocio_id=? GROUP BY p.nombre ORDER BY SUM(v.total) DESC LIMIT 5", (negocio_id,), fetch=True)
    return {
        "tendencia": {"labels": [x[0] for x in tendencia], "data": [x[1] for x in tendencia]},
        "distribucion": {"labels": [x[0] for x in distribucion], "data": [x[1] for x in distribucion]}
    }

def obtener_tablero_datos(negocio_id):
    res = ejecutar_query("""
        SELECT v.fecha, p.nombre, v.cantidad, v.total, v.costo_historico_total, (v.total - v.costo_historico_total) as utilidad
        FROM ventas v JOIN productos p ON v.producto_id = p.id
        WHERE v.negocio_id=?
        ORDER BY v.fecha DESC LIMIT 50
    """, (negocio_id,), fetch=True)
    return [{"fecha": x[0], "producto": x[1], "cantidad": x[2], "ingreso": x[3], "costo_v": x[4], "utilidad": x[5]} for x in res]

def obtener_rentabilidad_productos(negocio_id):
    prods = ejecutar_query("SELECT id, codigo, nombre, precio FROM productos WHERE negocio_id=?", (negocio_id,), fetch=True)
    reporte = []
    for p_id, p_cod, p_nom, p_pre in prods:
        res_c = ejecutar_query("""
            SELECT SUM(ri.cantidad_usada * i.costo_unitario_base)
            FROM producto_insumo ri JOIN inventario i ON ri.insumo_id = i.id
            WHERE ri.producto_id = ? AND ri.negocio_id=?
        """, (p_id, negocio_id), fetch=True)
        costo_v = res_c[0][0] or 0
        mcu = p_pre - costo_v
        reporte.append({"id": p_id, "codigo": p_cod, "producto": p_nom, "precio": p_pre, "costo": costo_v, "margen": mcu, "porcentaje": (mcu/p_pre*100) if p_pre>0 else 0})
    return reporte

def realizar_cierre_caja(negocio_id, fecha_cierre=None):
    if not fecha_cierre: fecha_cierre = datetime.now().strftime("%Y-%m-%d")
    pagos = ejecutar_query("SELECT metodo_pago, SUM(total) FROM ventas WHERE negocio_id=? AND metodo_pago != 'CRÉDITO' AND fecha LIKE ? GROUP BY metodo_pago", (negocio_id, f"{fecha_cierre}%"), fetch=True) or []
    abonos = ejecutar_query("SELECT metodo_pago, SUM(monto) FROM abonos_cartera WHERE negocio_id=? AND fecha LIKE ? GROUP BY metodo_pago", (negocio_id, f"{fecha_cierre}%"), fetch=True) or []

    detalle = {}
    total = 0.0
    for m, val in pagos:
        if val:
            detalle[m] = detalle.get(m, 0.0) + float(val)
            total += float(val)
    for m, val in abonos:
        if val:
            lbl = f"{m} (Abonos)"
            detalle[lbl] = detalle.get(lbl, 0.0) + float(val)
            total += float(val)

    return {"fecha": fecha_cierre, "total": total, "detalle": detalle}

def obtener_tablero_ejecutivo_completo(negocio_id, fecha_inicio=None, fecha_fin=None, periodo='TODO', comparar_anterior=True):
    try:
        from datetime import datetime, timedelta
        import statistics

        # ── 1. DETERMINACIÓN DEL RANGO DE FECHAS ──
        hoy = datetime.now()
        f_inicio_dt = None
        f_fin_dt = None

        if periodo == 'ESTE_MES':
            f_inicio_dt = datetime(hoy.year, hoy.month, 1)
            # Fin del mes actual
            if hoy.month == 12:
                f_fin_dt = datetime(hoy.year, 12, 31, 23, 59, 59)
            else:
                f_fin_dt = datetime(hoy.year, hoy.month + 1, 1) - timedelta(seconds=1)
        elif periodo == 'ULTIMO_TRIMESTRE':
            f_fin_dt = hoy
            f_inicio_dt = hoy - timedelta(days=90)
        elif periodo == 'ESTE_ANO':
            f_inicio_dt = datetime(hoy.year, 1, 1)
            f_fin_dt = datetime(hoy.year, 12, 31, 23, 59, 59)
        elif periodo == 'CUSTOM' and fecha_inicio and fecha_fin:
            try:
                f_inicio_dt = datetime.strptime(fecha_inicio[:10], "%Y-%m-%d")
                f_fin_dt = datetime.strptime(fecha_fin[:10] + " 23:59:59", "%Y-%m-%d %H:%M:%S")
            except Exception:
                f_inicio_dt = None; f_fin_dt = None

        # Formatos para consulta
        str_inicio = f_inicio_dt.strftime("%Y-%m-%d %H:%M:%S") if f_inicio_dt else None
        str_fin = f_fin_dt.strftime("%Y-%m-%d %H:%M:%S") if f_fin_dt else None

        # ── 2. CONSULTA DE VENTAS DEL PERÍODO (FLUJO) ──
        sql_ventas = "SELECT id, fecha, total, costo_historico_total, cantidad, producto_id, metodo_pago, cliente_nombre, observacion FROM ventas WHERE negocio_id=?"
        params_v = [negocio_id]
        if str_inicio and str_fin:
            sql_ventas += " AND fecha >= ? AND fecha <= ?"
            params_v.extend([str_inicio, str_fin])

        ventas = ejecutar_query(sql_ventas, params_v, fetch=True) or []

        total_ingresos = sum(float(v[2] or 0) for v in ventas)
        total_costos_v = sum(float(v[3] or 0) for v in ventas)
        total_unidades = sum(float(v[4] or 0) for v in ventas)
        utilidad_bruta = total_ingresos - total_costos_v
        margen_bruto_pct = (utilidad_bruta / total_ingresos * 100.0) if total_ingresos > 0 else 0.0

        ventas_credito = sum(float(v[2] or 0) for v in ventas if (v[6] or '').upper() == 'CRÉDITO')

        # ── 3. RECAUDO EN CAJA DEL PERÍODO (FLUJO) ──
        sql_abonos = "SELECT SUM(monto) FROM abonos_cartera WHERE negocio_id=?"
        params_ab = [negocio_id]
        if str_inicio and str_fin:
            sql_abonos += " AND fecha >= ? AND fecha <= ?"
            params_ab.extend([str_inicio[:10], str_fin[:10] + " 23:59:59"])
        res_ab = ejecutar_query(sql_abonos, params_ab, fetch=True)
        recaudo_abonos = res_ab[0][0] or 0.0 if res_ab else 0.0
        ventas_contado = total_ingresos - ventas_credito
        recaudo_total_periodo = ventas_contado + recaudo_abonos
        cobertura_caja_pct = (recaudo_total_periodo / total_ingresos * 100.0) if total_ingresos > 0 else 0.0

        # ── 4. COSTOS FIJOS Y UTILIDAD NETA DEL PERÍODO ──
        sql_fijos = "SELECT SUM(valor) FROM costos_fijos WHERE negocio_id=?"
        params_f = [negocio_id]
        if str_inicio and str_fin:
            mes_inicio = str_inicio[:7]
            mes_fin = str_fin[:7]
            sql_fijos += " AND mes >= ? AND mes <= ?"
            params_f.extend([mes_inicio, mes_fin])
        res_f = ejecutar_query(sql_fijos, params_f, fetch=True)
        costos_fijos_periodo = res_f[0][0] or 0.0 if res_f else 0.0

        tiene_costos_fijos_registrados = bool(costos_fijos_periodo > 0.0)
        utilidad_neta = (utilidad_bruta - costos_fijos_periodo) if tiene_costos_fijos_registrados else None

        # ── 5. PUNTO DE EQUILIBRIO CON MCU PONDERADO REAL ──
        # Obtener MCP ponderado
        mcp_ponderado = 0.0
        if total_unidades > 0:
            prods_dict = {}
            for v in ventas:
                pid = v[5]
                if pid not in prods_dict:
                    prods_dict[pid] = {"ingreso": 0.0, "costo": 0.0, "uds": 0.0}
                prods_dict[pid]["ingreso"] += float(v[2] or 0)
                prods_dict[pid]["costo"] += float(v[3] or 0)
                prods_dict[pid]["uds"] += float(v[4] or 0)

            for pid, pdata in prods_dict.items():
                mcu_p = (pdata["ingreso"] - pdata["costo"]) / pdata["uds"] if pdata["uds"] > 0 else 0.0
                participacion = pdata["uds"] / total_unidades
                mcp_ponderado += mcu_p * participacion

        pe_calculable = False
        pe_pesos = 0.0
        pe_unidades = 0.0
        pe_motivo = ""

        if not tiene_costos_fijos_registrados:
            pe_motivo = "Sin costos fijos registrados. Registra tus costos fijos para calcular el volumen de equilibrio."
        elif margen_bruto_pct <= 0:
            pe_motivo = "El margen de contribución del período es menor o igual a cero."
        else:
            ratio_m = margen_bruto_pct / 100.0
            pe_pesos = costos_fijos_periodo / ratio_m
            if mcp_ponderado > 0:
                pe_unidades = costos_fijos_periodo / mcp_ponderado
                pe_calculable = True
            elif total_ingresos > 0 and total_unidades > 0:
                precio_prom = total_ingresos / total_unidades
                pe_unidades = pe_pesos / precio_prom
                pe_calculable = True
            else:
                pe_motivo = "Falta un precio o contribución unitaria promedio válida para calcular las unidades de equilibrio."

        # ── 6. CARTERA PENDIENTE AL CIERRE (SALDO AL CIERRE) ──
        sql_cartera = """
            SELECT v.id, v.fecha, v.cliente_nombre, v.total, v.saldo_pendiente, v.observacion
            FROM ventas v
            WHERE v.negocio_id=? AND v.saldo_pendiente > 0.01
        """
        cartera_rows = ejecutar_query(sql_cartera, (negocio_id,), fetch=True) or []
        cartera_pendiente_total = sum(float(r[4] or 0) for r in cartera_rows)

        # Aging Buckets
        aging = {"d_0_30": 0.0, "d_31_60": 0.0, "d_61_90": 0.0, "d_91_180": 0.0, "d_180_plus": 0.0}
        top_deudores_dict = {}

        for c_row in cartera_rows:
            f_v = c_row[1]
            saldo = float(c_row[4] or 0)
            cli = c_row[2] or "Cliente General"
            top_deudores_dict[cli] = top_deudores_dict.get(cli, 0.0) + saldo

            try:
                dt_v = datetime.strptime(f_v[:10], "%Y-%m-%d")
                dias = (hoy - dt_v).days
            except Exception:
                dias = 0

            if dias <= 30: aging["d_0_30"] += saldo
            elif dias <= 60: aging["d_31_60"] += saldo
            elif dias <= 90: aging["d_61_90"] += saldo
            elif dias <= 180: aging["d_91_180"] += saldo
            else: aging["d_180_plus"] += saldo

        top_deudores = sorted([
            {"cliente": k, "saldo": v, "pct_concentracion": (v / cartera_pendiente_total * 100.0) if cartera_pendiente_total > 0 else 0.0}
            for k, v in top_deudores_dict.items()
        ], key=lambda x: x["saldo"], reverse=True)[:5]

        # ── 7. COMPARACIÓN CONTRA PERÍODO ANTERIOR ──
        delta_kpis = {}
        if comparar_anterior and f_inicio_dt and f_fin_dt:
            duracion_dias = max(1, (f_fin_dt - f_inicio_dt).days + 1)
            ant_fin_dt = f_inicio_dt - timedelta(seconds=1)
            ant_inicio_dt = ant_fin_dt - timedelta(days=duracion_dias - 1)

            str_ant_ini = ant_inicio_dt.strftime("%Y-%m-%d %H:%M:%S")
            str_ant_fin = ant_fin_dt.strftime("%Y-%m-%d %H:%M:%S")

            ant_ventas = ejecutar_query(
                "SELECT total, costo_historico_total FROM ventas WHERE negocio_id=? AND fecha >= ? AND fecha <= ?",
                (negocio_id, str_ant_ini, str_ant_fin), fetch=True
            ) or []

            ant_ingresos = sum(float(v[0] or 0) for v in ant_ventas)
            ant_costos_v = sum(float(v[1] or 0) for v in ant_ventas)
            ant_utilidad = ant_ingresos - ant_costos_v
            ant_margen = (ant_utilidad / ant_ingresos * 100.0) if ant_ingresos > 0 else 0.0

            # Calculamos diferencias (% para dinero, pp para margen)
            diff_ingresos_pct = ((total_ingresos - ant_ingresos) / ant_ingresos * 100.0) if ant_ingresos > 0 else 0.0
            diff_utilidad_pct = ((utilidad_bruta - ant_utilidad) / ant_utilidad * 100.0) if ant_utilidad > 0 else 0.0
            diff_margen_pp = margen_bruto_pct - ant_margen

            delta_kpis = {
                "ingresos_pct": diff_ingresos_pct,
                "utilidad_pct": diff_utilidad_pct,
                "margen_pp": diff_margen_pp,
                "tiene_anterior": True
            }
        else:
            delta_kpis = {"tiene_anterior": False}

        # ── 8. RANKING DE PRODUCTOS Y MATRIZ 2X2 (MEDIANA) ──
        sql_prods_perf = """
            SELECT p.id, p.nombre, p.codigo,
                   COALESCE(SUM(v.cantidad), 0) as unidades,
                   COALESCE(SUM(v.total), 0) as ventas,
                   COALESCE(SUM(v.costo_historico_total), 0) as costo,
                   COALESCE(SUM(v.saldo_pendiente), 0) as cartera
            FROM productos p
            LEFT JOIN ventas v ON v.producto_id = p.id AND v.negocio_id = p.negocio_id
        """
        params_p = [negocio_id]
        if str_inicio and str_fin:
            sql_prods_perf += " AND v.fecha >= ? AND v.fecha <= ?"
            params_p.extend([str_inicio, str_fin])
        sql_prods_perf += " WHERE p.negocio_id=? GROUP BY p.id, p.nombre, p.codigo HAVING ventas > 0"
        params_p.append(negocio_id)

        prods_perf_raw = ejecutar_query(sql_prods_perf, params_p, fetch=True) or []

        ranking_productos = []
        lista_márgenes = []
        lista_unidades = []

        for pr in prods_perf_raw:
            pid, pnom, pcod, uds, vtas, cstos, cart = pr[0], pr[1], pr[2], float(pr[3] or 0), float(pr[4] or 0), float(pr[5] or 0), float(pr[6] or 0)
            ut_b = vtas - cstos
            mg_pct = (ut_b / vtas * 100.0) if vtas > 0 else 0.0
            ranking_productos.append({
                "id": pid, "nombre": pnom, "codigo": pcod, "unidades": uds,
                "ventas": vtas, "costo": cstos, "utilidad": ut_b, "margen_pct": mg_pct, "cartera": cart
            })
            lista_márgenes.append(mg_pct)
            lista_unidades.append(uds)

        # Cálculo riguroso de Mediana del Período para Matriz 2x2
        mediana_margen = statistics.median(lista_márgenes) if lista_márgenes else 0.0
        mediana_unidades = statistics.median(lista_unidades) if lista_unidades else 0.0

        matriz_cuadrantes = {"estrellas": [], "oportunidades": [], "volumen": [], "revisar": []}

        for item in ranking_productos:
            es_alto_margen = item["margen_pct"] >= mediana_margen
            es_alto_volumen = item["unidades"] >= mediana_unidades

            if es_alto_margen and es_alto_volumen:
                matriz_cuadrantes["estrellas"].append(item)
            elif es_alto_margen and not es_alto_volumen:
                matriz_cuadrantes["oportunidades"].append(item)
            elif not es_alto_margen and es_alto_volumen:
                matriz_cuadrantes["volumen"].append(item)
            else:
                matriz_cuadrantes["revisar"].append(item)

        # ── 9. RENTABILIDAD Y ROI POR LOTE DE IMPORTACIÓN ──
        sql_lotes = """
            SELECT l.id, l.codigo_lote, l.fecha_compra, l.cantidad_inicial, l.cantidad_disponible, l.costo_unitario, l.proveedor
            FROM lotes_inventario l
            WHERE l.negocio_id=? ORDER BY l.id DESC LIMIT 20
        """
        lotes_raw = ejecutar_query(sql_lotes, (negocio_id,), fetch=True) or []
        lotes_roi = []

        for l_row in lotes_raw:
            lid, lcode, fcomp, c_ini, c_disp, c_unit, prov = l_row[0], l_row[1], l_row[2], float(l_row[3] or 0), float(l_row[4] or 0), float(l_row[5] or 0), l_row[6] or "Importación Directa"
            c_vend = c_ini - c_disp
            inversion_total = c_ini * c_unit
            costo_vendido = c_vend * c_unit

            # Obtener ventas vinculadas a movimientos de este lote
            res_v_lote = ejecutar_query(
                "SELECT SUM(costo_subtotal) FROM movimientos_lote WHERE lote_id=? AND tipo='SALIDA_VENTA' AND negocio_id=?",
                (lid, negocio_id), fetch=True
            )
            ventas_lote_costo = res_v_lote[0][0] or 0.0 if res_v_lote else 0.0
            
            # Estimación de ventas del lote
            res_v_real = ejecutar_query(
                """SELECT SUM(v.total) FROM ventas v 
                   JOIN movimientos_lote m ON m.venta_id = v.id 
                   WHERE m.lote_id=? AND m.negocio_id=?""",
                (lid, negocio_id), fetch=True
            )
            ingresos_lote = res_v_real[0][0] or 0.0 if res_v_real else 0.0
            if ingresos_lote == 0.0 and c_vend > 0:
                # Si no hay enlace directo a venta, estimamos con precio promedio
                ingresos_lote = costo_vendido * (1 + (margen_bruto_pct / 100.0))

            utilidad_realizada = ingresos_lote - costo_vendido
            roi_realizado = (utilidad_realizada / costo_vendido * 100.0) if costo_vendido > 0 else 0.0

            # ROI Proyectado incluyendo stock restante en bodega
            mcu_est = (utilidad_realizada / c_vend) if c_vend > 0 else (c_unit * (margen_bruto_pct / 100.0))
            utilidad_potencial_total = utilidad_realizada + (c_disp * mcu_est)
            roi_proyectado = (utilidad_potencial_total / inversion_total * 100.0) if inversion_total > 0 else 0.0

            lotes_roi.append({
                "lote_code": lcode, "fecha": fcomp, "proveedor": prov, "inversion": inversion_total,
                "vendidas": c_vend, "stock": c_disp, "ingresos": ingresos_lote, "utilidad": utilidad_realizada,
                "roi_realizado": roi_realizado, "roi_proyectado": roi_proyectado,
                "estado": "AGOTADO" if c_disp <= 0.001 else "ACTIVO"
            })

        # ── 10. EVOLUCIÓN TEMPORAL MULTI-MÉTRICA ──
        sql_trend = """
            SELECT SUBSTR(fecha, 1, 7) as mes,
                   SUM(total) as ingresos,
                   SUM(costo_historico_total) as costos,
                   SUM(total - costo_historico_total) as utilidad,
                   SUM(CASE WHEN UPPER(metodo_pago) = 'CRÉDITO' THEN total ELSE 0 END) as ventas_credito
            FROM ventas WHERE negocio_id=? GROUP BY mes ORDER BY mes ASC LIMIT 12
        """
        trend_rows = ejecutar_query(sql_trend, (negocio_id,), fetch=True) or []
        series_evolucion = {
            "labels": [t[0] for t in trend_rows],
            "ingresos": [float(t[1] or 0) for t in trend_rows],
            "costos": [float(t[2] or 0) for t in trend_rows],
            "utilidad": [float(t[3] or 0) for t in trend_rows],
            "margen_pct": [(float(t[3] or 0) / float(t[1] or 1) * 100.0) if float(t[1] or 0) > 0 else 0.0 for t in trend_rows],
            "ventas_credito": [float(t[4] or 0) for t in trend_rows]
        }

        # ── 11. INTELIGENCIA AS 🧠 (DIAGNÓSTICO BASADO EN EVIDENCIA EMPÍRICA) ──
        insights_as = []

        # Insight 1: Comparación de Margen
        if delta_kpis.get("tiene_anterior") and abs(delta_kpis.get("margen_pp", 0)) > 0.1:
            diff_pp = delta_kpis["margen_pp"]
            signo = "+" if diff_pp > 0 else ""
            insights_as.append({
                "icono": "🟢" if diff_pp > 0 else "🔴",
                "tipo": "ÉXITO" if diff_pp > 0 else "ALERTA",
                "categoria": "RENTABILIDAD",
                "evidencia": f"El margen bruto del período ({margen_bruto_pct:.1f}%) cambió en {signo}{diff_pp:.1f} pp respecto al período anterior.",
                "diagnostico": "La eficiencia operativa del negocio está variando positivamente." if diff_pp > 0 else "El costo de adquisición o los precios están reduciendo la rentabilidad relativa.",
                "accion": "Mantener estrategia comercial actual." if diff_pp > 0 else "Revisar precios de venta o renegociar costos de insumos/fletes."
            })

        # Insight 2: Concentración de Cartera
        if top_deudores and cartera_pendiente_total > 0:
            top1_pct = top_deudores[0]["pct_concentracion"]
            if top1_pct >= 40.0:
                insights_as.append({
                    "icono": "🟠",
                    "tipo": "RIESGO",
                    "categoria": "CONCENTRACIÓN DE CARTERA",
                    "evidencia": f"El cliente '{top_deudores[0]['cliente']}' concentra el {top1_pct:.1f}% de toda la cartera pendiente del negocio (${top_deudores[0]['saldo']:,.0f}).",
                    "diagnostico": "Alto riesgo de liquidez si esta cuenta entra en mora prolongada.",
                    "accion": "Establecer cupos de crédito estrictos y gestionar cobro prioritario con esta cuenta."
                })

        # Insight 3: Producto de Bajo Margen en el Período
        prods_bajo_margen = [p for p in ranking_productos if p["margen_pct"] < (margen_bruto_pct - 8.0) and p["ventas"] > 0]
        if prods_bajo_margen:
            p_peor = min(prods_bajo_margen, key=lambda x: x["margen_pct"])
            insights_as.append({
                "icono": "🔴",
                "tipo": "ALERTA",
                "categoria": "RENTABILIDAD POR PRODUCTO",
                "evidencia": f"El producto '{p_peor['nombre']}' registra un margen del {p_peor['margen_pct']:.1f}%, ubicado {margen_bruto_pct - p_peor['margen_pct']:.1f} pp por debajo del promedio del negocio.",
                "diagnostico": "Este artículo genera volumen pero erosiona la utilidad global.",
                "accion": "Ajustar precio de venta o evaluar costos landed del proveedor."
            })

        # Insight 4: Oportunidad Comercial (Alto Margen + Bajo Volumen)
        if matriz_cuadrantes["oportunidades"]:
            p_op = max(matriz_cuadrantes["oportunidades"], key=lambda x: x["margen_pct"])
            insights_as.append({
                "icono": "🔵",
                "tipo": "OPORTUNIDAD",
                "categoria": "DESARROLLO COMERCIAL",
                "evidencia": f"El producto '{p_op['nombre']}' cuenta con un alto margen del {p_op['margen_pct']:.1f}%, pero baja rotación ({p_op['unidades']:.0f} uds).",
                "diagnostico": "Potencial desaprovechado de alta rentabilidad.",
                "accion": "Impulsar campañas de mercadeo o ubicación destacada para este producto estrella."
            })

        return {
            "ok": True,
            "periodo": periodo,
            "kpis": {
                "ingresos": total_ingresos,
                "costos_v": total_costos_v,
                "utilidad_bruta": utilidad_bruta,
                "margen_bruto_pct": margen_bruto_pct,
                "costos_fijos": costos_fijos_periodo,
                "tiene_costos_fijos": tiene_costos_fijos_registrados,
                "utilidad_neta": utilidad_neta,
                "ventas_credito": ventas_credito,
                "recaudo_periodo": recaudo_total_periodo,
                "cobertura_caja_pct": cobertura_caja_pct,
                "cartera_pendiente_total": cartera_pendiente_total,
                "punto_equilibrio": {
                    "calculable": pe_calculable,
                    "pesos": pe_pesos,
                    "unidades": pe_unidades,
                    "motivo": pe_motivo
                }
            },
            "deltas": delta_kpis,
            "evolucion": series_evolucion,
            "ranking_productos": ranking_productos,
            "matriz_2x2": {
                "mediana_margen": mediana_margen,
                "mediana_unidades": mediana_unidades,
                "cuadrantes": matriz_cuadrantes
            },
            "lotes_roi": lotes_roi,
            "aging_cartera": aging,
            "top_deudores": top_deudores,
            "inteligencia_as": insights_as
        }
    except Exception as e:
        import traceback
        print(f"Error al generar tablero ejecutivo completo: {e}\n{traceback.format_exc()}")
        return {"ok": False, "error": str(e)}

def obtener_resumen_financiero(negocio_id, mes_filtro=None, producto_id=None, metodo_pago=None):
    query = "SELECT total, costo_historico_total, cantidad, producto_id FROM ventas WHERE negocio_id=?"
    params = [negocio_id]
    
    if mes_filtro:
        query += " AND fecha LIKE ?"
        params.append(f"{mes_filtro}%")
    if producto_id:
        query += " AND producto_id = ?"
        params.append(producto_id)
    if metodo_pago:
        query += " AND metodo_pago = ?"
        params.append(metodo_pago)
    
    ventas = ejecutar_query(query, params, fetch=True)
    
    total_ingresos = sum(v[0] for v in ventas)
    total_costos_v = sum(v[1] for v in ventas)
    total_unidades = sum(v[2] for v in ventas)
    utilidad_bruta = total_ingresos - total_costos_v
    
    mes_actual = mes_filtro if mes_filtro else datetime.now().strftime("%Y-%m")
    res_f = ejecutar_query("SELECT SUM(valor) FROM costos_fijos WHERE mes = ? AND negocio_id=?", (mes_actual, negocio_id), fetch=True)
    total_costos_f = res_f[0][0] or 0.0

    if total_costos_f == 0.0:
        res_f_global = ejecutar_query("SELECT SUM(valor) FROM costos_fijos WHERE negocio_id=?", (negocio_id,), fetch=True)
        total_costos_f = (res_f_global[0][0] or 0.0) if res_f_global else 0.0
    
    prods = ejecutar_query("SELECT id, nombre FROM productos WHERE negocio_id=?", (negocio_id,), fetch=True)
    
    mcp = 0.0
    analisis_productos = []
    for p_id, p_nombre in prods:
        p_ventas = [v for v in ventas if v[3] == p_id]
        p_unidades = sum(v[2] for v in p_ventas)
        p_ingreso = sum(v[0] for v in p_ventas)
        p_costo = sum(v[1] for v in p_ventas)
        mcu = (p_ingreso - p_costo) / p_unidades if p_unidades > 0 else 0
        participacion = p_unidades / total_unidades if total_unidades > 0 else 0
        mcp += mcu * participacion
        if p_unidades > 0:
            analisis_productos.append({"nombre": p_nombre, "unidades": p_unidades, "participacion": participacion * 100, "mcu": mcu})

    ratio_margen = (utilidad_bruta / total_ingresos) if total_ingresos > 0 else 0.0
    punto_equilibrio_pesos = (total_costos_f / ratio_margen) if ratio_margen > 0 else 0.0
    punto_equilibrio_unidades = (total_costos_f / mcp) if mcp > 0 else (punto_equilibrio_pesos / (total_ingresos / total_unidades) if (total_unidades > 0 and total_ingresos > 0) else 0.0)

    return {
        "ingresos": total_ingresos, "costos_v": total_costos_v, "costos_f": total_costos_f,
        "utilidad": utilidad_bruta - total_costos_f, "margen_contribucion": utilidad_bruta,
        "ratio_margen": ratio_margen * 100,
        "mcp": mcp,
        "punto_equilibrio": punto_equilibrio_unidades,
        "punto_equilibrio_pesos": punto_equilibrio_pesos,
        "unidades_totales": total_unidades,
        "requiere_costos_fijos": bool(total_costos_f == 0.0),
        "detalle_productos": analisis_productos
    }