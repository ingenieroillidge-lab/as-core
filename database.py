import sqlite3
import os

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
    
    # 0. Crear Tabla de Negocios
    cursor.execute(f"CREATE TABLE IF NOT EXISTS negocios (id {id_t}, nombre TEXT NOT NULL, status TEXT DEFAULT 'ACTIVO', fecha_registro TEXT, plan TEXT DEFAULT 'FREE')")

    # 1. Definir tablas base (CREATE TABLE IF NOT EXISTS)
    cursor.execute(f"CREATE TABLE IF NOT EXISTS configuracion_negocio (id {id_t}, negocio_id INTEGER, nombre_comercial TEXT, tipo_operacion TEXT)")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS usuarios (id {id_t}, negocio_id INTEGER, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT DEFAULT 'OPERADOR')")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS productos (id {id_t}, negocio_id INTEGER, codigo TEXT, nombre TEXT NOT NULL, precio REAL NOT NULL)")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS inventario (id {id_t}, negocio_id INTEGER, nombre TEXT NOT NULL, stock_actual REAL DEFAULT 0)")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS ventas (id {id_t}, negocio_id INTEGER, fecha TEXT, total REAL)")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS movimientos_inventario (id {id_t}, negocio_id INTEGER, fecha TEXT, cantidad REAL)")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS costos_fijos (id {id_t}, negocio_id INTEGER, concepto TEXT, valor REAL, mes TEXT)")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS producto_insumo (id {id_t}, negocio_id INTEGER, producto_id INTEGER, insumo_id INTEGER, cantidad_usada REAL)")

    # 2. AUTO-MIGRACIÓN: Asegurar que negocio_id existe en todas las tablas
    tablas_migrar = ['usuarios', 'configuracion_negocio', 'productos', 'inventario', 'ventas', 'movimientos_inventario', 'costos_fijos', 'producto_insumo']
    for tabla in tablas_migrar:
        try:
            # En Postgres usamos una sintaxis especial para ignorar si ya existe
            if IS_PG:
                cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN negocio_id INTEGER")
            else:
                cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN negocio_id INTEGER")
        except Exception:
            conn.rollback() # Ignoramos si la columna ya existe
    
    # 3. DATOS INICIALES
    placeholder = "%s" if IS_PG else "?"
    cursor.execute("SELECT COUNT(*) FROM negocios")
    if cursor.fetchone()[0] == 0:
        q_n = f"INSERT INTO negocios (nombre, status, plan) VALUES ({placeholder}, {placeholder}, {placeholder})"
        cursor.execute(q_n, ("Empresa Maestra", "ACTIVO", "PRO"))
        
        cursor.execute("SELECT id FROM negocios ORDER BY id DESC LIMIT 1")
        nid = cursor.fetchone()[0]
        
        # Super Admin
        cursor.execute("SELECT COUNT(*) FROM usuarios WHERE role='SUPER'")
        if cursor.fetchone()[0] == 0:
            q_u = f"INSERT INTO usuarios (negocio_id, username, password, role) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})"
            cursor.execute(q_u, (nid, "samuel_super", "super2024", "SUPER"))

    conn.commit(); conn.close()

def ejecutar_query(query, params=(), fetch=False):
    db_url = os.environ.get("DATABASE_URL")
    if db_url and POSTGRES_AVAILABLE: query = query.replace("?", "%s")
    conn = conectar(); cursor = conn.cursor()
    cursor.execute(query, params)
    data = None
    if fetch: data = cursor.fetchall()
    conn.commit(); conn.close()
    return data