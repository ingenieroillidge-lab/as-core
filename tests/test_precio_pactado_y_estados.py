"""Punto 2: precio de lista vs precio pactado (descuento), y estados con errores de digitación (caso Hincha, sintético)."""
import os, sys, tempfile
_tmp = tempfile.mkdtemp(); _repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _repo); os.chdir(_tmp)
from database import init_db, ejecutar_query
import services.importador_inteligente_service as svc

init_db()
NEG = 7001
HEAD = ["Lote", "Equipo", "Talla", "Fecha de pedido", "Costo total (COP)", "Precio de lista (COP)",
        "Cobrado (COP)", "Por cobrar (COP)", "Cliente", "Estado (original)"]
FILAS = [HEAD,
         ["L-001", "Real Madrid", "L",  "12/09/2025", "60000", "80000", "70000", "0",     "Ana",    "Vendidada"],   # descuento 10.000
         ["L-001", "Boca",        "XL", "12/09/2025", "55000", "85000", "85000", "0",     "Beto",   "Vendidada"],
         ["L-001", "River",       "L",  "12/09/2025", "55000", "70000", "80000", "0",     "Carla",  "Vendidada"],   # sobreprecio 10.000
         ["L-002", "Milan",       "M",  "20/09/2025", "58000", "80000", "0",     "80000", "Dani",   "Debe"],        # pendiente
         ["L-002", "Inter",       "L",  "20/09/2025", "58000", "90000", "40000", "40000", "Eva",    "Debe"],        # parcial, descuento 10.000
         ["L-002", "Juventus",    "L",  "20/09/2025", "58000", "80000", "0",     "0",     "",       "Stock"],
         ["L-002", "Roma",        "S",  "20/09/2025", "58000", "80000", "0",     "0",     "",       "Pedido por llegar"],
         ["L-002", "Lazio",       "S",  "20/09/2025", "58000", "80000", "0",     "0",     "",       "Perdida"]]
MAPEO = {"Lote": "codigo_lote", "Equipo": "nombre_producto", "Talla": "variante", "Fecha de pedido": "fecha_operacion",
         "Costo total (COP)": "costo_total", "Precio de lista (COP)": "precio_referencia", "Cobrado (COP)": "recaudo_efectivo",
         "Por cobrar (COP)": "cartera_reportada", "Cliente": "cliente_nombre", "Estado (original)": "estado_origen"}


def test_estados_con_errata_y_sinonimos():
    assert svc.interpretar_estado("Vendidada") == ("VENDIDA", "APROXIMADA")      # 208 filas en el Excel real
    assert svc.interpretar_estado("Debe") == ("DEBE", "EXACTA")
    assert svc.interpretar_estado("Fiada") == ("DEBE", "EXACTA")
    assert svc.interpretar_estado("Pérdida") == ("PERDIDA", "EXACTA")            # con acento
    assert svc.interpretar_estado("Pedido por llegar") == ("STOCK", "EXACTA")
    assert svc.interpretar_estado("  vendido  ") == ("VENDIDA", "EXACTA")
    assert svc.interpretar_estado("xyzzy")[1] == "AMBIGUA"
    assert svc.interpretar_estado("") == (None, "VACIA")
    assert svc.normalizar_concepto_estado("Vendidada") == "VENDIDA"


def test_mapeador_no_ignora_precio_de_lista_ni_producto():
    ok, msg, info = svc.crear_lote_staging(NEG, "hincha_sintetico.xlsx", FILAS)
    assert ok, msg
    prop = {p["columna_excel"]: p for p in svc.proponer_mapeo_heuristico(info["headers"], NEG, muestras=info.get("muestras", []))}
    assert prop["Precio de lista (COP)"]["campo_propuesto"] == "precio_referencia"
    assert prop["Equipo"]["campo_propuesto"] == "nombre_producto"


def test_precio_pactado_es_cobrado_mas_saldo_y_descuento_es_diferencia():
    ok, msg, info = svc.crear_lote_staging(NEG, "hincha_sintetico2.xlsx", FILAS)
    assert ok, msg
    contrato = svc.construir_contrato_semantico(MAPEO, {
        "campo_producto": "Equipo", "campo_precio_referencia": "Precio de lista (COP)", "campo_cantidad": None,
        "origen_total_venta": "RECAUDO_MAS_SALDO", "campo_total_venta_operacion": None,
        "campo_recaudo": "Cobrado (COP)", "campo_cartera_reportada": "Por cobrar (COP)"})
    assert "precio pactado" in contrato["formulas"]["total_venta"] and contrato["tiene_conciliacion_doble"] is False
    ok, msg, sim = svc.simular_importacion(info["batch_id"], NEG, MAPEO, contrato_semantico=contrato)
    assert ok, msg
    et4 = sim["matriz_conciliacion"]["etapa4_datos_definitivos"]
    assert abs(et4["ventas_definitivas"] - 395000) < 1, et4     # 70+85+80+80+80 mil (NO el precio de lista: 405 mil)
    assert abs(et4["recaudo_abonos"] - 275000) < 1, et4
    assert abs(et4["cartera_pendiente"] - 120000) < 1, et4      # 80.000 + 40.000


def test_precio_por_cantidad_sigue_funcionando_por_defecto():
    ok, msg, info = svc.crear_lote_staging(NEG, "hincha_sintetico3.xlsx", FILAS)
    contrato = svc.construir_contrato_semantico(MAPEO, {
        "campo_producto": "Equipo", "campo_precio_referencia": "Precio de lista (COP)", "campo_cantidad": None,
        "origen_total_venta": "PRECIO_X_CANTIDAD", "campo_total_venta_operacion": None,
        "campo_recaudo": "Cobrado (COP)", "campo_cartera_reportada": None})
    ok, msg, sim = svc.simular_importacion(info["batch_id"], NEG, MAPEO, contrato_semantico=contrato)
    assert ok, msg
    assert abs(sim["matriz_conciliacion"]["etapa4_datos_definitivos"]["ventas_definitivas"] - 405000) < 1   # lista ×1


if __name__ == '__main__':
    for n, f in list(globals().items()):
        if n.startswith('test_'):
            f(); print('OK', n)
    print('PRECIO PACTADO Y ESTADOS: TODAS LAS PRUEBAS PASARON')
