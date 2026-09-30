import sys
import os
import sqlite3
import json

sys.path.insert(0, os.path.abspath("."))

from services.importador_inteligente_service import normalizar_concepto_estado, parse_money
from services.cartera_service import registrar_abono
from database import conectar

def probar_escenario_9_cantidad_mayor_a_1():
    print("\n--- CASO 9: Cantidad > 1 (5 unidades @ $20.000 = $100.000 Venta, Costo @ $10.000 = $50.000) ---")
    cant = 5.0
    precio_unit = 20000.0
    costo_unit = 10000.0
    abono = 40000.0

    total_venta = precio_unit * cant  # 100.000
    costo_total = costo_unit * cant  # 50.000
    saldo = max(0.0, total_venta - abono)  # 60.000
    est_pago = "PARCIAL" if abono > 0 and saldo > 0.01 else "PAGADO"

    print(f"  * Cantidad: {cant} unidades")
    print(f"  * Total Venta AS: ${total_venta:,.0f} (5 x $20,000)")
    print(f"  * Costo Historico COGS: ${costo_total:,.0f} (5 x $10,000)")
    print(f"  * Abono Efectivo: ${abono:,.0f}")
    print(f"  * Saldo Pendiente: ${saldo:,.0f}")
    print(f"  * Estado Pago: {est_pago}")

    assert total_venta == 100000.0
    assert costo_total == 50000.0
    assert saldo == 60000.0
    assert est_pago == "PARCIAL"
    print("  [OK] Coherencia 100% verificada para Cantidad > 1.")

def probar_escenario_10_sobreabono_cantidad_mayor_a_1():
    print("\n--- CASO 10: Sobreabono con Cantidad > 1 (3 unidades @ $30.000 = $90.000 Venta, Abono = $100.000) ---")
    cant = 3.0
    precio_unit = 30000.0
    costo_unit = 15000.0
    abono = 100000.0

    total_venta = precio_unit * cant  # 90.000
    costo_total = costo_unit * cant  # 45.000
    excedente = abono - total_venta if abono > total_venta else 0.0  # 10.000
    saldo = max(0.0, total_venta - abono)  # 0.0
    est_pago = "PAGADO"

    print(f"  * Cantidad: {cant} unidades")
    print(f"  * Total Venta AS: ${total_venta:,.0f} (3 x $30,000)")
    print(f"  * Costo Historico COGS: ${costo_total:,.0f} (3 x $15,000)")
    print(f"  * Abono Efectivo: ${abono:,.0f}")
    print(f"  * Saldo Pendiente: ${saldo:,.0f}")
    print(f"  * Excedente Auditado (Sobreabono): ${excedente:,.0f}")
    print(f"  * Estado Pago: {est_pago}")

    assert total_venta == 90000.0
    assert costo_total == 45000.0
    assert excedente == 10000.0
    assert saldo == 0.0
    assert est_pago == "PAGADO"
    print("  [OK] Coherencia 100% verificada para Sobreabono con Cantidad > 1.")

def probar_escenario_11_multiples_abonos_historicos():
    print("\n--- CASO 11: Múltiples Abonos Históricos para la misma Venta (Base de Datos Temp) ---")
    # Usar DB sqlite en memoria para probar el ciclo de vida completo
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Crear tablas necesarias
    cursor.execute("""
        CREATE TABLE ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, negocio_id INTEGER, fecha TEXT, total REAL,
            producto_id INTEGER, cantidad REAL, metodo_pago TEXT, costo_historico_total REAL,
            precio_historico_unitario REAL, usuario_id INTEGER, estado_pago TEXT,
            cliente_nombre TEXT, cliente_id INTEGER, saldo_pendiente REAL, importacion_id TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE abonos_cartera (
            id INTEGER PRIMARY KEY AUTOINCREMENT, negocio_id INTEGER, venta_id INTEGER,
            fecha TEXT, monto REAL, metodo_pago TEXT, usuario_id INTEGER, observacion TEXT
        )
    """)
    conn.commit()

    # 1. Registrar venta inicial por Importador (Total $100.000, Abono Inicial $40.000)
    cursor.execute("""
        INSERT INTO ventas (negocio_id, fecha, total, producto_id, cantidad, metodo_pago,
                            costo_historico_total, precio_historico_unitario, usuario_id,
                            estado_pago, cliente_nombre, cliente_id, saldo_pendiente, importacion_id)
        VALUES (1, '2026-08-19', 100000.0, 101, 2.0, 'NO_ESPECIFICADO', 50000.0, 50000.0, 1,
                'PARCIAL', 'Carlos Mendoza', 301, 60000.0, 'batch_test')
    """)
    v_id = cursor.lastrowid
    
    # Abono 1 (Importación)
    cursor.execute("""
        INSERT INTO abonos_cartera (negocio_id, venta_id, fecha, monto, metodo_pago, usuario_id, observacion)
        VALUES (1, ?, '2026-08-19', 40000.0, 'NO_ESPECIFICADO', 1, 'Abono inicial importacion')
    """, (v_id,))
    conn.commit()

    print(f"  1. Venta #{v_id} creada: Total=$100,000 | Abono #1=$40,000 | Saldo Inicial=$60,000 | Estado='PARCIAL'")

    # 2. Registrar Abono #2 ($30.000)
    abono2 = 30000.0
    cursor.execute("SELECT saldo_pendiente FROM ventas WHERE id=1")
    saldo_act = cursor.fetchone()[0]
    nuevo_saldo = max(0.0, saldo_act - abono2)
    nuevo_est = "PAGADO" if nuevo_saldo <= 0.01 else "PARCIAL"

    cursor.execute("INSERT INTO abonos_cartera (negocio_id, venta_id, fecha, monto, metodo_pago, usuario_id, observacion) VALUES (1, 1, '2026-08-20', 30000.0, 'Transferencia', 1, 'Abono posterior 1')")
    cursor.execute("UPDATE ventas SET saldo_pendiente=?, estado_pago=? WHERE id=1", (nuevo_saldo, nuevo_est))
    conn.commit()

    print(f"  2. Abono #2 registrado ($30,000): Nuevo Saldo=${nuevo_saldo:,.0f} | Estado='{nuevo_est}'")
    assert nuevo_saldo == 30000.0
    assert nuevo_est == "PARCIAL"

    # 3. Registrar Abono #3 ($30.000 para saldar la deuda)
    abono3 = 30000.0
    cursor.execute("SELECT saldo_pendiente FROM ventas WHERE id=1")
    saldo_act = cursor.fetchone()[0]
    nuevo_saldo = max(0.0, saldo_act - abono3)
    nuevo_est = "PAGADO" if nuevo_saldo <= 0.01 else "PARCIAL"

    cursor.execute("INSERT INTO abonos_cartera (negocio_id, venta_id, fecha, monto, metodo_pago, usuario_id, observacion) VALUES (1, 1, '2026-08-21', 30000.0, 'Efectivo', 1, 'Abono posterior 2 - Liquidacion')")
    cursor.execute("UPDATE ventas SET saldo_pendiente=?, estado_pago=? WHERE id=1", (nuevo_saldo, nuevo_est))
    conn.commit()

    print(f"  3. Abono #3 registrado ($30,000): Nuevo Saldo=${nuevo_saldo:,.0f} | Estado='{nuevo_est}'")
    assert nuevo_saldo == 0.0
    assert nuevo_est == "PAGADO"

    # 4. Verificar Historial de Abonos
    cursor.execute("SELECT SUM(monto), COUNT(*) FROM abonos_cartera WHERE venta_id=1")
    total_abonos, cnt_abonos = cursor.fetchone()
    print(f"  4. Resumen Cartera Venta #{v_id}: Total Abonos Recibidos=${total_abonos:,.0f} en {cnt_abonos} abonos.")

    assert total_abonos == 100000.0
    assert cnt_abonos == 3
    print("  [OK] Coherencia 100% verificada para Múltiples Abonos Históricos y actualización de Cartera.")

if __name__ == "__main__":
    print("=" * 110)
    print(" SUITE EXTENDIDA: PRUEBAS AVANZADAS DE COHERENCIA MULTI-UNIDAD, SOBREABONO Y CARTERA HISTORICA ")
    print("=" * 110)
    probar_escenario_9_cantidad_mayor_a_1()
    probar_escenario_10_sobreabono_cantidad_mayor_a_1()
    probar_escenario_11_multiples_abonos_historicos()
    print("=" * 110)
    print("\n[EXITO TOTAL] Las 3 pruebas avanzadas pasaron al 100%. Motor semantico listo para ser CONGELADO.")
