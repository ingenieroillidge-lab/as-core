from flask import Flask, jsonify, request, render_template, Response, session, redirect, url_for
import services.ventas_service as ventas_service
import services.inventario_service as inventario_service
import services.financiero_service as financiero_service
from database import conectar, crear_tablas, ejecutar_query
import shutil
import os
import csv
import io
import urllib.request
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = "as_platform_super_secret_2024"

# Asegurar que las tablas existan
crear_tablas()

# ==========================
# SEGURIDAD Y SESIÓN
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form['username']; p = request.form['password']
        res = ejecutar_query("SELECT id, username, role, negocio_id FROM usuarios WHERE username=? AND password=?", (u, p), fetch=True)
        if res:
            session['user_id'] = res[0][0]; session['username'] = res[0][1]
            session['role'] = res[0][2]; session['negocio_id'] = res[0][3]
            if session['role'] == 'SUPER': return redirect(url_for('super_admin_page'))
            return redirect(url_for('index') if session['role'] == 'ADMIN' else url_for('ventas_page'))
        return render_template('login.html', error="Acceso denegado")
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

# ==========================
# RUTAS DE PÁGINAS
# ==========================

@app.route('/')
@login_required
def index(): return render_template('index.html', session=session)

@app.route('/super-admin')
@login_required
@super_required
def super_admin_page(): return render_template('super_admin.html', session=session)

@app.route('/ventas')
@login_required
def ventas_page(): return render_template('ventas.html', session=session)

@app.route('/inventario')
@login_required
def inventario_page(): return render_template('inventario.html', session=session)

@app.route('/configuracion')
@login_required
@admin_required
def configuracion_page(): return render_template('configuracion.html', session=session)

# ==========================
# API: SUPER ADMIN (CONTROL TOTAL)
# ==========================

@app.route('/api/super/negocios', methods=['GET', 'POST'])
@login_required
@super_required
def handle_super_negocios():
    if request.method == 'POST':
        d = request.json
        ejecutar_query("INSERT INTO negocios (nombre, status, plan) VALUES (?,?,?)", (d['nombre'], 'ACTIVO', d.get('plan', 'FREE')))
        nid = ejecutar_query("SELECT id FROM negocios WHERE nombre=? ORDER BY id DESC LIMIT 1", (d['nombre'],), fetch=True)[0][0]
        # Crear el primer Admin para ese negocio
        ejecutar_query("INSERT INTO usuarios (negocio_id, username, password, role) VALUES (?,?,?,?)", (nid, d['admin_user'], d['admin_pass'], 'ADMIN'))
        return jsonify({"message": "Nuevo cliente registrado exitosamente"})
    else:
        res = ejecutar_query("SELECT id, nombre, status, plan FROM negocios", fetch=True)
        return jsonify([{"id": x[0], "nombre": x[1], "status": x[2], "plan": x[3]} for x in res])

# ==========================
# API: CLIENTES (FILTRADO POR NEGOCIO)
# ==========================

@app.route('/api/ventas', methods=['POST'])
@login_required
def post_venta():
    d = request.json
    s, r = ventas_service.registrar_venta(d['producto_id'], float(d['cantidad']), d.get('metodo_pago', 'Efectivo'), session['user_id'], session['negocio_id'])
    return jsonify({"message": "ok", "total": r}) if s else (jsonify({"error": r}), 400)

@app.route('/api/resumen')
@login_required
def g_res(): return jsonify(financiero_service.obtener_resumen_financiero(session['negocio_id'], request.args.get('mes')))

@app.route('/api/inventario')
@login_required
def g_inv(): return jsonify([{"id": x[0], "nombre": x[2], "stock_actual": x[4], "unidad": x[3]} for x in inventario_service.obtener_inventario(session['negocio_id'])])

@app.route('/api/productos')
@login_required
def g_pro():
    res = ejecutar_query("SELECT id, nombre, precio FROM productos WHERE negocio_id=?", (session['negocio_id'],), fetch=True)
    return jsonify([{"id": x[0], "nombre": x[1], "precio": x[2]} for x in res])

@app.route('/api/config/negocio', methods=['GET', 'POST'])
@login_required
def h_conf():
    if request.method == 'POST':
        d = request.json
        ejecutar_query("UPDATE configuracion_negocio SET nombre_comercial=?, tipo_operacion=?, sheet_url_ventas=? WHERE negocio_id=?", (d['nombre'], d['tipo'], d.get('sheet_url_ventas'), session['negocio_id']))
        return jsonify({"message": "ok"})
    else:
        res = ejecutar_query("SELECT nombre_comercial, tipo_operacion, sheet_url_ventas, color_acento FROM configuracion_negocio WHERE negocio_id=?", (session['negocio_id'],), fetch=True)
        return jsonify({"nombre": res[0][0], "tipo": res[0][1], "sheet_url_ventas": res[0][2], "color_acento": res[0][3]}) if res else jsonify({"nombre": "Mi Negocio", "tipo": "HÍBRIDO"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
