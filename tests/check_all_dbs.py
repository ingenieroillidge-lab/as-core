import sqlite3
import os

for db_name in ["as_platform.db", "sistema.db"]:
    if not os.path.exists(db_name):
        continue
    print(f"=== REVISANDO BASE DE DATOS: {db_name} ===")
    conn = sqlite3.connect(db_name)
    cur = conn.cursor()
    
    # Check tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cur.fetchall()]
    print(f"Tablas ({len(tables)}): {tables}")
    
    if "ventas" in tables:
        cur.execute("SELECT negocio_id, COUNT(*), SUM(total), SUM(saldo_pendiente) FROM ventas GROUP BY negocio_id")
        print(f"Ventas por negocio: {cur.fetchall()}")
        
    if "abonos_cartera" in tables:
        cur.execute("SELECT negocio_id, COUNT(*), SUM(monto) FROM abonos_cartera GROUP BY negocio_id")
        print(f"Abonos por negocio: {cur.fetchall()}")

    if "auditoria_importaciones" in tables:
        cur.execute("SELECT negocio_id, undo_token, nombre_archivo, total_registros, fecha, estado FROM auditoria_importaciones")
        print(f"Auditoría: {cur.fetchall()}")
        
    conn.close()
    print("\n")
