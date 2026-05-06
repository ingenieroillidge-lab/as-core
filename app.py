from flask import Flask, jsonify, request, render_template, session, redirect, url_for
import services.ventas_service as ventas_service
import services.inventario_service as inventario_service
import services.financiero_service as financiero_service
from database import conectar, crear_tablas, ejecutar_query
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = "as_platform_high_conversion_2024"

# Asegurar tablas al iniciar
crear_tablas()

# ==========================
# 1. DECORADORES DE SEGURIDAD (DEBEN IR PRIMERO)
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
# 2. LÓGICA DE MONETIZACIÓN
# ==========================

def get_negocio_status_ext(negocio_id):
    res = ejecutar_query("SELECT plan, fecha_vencimiento, trial_activo FROM negocios WHERE id=?", (negocio_id,), fetch=True)
    if not res: return {"plan": "FREE", "dias": 0, "es_trial": False, "banner_msg": ""}
    plan, vence, trial = res[0]
    
    dias = 0
    if vence:
        try:
            dias = (datetime.strptime(vence, "%Y-%m-%d") - datetime.now()).days
        except: dias = 0
    
    if dias < 0 and plan != 'FREE':
        ejecutar_query("UPDATE negocios SET plan='FREE' WHERE id=?", (negocio_id,))
        plan = 'FREE'

    banner_msg = "Estás en PRO Trial 🚀"
    if dias <= 1: banner_msg = "Último día — activa tu rentabilidad ⏳"
    elif dias <= 3: banner_msg = f"Te quedan {dias} días de Trial 📊"
    
    return {"plan": plan, "dias": max(0, dias), "es_trial": bool(trial), "banner_msg": banner_msg}

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

# [A partir de aquí van las rutas @app.route...]
# ==========================
# 3. RUTAS DE PÁGINAS
# ==========================

@app.route('/')
@login_required
def index(): return render_template('index.html', session=session)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form['username']; p = request.form['password']
        res = ejecutar_query("SELECT id, username, role, negocio_id FROM usuarios WHERE username=? AND password=?", (u, p), fetch=True)
        if res:
            session['user_id'] = res[0][0]; session['username'] = res[0][1]
            session['role'] = res[0][2]; session['negocio_id'] = res[0][3]
            status = get_negocio_status_ext(session['negocio_id'])
            session['plan'] = status['plan']
            if session['role'] == 'SUPER': return redirect(url_for('super_admin_page'))
            return redirect(url_for('index') if session['role'] in ['ADMIN', 'SUPER'] else url_for('ventas_page'))
        return render_template('login.html', error="Acceso denegado")
    return render_template('login.html')

@app.route('/super-admin')
@login_required
@super_required
def super_admin_page(): return render_template('super_admin.html', session=session)

@app.route('/api/super/stats')
@login_required
@super_required
def get_super_stats():
    res_neg = ejecutar_query("SELECT plan, COUNT(*) FROM negocios GROUP BY plan", fetch=True)
    stats = {x[0]: x[1] for x in res_neg}
    hot_leads = ejecutar_query("SELECT nombre, intentos_pro_bloqueados FROM negocios ORDER BY intentos_pro_bloqueados DESC LIMIT 5", fetch=True)
    pro_clients = stats.get('PRO', 0)
    return jsonify({"total_negocios": sum(stats.values()), "planes": stats, "mrr_proyectado": pro_clients * 24900, "hot_leads": [{"nombre": x[0], "intentos": x[1]} for x in hot_leads]})

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/ventas')
@login_required
def ventas_page(): return render_template('ventas.html', session=session)

@app.route('/inventario')
@login_required
def inventario_page(): return render_template('inventario.html', session=session)

@app.route('/analisis')
@login_required
@require_plan("analytics")
def analisis_page(): return render_template('analisis.html', session=session)

@app.route('/configuracion')
@login_required
@admin_required
def configuracion_page(): return render_template('configuracion.html', session=session)

@app.route('/upgrade_needed')
@login_required
def upgrade_page(): return render_template('upgrade_needed.html', feature="Análisis Avanzado")

# ==========================
# 4. API ENDPOINTS
# ==========================

@app.route('/api/resumen')
@login_required
def g_res():
    status = get_negocio_status_ext(session['negocio_id'])
    data = financiero_service.obtener_resumen_financiero(session['negocio_id'], request.args.get('mes'))
    count_prod = ejecutar_query("SELECT COUNT(*) FROM productos WHERE negocio_id=?", (session['negocio_id'],), fetch=True)[0][0]
    return jsonify({"ingresos": data['ingresos'], "utilidad": data['utilidad'], "margen": data['margen_contribucion'], "punto_equilibrio": data['punto_equilibrio'], "is_locked": (status['plan'] == 'FREE'), "cuotas": {"productos": count_prod, "productos_max": 10}})

@app.route('/api/productos', methods=['GET', 'POST'])
@login_required
def h_prod():
    if request.method == 'POST':
        status = get_negocio_status_ext(session['negocio_id'])
        if status['plan'] == 'FREE':
            count = ejecutar_query("SELECT COUNT(*) FROM productos WHERE negocio_id=?", (session['negocio_id'],), fetch=True)[0][0]
            if count >= 10: return jsonify({"error": "QUOTA_EXCEEDED"}), 403
        d = request.json
        ejecutar_query("INSERT INTO productos (negocio_id, nombre, precio) VALUES (?,?,?)", (session['negocio_id'], d['nombre'], d['precio']))
        return jsonify({"message": "ok"})
    res = ejecutar_query("SELECT id, nombre, precio FROM productos WHERE negocio_id=?", (session['negocio_id'],), fetch=True)
    return jsonify([{"id": x[0], "nombre": x[1], "precio": x[2]} for x in res])

@app.context_processor
def inject_global_info():
    if 'negocio_id' in session: return get_negocio_status_ext(session['negocio_id'])
    return {}

if __name__ == '__main__':
    app.run(debug=True, port=5000)
