import sys
sys.path.insert(0, r"c:\Users\samue\Aplicaciones\Proyecto2")
from database import ejecutar_query, init_db

init_db()

# Check all negocio_ids in ventas
negocios = ejecutar_query("SELECT DISTINCT negocio_id FROM ventas", fetch=True)
print(f"Negocios en ventas: {negocios}")

for (nid,) in negocios:
    rows = ejecutar_query("SELECT id, fecha, total, importacion_id, archivo_origen FROM ventas WHERE negocio_id=?", (nid,), fetch=True)
    total_sum = sum(r[2] for r in rows if r[2])
    print(f"\n--- NEGOCIO_ID: {nid} ---")
    print(f"Total filas en ventas: {len(rows)}")
    print(f"Suma total ventas: ${total_sum:,.2f}")
    
    # Group by importacion_id
    imports = {}
    for r in rows:
        imp_id = r[3] or "MANUAL/LEGACY"
        imports[imp_id] = imports.get(imp_id, 0) + r[2]
    
    for imp_id, imp_total in imports.items():
        print(f"  Importación ID '{imp_id}': ${imp_total:,.2f}")

audits = ejecutar_query("SELECT id, negocio_id, undo_token, nombre_archivo, total_registros, fecha, estado FROM auditoria_importaciones", fetch=True)
print(f"\n--- AUDITORIA DE IMPORTACIONES ({len(audits)} registros) ---")
for a in audits:
    print(f"  Audit ID={a[0]}, Negocio={a[1]}, Token={a[2]}, Archivo='{a[3]}', Regs={a[4]}, Fecha={a[5]}, Estado={a[6]}")
