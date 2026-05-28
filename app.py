from flask import Flask, jsonify, request, render_template, session, redirect, url_for
import services.ventas_service as ventas_service
import services.inventario_service as inventario_service
import services.financiero_service as financiero_service
from database import conectar, crear_tablas, ejecutar_query
from datetime import datetime, timedelta
from functools import wraps
import sys

app = Flask(__name__)
app.secret_key = "as_platform_high_conversion_2024"

# Asegurar tablas al iniciar
try:
    crear_tablas()
    DB_STATUS = "Conectado y Tablas Listas"
except Exception as e:
    DB_STATUS = f"Error de DB: {str(e)}"
    print(f"CRITICAL DB ERROR: {e}", file=sys.stderr)

# ==========================
# DECORADORES DE SEGURIDAD
# ==========================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') not in ['ADMIN', 'SUPER']: return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def super_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'SUPER': return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ==========================
# LÓGICA DE MONETIZACIÓN / CONVERSIÓN
# ==========================

def get_negocio_status_ext(negocio_id):
    try:
        res = ejecutar_query("SELECT plan, fecha_vencimiento, trial_activo FROM negocios WHERE id=?", (negocio_id,), fetch=True)
        if not res: return {"plan": "FREE", "dias": 0, "es_trial": False, "banner_msg": "Trial PRO Disponible"}
        plan, vence, trial = res[0]
        
        dias = 0
        if vence:
            try:
                dias = (datetime.strptime(vence, "%Y-%m-%d") - datetime.now()).days
            except:
                dias = 0
        
        if dias < 0 and plan != 'FREE':
            ejecutar_query("UPDATE negocios SET plan='FREE' WHERE id=?", (negocio_id,))
            plan = 'FREE'

        banner_msg = "Estás en PRO Trial 🚀"
        if dias <= 1: banner_msg = "Último día — desbloquea tu rentabilidad ⏳"
        elif dias <= 3: banner_msg = f"Te quedan {dias} días — no pierdas tu análisis 📊"
        
        return {
            "plan": plan, 
            "dias": max(0, dias), 
            "es_trial": bool(trial),
            "banner_msg": banner_msg
        }
    except Exception as e:
        print(f"Error status check: {e}")
        return {"plan": "FREE", "dias": 0, "es_trial": False, "banner_msg": "Sincronizando plan..."}

def require_plan(feature):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            status = get_negocio_status_ext(session.get('negocio_id'))
            if status['plan'] == 'FREE':
                ejecutar_query("UPDATE negocios SET intentos_pro_bloqueados = intentos_pro_bloqueados + 1 WHERE id=?", (session['negocio_id'],))
                if request.is_json:
                    return jsonify({"error": "PLAN_REQUIRED", "feature": feature}), 403
                return render_template('upgrade_needed.html', feature=feature)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ==========================
# RUTAS DE DIAGNÓSTICO
# ==========================

@app.route('/health')
def health():
    return f"Status: {DB_STATUS} | Server Time: {datetime.now()}"

# ==========================
# RUTAS PRINCIPALES (LANDING / LOGIN / REGISTER)
# ==========================

@app.route('/')
def index():
    if 'user_id' in session:
        # Si está logueado, se comporta como Dashboard
        return render_template('index.html', session=session)
    # Si no, se comporta como Landing Page
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        try:
            res = ejecutar_query("SELECT id, username, role, negocio_id FROM usuarios WHERE username=? AND password=?", (u, p), fetch=True)
            if res:
                session['user_id'] = res[0][0]
                session['username'] = res[0][1]
                session['role'] = res[0][2]
                session['negocio_id'] = res[0][3]
                status = get_negocio_status_ext(session['negocio_id'])
                session['plan'] = status['plan']
                if session['role'] == 'SUPER': 
                    return redirect(url_for('super_admin_page'))
                return redirect(url_for('index'))
        except Exception as e:
            return render_template('login.html', error=f"Error de sistema: {str(e)}")
        return render_template('login.html', error="Credenciales inválidas")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        business_name = request.form.get('business_name')
        username = request.form.get('username')
        password = request.form.get('password')
        operation_type = request.form.get('operation_type', 'HÍBRIDO')
        
        if not business_name or not username or not password:
            return render_template('register.html', error="Todos los campos son obligatorios.")
            
        try:
            user_exists = ejecutar_query("SELECT id FROM usuarios WHERE username=?", (username,), fetch=True)
            if user_exists:
                return render_template('register.html', error="El nombre de usuario ya está registrado.")
            
            hoy = datetime.now()
            vence = (hoy + timedelta(days=7)).strftime("%Y-%m-%d")
            
            # Crear negocio en plan FREE, con trial PRO activo de 7 días
            ejecutar_query("INSERT INTO negocios (nombre, plan, fecha_registro, fecha_vencimiento, trial_activo) VALUES (?, 'FREE', ?, ?, 1)", 
                           (business_name, hoy.strftime("%Y-%m-%d"), vence))
            
            res = ejecutar_query("SELECT id FROM negocios WHERE nombre=? ORDER BY id DESC LIMIT 1", (business_name,), fetch=True)
            if not res:
                return render_template('register.html', error="Error al crear el registro del negocio.")
            nid = res[0][0]
            
            # Crear administrador de la cuenta
            ejecutar_query("INSERT INTO usuarios (negocio_id, username, password, role) VALUES (?, ?, ?, 'ADMIN')", 
                           (nid, username, password))
            
            # Inicializar configuración del negocio
            ejecutar_query("INSERT INTO configuracion_negocio (negocio_id, nombre_comercial, tipo_operacion, color_acento) VALUES (?, ?, ?, '#38bdf8')",
                           (nid, business_name, operation_type))
            
            # Loguear automáticamente
            session['user_id'] = ejecutar_query("SELECT id FROM usuarios WHERE username=?", (username,), fetch=True)[0][0]
            session['username'] = username
            session['role'] = 'ADMIN'
            session['negocio_id'] = nid
            session['plan'] = 'FREE'
            
            return redirect(url_for('index'))
        except Exception as e:
            return render_template('register.html', error=f"Error al registrar cuenta: {str(e)}")
            
    return render_template('register.html')

@app.route('/logout')
def logout(): 
    session.clear()
    return redirect(url_for('index'))

# ==========================
# RUTAS DE PÁGINAS OPERATIVAS (CON AUTENTICACIÓN)
# ==========================

@app.route('/ventas')
@login_required
def ventas_page():
    return render_template('ventas.html', session=session)

@app.route('/inventario')
@login_required
def inventario_page():
    return render_template('inventario.html', session=session)

@app.route('/analisis')
@login_required
@require_plan("analytics")
def analisis_page():
    return render_template('analisis.html', session=session)

@app.route('/configuracion')
@login_required
@admin_required
def configuracion_page():
    return render_template('configuracion.html', session=session)

@app.route('/upgrade_needed')
@login_required
def upgrade_page():
    return render_template('upgrade_needed.html', feature="Análisis Avanzado")

@app.route('/super-admin')
@login_required
@super_required
def super_admin_page():
    return render_template('super_admin.html', session=session)

# ==========================
# RUTA DE DEMO INTERACTIVA
# ==========================

@app.route('/demo')
def demo_page():
    return render_template('demo.html')

# ==========================
# API ENDPOINTS
# ==========================

@app.route('/api/resumen')
@login_required
def g_res():
    status = get_negocio_status_ext(session['negocio_id'])
    data = financiero_service.obtener_resumen_financiero(session['negocio_id'], request.args.get('mes'))
    count_prod = ejecutar_query("SELECT COUNT(*) FROM productos WHERE negocio_id=?", (session['negocio_id'],), fetch=True)[0][0]
    
    return jsonify({
        "ingresos": data['ingresos'],
        "utilidad": data['utilidad'],
        "margen": data['margen_contribucion'],
        "punto_equilibrio": data['punto_equilibrio'],
        "is_locked": (status['plan'] == 'FREE'),
        "cuotas": {
            "productos": count_prod,
            "productos_max": 10
        }
    })

@app.route('/api/dashboard/graficos')
@login_required
def api_graficos():
    data = financiero_service.obtener_datos_graficos(session['negocio_id'])
    return jsonify(data)

@app.route('/api/productos', methods=['GET', 'POST'])
@login_required
def api_productos():
    nid = session['negocio_id']
    if request.method == 'POST':
        status = get_negocio_status_ext(nid)
        if status['plan'] == 'FREE':
            count = ejecutar_query("SELECT COUNT(*) FROM productos WHERE negocio_id=?", (nid,), fetch=True)[0][0]
            if count >= 10: 
                return jsonify({"error": "QUOTA_EXCEEDED"}), 403
        d = request.json
        ejecutar_query("INSERT INTO productos (negocio_id, nombre, precio) VALUES (?,?,?)", (nid, d['nombre'], d['precio']))
        return jsonify({"message": "ok"})
    res = ejecutar_query("SELECT id, nombre, precio FROM productos WHERE negocio_id=?", (nid,), fetch=True)
    return jsonify([{"id": x[0], "nombre": x[1], "precio": x[2]} for x in res] if res else [])

@app.route('/api/ventas', methods=['POST'])
@login_required
def post_venta():
    d = request.json
    s, r = ventas_service.registrar_venta(d['producto_id'], float(d['cantidad']), d.get('metodo_pago', 'Efectivo'), session['user_id'], session['negocio_id'])
    return jsonify({"message": "ok", "total": r}) if s else (jsonify({"error": r}), 400)

@app.route('/api/inventario')
@login_required
def g_inv():
    res = inventario_service.obtener_inventario(session['negocio_id'])
    return jsonify([{"id": x[0], "nombre": x[2], "stock_actual": x[4], "unidad": x[3]} for x in res] if res else [])

@app.route('/api/config/negocio', methods=['GET', 'POST'])
@login_required
def h_conf():
    nid = session['negocio_id']
    if request.method == 'POST':
        d = request.json
        ejecutar_query("UPDATE configuracion_negocio SET nombre_comercial=?, tipo_operacion=?, sheet_url_ventas=? WHERE negocio_id=?", (d['nombre'], d['tipo'], d.get('sheet_url_ventas'), nid))
        return jsonify({"message": "ok"})
    else:
        res = ejecutar_query("SELECT nombre_comercial, tipo_operacion, sheet_url_ventas, color_acento FROM configuracion_negocio WHERE negocio_id=?", (nid,), fetch=True)
        return jsonify({"nombre": res[0][0], "tipo": res[0][1], "sheet_url_ventas": res[0][2], "color_acento": res[0][3]}) if res else jsonify({"nombre": "Mi Negocio", "tipo": "HÍBRIDO"})

# ==========================
# API: SUPER ADMIN ENDPOINTS
# ==========================

@app.route('/api/super/stats')
@login_required
@super_required
def get_super_stats():
    res_neg = ejecutar_query("SELECT plan, COUNT(*) FROM negocios GROUP BY plan", fetch=True)
    stats = {x[0]: x[1] for x in res_neg} if res_neg else {}
    hot_leads = ejecutar_query("SELECT nombre, intentos_pro_bloqueados FROM negocios ORDER BY intentos_pro_bloqueados DESC LIMIT 5", fetch=True)
    pro_clients = stats.get('PRO', 0)
    return jsonify({
        "total_negocios": sum(stats.values()),
        "planes": stats,
        "mrr_proyectado": pro_clients * 24900,
        "hot_leads": [{"nombre": x[0], "intentos": x[1]} for x in hot_leads] if hot_leads else []
    })

@app.route('/api/super/negocios', methods=['GET', 'POST'])
@login_required
@super_required
def handle_super_negocios():
    if request.method == 'POST':
        d = request.json
        ejecutar_query("INSERT INTO negocios (nombre, status, plan) VALUES (?,?,?)", (d['nombre'], 'ACTIVO', d.get('plan', 'FREE')))
        nid = ejecutar_query("SELECT id FROM negocios WHERE nombre=? ORDER BY id DESC LIMIT 1", (d['nombre'],), fetch=True)[0][0]
        # Crear primer Admin
        ejecutar_query("INSERT INTO usuarios (negocio_id, username, password, role) VALUES (?,?,?,?)", (nid, d['admin_user'], d['admin_pass'], 'ADMIN'))
        # Crear config inicial
        ejecutar_query("INSERT INTO configuracion_negocio (negocio_id, nombre_comercial, tipo_operacion) VALUES (?, ?, 'HÍBRIDO')", (nid, d['nombre']))
        return jsonify({"message": "Nuevo cliente registrado exitosamente"})
    else:
        res = ejecutar_query("SELECT id, nombre, status, plan FROM negocios", fetch=True)
        return jsonify([{"id": x[0], "nombre": x[1], "status": x[2], "plan": x[3]} for x in res] if res else [])

@app.context_processor
def inject_global_info():
    if 'negocio_id' in session:
        return get_negocio_status_ext(session['negocio_id'])
    return {"plan": "FREE", "dias_restantes": 0, "es_trial": False}

if __name__ == '__main__':
    app.run(debug=True, port=5000)
