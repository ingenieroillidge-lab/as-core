"""Montos, cantidades y fechas sucios (convención es-CO). Casos tomados de fixtures/03_datos_sucios_edge_cases.xlsx."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.normalizador import analizar_monto, analizar_cantidad, analizar_fecha, parse_money


def test_montos_es_co():
    casos = {
        '$ 45.000': 45000.0, '45000,00': 45000.0, '85.000,50': 85000.5, '$ 255.001,50': 255001.5,
        '$ 18,500': 18500.0, ',500': 0.5, '1.234,50': 1234.5, '1,234.50': 1234.5, '61612.5': 61612.5,
        '18900.0': 18900.0, '18.900': 18900.0, '1.234.567': 1234567.0, 45000: 45000.0, 0.5: 0.5,
    }
    for entrada, esperado in casos.items():
        assert parse_money(entrada) == esperado, (entrada, parse_money(entrada), esperado)


def test_negativos_y_gratis_se_distinguen_de_cero():
    assert analizar_monto('-$ 120.000') == (-120000.0, 'OK')      # devolución: no se pierde el signo
    assert analizar_monto('(120.000)') == (-120000.0, 'OK')
    assert analizar_monto('GRATIS') == (0.0, 'GRATIS')
    assert analizar_monto('') == (0.0, 'VACIO') and analizar_monto(None) == (0.0, 'VACIO')
    assert analizar_monto('NO DISPONIBLE')[1] == 'INVALIDO'        # texto ≠ cero


def test_cantidades():
    assert analizar_cantidad(' 2 ') == (2.0, 'OK')
    assert analizar_cantidad('1.0') == (1.0, 'OK')
    assert analizar_cantidad('dos') == (2.0, 'OK')
    assert analizar_cantidad('-1') == (-1.0, 'OK')
    assert analizar_cantidad('abc')[1] == 'INVALIDO'


def test_fechas_heterogeneas():
    casos = {
        '15/03/2026': '2026-03-15', '2026-03-16': '2026-03-16', '17 de Marzo de 2026': '2026-03-17',
        '2026/03/18 14:32:00': '2026-03-18 14:32:00', '19-03-2026': '2026-03-19', '17-mar-2026': '2026-03-17',
        '03/25/2026': '2026-03-25', '5/5/26': '2026-05-05',
    }
    for entrada, esperado in casos.items():
        assert analizar_fecha(entrada)[0] == esperado, (entrada, analizar_fecha(entrada))
    assert analizar_fecha('NO DISPONIBLE') == ('', 'INVALIDA')
    assert analizar_fecha('2025-02-30') == ('', 'INVALIDA')       # fecha imposible
    assert analizar_fecha('') == ('', 'VACIA')
    assert analizar_fecha('05/03/2026') == ('2026-03-05', 'AMBIGUA')   # se asume día/mes (Colombia) y se avisa


def test_fixture_sucio_total_coincide_con_precio_por_cantidad():
    import openpyxl
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', '03_datos_sucios_edge_cases.xlsx')
    ws = openpyxl.load_workbook(ruta).active
    ok, incoherentes = 0, []
    for fila in ws.iter_rows(min_row=4, values_only=True):
        if not fila[1]:
            continue
        cant, _ = analizar_cantidad(fila[2]); precio, _ = analizar_monto(fila[3]); total, _ = analizar_monto(fila[4])
        if abs(precio * cant - total) < 1:
            ok += 1
        else:
            incoherentes.append(str(fila[1]).strip())
    # Cuadran 7 de 8 (incluye 'dos' unidades, la devolución -1 y la cortesía gratis).
    # Solo 'Gorra' no: precio ',500' vs total '$ 18,500' -> debe quedar como advertencia para el usuario.
    assert ok == 7, ok
    assert incoherentes == ['Gorra Urbana Negra'], incoherentes


if __name__ == '__main__':
    for n, f in list(globals().items()):
        if n.startswith('test_'):
            f(); print('OK', n)
    print('NORMALIZADOR: TODAS LAS PRUEBAS PASARON')
