from database import ejecutar_query
from datetime import datetime

def obtener_resumen_financiero(mes_filtro=None, producto_id=None, metodo_pago=None):
    query = "SELECT total, costo_historico_total, cantidad, producto_id FROM ventas WHERE 1=1"
    params = []
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
    res_f = ejecutar_query("SELECT SUM(valor) FROM costos_fijos WHERE mes = ?", (mes_actual,), fetch=True)
    total_costos_f = res_f[0][0] or 0
    
    prods = ejecutar_query("SELECT id, nombre FROM productos", fetch=True)
    
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

def obtener_tablero_datos():
    res = ejecutar_query("""
        SELECT v.fecha, p.nombre, v.cantidad, v.total, v.costo_historico_total, (v.total - v.costo_historico_total) as utilidad
        FROM ventas v JOIN productos p ON v.producto_id = p.id
        ORDER BY v.fecha DESC LIMIT 100
    """, fetch=True)
    return [{"fecha": x[0], "producto": x[1], "cantidad": x[2], "ingreso": x[3], "costo_v": x[4], "utilidad": x[5]} for x in res]

def obtener_rentabilidad_productos():
    prods = ejecutar_query("SELECT id, codigo, nombre, precio FROM productos", fetch=True)
    reporte = []
    for p_id, p_cod, p_nom, p_pre in prods:
        res_c = ejecutar_query("""
            SELECT SUM(ri.cantidad_usada * i.costo_unitario_base)
            FROM producto_insumo ri JOIN inventario i ON ri.insumo_id = i.id
            WHERE ri.producto_id = ?
        """, (p_id,), fetch=True)
        costo_v = res_c[0][0] or 0
        mcu = p_pre - costo_v
        reporte.append({"id": p_id, "codigo": p_cod, "producto": p_nom, "precio": p_pre, "costo": costo_v, "margen": mcu, "porcentaje": (mcu/p_pre*100) if p_pre>0 else 0})
    return reporte

def obtener_utilidad_mensual_historica():
    meses = ejecutar_query("SELECT strftime('%Y-%m', fecha) as mes, SUM(total), SUM(costo_historico_total) FROM ventas GROUP BY mes ORDER BY mes DESC", fetch=True)
    reporte = []
    for mes, ing, c_v in meses:
        res_f = ejecutar_query("SELECT SUM(valor) FROM costos_fijos WHERE mes = ?", (mes,), fetch=True)
        c_f = res_f[0][0] or 0
        reporte.append({"mes": mes, "ingresos": ing, "costos_v": c_v, "costos_f": c_f, "utilidad": ing - c_v - c_f})
    return reporte

def obtener_datos_graficos():
    tendencia = ejecutar_query("SELECT strftime('%Y-%m', fecha) as mes, SUM(total) FROM ventas GROUP BY mes ORDER BY mes ASC LIMIT 6", fetch=True)
    distribucion = ejecutar_query("SELECT p.nombre, SUM(v.total) FROM ventas v JOIN productos p ON v.producto_id = p.id GROUP BY p.nombre ORDER BY SUM(v.total) DESC LIMIT 5", fetch=True)
    rentables = ejecutar_query("SELECT p.nombre, (SUM(v.total) - SUM(v.costo_historico_total)) as margen FROM ventas v JOIN productos p ON v.producto_id = p.id GROUP BY p.nombre ORDER BY margen DESC LIMIT 5", fetch=True)
    return {
        "tendencia": {"labels": [x[0] for x in tendencia], "data": [x[1] for x in tendencia]},
        "distribucion": {"labels": [x[0] for x in distribucion], "data": [x[1] for x in distribucion]},
        "top_rentables": [{"producto": x[0], "margen": x[1]} for x in rentables]
    }

def realizar_cierre_caja(fecha_cierre=None):
    if not fecha_cierre: fecha_cierre = datetime.now().strftime("%Y-%m-%d")
    pagos = ejecutar_query("SELECT metodo_pago, SUM(total) FROM ventas WHERE fecha LIKE ? GROUP BY metodo_pago", (f"{fecha_cierre}%",), fetch=True)
    return {"fecha": fecha_cierre, "total": sum(x[1] for x in pagos), "detalle": {x[0]: x[1] for x in pagos}}