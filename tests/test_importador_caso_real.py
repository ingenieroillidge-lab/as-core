import sys
import os
sys.path.insert(0, '.')

from database import conectar, crear_tablas, ejecutar_query
import services.importador_inteligente_service as importador_service
import services.costos_variables_service as costos_variables_service
import services.analisis_service as analisis_service

def test_caso_real_empresario():
    print("=== INICIANDO PRUEBA MÍNIMA OBLIGATORIA CON CASO REAL DE EMPRESARIO Y ANÁLISIS ===")
    crear_tablas()
    nid = 8888
    uid = 101

    # Cleanup
    ejecutar_query("DELETE FROM productos WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM ventas WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM clientes WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM importaciones_staging WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM auditoria_importaciones WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM costos_variables WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM producto_atributos WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM mapeos_importacion WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM lotes_inventario WHERE negocio_id=?", (nid,))

    headers = [
        "Equipo", "Jugador", "Tipo", "Talla", "Fecha", "Cantidad de unidades", 
        "US", "Precio US", "Costo unitario (COP)", "Costo de envio", "Costo total", 
        "Utilidad", "Precio de venta", "Deudas por cobrar", "Pagos/abonos", "Cliente"
    ]
    row1 = [
        "Italia", "Totti", "Retro", "XL", "2026-05-10", "2", 
        "3.757", "15", "56355", "2478.67", "58833.67", 
        "26166.33", "85000", "0", "85000", "Juan Perez"
    ]
    row_discrepante = [
        "Barcelona", "Ronaldinho", "Retro", "L", "2026-05-10", "1", 
        "3.757", "15", "60000", "2500", "62500", 
        "22500", "85000", "85000", "0", "Carlos Gomez"
    ]

    matriz = [headers, row1, row_discrepante]

    # STAGE 1: Carga y Staging
    ok_stage1, msg1, info1 = importador_service.crear_lote_staging(nid, "CasoReal_Camisetas.xlsx", matriz)
    assert ok_stage1, f"Falló Stage 1: {msg1}"
    batch_id = info1["batch_id"]
    muestras = info1["muestras"]
    print(f"-> STAGE 1 OK: Batch creado {batch_id} con {info1['total_registros']} filas.")

    # STAGE 2: Propuesta Heurística Contextual (con inspección de muestras)
    propuesta = importador_service.proponer_mapeo_heuristico(headers, nid, muestras=muestras)
    map_dict = { p['columna_excel']: p['campo_propuesto'] for p in propuesta }
    
    print("-> Propuesta de Mapeo Heurístico Contextual:")
    for p in propuesta:
        mot_str = f" | Motivo: {p['motivos'][0]}" if p.get('motivos') else ""
        print(f"   [{p['columna_excel']}] -> [{p['campo_propuesto']}] (Confianza: {p['confianza']})".encode('ascii', errors='ignore').decode('ascii'))


    # Verificar contextual de "Equipo"
    assert map_dict["Equipo"] == "nombre_producto", f"REGLA CONTEXTUAL: Equipo debe ser nombre_producto, dio {map_dict['Equipo']}"
    equipo_prop = next(p for p in propuesta if p['columna_excel'] == 'Equipo')
    assert equipo_prop['confianza'] == "MEDIA", "REGLA: Confianza de Equipo debe ser MEDIA (🟡 Revisar)"
    print("   [OK] Equipo clasificado contextual como nombre_producto (Revisar MEDIA)")


    assert map_dict["US"] == "costo_unitario_origen", f"REGLA: US debe ser costo_unitario_origen, dio {map_dict['US']}"
    assert map_dict["Precio US"] == "tasa_cambio", f"REGLA: Precio US debe ser tasa_cambio, dio {map_dict['Precio US']}"
    assert map_dict["Jugador"] == "atributo", f"REGLA: Jugador debe ser atributo"
    assert map_dict["Talla"] == "variante", f"REGLA: Talla debe ser variante"

    # STAGE 3: Prevalidación Batch
    ok_prev, msg_prev, resumen = importador_service.conciliar_y_prevalidar(batch_id, nid, map_dict)
    assert ok_prev, f"Falló Prevalidación: {msg_prev}"
    print(f"-> STAGE 3 OK: Prevalidación terminada en {resumen.get('tiempo_ms', '?')}ms: Válidos={resumen['validos']}, Advertencias={resumen['advertencias']}")

    # STAGE 4: Procesamiento Aprobado
    ok_proc, msg_proc, data_proc = importador_service.procesar_importacion_aprobada(batch_id, nid, uid, map_dict)
    assert ok_proc, f"Falló Procesamiento: {msg_proc}"
    undo_token = data_proc["undo_token"]
    print(f"-> STAGE 4 OK: Procesamiento exitoso. Token de reversión: {undo_token}")

    # Verificar que los atributos se persisten manteniendo el nombre original de la columna
    attrs = ejecutar_query("SELECT nombre_atributo, valor_atributo, tipo FROM producto_atributos WHERE negocio_id=?", (nid,), fetch=True)
    assert len(attrs) >= 4, f"Se esperaban múltiples atributos, se obtuvieron {len(attrs)}"
    print(f"   [OK] Múltiples atributos persistidos en producto_atributos: {[(a[0], a[1], a[2]) for a in attrs]}")

    # STAGE 5: Centro de Análisis Empresarial y Contexto de Filtros
    # A. Consulta sin filtros (Todo el universo)
    res_analisis_todo = analisis_service.obtener_centro_analisis_completo(nid, {})
    assert res_analisis_todo["ok"], "Falló consulta de Centro de Análisis"
    k_todo = res_analisis_todo["kpis"]
    assert k_todo["ventas_count"] == 2, f"Se esperaban 2 ventas en el universo total, se obtuvieron {k_todo['ventas_count']}"
    print(f"-> STAGE 5A OK: Universo total consultado: {res_analisis_todo['alcance']['texto']}")
    print(f"   [KPIs] Ingresos=${k_todo['ingresos']:,.0f} | Costos=${k_todo['costos']:,.0f} | Utilidad=${k_todo['utilidad']:,.0f} | Margen={k_todo['margen_pct']}%")

    # Coherencia matemática: Utilidad = Ingresos - Costos
    assert abs(k_todo["utilidad"] - (k_todo["ingresos"] - k_todo["costos"])) < 0.01, "Error de coherencia matemática en KPIs"

    # B. Consulta con filtro (Cliente: Juan Perez)
    res_analisis_juan = analisis_service.obtener_centro_analisis_completo(nid, {"cliente_nombre": "Juan Perez"})
    k_juan = res_analisis_juan["kpis"]
    assert k_juan["ventas_count"] == 1, f"Se esperaba 1 venta filtrada por Juan Perez, dio {k_juan['ventas_count']}"
    print(f"-> STAGE 5B OK: Filtro por cliente 'Juan Perez' aplicado correctamente: Ingresos=${k_juan['ingresos']:,.0f}")

    # STAGE 6: Reversión
    ok_und, msg_und, _data_und = importador_service.revertir_importacion(undo_token, nid, uid)
    assert ok_und, f"Falló Reversión: {msg_und}"
    print(f"-> STAGE 6 OK: Reversión asistida completada.")

    # Cleanup final
    ejecutar_query("DELETE FROM productos WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM ventas WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM clientes WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM importaciones_staging WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM auditoria_importaciones WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM costos_variables WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM producto_atributos WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM mapeos_importacion WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM lotes_inventario WHERE negocio_id=?", (nid,))

    print("=== SUCCESS: TODAS LAS PRUEBAS OBLIGATORIAS PASARON CON ÉXITO ===")

if __name__ == '__main__':
    test_caso_real_empresario()
