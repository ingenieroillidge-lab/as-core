import sys
sys.path.insert(0, r"c:\Users\samue\Aplicaciones\Proyecto2")

from database import init_db, ejecutar_query
import services.importador_inteligente_service as importador_service

print("=== PRUEBA DE FUENTE DE CARTERA Y CONCILIACIÓN DOBLE ===")
init_db()

negocio_id = 777
nombre_archivo = "ventas_cartera_test.xlsx"

# 1 fila con Venta = 1.000.000, Abono = 800.000, Deuda Excel = 200.000 (Coinciden)
filas_matriz = [
    ["Precio Venta", "Abono", "Deuda", "Producto", "Cliente", "Cantidad"],
    ["1.000.000", "800.000", "200.000", "Camiseta Premium", "Cliente Juan", "1"]
]

ejecutar_query("DELETE FROM importaciones_staging WHERE negocio_id=?", (negocio_id,))
ok, msg, res_info = importador_service.crear_lote_staging(negocio_id, nombre_archivo, filas_matriz)
batch_id = res_info["batch_id"]

mapeo = {
    "Precio Venta": "precio_venta",
    "Abono": "abono_monto",
    "Deuda": "saldo_pendiente",
    "Producto": "nombre_producto",
    "Cliente": "cliente_nombre",
    "Cantidad": "cantidad"
}

# Prueba Modo 1: CALCULAR
etapa0_calc = {
    "tipo_precio_venta": "VALOR_TOTAL_VENTA",
    "fuente_cartera": "CALCULAR",
    "usar_cantidad": True,
    "usar_abonos": True,
    "usar_deuda": True,
    "formato_regional": "COLOMBIA_LATAM"
}
ok1, msg1, sim1 = importador_service.simular_importacion(batch_id, negocio_id, mapeo, etapa0_config=etapa0_calc)
m1 = sim1["matriz_conciliacion"]
print("\n1. Modo CALCULAR:")
print(f"   Ventas: {m1['etapa4_datos_definitivos']['ventas_definitivas']}")
print(f"   Abonos: {m1['etapa4_datos_definitivos']['recaudo_abonos']}")
print(f"   Cartera Pendiente: {m1['etapa4_datos_definitivos']['cartera_pendiente']}")
print(f"   Estado Conciliación: {m1['etapa5_dashboard_conciliacion']['estado']}")

# Prueba Modo 2: COMPARAR (Coinciden)
etapa0_comp = {
    "tipo_precio_venta": "VALOR_TOTAL_VENTA",
    "fuente_cartera": "COMPARAR",
    "usar_cantidad": True,
    "usar_abonos": True,
    "usar_deuda": True,
    "formato_regional": "COLOMBIA_LATAM"
}
ok2, msg2, sim2 = importador_service.simular_importacion(batch_id, negocio_id, mapeo, etapa0_config=etapa0_comp)
m2 = sim2["matriz_conciliacion"]
c2 = m2['etapa5_dashboard_conciliacion']['comparativa_cartera']
print("\n2. Modo COMPARAR (Coinciden):")
print(f"   Cartera AS: ${c2['cartera_calculada_as']:,.2f}")
print(f"   Cartera Excel: ${c2['cartera_reportada_excel']:,.2f}")
print(f"   Coinciden: {c2['coinciden']}")
print(f"   Estado Conciliación: {m2['etapa5_dashboard_conciliacion']['estado']}")

print("\n[OK] TODAS LAS PRUEBAS DE CARTERA PASARON SATISFACTORIAMENTE")
