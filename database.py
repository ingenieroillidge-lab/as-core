import os
import sqlite3
import json
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

try:
    import psycopg2
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

def conectar():
    db_url = os.environ.get("DATABASE_URL")
    if db_url and POSTGRES_AVAILABLE:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(db_url)
    return sqlite3.connect("as_platform.db")

def init_db():
    conn = conectar(); cursor = conn.cursor()
    db_url = os.environ.get("DATABASE_URL")
    IS_PG = (db_url and POSTGRES_AVAILABLE)
    id_t = "SERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    # 1. CREACIÓN DE TABLAS (UNA POR UNA CON COMMIT)
    tablas_sql = [
        f"CREATE TABLE IF NOT EXISTS negocios (id {id_t}, nombre TEXT NOT NULL, status TEXT DEFAULT 'ACTIVO', plan TEXT DEFAULT 'FREE', fecha_registro TEXT, fecha_vencimiento TEXT, trial_activo INTEGER DEFAULT 1, wompi_secret TEXT, intentos_pro_bloqueados INTEGER DEFAULT 0, tipo_cuenta TEXT DEFAULT 'CLIENTE', es_interna INTEGER DEFAULT 0, es_datos_prueba INTEGER DEFAULT 0)",
        f"CREATE TABLE IF NOT EXISTS pagos (id {id_t}, negocio_id INTEGER, referencia_wompi TEXT UNIQUE, transaction_id_wompi TEXT UNIQUE, monto REAL, estado TEXT, fecha TEXT)",
        f"CREATE TABLE IF NOT EXISTS usuarios (id {id_t}, negocio_id INTEGER, username TEXT UNIQUE NOT NULL, password TEXT, password_hash TEXT, role TEXT DEFAULT 'OPERADOR', email TEXT, nombre_completo TEXT, estado TEXT DEFAULT 'ACTIVO', fecha_registro TEXT, ultimo_acceso TEXT)",
        f"CREATE TABLE IF NOT EXISTS productos (id {id_t}, negocio_id INTEGER, nombre TEXT NOT NULL, precio REAL NOT NULL, codigo TEXT, tipo_producto TEXT DEFAULT 'TRANSFORMADO', categoria TEXT)",
        f"CREATE TABLE IF NOT EXISTS inventario (id {id_t}, negocio_id INTEGER, nombre TEXT NOT NULL, stock_actual REAL DEFAULT 0, codigo TEXT, unidad_base TEXT, stock_inicial REAL DEFAULT 0, stock_minimo REAL DEFAULT 5, costo_unitario_base REAL DEFAULT 0, costo_presentacion REAL DEFAULT 0, cantidad_presentacion REAL DEFAULT 1)",
        f"CREATE TABLE IF NOT EXISTS ventas (id {id_t}, negocio_id INTEGER, fecha TEXT, total REAL, producto_id INTEGER, cantidad REAL, metodo_pago TEXT, costo_historico_total REAL, precio_historico_unitario REAL, usuario_id INTEGER)",
        f"CREATE TABLE IF NOT EXISTS logs_conversion (id {id_t}, negocio_id INTEGER, feature TEXT, fecha TEXT, usuario_id INTEGER)",
        f"CREATE TABLE IF NOT EXISTS costos_fijos (id {id_t}, negocio_id INTEGER, concepto TEXT, valor REAL, mes TEXT)",
        f"CREATE TABLE IF NOT EXISTS producto_insumo (id {id_t}, negocio_id INTEGER, producto_id INTEGER, insumo_id INTEGER, cantidad_usada REAL)",
        f"CREATE TABLE IF NOT EXISTS movimientos_inventario (id {id_t}, negocio_id INTEGER, fecha TEXT, insumo_id INTEGER, tipo TEXT, cantidad REAL, referencia TEXT, usuario_id INTEGER)",
        f"CREATE TABLE IF NOT EXISTS configuracion_negocio (id {id_t}, negocio_id INTEGER, nombre_comercial TEXT, tipo_operacion TEXT DEFAULT 'HÍBRIDO', sheet_url_ventas TEXT, color_acento TEXT DEFAULT '#38bdf8', maneja_cartera INTEGER DEFAULT 0)",
        f"CREATE TABLE IF NOT EXISTS abonos_cartera (id {id_t}, negocio_id INTEGER, venta_id INTEGER, fecha TEXT, monto REAL, metodo_pago TEXT, usuario_id INTEGER, observacion TEXT)",
        f"CREATE TABLE IF NOT EXISTS tickets_soporte (id {id_t}, negocio_id INTEGER, usuario_id INTEGER, fecha TEXT, modulo TEXT, pregunta TEXT, respuesta_bot TEXT, estado TEXT DEFAULT 'PENDIENTE', respuesta_admin TEXT)",
        f"CREATE TABLE IF NOT EXISTS clientes (id {id_t}, negocio_id INTEGER, nombre TEXT NOT NULL, tipo TEXT DEFAULT 'PERSONA', documento TEXT, telefono TEXT, whatsapp TEXT, email TEXT, direccion TEXT, limite_credito REAL DEFAULT 0, dias_credito_predeterminado INTEGER DEFAULT 15, estado TEXT DEFAULT 'ACTIVO')",
        f"CREATE TABLE IF NOT EXISTS compras_entradas (id {id_t}, negocio_id INTEGER, fecha_compra TEXT NOT NULL, proveedor TEXT, numero_factura TEXT, insumo_id INTEGER NOT NULL, codigo_lote TEXT NOT NULL, cantidad_comprada REAL NOT NULL, costo_unitario_compra REAL NOT NULL, costo_total_compra REAL NOT NULL, fecha_vencimiento TEXT, observaciones TEXT, usuario_id INTEGER)",
        f"CREATE TABLE IF NOT EXISTS lotes_inventario (id {id_t}, negocio_id INTEGER, compra_id INTEGER, insumo_id INTEGER NOT NULL, codigo_lote TEXT NOT NULL, fecha_compra TEXT, fecha_vencimiento TEXT, cantidad_inicial REAL NOT NULL, cantidad_disponible REAL NOT NULL, costo_unitario REAL NOT NULL, proveedor TEXT, numero_factura TEXT, estado TEXT DEFAULT 'ACTIVO')",
        f"CREATE TABLE IF NOT EXISTS movimientos_lote (id {id_t}, negocio_id INTEGER, lote_id INTEGER NOT NULL, fecha TEXT NOT NULL, tipo TEXT NOT NULL, cantidad REAL NOT NULL, costo_unitario_lote REAL NOT NULL, costo_subtotal REAL NOT NULL, referencia TEXT, venta_id INTEGER, usuario_id INTEGER)",
        f"CREATE TABLE IF NOT EXISTS informes_guardados (id {id_t}, negocio_id INTEGER, nombre_informe TEXT NOT NULL, tipo_objeto TEXT NOT NULL, columnas_json TEXT NOT NULL, filtros_json TEXT NOT NULL, agrupacion_json TEXT, fecha_creacion TEXT)",
        f"CREATE TABLE IF NOT EXISTS planes (id {id_t}, codigo TEXT UNIQUE NOT NULL, nombre TEXT NOT NULL, precio_mensual REAL NOT NULL, limite_productos INTEGER, limite_ventas INTEGER, funcionalidades_json TEXT NOT NULL)",
        f"CREATE TABLE IF NOT EXISTS suscripciones (id {id_t}, negocio_id INTEGER NOT NULL, plan_id INTEGER, plan TEXT DEFAULT 'FREE', precio_mensual REAL DEFAULT 24900.0, precio_contratado REAL DEFAULT 24900.0, moneda TEXT DEFAULT 'COP', periodicidad TEXT DEFAULT 'MENSUAL', fecha_inicio TEXT, fecha_vencimiento TEXT, estado TEXT DEFAULT 'ACTIVO', metodo_pago TEXT DEFAULT 'WOMPI', trial_activo INTEGER DEFAULT 0, es_trial INTEGER DEFAULT 0, fecha_fin_trial TEXT, auto_renovar INTEGER DEFAULT 0, fecha_ultimo_pago TEXT, fecha_proximo_pago TEXT)",
        f"CREATE TABLE IF NOT EXISTS historial_suscripciones (id {id_t}, negocio_id INTEGER NOT NULL, suscripcion_id INTEGER NOT NULL, evento TEXT NOT NULL, plan_anterior_id INTEGER, plan_nuevo_id INTEGER, fecha TEXT NOT NULL, usuario_id INTEGER, motivo TEXT, referencia_pago TEXT)",
        f"CREATE TABLE IF NOT EXISTS pagos_wompi (id {id_t}, negocio_id INTEGER NOT NULL, suscripcion_id INTEGER, referencia_wompi TEXT UNIQUE NOT NULL, transaction_id TEXT UNIQUE, monto REAL NOT NULL, tipo_pago TEXT DEFAULT 'RECURRENTE_MRR', concepto TEXT NOT NULL, periodo_facturado TEXT, estado TEXT NOT NULL, metodo_pago TEXT, fecha TEXT NOT NULL, respuesta_raw TEXT)",
        f"CREATE TABLE IF NOT EXISTS auditoria_impersonacion (id {id_t}, super_admin_id INTEGER NOT NULL, target_negocio_id INTEGER NOT NULL, fecha_inicio TEXT NOT NULL, fecha_fin TEXT, ip_origen TEXT, motivo TEXT DEFAULT 'SOPORTE')",
        f"CREATE TABLE IF NOT EXISTS log_impersonacion (id {id_t}, super_user_id INTEGER NOT NULL, target_negocio_id INTEGER NOT NULL, fecha_inicio TEXT NOT NULL, fecha_fin TEXT, motivo TEXT DEFAULT 'SOPORTE')",
        f"CREATE TABLE IF NOT EXISTS notificaciones (id {id_t}, negocio_id INTEGER NOT NULL, fecha TEXT NOT NULL, tipo TEXT NOT NULL, titulo TEXT NOT NULL, mensaje TEXT NOT NULL, leida INTEGER DEFAULT 0)"
    ]

    for sql in tablas_sql:
        try:
            cursor.execute(sql)
            conn.commit()
        except Exception as e:
            print(f"Error creando tabla: {e}")
            conn.rollback()

    def agregar_columna(tabla, columna, tipo):
        try:
            cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
            conn.commit()
        except:
            conn.rollback()

    agregar_columna('usuarios', 'password_hash', 'TEXT')
    agregar_columna('usuarios', 'email', 'TEXT')
    agregar_columna('usuarios', 'nombre_completo', 'TEXT')
    agregar_columna('usuarios', 'estado', "TEXT DEFAULT 'ACTIVO'")
    agregar_columna('usuarios', 'fecha_registro', 'TEXT')
    agregar_columna('usuarios', 'ultimo_acceso', 'TEXT')

    agregar_columna('suscripciones', 'plan_id', 'INTEGER')
    agregar_columna('suscripciones', 'precio_contratado', 'REAL DEFAULT 24900.0')
    agregar_columna('suscripciones', 'moneda', "TEXT DEFAULT 'COP'")
    agregar_columna('suscripciones', 'periodicidad', "TEXT DEFAULT 'MENSUAL'")
    agregar_columna('suscripciones', 'es_trial', 'INTEGER DEFAULT 0')
    agregar_columna('suscripciones', 'auto_renovar', 'INTEGER DEFAULT 0')
    agregar_columna('suscripciones', 'fecha_ultimo_pago', 'TEXT')
    agregar_columna('suscripciones', 'fecha_proximo_pago', 'TEXT')

    agregar_columna('negocios', 'intentos_pro_bloqueados', 'INTEGER DEFAULT 0')
    agregar_columna('negocios', 'wompi_secret', 'TEXT')
    agregar_columna('negocios', 'fecha_registro', 'TEXT')
    agregar_columna('negocios', 'fecha_vencimiento', 'TEXT')
    agregar_columna('negocios', 'trial_activo', 'INTEGER DEFAULT 1')
    agregar_columna('negocios', 'status', "TEXT DEFAULT 'ACTIVO'")
    agregar_columna('negocios', 'plan', "TEXT DEFAULT 'FREE'")
    agregar_columna('negocios', 'tipo_cuenta', "TEXT DEFAULT 'CLIENTE'")
    agregar_columna('negocios', 'es_interna', 'INTEGER DEFAULT 0')
    agregar_columna('negocios', 'es_datos_prueba', 'INTEGER DEFAULT 0')
    
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
    
    agregar_columna('ventas', 'producto_id', 'INTEGER')
    agregar_columna('ventas', 'cantidad', 'REAL')
    agregar_columna('ventas', 'metodo_pago', 'TEXT')
    agregar_columna('ventas', 'costo_historico_total', 'REAL')
    agregar_columna('ventas', 'precio_historico_unitario', 'REAL')
    agregar_columna('ventas', 'usuario_id', 'INTEGER')
    agregar_columna('ventas', 'estado_pago', "TEXT DEFAULT 'PAGADO'")
    agregar_columna('ventas', 'cliente_nombre', 'TEXT')
    agregar_columna('ventas', 'saldo_pendiente', 'REAL DEFAULT 0')
    agregar_columna('ventas', 'fecha_limite_pago', 'TEXT')
    agregar_columna('ventas', 'observacion', 'TEXT')
    agregar_columna('ventas', 'cliente_id', 'INTEGER')

    agregar_columna('configuracion_negocio', 'nombre_comercial', 'TEXT')
    agregar_columna('configuracion_negocio', 'color_acento', 'TEXT DEFAULT \'#38bdf8\'')
    agregar_columna('configuracion_negocio', 'maneja_cartera', 'INTEGER DEFAULT 0')
    agregar_columna('configuracion_negocio', 'maneja_lotes', 'INTEGER DEFAULT 0')
    agregar_columna('configuracion_negocio', 'metodo_salida_lotes', "TEXT DEFAULT 'FEFO'")
    agregar_columna('configuracion_negocio', 'bloquear_lotes_vencidos', "TEXT DEFAULT 'SI'")

    tablas_con_negocio = ['usuarios', 'productos', 'inventario', 'ventas', 'logs_conversion', 'costos_fijos', 'producto_insumo', 'movimientos_inventario', 'configuracion_negocio', 'abonos_cartera', 'tickets_soporte', 'clientes', 'compras_entradas', 'lotes_inventario', 'movimientos_lote', 'informes_guardados', 'suscripciones', 'pagos_wompi', 'notificaciones']
    for t in tablas_con_negocio:
        agregar_columna(t, 'negocio_id', 'INTEGER')

    cursor.execute("SELECT COUNT(*) FROM planes")
    if cursor.fetchone()[0] == 0:
        planes_def = [
            ("FREE", "Plan Gratuito", 0.0, 10, 50, json.dumps({
                "analisis": False, "informes": False, "exportar_excel": False, "cartera": True, "lotes": False
            })),
            ("PRO", "Plan Crecimiento PRO", 24900.0, None, None, json.dumps({
                "analisis": True, "informes": True, "exportar_excel": True, "cartera": True, "lotes": True
            })),
            ("ENTERPRISE", "Plan Empresarial Enterprise", 150000.0, None, None, json.dumps({
                "analisis": True, "informes": True, "exportar_excel": True, "cartera": True, "lotes": True, "soporte_dedicado": True
            }))
        ]
        placeholder = "%s" if IS_PG else "?"
        for cod, nom, pre, lp, lv, func in planes_def:
            cursor.execute(f"INSERT INTO planes (codigo, nombre, precio_mensual, limite_productos, limite_ventas, funcionalidades_json) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})",
                           (cod, nom, pre, lp, lv, func))
        conn.commit()

    placeholder = "%s" if IS_PG else "?"
    cursor.execute("SELECT COUNT(*) FROM negocios")
    if cursor.fetchone()[0] == 0:
        hoy = datetime.now()
        vence = (hoy + timedelta(days=3650)).strftime("%Y-%m-%d")
        cursor.execute(f"INSERT INTO negocios (nombre, plan, fecha_registro, fecha_vencimiento, trial_activo, tipo_cuenta, es_interna) VALUES ({placeholder}, 'PRO', {placeholder}, {placeholder}, 0, 'INTERNA', 1)", 
                       ("AS Solutions", hoy.strftime("%Y-%m-%d"), vence))
        conn.commit()

        cursor.execute("SELECT id FROM negocios ORDER BY id DESC LIMIT 1")
        nid = cursor.fetchone()[0]

        cursor.execute(f"INSERT INTO configuracion_negocio (negocio_id, nombre_comercial, tipo_operacion, color_acento) VALUES ({placeholder}, 'AS Solutions', 'SERVICIOS', '#38bdf8')", (nid,))
        conn.commit()

    cursor.execute("SELECT id FROM negocios WHERE es_interna=1 ORDER BY id ASC LIMIT 1")
    row = cursor.fetchone()
    nid = row[0] if row else 1

    hash_super = generate_password_hash('super2024')
    cursor.execute("SELECT id, password_hash FROM usuarios WHERE LOWER(username) = 'samuel_super'")
    user_row = cursor.fetchone()
    if not user_row:
        cursor.execute(f"INSERT INTO usuarios (negocio_id, username, password_hash, role) VALUES ({placeholder}, 'samuel_super', {placeholder}, 'SUPER')", (nid, hash_super))
        conn.commit()
    else:
        # Preservar la contraseña personalizada que haya cambiado el usuario y solo garantizar rol SUPER
        cursor.execute(f"UPDATE usuarios SET role = 'SUPER' WHERE id = {placeholder}", (user_row[0],))
        conn.commit()

    cursor.execute("SELECT id, password, password_hash FROM usuarios")
    users = cursor.fetchall()
    for uid, plain_p, p_hash in users:
        if not p_hash and plain_p:
            new_h = generate_password_hash(plain_p)
            cursor.execute(f"UPDATE usuarios SET password_hash = {placeholder} WHERE id = {placeholder}", (new_h, uid))
    conn.commit()

    conn.close()

def ejecutar_query(query, params=(), fetch=False):
    db_url = os.environ.get("DATABASE_URL")
    if db_url and POSTGRES_AVAILABLE: query = query.replace("?", "%s")
    conn = conectar(); cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        if fetch:
            res = cursor.fetchall()
            conn.close()
            return res
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Database query error: {e}")
        conn.rollback()
        conn.close()
        return [] if fetch else False

crear_tablas = init_db