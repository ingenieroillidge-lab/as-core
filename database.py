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
    
    # 0. Negocios con TRIAL FLAG
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS negocios (
        id {id_t}, nombre TEXT NOT NULL, status TEXT DEFAULT 'ACTIVO', 
        plan TEXT DEFAULT 'FREE', fecha_registro TEXT, fecha_vencimiento TEXT,
        trial_activo INTEGER DEFAULT 1,
        wompi_secret TEXT
    )""")

    # 1. LOG DE EVENTOS DE CONVERSIÓN (Para saber qué vender)
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS logs_conversion (
        id {id_t}, negocio_id INTEGER, feature TEXT, fecha TEXT, usuario_id INTEGER
    )""")

    # 2. Pagos con IDEMPOTENCIA (transaction_id único)
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS pagos (
        id {id_t}, negocio_id INTEGER, referencia_wompi TEXT UNIQUE,
        transaction_id_wompi TEXT UNIQUE, -- Evita procesar 2 veces
        monto REAL, estado TEXT, fecha TEXT
    )""")

    # Tablas Operativas...
    cursor.execute(f"CREATE TABLE IF NOT EXISTS usuarios (id {id_t}, negocio_id INTEGER, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT DEFAULT 'OPERADOR')")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS productos (id {id_t}, negocio_id INTEGER, nombre TEXT NOT NULL, precio REAL NOT NULL)")

    # MIGRACIÓN SEGURA
    try: cursor.execute("ALTER TABLE negocios ADD COLUMN trial_activo INTEGER DEFAULT 1")
    except: conn.rollback()
    
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