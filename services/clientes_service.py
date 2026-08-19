from database import ejecutar_query
from datetime import datetime, timedelta

def obtener_directorio_clientes_360(negocio_id, busqueda=None, filtro_estado=None):
    """
    Capa de Inteligencia Comercial 360° para Clientes.
    Reutiliza la tabla 'clientes' y calcula los indicadores en tiempo real
    desde las fuentes transaccionales existentes ('ventas' y 'abonos_cartera').
    """
    try:
        sql_clientes = """
            SELECT id, nombre, tipo, documento, telefono, whatsapp, email, direccion, 
                   limite_credito, dias_credito_predeterminado, estado
            FROM clientes
            WHERE negocio_id = ?
        """
        params_c = [negocio_id]

        if busqueda:
            sql_clientes += " AND (LOWER(nombre) LIKE LOWER(?) OR LOWER(documento) LIKE LOWER(?) OR LOWER(telefono) LIKE LOWER(?))"
            term = f"%{busqueda.strip()}%"
            params_c.extend([term, term, term])

        sql_clientes += " ORDER BY nombre ASC"
        res_clientes = ejecutar_query(sql_clientes, tuple(params_c), fetch=True) or []

        # Obtener agregados de ventas por cliente para este negocio
        sql_agregados = """
            SELECT LOWER(cliente_nombre) as cli_key,
                   COUNT(id) as ops,
                   SUM(total) as total_compras,
                   SUM(saldo_pendiente) as saldo_activo,
                   MAX(fecha) as ultima_fecha
            FROM ventas
            WHERE negocio_id = ? AND cliente_nombre IS NOT NULL AND cliente_nombre != ''
            GROUP BY LOWER(cliente_nombre)
        """
        res_agregados = ejecutar_query(sql_agregados, (negocio_id,), fetch=True) or []
        mapa_agregados = {}
        for r in res_agregados:
            mapa_agregados[r[0]] = {
                "ops": r[1] or 0,
                "total_compras": float(r[2] or 0.0),
                "saldo_activo": float(r[3] or 0.0),
                "ultima_fecha": r[4] or ""
            }

        hoy_date = datetime.now().date()
        out = []

        for c in res_clientes:
            cid, nom, tipo, doc, tel, ws, em, dir_c, lim, dias, est = c
            nom_key = (nom or '').strip().lower()
            agr = mapa_agregados.get(nom_key, {"ops": 0, "total_compras": 0.0, "saldo_activo": 0.0, "ultima_fecha": ""})

            ops = agr["ops"]
            total_compras = agr["total_compras"]
            saldo_activo = agr["saldo_activo"]
            ult_fecha = agr["ultima_fecha"]
            ticket_promedio = round(total_compras / ops, 2) if ops > 0 else 0.0

            # Determinar nivel de recurrencia
            frecuencia_lbl = "NUEVO"
            if ops >= 3:
                frecuencia_lbl = "FRECUENTE"
            elif ops >= 1:
                if ult_fecha:
                    try:
                        f_dt = datetime.strptime(ult_fecha[:10], "%Y-%m-%d").date()
                        dias_desde = (hoy_date - f_dt).days
                        frecuencia_lbl = "RECIENTE" if dias_desde <= 30 else "OCASIONAL"
                    except Exception:
                        frecuencia_lbl = "RECIENTE"
                else:
                    frecuencia_lbl = "OCASIONAL"

            ws_num = ws or tel or ""

            out.append({
                "id": cid,
                "nombre": nom or "Cliente General",
                "tipo": tipo or "PERSONA",
                "documento": doc or "",
                "telefono": tel or "",
                "whatsapp": ws_num,
                "email": em or "",
                "direccion": dir_c or "",
                "limite_credito": float(lim or 0.0),
                "dias_credito": int(dias or 15),
                "estado": est or "ACTIVO",
                "total_compras": total_compras,
                "operaciones": ops,
                "ticket_promedio": ticket_promedio,
                "saldo_pendiente": saldo_activo,
                "ultima_compra": ult_fecha,
                "frecuencia": frecuencia_lbl,
                "tiene_cartera_activa": bool(saldo_activo > 0.01)
            })

        # Aplicar filtro de estado/cartera si se especificó
        if filtro_estado == 'con_cartera':
            out = [x for x in out if x["tiene_cartera_activa"]]
        elif filtro_estado == 'frecuentes':
            out = [x for x in out if x["frecuencia"] in ("FRECUENTE", "RECIENTE")]
        elif filtro_estado == 'al_dia':
            out = [x for x in out if not x["tiene_cartera_activa"] and x["operaciones"] > 0]

        return out
    except Exception as e:
        print(f"Error directorio clientes 360: {e}")
        return []

def obtener_ficha_cliente_360(cliente_id, negocio_id):
    """
    Obtiene el detalle analítico completo 360° para un cliente específico.
    Incluye datos de contacto, historial de compras, preferencia de productos y cartera.
    """
    try:
        res_c = ejecutar_query(
            """SELECT id, nombre, tipo, documento, telefono, whatsapp, email, direccion, 
                      limite_credito, dias_credito_predeterminado, estado
               FROM clientes WHERE id=? AND negocio_id=?""",
            (cliente_id, negocio_id), fetch=True
        )
        if not res_c:
            return False, "Cliente no encontrado", None

        c = res_c[0]
        cid, nom, tipo, doc, tel, ws, em, dir_c, lim, dias, est = c

        # 1. Ventas e Historial
        sql_v = """
            SELECT v.id, v.fecha, p.nombre as producto_nombre, v.cantidad, v.total, 
                   v.saldo_pendiente, v.estado_pago, v.metodo_pago, v.observacion
            FROM ventas v
            LEFT JOIN productos p ON v.producto_id = p.id
            WHERE LOWER(v.cliente_nombre) = LOWER(?) AND v.negocio_id = ?
            ORDER BY v.fecha DESC
        """
        filas_v = ejecutar_query(sql_v, (nom, negocio_id), fetch=True) or []

        historial_compras = []
        total_compras = 0.0
        saldo_pendiente = 0.0
        productos_conteo = {}

        for r in filas_v:
            v_id, fecha, prod_nom, cant, total, saldo, est_pago, metodo, obs = r
            v_tot = float(total or 0.0)
            v_saldo = float(saldo or 0.0)
            p_name = prod_nom or "Producto General"

            total_compras += v_tot
            if v_saldo > 0.01:
                saldo_pendiente += v_saldo

            productos_conteo[p_name] = productos_conteo.get(p_name, 0.0) + float(cant or 1.0)

            historial_compras.append({
                "id": v_id,
                "fecha": fecha,
                "producto": p_name,
                "cantidad": float(cant or 1.0),
                "total": v_tot,
                "saldo_pendiente": v_saldo,
                "estado_pago": est_pago,
                "metodo_pago": metodo or "NO_ESPECIFICADO",
                "observacion": obs or ""
            })

        ops = len(historial_compras)
        ticket_promedio = round(total_compras / ops, 2) if ops > 0 else 0.0
        prod_preferido = max(productos_conteo.items(), key=lambda x: x[1])[0] if productos_conteo else "N/A"

        # 2. Historial de Abonos
        sql_a = """
            SELECT a.id, a.fecha, a.monto, a.metodo_pago, a.observacion, v.id as venta_id
            FROM abonos_cartera a
            JOIN ventas v ON a.venta_id = v.id
            WHERE LOWER(v.cliente_nombre) = LOWER(?) AND a.negocio_id = ?
            ORDER BY a.fecha DESC
        """
        filas_a = ejecutar_query(sql_a, (nom, negocio_id), fetch=True) or []
        historial_abonos = [{
            "id": r[0], "fecha": r[1], "monto": float(r[2] or 0), "metodo_pago": r[3] or "Efectivo", "observacion": r[4] or "", "venta_id": r[5]
        } for r in filas_a]

        return True, "Ficha 360° recuperada", {
            "cliente": {
                "id": cid, "nombre": nom, "tipo": tipo, "documento": doc or "",
                "telefono": tel or "", "whatsapp": ws or tel or "", "email": em or "",
                "direccion": dir_c or "", "limite_credito": float(lim or 0.0),
                "dias_credito": int(dias or 15), "estado": est or "ACTIVO"
            },
            "kpis": {
                "total_compras": total_compras,
                "operaciones": ops,
                "ticket_promedio": ticket_promedio,
                "saldo_pendiente": saldo_pendiente,
                "credito_disponible": max(0.0, float(lim or 0.0) - saldo_pendiente),
                "producto_preferido": prod_preferido,
                "ultima_compra": historial_compras[0]["fecha"] if historial_compras else "Sin compras"
            },
            "historial_compras": historial_compras[:50],
            "historial_abonos": historial_abonos[:50]
        }
    except Exception as e:
        print(f"Error ficha cliente 360: {e}")
        return False, f"Error al cargar ficha de cliente: {str(e)}", None
