import sys
import os
import json

sys.path.insert(0, '.')

from database import conectar, crear_tablas, ejecutar_query
import services.importador_inteligente_service as importador_service

def test_stream_sse():
    print("=== PRUEBA DE GENERADOR SSE STREAMING DE PROGRESO DE IMPORTACIÓN ===")
    crear_tablas()
    nid = 7777
    uid = 101

    # Cleanup
    ejecutar_query("DELETE FROM productos WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM ventas WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM clientes WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM importaciones_staging WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM auditoria_importaciones WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM producto_atributos WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM lotes_inventario WHERE negocio_id=?", (nid,))

    headers = [
        "Equipo", "Jugador", "Tipo", "Talla", "Fecha", "Cantidad de unidades", 
        "Costo unitario (COP)", "Precio de venta", "Cliente"
    ]
    row1 = ["Italia", "Totti", "Retro", "XL", "2026-05-10", "2", "58833.67", "85000", "Juan Perez"]
    matriz = [headers, row1]

    # Staging
    ok_stg, msg_stg, info_stg = importador_service.crear_lote_staging(nid, "CasoStream.xlsx", matriz)
    assert ok_stg, f"Falló Staging: {msg_stg}"
    batch_id = info_stg["batch_id"]

    mapeo = {
        "Equipo": "nombre_producto",
        "Jugador": "atributo",
        "Tipo": "categoria",
        "Talla": "variante",
        "Fecha": "fecha_operacion",
        "Cantidad de unidades": "cantidad",
        "Costo unitario (COP)": "costo_unitario_local",
        "Precio de venta": "precio_venta",
        "Cliente": "cliente_nombre"
    }

    # Probar el generador SSE directamente
    generator = importador_service.procesar_importacion_aprobada_stream(batch_id, nid, uid, mapeo)
    
    events_received = []
    for line in generator:
        line_str = line.strip()
        if line_str.startswith("data: "):
            json_payload = line_str.replace("data: ", "")
            evt = json.loads(json_payload)
            events_received.append(evt)
            det_clean = evt['detail'].encode('ascii', errors='ignore').decode('ascii')
            print(f"   [{evt['stage']}] {evt['title']} -> Status: {evt['status']} | Detail: {det_clean}")

    assert len(events_received) >= 8, f"Se esperaban al menos 8 eventos SSE, se recibieron {len(events_received)}"
    last_evt = events_received[-1]
    assert last_evt['stage'] == 'COMPLETADO', f"El último evento debía ser COMPLETADO, fue {last_evt['stage']}"
    assert 'undo_token' in last_evt['result'], "El resultado final debe contener undo_token"

    print(f"-> STREAMING SSE EXITOSO. Undo Token: {last_evt['result']['undo_token']}")

    # Cleanup final
    ejecutar_query("DELETE FROM productos WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM ventas WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM clientes WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM importaciones_staging WHERE negocio_id=?", (nid,))
    ejecutar_query("DELETE FROM auditoria_importaciones WHERE negocio_id=?", (nid,))

    print("=== ÉXITO COMPLETO: GENERADOR DE STREAMING SSE FUNCIONA PERFECTAMENTE ===")

if __name__ == '__main__':
    test_stream_sse()
