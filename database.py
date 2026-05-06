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
    id_t = "SERIAL PRIMARY KEY" if (db_url and POSTGRES_AVAILABLE) else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    # ==========================
    # 0. MAESTRO DE EMPRESAS (SaaS)
    # ==========================
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS negocios (
        id {id_t},
        nombre TEXT NOT NULL,
        status TEXT DEFAULT 'ACTIVO', -- 'ACTIVO', 'SUSPENDIDO'
        fecha_registro TEXT,
        plan TEXT DEFAULT 'FREE'
    )
    """)

    # ==========================
    # 1. TABLAS PERTENECIENTES A UN NEGOCIO
    # ==========================
    # Todas las tablas ahora llevan negocio_id
    
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS configuracion_negocio (
        id {id_t},
        negocio_id INTEGER,
        nombre_comercial TEXT,
        tipo_operacion TEXT,
        moneda TEXT DEFAULT 'COP',
        color_acento TEXT DEFAULT '#38bdf8',
        sheet_url_ventas TEXT,
        FOREIGN KEY(negocio_id) REFERENCES negocios(id)
    )
    """)

    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS usuarios (
        id {id_t},
        negocio_id INTEGER,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'OPERADOR', -- 'SUPER', 'ADMIN', 'OPERADOR'
        FOREIGN KEY(negocio_id) REFERENCES negocios(id)
    )
    """)

    cursor.execute(f"CREATE TABLE IF NOT EXISTS productos (id {id_t}, negocio_id INTEGER, codigo TEXT, nombre TEXT NOT NULL, precio REAL NOT NULL, tipo_producto TEXT DEFAULT 'TRANSFORMADO')")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS inventario (id {id_t}, negocio_id INTEGER, codigo TEXT, nombre TEXT NOT NULL, unidad_base TEXT, stock_actual REAL DEFAULT 0, costo_unitario_base REAL DEFAULT 0, cantidad_presentacion REAL DEFAULT 1)")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS ventas (id {id_t}, negocio_id INTEGER, fecha TEXT, producto_id INTEGER, cantidad REAL, total REAL, metodo_pago TEXT, costo_historico_total REAL, precio_historico_unitario REAL, usuario_id INTEGER)")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS movimientos_inventario (id {id_t}, negocio_id INTEGER, fecha TEXT, insumo_id INTEGER, tipo TEXT, cantidad REAL, referencia TEXT, usuario_id INTEGER)")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS costos_fijos (id {id_t}, negocio_id INTEGER, concepto TEXT, valor REAL, mes TEXT)")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS producto_insumo (id {id_t}, negocio_id INTEGER, producto_id INTEGER, insumo_id INTEGER, cantidad_usada REAL)")

    # ==========================
    # MIGRACIÓN Y DATOS INICIALES
    # ==========================
    
    # 1. Crear el primer negocio (El tuyo original) si no existe
    cursor.execute("SELECT COUNT(*) FROM negocios")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO negocios (nombre, status, plan) VALUES (?, ?, ?)", ("Negocio Original", "ACTIVO", "PRO"))
        negocio_id_def = cursor.lastrowid
        
        # 2. Crear Super Admin vinculado al negocio 1
        cursor.execute("SELECT COUNT(*) FROM usuarios WHERE role='SUPER'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO usuarios (negocio_id, username, password, role) VALUES (?, ?, ?, ?)", (negocio_id_def, "samuel_super", "super2024", "SUPER"))

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