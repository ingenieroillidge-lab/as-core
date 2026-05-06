import sqlite3
import os

try:
    import psycopg2
    POSTGRES_AVAILABLE = True
except Exception:
    POSTGRES_AVAILABLE = False

def conectar():
    db_url = os.environ.get("DATABASE_URL")
    
    # Solo intentamos conectar a Postgres si hay URL y la librería está instalada
    if db_url and POSTGRES_AVAILABLE:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(db_url)
    
    # Por defecto usamos SQLite para desarrollo local
    return sqlite3.connect("sistema.db")

def crear_tablas():
    conn = conectar(); cursor = conn.cursor()
    db_url = os.environ.get("DATABASE_URL")
    
    # Determinamos el tipo de ID según la base de datos
    id_t = "SERIAL PRIMARY KEY" if (db_url and POSTGRES_AVAILABLE) else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    cursor.execute(f"CREATE TABLE IF NOT EXISTS configuracion_negocio (id {id_t}, nombre_negocio TEXT, tipo_operacion TEXT, moneda TEXT DEFAULT 'COP', sheet_url_insumos TEXT, sheet_url_ventas TEXT, color_primario TEXT DEFAULT '#1e293b', color_acento TEXT DEFAULT '#38bdf8')")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS usuarios (id {id_t}, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT DEFAULT 'OPERADOR')")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS productos (id {id_t}, codigo TEXT, nombre TEXT NOT NULL, precio REAL NOT NULL, tipo_producto TEXT DEFAULT 'TRANSFORMADO')")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS inventario (id {id_t}, codigo TEXT, nombre TEXT NOT NULL, unidad_base TEXT, stock_actual REAL DEFAULT 0, stock_minimo REAL DEFAULT 5, costo_unitario_base REAL DEFAULT 0, costo_presentacion REAL DEFAULT 0, cantidad_presentacion REAL DEFAULT 1)")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS ventas (id {id_t}, fecha TEXT, producto_id INTEGER, cantidad REAL, total REAL, metodo_pago TEXT, costo_historico_total REAL, precio_historico_unitario REAL, usuario_id INTEGER)")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS movimientos_inventario (id {id_t}, fecha TEXT, insumo_id INTEGER, tipo TEXT, cantidad REAL, referencia TEXT, usuario_id INTEGER)")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS producto_insumo (id {id_t}, producto_id INTEGER, insumo_id INTEGER, cantidad_usada REAL)")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS costos_fijos (id {id_t}, concepto TEXT, valor REAL, mes TEXT)")

    # Admin por defecto
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO usuarios (username, password, role) VALUES (?, ?, ?)", ("admin", "admin123", "ADMIN"))

    conn.commit(); conn.close()

def ejecutar_query(query, params=(), fetch=False):
    db_url = os.environ.get("DATABASE_URL")
    # Si estamos en modo Postgres, cambiamos los placeholders
    if db_url and POSTGRES_AVAILABLE:
        query = query.replace("?", "%s")
    
    conn = conectar(); cursor = conn.cursor()
    cursor.execute(query, params)
    data = None
    if fetch: data = cursor.fetchall()
    conn.commit(); conn.close()
    return data