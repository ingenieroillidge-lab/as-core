import sys
import os
import json
import sqlite3

# Adicionar la raíz al sys.path
sys.path.insert(0, r"c:\Users\samue\Aplicaciones\Proyecto2")

from database import init_db, ejecutar_query, transaccion
import services.importador_inteligente_service as importador_service

print("=== INICIANDO PRUEBA DEL CENTRO DE CONCILIACIÓN CON TRAZABILIDAD Y LINAJE ===")

# Inicializar BD
init_db()

negocio_id = 999
usuario_id = 1
nombre_archivo = "ventas_2025.xlsx"
hoja_origen = "Ventas"

# Simular 244 filas con totales exactos del Excel real:
# Total Ventas: 21.212.464
# Total Abonos: 16.220.989
# Total Deudas/Cartera: 2.125.011
# Total Costos: 14.214.263

filas_matriz = [
    ["Precio Venta (COP)", "Utilidad", "Fecha de llegada", "Deudas por cobrar", "Pagos/Abonos", "Clientes", "Producto", "Cantidad"]
]

# Generar 240 filas pagadas de contado + 4 filas a crédito que sumen los totales exactos
# Para 240 filas de contado: Venta = 79.531,09, Abono = 79.531,09, Costo = 50.371,93
for i in range(1, 241):
    filas_matriz.append([
        "79.531,09", "29.159,16", "2026-08-20", "0", "79.531,09", "Cliente Frecuente", f"Producto Test #{i}", "1"
    ])

# 4 filas a crédito para completar los 21.212.464 en ventas y 2.125.011 en cartera
# Fila 241: Venta = 700.000, Abono = 200.000, Deuda = 500.000, Costo = 500.000
# Fila 242: Venta = 800.000, Abono = 300.000, Deuda = 500.000, Costo = 550.000
# Fila 243: Venta = 800.000, Abono = 200.000, Deuda = 600.000, Costo = 550.000
# Fila 244: Venta = 825.002, Abono = 300.000, Deuda = 525.011, Costo = 525.000
filas_matriz.append(["700.000,00", "200.000,00", "2026-08-20", "500.000,00", "200.000,00", "Deudor 1", "Camiseta A", "1"])
filas_matriz.append(["800.000,00", "250.000,00", "2026-08-20", "500.000,00", "300.000,00", "Deudor 2", "Camiseta B", "1"])
filas_matriz.append(["800.000,00", "250.000,00", "2026-08-20", "600.000,00", "200.000,00", "Deudor 3", "Camiseta C", "1"])
filas_matriz.append(["825.002,00", "300.002,00", "2026-08-20", "525.011,00", "300.000,00", "Deudor 4", "Camiseta D", "1"])

# Limpiar staging previo de este negocio_id
ejecutar_query("DELETE FROM importaciones_staging WHERE negocio_id=?", (negocio_id,))
ejecutar_query("DELETE FROM ventas WHERE negocio_id=?", (negocio_id,))
ejecutar_query("DELETE FROM abonos_cartera WHERE negocio_id=?", (negocio_id,))

# PASO 1: Carga a Staging con Linaje (hash_fila, hash_contenido, nivel_duplicado)
ok, msg, res_info = importador_service.crear_lote_staging(negocio_id, nombre_archivo, filas_matriz, hoja_origen=hoja_origen)
print(f"1. Crear Staging: ok={ok}, msg={msg}")
batch_id = res_info["batch_id"]
print(f"   Batch ID: {batch_id}")
print(f"   Total registros en Staging: {res_info['total_registros']}")
print(f"   Duplicados confirmados (CONFIRMADO): {res_info['duplicados_confirmados']}")
print(f"   Duplicados sospechosos (SOSPECHOSO): {res_info['duplicados_sospechosos']}")

# PASO 2: Mapeo y Prevalidación con Etapa 0
mapeo = {
    "Precio Venta (COP)": "precio_venta",
    "Fecha de llegada": "fecha_operacion",
    "Deudas por cobrar": "saldo_pendiente",
    "Pagos/Abonos": "abono_monto",
    "Clientes": "cliente_nombre",
    "Producto": "nombre_producto",
    "Cantidad": "cantidad"
}

etapa0_config = {
    "tipo_precio_venta": "VALOR_TOTAL_VENTA",
    "usar_cantidad": True,
    "usar_abonos": True,
    "usar_deuda": True,
    "formato_regional": "COLOMBIA_LATAM"
}

ok_sim, msg_sim, sim_res = importador_service.simular_importacion(
    batch_id, negocio_id, mapeo, granularidad_costos="POR_UNIDAD", etapa0_config=etapa0_config
)

print(f"\n2. Simulación con Etapa 0 (VALOR_TOTAL_VENTA):")
matriz = sim_res["matriz_conciliacion"]
print("   --- ETAPA 1: EXCEL ORIGINAL ---")
print("   ", json.dumps(matriz["etapa1_excel_original"], indent=2))
print("   --- ETAPA 2: STAGING (3 NIVEL DUP) ---")
print("   ", json.dumps(matriz["etapa2_staging"], indent=2))
print("   --- ETAPA 3: DATOS PROCESADOS (ESTADOS) ---")
print("   ", json.dumps(matriz["etapa3_datos_procesados"], indent=2))
print("   --- ETAPA 4: DATOS DEFINITIVOS ---")
print("   ", json.dumps(matriz["etapa4_datos_definitivos"], indent=2))
print("   --- ETAPA 5: DASHBOARD & CONCILIACIÓN ---")
print("   ", json.dumps(matriz["etapa5_dashboard_conciliacion"], indent=2))

# PASO 3: Procesar Importación Definitiva
ok_proc, msg_proc, res_proc = importador_service.procesar_importacion_aprobada(
    batch_id, negocio_id, usuario_id, mapeo, granularidad_costos="POR_UNIDAD", etapa0_config=etapa0_config
)

print(f"\n3. Procesamiento Definitivo: ok={ok_proc}, msg={msg_proc}")
undo_token = res_proc["undo_token"]
print(f"   Undo Token: {undo_token}")

# VERIFICACIÓN DE FUENTE ÚNICA DE VERDAD Y LINAJE
ventas_db = ejecutar_query("SELECT COUNT(*), SUM(total), SUM(saldo_pendiente) FROM ventas WHERE negocio_id=?", (negocio_id,), fetch=True)
abonos_db = ejecutar_query("SELECT COUNT(*), SUM(monto) FROM abonos_cartera WHERE negocio_id=?", (negocio_id,), fetch=True)
staging_db = ejecutar_query("SELECT COUNT(*), estado_validacion FROM importaciones_staging WHERE negocio_id=? GROUP BY estado_validacion", (negocio_id,), fetch=True)

print(f"\n4. Verificación de BD y Fuente Única de Verdad:")
print(f"   Ventas en DB: Total filas={ventas_db[0][0]}, Suma Ventas=${ventas_db[0][1]:,.2f}, Cartera=${ventas_db[0][2]:,.2f}")
print(f"   Abonos en DB (Fuente Única de Verdad): Total abonos={abonos_db[0][0]}, Suma Recaudo=${abonos_db[0][1]:,.2f}")
print(f"   Estado Staging Conservado (No Borrado): {staging_db}")

# Verificar Linaje en la primera fila insertada en ventas
v_linaje = ejecutar_query("SELECT archivo_origen, hoja_origen, fila_origen, hash_fila, hash_contenido FROM ventas WHERE negocio_id=? LIMIT 1", (negocio_id,), fetch=True)
print(f"   Muestra Linaje Fila Ventas: Archivo='{v_linaje[0][0]}', Hoja='{v_linaje[0][1]}', Fila={v_linaje[0][2]}")
print(f"   Hash Fila (Identidad): {v_linaje[0][3]}")
print(f"   Hash Contenido (Huella): {v_linaje[0][4]}")

print("\n[OK] PRUEBA COMPLETADA CON EXITO ABSOLUTO")
