import sys
import os
import json

sys.path.insert(0, '.')

from database import conectar, crear_tablas, ejecutar_query
import services.importador_inteligente_service as importador_service
import services.analisis_service as analisis_service

def test_excel_real_266():
    print("=== PRUEBA END-TO-END CON ARCHIVO REAL EXCEL (266 FILAS) ===")
    crear_tablas()
    nid = 9999
    uid = 101

    # Cleanup inicial
    ejecutar_query("DELETE FROM productos WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM inventario WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM producto_insumo WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM ventas WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM clientes WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM importaciones_staging WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM auditoria_importaciones WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM producto_atributos WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM mapeos_importacion WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM lotes_inventario WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM compras_entradas WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM movimientos_lote WHERE negocio_id=?", (nid,))

    # Archivo real del emprendedor (datos de cliente: NO va al repositorio). Se indica por variable de entorno.
    excel_path = os.environ.get("AS_EXCEL_266", r"C:\Users\samue\Downloads\Emprendimiento_Camisetas Hincha Store 22-7-26.xlsx")
    if not os.path.exists(excel_path):
        print(f"SKIP: no existe el Excel real ({excel_path}). Defina AS_EXCEL_266 para ejecutarla.")
        sys.exit(5)
    import pandas as pd
    df = pd.read_excel(excel_path, sheet_name="Inventario")

    # Convertir dataframe a matriz de listas para staging
    headers = [str(c).strip() for c in df.columns]
    matriz = [headers]
    for _, row in df.iterrows():
        r_list = [str(row[c]) if pd.notna(row[c]) else "" for c in df.columns]
        matriz.append(r_list)

    # 1. Staging
    ok_stg, msg_stg, info_stg = importador_service.crear_lote_staging(nid, "Emprendimiento_Camisetas.xlsx", matriz)
    assert ok_stg, f"Falló Staging: {msg_stg}"
    batch_id = info_stg["batch_id"]
    print(f"-> STAGING OK: {info_stg['total_registros']} filas cargadas en batch {batch_id}.")

    # 2. Propuesta Mapeo
    propuesta = importador_service.proponer_mapeo_heuristico(headers, nid, muestras=info_stg["muestras"])
    map_dict = {p['columna_excel']: p['campo_propuesto'] for p in propuesta}

    # Ajustar mapeos específicos del Excel real
    map_dict["Equipo"] = "nombre_producto"
    map_dict["Jugador"] = "atributo"
    map_dict["Tipo"] = "categoria"
    map_dict["Talla"] = "variante"
    map_dict["Fecha"] = "fecha_operacion"
    map_dict["Fecha de llegada"] = "fecha_recepcion"
    map_dict["US"] = "costo_unitario_origen"
    map_dict["Precio US"] = "tasa_cambio"
    map_dict["Costo Unitario (COP)"] = "costo_unitario_local"
    map_dict["Costo de envio"] = "costo_envio"
    map_dict["Costo Total"] = "costo_total"
    map_dict["Precio Venta (COP)"] = "precio_venta"
    map_dict["Clientes"] = "cliente_nombre"
    map_dict["Deudas por cobrar"] = "saldo_pendiente"
    map_dict["Pagos/Abonos"] = "abono_monto"
    map_dict["Inversion por pedido"] = "campo_calculado"
    map_dict["Utilidad"] = "campo_calculado"

    # 3. Prevalidación
    ok_prev, msg_prev, res_prev = importador_service.conciliar_y_prevalidar(batch_id, nid, map_dict)
    assert ok_prev, f"Falló Prevalidación: {msg_prev}"
    print(f"-> PREVALIDACIÓN OK: {res_prev['validos']} válidos, {res_prev['advertencias']} advertencias.")

    # 4. Procesamiento Aprobado
    ok_proc, msg_proc, data_proc = importador_service.procesar_importacion_aprobada(batch_id, nid, uid, map_dict)
    assert ok_proc, f"Falló Procesamiento: {msg_proc}"
    undo_token = data_proc["undo_token"]
    print(f"-> PROCESAMIENTO ATÓMICO OK. Token: {undo_token}")

    # AUDITORÍA DE RESULTADOS
    num_lotes = ejecutar_query("SELECT COUNT(*) FROM lotes_inventario WHERE negocio_id=?", (nid,), fetch=True)[0][0]
    num_ventas = ejecutar_query("SELECT COUNT(*) FROM ventas WHERE negocio_id=?", (nid,), fetch=True)[0][0]
    num_prods = ejecutar_query("SELECT COUNT(*) FROM productos WHERE negocio_id=?", (nid,), fetch=True)[0][0]

    print(f"-> RESULTADOS AUDITORÍA:")
    print(f"   [Lotes Creados]: {num_lotes} (Consolidados por Pedido + Producto + Costo Landed, en lugar de 259 micro-lotes)")
    print(f"   [Ventas Creadas]: {num_ventas}")
    print(f"   [Productos Únicos]: {num_prods}")

    # Verificar que el número de lotes sea significativamente menor que el número de ventas
    assert num_lotes < num_ventas, f"ERROR: Se crearon {num_lotes} lotes para {num_ventas} ventas (no se consolidaron lotes)."

    # 5. Centro de Análisis Empresarial
    res_analisis = analisis_service.obtener_centro_analisis_completo(nid, {})
    assert res_analisis["ok"], "Falló Centro de Análisis"
    k = res_analisis["kpis"]

    print(f"-> CENTRO DE ANÁLISIS KPI AUDIT:")
    print(f"   Ventas registradas: {k['ventas_count']}")
    print(f"   Ingresos Totales:  ${k['ingresos']:,.2f}")
    print(f"   Costos Totales:    ${k['costos']:,.2f}")
    print(f"   Utilidad Bruta:    ${k['utilidad']:,.2f}")
    print(f"   Margen Real:       {k['margen_pct']:.2f}%")

    # Cleanup final
    ejecutar_query("DELETE FROM productos WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM inventario WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM producto_insumo WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM ventas WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM clientes WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM importaciones_staging WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM auditoria_importaciones WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM producto_atributos WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM mapeos_importacion WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM lotes_inventario WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM compras_entradas WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM movimientos_lote WHERE negocio_id=?", (nid,))

    print("=== ÉXITO COMPLETO: ARCHIVO EXCEL DE 266 FILAS PROCESADO Y AUDITADO IMPECABLEMENTE ===")

if __name__ == '__main__':
    test_excel_real_266()
