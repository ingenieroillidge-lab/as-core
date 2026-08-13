import sqlite3
import os
from datetime import datetime, timedelta

try:
    import psycopg2
    POSTGRES_AVAILABLE = True
except Exception:
    POSTGRES_AVAILABLE = False

def conectar():
    db_url = os.environ.get("DATABASE_URL")
    if db_url and POSTGRES_AVAILABLE:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(db_url)
    return sqlite3.connect("sistema.db")

def crear_tablas():
    conn = conectar(); cursor = conn.cursor()
    db_url = os.environ.get("DATABASE_URL")
    IS_PG = (db_url and POSTGRES_AVAILABLE)
    id_t = "SERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    # 1. CREACIÓN DE TABLAS (UNA POR UNA CON COMMIT)
    tablas_sql = [
        f"CREATE TABLE IF NOT EXISTS negocios (id {id_t}, nombre TEXT NOT NULL, status TEXT DEFAULT 'ACTIVO', plan TEXT DEFAULT 'FREE', fecha_registro TEXT, fecha_vencimiento TEXT, trial_activo INTEGER DEFAULT 1, wompi_secret TEXT, intentos_pro_bloqueados INTEGER DEFAULT 0)",
        f"CREATE TABLE IF NOT EXISTS pagos (id {id_t}, negocio_id INTEGER, referencia_wompi TEXT UNIQUE, transaction_id_wompi TEXT UNIQUE, monto REAL, estado TEXT, fecha TEXT)",
        f"CREATE TABLE IF NOT EXISTS usuarios (id {id_t}, negocio_id INTEGER, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT DEFAULT 'OPERADOR')",
        f"CREATE TABLE IF NOT EXISTS productos (id {id_t}, negocio_id INTEGER, nombre TEXT NOT NULL, precio REAL NOT NULL, codigo TEXT, tipo_producto TEXT DEFAULT 'TRANSFORMADO', categoria TEXT)",
        f"CREATE TABLE IF NOT EXISTS inventario (id {id_t}, negocio_id INTEGER, nombre TEXT NOT NULL, stock_actual REAL DEFAULT 0, codigo TEXT, unidad_base TEXT, stock_inicial REAL DEFAULT 0, stock_minimo REAL DEFAULT 5, costo_unitario_base REAL DEFAULT 0, costo_presentacion REAL DEFAULT 0, cantidad_presentacion REAL DEFAULT 1)",
        f"CREATE TABLE IF NOT EXISTS ventas (id {id_t}, negocio_id INTEGER, fecha TEXT, total REAL, producto_id INTEGER, cantidad REAL, metodo_pago TEXT, costo_historico_total REAL, precio_historico_unitario REAL, usuario_id INTEGER)",
        f"CREATE TABLE IF NOT EXISTS logs_conversion (id {id_t}, negocio_id INTEGER, feature TEXT, fecha TEXT, usuario_id INTEGER)",
        f"CREATE TABLE IF NOT EXISTS costos_fijos (id {id_t}, negocio_id INTEGER, concepto TEXT, valor REAL, mes TEXT)",
        f"CREATE TABLE IF NOT EXISTS producto_insumo (id {id_t}, negocio_id INTEGER, producto_id INTEGER, insumo_id INTEGER, cantidad_usada REAL)",
        f"CREATE TABLE IF NOT EXISTS movimientos_inventario (id {id_t}, negocio_id INTEGER, fecha TEXT, insumo_id INTEGER, tipo TEXT, cantidad REAL, referencia TEXT, usuario_id INTEGER)",
        f"CREATE TABLE IF NOT EXISTS configuracion_negocio (id {id_t}, negocio_id INTEGER, nombre_comercial TEXT, tipo_operacion TEXT DEFAULT 'HÍBRIDO', sheet_url_ventas TEXT, color_acento TEXT DEFAULT '#38bdf8')"
    ]

    for sql in tablas_sql:
        try:
            cursor.execute(sql)
            conn.commit()
        except Exception as e:
            print(f"Error creando tabla: {e}")
            conn.rollback()

    # 2. MIGRACIONES (AÑADIR COLUMNAS FALTANTES)
    def agregar_columna(tabla, columna, tipo):
        try:
            cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
            conn.commit()
        except:
            conn.rollback()

    agregar_columna('negocios', 'intentos_pro_bloqueados', 'INTEGER DEFAULT 0')
    agregar_columna('negocios', 'wompi_secret', 'TEXT')
    agregar_columna('negocios', 'fecha_registro', 'TEXT')
    agregar_columna('negocios', 'fecha_vencimiento', 'TEXT')
    agregar_columna('negocios', 'trial_activo', 'INTEGER DEFAULT 1')
    agregar_columna('negocios', 'status', "TEXT DEFAULT 'ACTIVO'")
    agregar_columna('negocios', 'plan', "TEXT DEFAULT 'FREE'")
    
    # Asegurar que todas las columnas clave estén en inventario y productos
    agregar_columna('inventario', 'codigo', 'TEXT')
    agregar_columna('inventario', 'unidad_base', 'TEXT')
    agregar_columna('inventario', 'costo_unitario_base', 'REAL DEFAULT 0')
    agregar_columna('inventario', 'stock_inicial', 'REAL DEFAULT 0')
    agregar_columna('inventario', 'stock_minimo', 'REAL DEFAULT 5')
    agregar_columna('inventario', 'costo_presentacion', 'REAL DEFAULT 0')
    agregar_columna('inventario', 'cantidad_presentacion', 'REAL DEFAULT 1')
    
    agregar_columna('productos', 'codigo', 'TEXT')
    agregar_columna('productos', 'tipo_producto', 'TEXT DEFAULT \'TRANSFORMADO\'')
    agregar_columna('productos', 'categoria', 'TEXT')
    
    # Columnas de ventas
    agregar_columna('ventas', 'producto_id', 'INTEGER')
    agregar_columna('ventas', 'cantidad', 'REAL')
    agregar_columna('ventas', 'metodo_pago', 'TEXT')
    agregar_columna('ventas', 'costo_historico_total', 'REAL')
    agregar_columna('ventas', 'precio_historico_unitario', 'REAL')
    agregar_columna('ventas', 'usuario_id', 'INTEGER')

    # Columnas de configuracion_negocio
    agregar_columna('configuracion_negocio', 'nombre_comercial', 'TEXT')
    agregar_columna('configuracion_negocio', 'color_acento', 'TEXT DEFAULT \'#38bdf8\'')

    tablas_con_negocio = ['usuarios', 'productos', 'inventario', 'ventas', 'logs_conversion', 'costos_fijos', 'producto_insumo', 'movimientos_inventario', 'configuracion_negocio']
    for t in tablas_con_negocio:
        agregar_columna(t, 'negocio_id', 'INTEGER')

    # 3. DATOS INICIALES
    placeholder = "%s" if IS_PG else "?"
    cursor.execute("SELECT COUNT(*) FROM negocios")
    if cursor.fetchone()[0] == 0:
        hoy = datetime.now()
        vence = (hoy + timedelta(days=7)).strftime("%Y-%m-%d")
        cursor.execute(f"INSERT INTO negocios (nombre, plan, fecha_registro, fecha_vencimiento, trial_activo) VALUES ({placeholder}, 'PRO', {placeholder}, {placeholder}, 1)", 
                       ("Empresa Maestra", hoy.strftime("%Y-%m-%d"), vence))
        conn.commit()
        
        cursor.execute("SELECT id FROM negocios ORDER BY id DESC LIMIT 1")
        nid = cursor.fetchone()[0]
        
        cursor.execute(f"INSERT INTO usuarios (negocio_id, username, password, role) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})", 
                       (nid, "samuel_super", "super2024", "SUPER"))
        conn.commit()
        
        # Crear configuración para la Empresa Maestra
        cursor.execute(f"INSERT INTO configuracion_negocio (negocio_id, nombre_comercial, tipo_operacion, color_acento) VALUES ({placeholder}, 'Empresa Maestra', 'HÍBRIDO', '#38bdf8')", (nid,))
        conn.commit()

    conn.close()

def ejecutar_query(query, params=(), fetch=False):
    db_url = os.environ.get("DATABASE_URL")
    if db_url and POSTGRES_AVAILABLE: query = query.replace("?", "%s")
    conn = conectar(); cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        data = None
        if fetch: data = cursor.fetchall()
        conn.commit()
        return data
    except Exception as e:
        conn.rollback()
        print(f"Error en query: {e}")
        return None
    finally:
        conn.close()