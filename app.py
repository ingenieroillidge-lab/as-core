from flask import Flask, jsonify, request, render_template, session, redirect, url_for
import services.ventas_service as ventas_service
import services.inventario_service as inventario_service
import services.financiero_service as financiero_service
from database import conectar, crear_tablas, ejecutar_query
from datetime import datetime, timedelta
from functools import wraps
import sys

app = Flask(__name__)
app.secret_key = "as_platform_final_debug_2024"

# Intentar crear tablas con captura de error para diagnóstico
try:
    crear_tablas()
    DB_STATUS = "Conectado y Tablas Listas"
except Exception as e:
    DB_STATUS = f"Error de DB: {str(e)}"
    print(f"CRITICAL DB ERROR: {e}", file=sys.stderr)

# ==========================
# DECORADORES
# ==========================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def super_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'SUPER': return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ==========================
# LÓGICA DE NEGOCIO
# ==========================

def get_status_safe(nid):
    try:
        res = ejecutar_query("SELECT plan, fecha_vencimiento, trial_activo FROM negocios WHERE id=?", (nid,), fetch=True)
        if not res: return {"plan": "FREE", "dias": 0, "es_trial": False, "banner_msg": ""}
        p, v, t = res[0]
        d = 0
        if v:
            try: d = (datetime.strptime(v, "%Y-%m-%d") - datetime.now()).days
            except: d = 0
        return {"plan": p, "dias": max(0, d), "es_trial": bool(t), "banner_msg": "Modo PRO Activo" if p=="PRO" else "Trial PRO Disponible"}
    except:
        return {"plan": "FREE", "dias": 0, "es_trial": False, "banner_msg": "Error de sincronización"}

# ==========================
# RUTAS DE DIAGNÓSTICO
# ==========================

@app.route('/health')
def health():
    return f"Status: {DB_STATUS} | Server Time: {datetime.now()}"

# ==========================
# RUTAS PRINCIPALES
# ==========================

@app.route('/')
@login_required
def index():
    return render_template('index.html', session=session)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('username'); p = request.form.get('password')
        try:
            res = ejecutar_query("SELECT id, username, role, negocio_id FROM usuarios WHERE username=? AND password=?", (u, p), fetch=True)
            if res:
                session['user_id'] = res[0][0]; session['username'] = res[0][1]
                session['role'] = res[0][2]; session['negocio_id'] = res[0][3]
                if session['role'] == 'SUPER': return redirect(url_for('super_admin_page'))
                return redirect(url_for('index'))
        except Exception as e:
            return render_template('login.html', error=f"Error de sistema: {str(e)}")
        return render_template('login.html', error="Credenciales inválidas")
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/super-admin')
@login_required
@super_required
def super_admin_page():
    return render_template('super_admin.html', session=session)

# [API de Productos con manejo de errores]
@app.route('/api/productos', methods=['GET', 'POST'])
@login_required
def api_productos():
    nid = session['negocio_id']
    if request.method == 'POST':
        d = request.json
        ejecutar_query("INSERT INTO productos (negocio_id, nombre, precio) VALUES (?,?,?)", (nid, d['nombre'], d['precio']))
        return jsonify({"message": "ok"})
    res = ejecutar_query("SELECT id, nombre, precio FROM productos WHERE negocio_id=?", (nid,), fetch=True)
    return jsonify([{"id": x[0], "nombre": x[1], "precio": x[2]} for x in res] if res else [])

@app.context_processor
def inject_global_info():
    if 'negocio_id' in session:
        return get_status_safe(session['negocio_id'])
    return {"plan": "FREE", "dias_restantes": 0, "es_trial": False}

if __name__ == '__main__':
    app.run(debug=True, port=5000)
