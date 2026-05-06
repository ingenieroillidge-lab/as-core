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
        f"CREATE TABLE IF NOT EXISTS productos (id {id_t}, negocio_id INTEGER, nombre TEXT NOT NULL, precio REAL NOT NULL)",
        f"CREATE TABLE IF NOT EXISTS inventario (id {id_t}, negocio_id INTEGER, nombre TEXT NOT NULL, stock_actual REAL DEFAULT 0)",
        f"CREATE TABLE IF NOT EXISTS ventas (id {id_t}, negocio_id INTEGER, fecha TEXT, total REAL)",
        f"CREATE TABLE IF NOT EXISTS logs_conversion (id {id_t}, negocio_id INTEGER, feature TEXT, fecha TEXT, usuario_id INTEGER)"
    ]

    for sql in tablas_sql:
        try:
            cursor.execute(sql)
            conn.commit()
        except:
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
    
    tablas_con_negocio = ['usuarios', 'productos', 'inventario', 'ventas', 'logs_conversion']
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