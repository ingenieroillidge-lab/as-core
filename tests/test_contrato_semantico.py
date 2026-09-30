"""
Test de integración del Contrato Semántico v2.

Caso 1: Excel con columna "Total Venta" independiente (origen COLUMNA)
Caso 2: Excel con precio × cantidad (origen PRECIO_X_CANTIDAD)
Caso 3: Conciliación doble — cartera calculada vs cartera reportada
"""
import sys
sys.path.insert(0, r"c:\Users\samue\Aplicaciones\Proyecto2")

from database import init_db
import services.importador_inteligente_service as svc

print("=" * 70)
print("TEST CONTRATO SEMÁNTICO FINANCIERO v2")
print("=" * 70)

init_db()
NEGOCIO = 9999

# Limpiar datos de prueba anteriores
from database import ejecutar_query
ejecutar_query("DELETE FROM importaciones_staging WHERE negocio_id=?", (NEGOCIO,))

# ─── Datos de prueba (headers + filas) ───────────────────────────────────────
headers = ["Artículo", "Precio Referencia", "Cantidad", "Total Venta", "Pagos", "Deuda"]
filas = [
    headers,
    ["Camiseta Roja",  "30000",  "3", "90000",  "90000",  "0"],       # PAGADO, cartera coincide
    ["Pantalón Azul",  "80000",  "2", "160000", "100000", "60000"],   # PARCIAL, cartera coincide
    ["Zapatos Negros", "120000", "1", "120000", "0",      "120000"],  # PENDIENTE
]

ok, msg, info = svc.crear_lote_staging(NEGOCIO, "test_contrato.xlsx", filas)
assert ok, f"Staging falló: {msg}"
batch_id = info["batch_id"]
print(f"\n[OK] Staging: {info['total_registros']} filas en batch {batch_id}")

mapeo = {
    "Artículo":          "nombre_producto",
    "Precio Referencia": "precio_referencia",
    "Cantidad":          "cantidad",
    "Total Venta":       "total_venta_operacion",
    "Pagos":             "recaudo_efectivo",
    "Deuda":             "cartera_reportada",
}

# ─── Caso 1: origen COLUMNA (Total Venta viene de la columna "Total Venta") ──
print("\n" + "─" * 50)
print("CASO 1: origen_total_venta = COLUMNA")
decisiones_caso1 = {
    "campo_producto":              "Artículo",
    "campo_precio_referencia":     "Precio Referencia",
    "campo_cantidad":              "Cantidad",
    "origen_total_venta":          "COLUMNA",
    "campo_total_venta_operacion": "Total Venta",
    "campo_recaudo":               "Pagos",
    "campo_cartera_reportada":     "Deuda",
}
contrato1 = svc.construir_contrato_semantico(mapeo, decisiones_caso1)
print(f"  Fórmula Total Venta: {contrato1['formulas']['total_venta']}")
print(f"  Fórmula Cartera:     {contrato1['formulas']['cartera_calculada']}")
print(f"  Fórmula Diferencia:  {contrato1['formulas']['diferencia']}")

ok1, m1, sim1 = svc.simular_importacion(batch_id, NEGOCIO, mapeo, contrato_semantico=contrato1)
assert ok1, f"Simulación caso 1 falló: {m1}"
et4 = sim1["matriz_conciliacion"]["etapa4_datos_definitivos"]
et5 = sim1["matriz_conciliacion"]["etapa5_dashboard_conciliacion"]
print(f"  Ventas definitivas:  ${et4['ventas_definitivas']:,.0f}  (esperado: $370.000)")
print(f"  Recaudo:             ${et4['recaudo_abonos']:,.0f}  (esperado: $190.000)")
print(f"  Cartera Calculada:   ${et4['cartera_pendiente']:,.0f}  (esperado: $180.000)")
print(f"  Estado conciliación: {et5['estado']}")
comp = et5["comparativa_cartera"]
print(f"  Cartera AS: ${comp['cartera_calculada_as']:,.0f} | Reportada Excel: ${comp['cartera_reportada_excel']:,.0f} | Coinciden: {comp['coinciden']}")

assert abs(et4["ventas_definitivas"] - 370000) < 1, f"Ventas incorrectas: {et4['ventas_definitivas']}"
assert abs(et4["recaudo_abonos"] - 190000) < 1, f"Recaudo incorrecto: {et4['recaudo_abonos']}"
assert abs(et4["cartera_pendiente"] - 180000) < 1, f"Cartera incorrecta: {et4['cartera_pendiente']}"
print("  [OK] Caso 1 PASADO ✓")

# ─── Caso 2: origen PRECIO_X_CANTIDAD ────────────────────────────────────────
print("\n" + "─" * 50)
print("CASO 2: origen_total_venta = PRECIO_X_CANTIDAD")
decisiones_caso2 = {
    "campo_producto":              "Artículo",
    "campo_precio_referencia":     "Precio Referencia",
    "campo_cantidad":              "Cantidad",
    "origen_total_venta":          "PRECIO_X_CANTIDAD",  # 30.000×3, 80.000×2, 120.000×1
    "campo_total_venta_operacion": None,
    "campo_recaudo":               "Pagos",
    "campo_cartera_reportada":     None,  # Sin conciliación doble
}
contrato2 = svc.construir_contrato_semantico(mapeo, decisiones_caso2)
print(f"  Fórmula Total Venta: {contrato2['formulas']['total_venta']}")
print(f"  Tiene doble conciliación: {contrato2['tiene_conciliacion_doble']}")

ok2, m2, sim2 = svc.simular_importacion(batch_id, NEGOCIO, mapeo, contrato_semantico=contrato2)
assert ok2, f"Simulación caso 2 falló: {m2}"
et4_2 = sim2["matriz_conciliacion"]["etapa4_datos_definitivos"]
print(f"  Ventas definitivas:  ${et4_2['ventas_definitivas']:,.0f}  (esperado: $370.000)")
assert abs(et4_2["ventas_definitivas"] - 370000) < 1, f"Ventas caso 2 incorrectas: {et4_2['ventas_definitivas']}"
print("  [OK] Caso 2 PASADO ✓")

# ─── Caso 3: Migración de mapeo legado ───────────────────────────────────────
print("\n" + "─" * 50)
print("CASO 3: Migración de mapeo legado")
mapeo_legado = {
    "Artículo":          "nombre_producto",
    "Precio Referencia": "precio_venta",     # campo legacy
    "Cantidad":          "cantidad",
    "Total Venta":       "campo_calculado",  # ignorado por legado
    "Pagos":             "abono_monto",      # campo legacy
    "Deuda":             "saldo_pendiente",  # campo legacy
}
migracion = svc.intentar_migrar_mapeo_legado(mapeo_legado, headers)
print(f"  Requiere confirmación: {migracion['requiere_confirmacion']}")
print(f"  Contrato parcial: {list(migracion['contrato_parcial'].keys())}")
print(f"  Ambigüedades: {[a['campo_rol'] for a in migracion['ambiguedades']]}")
assert migracion['requiere_confirmacion'] == True, "Debería requerir confirmación por origen_total_venta"
assert "precio_referencia" in migracion["contrato_parcial"], "precio_referencia debería haberse migrado"
print("  [OK] Caso 3 PASADO ✓")

print("\n" + "=" * 70)
print("TODOS LOS TESTS DEL CONTRATO SEMÁNTICO PASARON SATISFACTORIAMENTE ✓")
print("=" * 70)
