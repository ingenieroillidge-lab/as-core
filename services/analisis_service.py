import json
from datetime import datetime, timedelta
from database import ejecutar_query

def parsear_periodo_fechas(filtros):
    """
    Normaliza el objeto filtros para obtener fecha_inicio y fecha_fin (YYYY-MM-DD).
    Soporta accesos rápidos de periodo (hoy, esta_semana, este_mes, ultimos_30_dias, etc).
    """
    hoy = datetime.now().date()
    fecha_inicio = filtros.get('fecha_inicio')
    fecha_fin = filtros.get('fecha_fin')
    periodo = filtros.get('periodo')

    if periodo:
        if periodo == 'hoy':
            fecha_inicio = hoy.strftime("%Y-%m-%d")
            fecha_fin = hoy.strftime("%Y-%m-%d")
        elif periodo == 'esta_semana':
            start = hoy - timedelta(days=hoy.weekday())
            fecha_inicio = start.strftime("%Y-%m-%d")
            fecha_fin = hoy.strftime("%Y-%m-%d")
        elif periodo == 'este_mes':
            start = hoy.replace(day=1)
            fecha_inicio = start.strftime("%Y-%m-%d")
            fecha_fin = hoy.strftime("%Y-%m-%d")
        elif periodo == 'mes_anterior':
            first_this_month = hoy.replace(day=1)
            last_month_end = first_this_month - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            fecha_inicio = last_month_start.strftime("%Y-%m-%d")
            fecha_fin = last_month_end.strftime("%Y-%m-%d")
        elif periodo == 'ultimos_30_dias':
            fecha_inicio = (hoy - timedelta(days=30)).strftime("%Y-%m-%d")
            fecha_fin = hoy.strftime("%Y-%m-%d")
        elif periodo == 'ultimos_90_dias':
            fecha_inicio = (hoy - timedelta(days=90)).strftime("%Y-%m-%d")
            fecha_fin = hoy.strftime("%Y-%m-%d")
        elif periodo == 'este_ano':
            fecha_inicio = f"{hoy.year}-01-01"
            fecha_fin = hoy.strftime("%Y-%m-%d")

    return fecha_inicio, fecha_fin

def obtener_opciones_filtros(negocio_id):
    """
    Devuelve dimensiones analíticas realmente disponibles para el negocio actual
    para alimentar desplegables dinámicos en el frontend.
    """
    cats = ejecutar_query(
        "SELECT DISTINCT categoria FROM productos WHERE negocio_id=? AND categoria IS NOT NULL AND categoria!=''",
        (negocio_id,), fetch=True
    ) or []
    
    subcats = ejecutar_query(
        "SELECT DISTINCT subcategoria FROM productos WHERE negocio_id=? AND subcategoria IS NOT NULL AND subcategoria!=''",
        (negocio_id,), fetch=True
    ) or []

    prods = ejecutar_query(
        "SELECT id, nombre FROM productos WHERE negocio_id=? ORDER BY nombre ASC",
        (negocio_id,), fetch=True
    ) or []

    clis = ejecutar_query(
        "SELECT DISTINCT nombre FROM clientes WHERE negocio_id=? ORDER BY nombre ASC",
        (negocio_id,), fetch=True
    ) or []

    lotes = ejecutar_query(
        "SELECT DISTINCT codigo_lote, proveedor FROM lotes_inventario WHERE negocio_id=? ORDER BY codigo_lote ASC",
        (negocio_id,), fetch=True
    ) or []

    provs = list({l[1] for l in lotes if l[1]})

    return {
        "categorias": [c[0] for c in cats],
        "subcategorias": [s[0] for s in subcats],
        "productos": [{"id": p[0], "nombre": p[1]} for p in prods],
        "clientes": [c[0] for c in clis],
        "lotes": [l[0] for l in lotes],
        "proveedores": provs
    }

def obtener_centro_analisis_completo(negocio_id, filtros=None):
    """
    Motor central del Centro de Análisis Empresarial.
    Aplica el mismo objeto de contexto semántico 'filtros' a todas las consultas.
    Garantiza multi-tenancy estricto (negocio_id) y coherencia matemática entre KPIs:
      Utilidad = Ingresos - Costos
      Margen % = (Utilidad / Ingresos) * 100
    """
    filtros = filtros or {}
    f_inicio, f_fin = parsear_periodo_fechas(filtros)

    cat = filtros.get('categoria')
    subcat = filtros.get('subcategoria')
    prod_id = filtros.get('producto_id')
    var_val = filtros.get('variante')
    cli_nom = filtros.get('cliente_nombre')
    lote_cod = filtros.get('lote_codigo')
    prov_nom = filtros.get('proveedor')
    est_val = filtros.get('estado')

    # ──────────────────────────────────────────────────────────────────
    # 1. TOTALES DE UNIVERSO PARA CONTEO ("¿Qué estoy analizando?")
    # ──────────────────────────────────────────────────────────────────
    tot_ventas_universo = (ejecutar_query(
        "SELECT COUNT(*) FROM ventas WHERE negocio_id=?", (negocio_id,), fetch=True
    ) or [(0,)])[0][0]

    tot_prods_universo = (ejecutar_query(
        "SELECT COUNT(*) FROM productos WHERE negocio_id=?", (negocio_id,), fetch=True
    ) or [(0,)])[0][0]

    tot_lotes_universo = (ejecutar_query(
        "SELECT COUNT(*) FROM lotes_inventario WHERE negocio_id=?", (negocio_id,), fetch=True
    ) or [(0,)])[0][0]

    # ──────────────────────────────────────────────────────────────────
    # 2. CONSTRUCCIÓN DE CONSULTA DE VENTAS FILTRADA
    # ──────────────────────────────────────────────────────────────────
    sql_v = """
        SELECT 
            v.id, v.fecha, v.total, v.cantidad, v.costo_historico_total, 
            v.precio_historico_unitario, v.metodo_pago, v.cliente_nombre, v.saldo_pendiente,
            p.id as prod_id, p.nombre as prod_nombre, p.categoria, p.subcategoria, p.variante
        FROM ventas v
        LEFT JOIN productos p ON v.producto_id = p.id
        WHERE v.negocio_id = ?
    """
    params_v = [negocio_id]

    if f_inicio:
        sql_v += " AND v.fecha >= ?"
        params_v.append(f_inicio)
    if f_fin:
        sql_v += " AND v.fecha <= ?"
        params_v.append(f"{f_fin} 23:59:59")
    if cat:
        sql_v += " AND p.categoria = ?"
        params_v.append(cat)
    if subcat:
        sql_v += " AND p.subcategoria = ?"
        params_v.append(subcat)
    if prod_id:
        sql_v += " AND p.id = ?"
        params_v.append(int(prod_id))
    if var_val:
        sql_v += " AND p.variante = ?"
        params_v.append(var_val)
    if cli_nom:
        sql_v += " AND (LOWER(v.cliente_nombre) LIKE LOWER(?))"
        params_v.append(f"%{cli_nom}%")

    sql_v += " ORDER BY v.fecha DESC"
    filas_ventas = ejecutar_query(sql_v, tuple(params_v), fetch=True) or []

    # ──────────────────────────────────────────────────────────────────
    # 3. CÁLCULO DE KPIS COHERENTES SOBRE EL CONJUNTO FILTRADO
    # ──────────────────────────────────────────────────────────────────
    ingresos = 0.0
    costos = 0.0
    unidades_vendidas = 0.0
    cartera_pendiente = 0.0
    ventas_count = len(filas_ventas)

    prod_ids_filtrados = set()
    clientes_filtrados = set()

    desglose_productos = {}

    for row in filas_ventas:
        v_tot = float(row[2] or 0)
        v_cant = float(row[3] or 1)
        v_costo = float(row[4] or 0)
        v_cli = row[7] or 'Cliente General'
        v_saldo = float(row[8] or 0)
        pid = row[9]
        pname = row[10] or 'Producto General'
        pcat = row[11] or 'Sin Categoría'

        ingresos += v_tot
        costos += v_costo
        unidades_vendidas += v_cant
        cartera_pendiente += v_saldo

        if pid:
            prod_ids_filtrados.add(pid)
        if v_cli:
            clientes_filtrados.add(v_cli)

        if pname not in desglose_productos:
            desglose_productos[pname] = {
                "id": pid,
                "nombre": pname,
                "categoria": pcat,
                "unidades": 0.0,
                "ingresos": 0.0,
                "costos": 0.0,
                "utilidad": 0.0,
                "margen_pct": 0.0
            }
        
        desglose_productos[pname]["unidades"] += v_cant
        desglose_productos[pname]["ingresos"] += v_tot
        desglose_productos[pname]["costos"] += v_costo

    utilidad = ingresos - costos
    margen_pct = ((utilidad / ingresos) * 100.0) if ingresos > 0 else 0.0

    # Calcular margen por producto en desglose
    lista_rentabilidad_productos = []
    for pname, item in desglose_productos.items():
        item["utilidad"] = item["ingresos"] - item["costos"]
        item["margen_pct"] = ((item["utilidad"] / item["ingresos"]) * 100.0) if item["ingresos"] > 0 else 0.0
        
        # Cargar atributos guardados de este producto
        attrs = []
        if item["id"]:
            attr_rows = ejecutar_query(
                "SELECT nombre_atributo, valor_atributo, tipo FROM producto_atributos WHERE negocio_id=? AND producto_id=?",
                (negocio_id, item["id"]), fetch=True
            ) or []
            attrs = [{"nombre": a[0], "valor": a[1], "tipo": a[2]} for a in attr_rows]
        item["atributos"] = attrs
        lista_rentabilidad_productos.append(item)

    lista_rentabilidad_productos.sort(key=lambda x: x["ingresos"], reverse=True)

    # ──────────────────────────────────────────────────────────────────
    # 4. INVENTARIO Y LOTES EN EL MISMO CONTEXTO
    # ──────────────────────────────────────────────────────────────────
    sql_lotes = "SELECT id, codigo_lote, proveedor, cantidad_inicial, cantidad_disponible, costo_unitario, fecha_compra FROM lotes_inventario WHERE negocio_id=?"
    params_lotes = [negocio_id]
    if lote_cod:
        sql_lotes += " AND codigo_lote=?"
        params_lotes.append(lote_cod)
    if prov_nom:
        sql_lotes += " AND proveedor=?"
        params_lotes.append(prov_nom)

    filas_lotes = ejecutar_query(sql_lotes, tuple(params_lotes), fetch=True) or []
    lotes_map = {}
    valor_inventario_lotes = 0.0

    for l in filas_lotes:
        lid = l[0]
        code = (l[1] or 'LOTE-GENERAL').strip()
        prov = l[2] or 'Proveedor General'
        c_ini = float(l[3] or 0)
        c_disp = float(l[4] or 0)
        c_unit = float(l[5] or 0)
        f_comp = l[6] or ''

        inversion_row = c_ini * c_unit
        stock_valor_row = c_disp * c_unit
        valor_inventario_lotes += stock_valor_row

        if code not in lotes_map:
            lotes_map[code] = {
                "id": lid,
                "codigo_lote": code,
                "proveedor": prov,
                "cantidad_inicial": 0.0,
                "cantidad_disponible": 0.0,
                "unidades_vendidas": 0.0,
                "inversion_total": 0.0,
                "valor_inventario_restante": 0.0,
                "fecha_compra": f_comp
            }
        
        lotes_map[code]["cantidad_inicial"] += c_ini
        lotes_map[code]["cantidad_disponible"] += c_disp
        lotes_map[code]["unidades_vendidas"] += (c_ini - c_disp)
        lotes_map[code]["inversion_total"] += inversion_row
        lotes_map[code]["valor_inventario_restante"] += stock_valor_row

    lista_lotes = []
    for code, item in lotes_map.items():
        item["costo_unitario"] = (item["inversion_total"] / item["cantidad_inicial"]) if item["cantidad_inicial"] > 0 else 0.0
        lista_lotes.append(item)

    # ──────────────────────────────────────────────────────────────────
    # 5. ALCANCE DE ANÁLISIS ("¿Qué estoy analizando?")
    # ──────────────────────────────────────────────────────────────────
    texto_alcance = f"Analizando {ventas_count} ventas de {tot_ventas_universo} totales | {len(prod_ids_filtrados)} productos | {len(lista_lotes)} lotes"

    # ──────────────────────────────────────────────────────────────────
    # 6. CARTERA Y ANÁLISIS DE CLIENTES ENRIQUECIDO
    # ──────────────────────────────────────────────────────────────────
    sql_cartera_cli = """
        SELECT v.cliente_nombre, COUNT(*) as ops, SUM(v.total) as compras,
               SUM(v.total - v.saldo_pendiente) as abonado, SUM(v.saldo_pendiente) as saldo,
               MAX(v.fecha) as ultima_compra
        FROM ventas v
        WHERE v.negocio_id=? AND v.cliente_nombre IS NOT NULL AND v.cliente_nombre != ''
        GROUP BY v.cliente_nombre
        HAVING SUM(v.saldo_pendiente) > 0.01
        ORDER BY saldo DESC
    """
    cartera_cli_rows = ejecutar_query(sql_cartera_cli, (negocio_id,), fetch=True) or []
    cartera_por_cliente = []

    for r in cartera_cli_rows:
        cli_nom_r = r[0] or "Cliente General"
        ops_r = r[1] or 0
        compras_r = r[2] or 0.0
        abonos_r = r[3] or 0.0
        saldo_r = r[4] or 0.0
        ult_comp_r = r[5] or ""

        # Producto preferido del cliente (mayor número de unidades compradas)
        pref_row = ejecutar_query(
            """SELECT p.nombre, SUM(v.cantidad) as total_qty
               FROM ventas v
               LEFT JOIN productos p ON v.producto_id = p.id
               WHERE v.negocio_id=? AND LOWER(v.cliente_nombre) = LOWER(?)
               GROUP BY p.nombre ORDER BY total_qty DESC LIMIT 1""",
            (negocio_id, cli_nom_r), fetch=True
        )
        prod_preferido = pref_row[0][0] if (pref_row and pref_row[0] and pref_row[0][0]) else "N/A"

        cartera_por_cliente.append({
            "cliente": cli_nom_r,
            "operaciones": ops_r,
            "total_compras": compras_r,
            "total_abonos": abonos_r,
            "saldo_pendiente": saldo_r,
            "ticket_promedio": round(compras_r / ops_r, 2) if ops_r > 0 else 0.0,
            "ultima_compra": ult_comp_r,
            "producto_preferido": prod_preferido
        })

    # ──────────────────────────────────────────────────────────────────
    # 7. COSTOS FIJOS Y PUNTO DE EQUILIBRIO (PESOS Y UNIDADES)
    # ──────────────────────────────────────────────────────────────────
    cf_res = ejecutar_query(
        "SELECT SUM(valor) FROM costos_fijos WHERE negocio_id=?",
        (negocio_id,), fetch=True
    )
    costos_fijos_tot = (cf_res[0][0] or 0.0) if (cf_res and cf_res[0]) else 0.0

    ratio_m = (utilidad / ingresos) if ingresos > 0 else 0.0
    punto_equilibrio_pesos = (costos_fijos_tot / ratio_m) if ratio_m > 0 else 0.0
    mcu_ponderado = (utilidad / unidades_vendidas) if unidades_vendidas > 0 else 0.0
    punto_equilibrio_unidades = (costos_fijos_tot / mcu_ponderado) if mcu_ponderado > 0 else 0.0

    return {
        "ok": True,
        "kpis": {
            "ingresos": ingresos,
            "costos": costos,
            "costos_fijos": costos_fijos_tot,
            "utilidad": utilidad,
            "utilidad_neta": utilidad - costos_fijos_tot,
            "margen_pct": round(margen_pct, 2),
            "cartera_pendiente": cartera_pendiente,
            "unidades_vendidas": unidades_vendidas,
            "ventas_count": ventas_count,
            "valor_inventario_lotes": valor_inventario_lotes,
            "punto_equilibrio_pesos": punto_equilibrio_pesos,
            "punto_equilibrio_unidades": punto_equilibrio_unidades
        },
        "alcance": {
            "texto": texto_alcance,
            "ventas_filtradas": ventas_count,
            "ventas_totales": tot_ventas_universo,
            "productos_filtrados": len(prod_ids_filtrados),
            "productos_totales": tot_prods_universo,
            "lotes_filtrados": len(lista_lotes),
            "lotes_totales": tot_lotes_universo
        },
        "rentabilidad_productos": lista_rentabilidad_productos[:50],
        "lotes": lista_lotes,
        "cartera_por_cliente": cartera_por_cliente,
        "ventas_recientes": [{
            "id": r[0],
            "fecha": r[1],
            "total": r[2],
            "cantidad": r[3],
            "costo": r[4],
            "utilidad": (r[2] or 0) - (r[4] or 0),
            "cliente": r[7] or 'Cliente General',
            "saldo_pendiente": r[8] or 0,
            "producto": r[10] or 'Producto'
        } for r in filas_ventas[:30]]
    }

