from database import ejecutar_query
from datetime import datetime

def registrar_abono(venta_id, monto, metodo_pago, usuario_id, negocio_id, observacion="", fecha_custom=None):
    try:
        monto = float(monto)
        if monto <= 0:
            return False, "El monto del abono debe ser mayor a cero."

        # 1. Verificar venta origen
        res_v = ejecutar_query(
            "SELECT total, saldo_pendiente, estado_pago, cliente_nombre FROM ventas WHERE id=? AND negocio_id=?",
            (venta_id, negocio_id), fetch=True
        )
        if not res_v:
            return False, "Venta no encontrada."

        total_venta, saldo_actual, estado_actual, cliente = res_v[0]
        if saldo_actual is None:
            saldo_actual = total_venta

        if saldo_actual <= 0:
            return False, "Esta venta ya se encuentra totalmente saldada."

        if monto > saldo_actual + 0.01:
            return False, f"El abono (${monto:,.0f}) no puede superar el saldo pendiente (${saldo_actual:,.0f})."

        # 2. Fecha del abono
        if fecha_custom and str(fecha_custom).strip():
            fecha_abono = str(fecha_custom).strip()
            if len(fecha_abono) == 10:
                fecha_abono = f"{fecha_abono} 12:00:00"
        else:
            fecha_abono = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 3. Registrar el abono
        ejecutar_query(
            """INSERT INTO abonos_cartera (negocio_id, venta_id, fecha, monto, metodo_pago, usuario_id, observacion)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (negocio_id, venta_id, fecha_abono, monto, metodo_pago, usuario_id, observacion)
        )

        # 4. Actualizar saldo y estado de la venta
        nuevo_saldo = max(0.0, saldo_actual - monto)
        nuevo_estado = "PAGADO" if nuevo_saldo <= 0.01 else "PARCIAL"

        ejecutar_query(
            "UPDATE ventas SET saldo_pendiente=?, estado_pago=? WHERE id=? AND negocio_id=?",
            (nuevo_saldo, nuevo_estado, venta_id, negocio_id)
        )

        return True, {"saldo_anterior": saldo_actual, "nuevo_saldo": nuevo_saldo, "estado": nuevo_estado}
    except Exception as e:
        return False, f"Error al registrar abono: {str(e)}"

def obtener_resumen_cartera(negocio_id, mes_filtro=None):
    try:
        hoy_str = datetime.now().strftime("%Y-%m-%d")
        mes_actual = mes_filtro if mes_filtro else datetime.now().strftime("%Y-%m")

        # 1. Cuentas a crédito / Cartera total
        ventas_credito = ejecutar_query(
            """SELECT v.id, v.total, v.saldo_pendiente, v.fecha, v.fecha_limite_pago, v.cliente_nombre, v.estado_pago
               FROM ventas v
               WHERE v.negocio_id=? AND (v.metodo_pago='CRÉDITO' OR v.saldo_pendiente > 0 OR v.estado_pago IN ('PENDIENTE', 'PARCIAL'))""",
            (negocio_id,), fetch=True
        ) or []

        cartera_total = 0.0
        cartera_vencida = 0.0
        cartera_por_vencer = 0.0
        total_dias = 0
        conteo_cuentas = 0

        # Rango de edades de cartera
        edad_0_30 = 0.0
        edad_31_60 = 0.0
        edad_61_90 = 0.0
        edad_90_mas = 0.0

        for v_id, total, saldo, fecha, vence, cliente, estado in ventas_credito:
            saldo_p = saldo if saldo is not None else (total if estado in ('PENDIENTE', 'PARCIAL') else 0.0)
            if saldo_p <= 0.01:
                continue

            cartera_total += saldo_p
            conteo_cuentas += 1

            # Días de antigüedad desde la venta
            try:
                f_venta = datetime.strptime(fecha[:10], "%Y-%m-%d")
                dias_antiguedad = (datetime.now() - f_venta).days
            except:
                dias_antiguedad = 0

            total_dias += max(0, dias_antiguedad)

            # Clasificación por vencimiento
            if vence and vence < hoy_str:
                cartera_vencida += saldo_p
            else:
                cartera_por_vencer += saldo_p

            # Clasificación por edad de cartera
            if dias_antiguedad <= 30:
                edad_0_30 += saldo_p
            elif dias_antiguedad <= 60:
                edad_31_60 += saldo_p
            elif dias_antiguedad <= 90:
                edad_61_90 += saldo_p
            else:
                edad_90_mas += saldo_p

        dias_promedio = round(total_dias / conteo_cuentas) if conteo_cuentas > 0 else 0

        # 2. Recaudo del mes (Abonos recibidos en el mes + Ventas al contado del mes)
        abonos_mes = ejecutar_query(
            "SELECT SUM(monto) FROM abonos_cartera WHERE negocio_id=? AND fecha LIKE ?",
            (negocio_id, f"{mes_actual}%"), fetch=True
        )
        total_abonos_mes = abonos_mes[0][0] or 0.0 if abonos_mes else 0.0

        ventas_contado_mes = ejecutar_query(
            "SELECT SUM(total) FROM ventas WHERE negocio_id=? AND metodo_pago != 'CRÉDITO' AND (estado_pago='PAGADO' OR estado_pago IS NULL) AND fecha LIKE ?",
            (negocio_id, f"{mes_actual}%"), fetch=True
        )
        total_contado_mes = ventas_contado_mes[0][0] or 0.0 if ventas_contado_mes else 0.0

        recaudo_mes = total_abonos_mes + total_contado_mes

        # 3. Top Clientes Deudores
        top_deudores_res = ejecutar_query(
            """SELECT cliente_nombre, SUM(saldo_pendiente) as saldo, COUNT(*) as facturas
               FROM ventas
               WHERE negocio_id=? AND saldo_pendiente > 0.01 AND cliente_nombre IS NOT NULL AND cliente_nombre != ''
               GROUP BY cliente_nombre ORDER BY saldo DESC LIMIT 5""",
            (negocio_id,), fetch=True
        ) or []

        top_deudores = [{"cliente": x[0], "saldo": x[1], "facturas": x[2]} for x in top_deudores_res]

        return {
            "cartera_total": cartera_total,
            "cartera_vencida": cartera_vencida,
            "cartera_por_vencer": cartera_por_vencer,
            "recaudo_mes": recaudo_mes,
            "dias_promedio": dias_promedio,
            "cuentas_activas": conteo_cuentas,
            "edad_cartera": {
                "dias_0_30": edad_0_30,
                "dias_31_60": edad_31_60,
                "dias_61_90": edad_61_90,
                "dias_90_mas": edad_90_mas
            },
            "top_deudores": top_deudores
        }
    except Exception as e:
        print(f"Error resumen cartera: {e}")
        return {
            "cartera_total": 0.0, "cartera_vencida": 0.0, "cartera_por_vencer": 0.0,
            "recaudo_mes": 0.0, "dias_promedio": 0, "cuentas_activas": 0,
            "edad_cartera": {"dias_0_30": 0, "dias_31_60": 0, "dias_61_90": 0, "dias_90_mas": 0},
            "top_deudores": []
        }

def obtener_cuentas_por_cobrar(negocio_id, cliente_filtro=None, estado_filtro=None):
    try:
        query = """
            SELECT v.id, v.fecha, p.nombre as producto_nombre, v.total, v.saldo_pendiente, 
                   v.estado_pago, v.cliente_nombre, v.fecha_limite_pago, v.observacion
            FROM ventas v
            LEFT JOIN productos p ON v.producto_id = p.id
            WHERE v.negocio_id=? AND (v.metodo_pago='CRÉDITO' OR v.saldo_pendiente > 0 OR v.estado_pago IN ('PENDIENTE', 'PARCIAL'))
        """
        params = [negocio_id]

        if cliente_filtro:
            query += " AND LOWER(v.cliente_nombre) LIKE LOWER(?)"
            params.append(f"%{cliente_filtro}%")

        if estado_filtro:
            query += " AND v.estado_pago = ?"
            params.append(estado_filtro)

        query += " ORDER BY v.fecha DESC"

        res = ejecutar_query(query, params, fetch=True) or []
        hoy_str = datetime.now().strftime("%Y-%m-%d")

        out = []
        for x in res:
            v_id, fecha, prod_nombre, total, saldo, estado, cliente, vence, obs = x
            saldo_p = saldo if saldo is not None else total
            abonado = total - saldo_p

            es_vencido = bool(vence and vence < hoy_str and saldo_p > 0.01)

            out.append({
                "id": v_id,
                "fecha": fecha,
                "producto": prod_nombre or "Producto",
                "total": total,
                "abonado": max(0.0, abonado),
                "saldo": max(0.0, saldo_p),
                "estado": estado or "PENDIENTE",
                "cliente": cliente or "Cliente General",
                "vencimiento": vence or "Sin fecha",
                "es_vencido": es_vencido,
                "observacion": obs or ""
            })
        return out
    except Exception as e:
        print(f"Error cuentas por cobrar: {e}")
        return []

def obtener_historial_abonos(venta_id, negocio_id):
    try:
        res = ejecutar_query(
            """SELECT a.id, a.fecha, a.monto, a.metodo_pago, u.username, a.observacion
               FROM abonos_cartera a
               LEFT JOIN usuarios u ON a.usuario_id = u.id
               WHERE a.venta_id=? AND a.negocio_id=?
               ORDER BY a.fecha DESC""",
            (venta_id, negocio_id), fetch=True
        ) or []

        return [{
            "id": x[0],
            "fecha": x[1],
            "monto": x[2],
            "metodo_pago": x[3] or "Efectivo",
            "usuario": x[4] or "Sistema",
            "observacion": x[5] or ""
        } for x in res]
    except Exception as e:
        print(f"Error historial abonos: {e}")
        return []
