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
    total_costos_f = res_f[0][0] or 0
    
    prods = ejecutar_query("SELECT id, nombre FROM productos WHERE negocio_id=?", (negocio_id,), fetch=True)
    
    mcp = 0
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

    punto_equilibrio = total_costos_f / mcp if mcp > 0 else 0
    return {
        "ingresos": total_ingresos, "costos_v": total_costos_v, "costos_f": total_costos_f,
        "utilidad": utilidad_bruta - total_costos_f, "margen_contribucion": utilidad_bruta,
        "mcp": mcp, "punto_equilibrio": punto_equilibrio, "unidades_totales": total_unidades,
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

def obtener_diagnostico_inteligencia(negocio_id):
    try:
        import services.cartera_service as cartera_service
        rf = obtener_resumen_financiero(negocio_id)
        rc = cartera_service.obtener_resumen_cartera(negocio_id)

        utilidad = rf.get('utilidad', 0.0)
        cartera_vencida = rc.get('cartera_vencida', 0.0)
        cartera_total = rc.get('cartera_total', 0.0)
        recaudo_mes = rc.get('recaudo_mes', 0.0)

        alertas = []
        tipo_diag = "NORMAL"

        if utilidad > 0 and cartera_vencida > 0 and cartera_vencida > recaudo_mes * 0.5:
            tipo_diag = "ALERTA_LIQUIDEZ"
            alertas.append(f"💡 Diagnóstico AS: Tu negocio es rentable (Utilidad: ${utilidad:,.0f}), pero tienes un problema de liquidez por cartera vencida (${cartera_vencida:,.0f}).")
        elif cartera_vencida > 0:
            alertas.append(f"⚠️ Atención de Cartera: Tienes ${cartera_vencida:,.0f} en cartera vencida que requieren cobro inmediato.")
        elif utilidad < 0:
            alertas.append("🔴 Alerta de Rentabilidad: Tus costos fijos e insumos están superando tus ingresos. Revisa tus precios de venta o costos.")
        else:
            alertas.append("🟢 Operación Saludable: Tus ventas y recaudos se encuentran dentro de los parámetros esperados.")

        return {
            "tipo": tipo_diag,
            "utilidad": utilidad,
            "recaudo_mes": recaudo_mes,
            "cartera_total": cartera_total,
            "cartera_vencida": cartera_vencida,
            "mensaje": alertas[0] if alertas else "Operación en orden."
        }
    except Exception as e:
        print(f"Error diagnostico inteligencia: {e}")
        return {"tipo": "NORMAL", "mensaje": "Operación estándar."}