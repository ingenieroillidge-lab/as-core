import sys
sys.path.insert(0, '.')

from database import conectar, ejecutar_query

def check_ventas():
    print("--- CONSULTANDO VENTAS EXISTENTES EN LA BASE DE DATOS LOCAL ---")
    res = ejecutar_query("""
        SELECT v.id, v.negocio_id, v.fecha, p.nombre as producto_nombre, v.cantidad, v.total, v.metodo_pago,
               u.username as usuario_nombre, COALESCE(v.cliente_nombre, '') as cliente_nombre,
               COALESCE(v.observacion, '') as observacion, v.producto_id
        FROM ventas v
        LEFT JOIN productos p ON v.producto_id = p.id
        LEFT JOIN usuarios u ON v.usuario_id = u.id
        ORDER BY v.id DESC LIMIT 10
    """, fetch=True)
    
    print(f"Total ventas encontradas en la consulta: {len(res) if res else 0}")
    if res:
        for row in res:
            print("  Venta:", row)

if __name__ == '__main__':
    check_ventas()
