from flask import Flask, jsonify, request, render_template, session, redirect, url_for, Response
import services.ventas_service as ventas_service
import services.inventario_service as inventario_service
import services.financiero_service as financiero_service
import services.cartera_service as cartera_service
from database import conectar, crear_tablas, ejecutar_query
from datetime import datetime, timedelta
from functools import wraps
import sys
import io
import csv
import urllib.request

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
        if session.get('role') == 'SUPER':
            return {"plan": "PRO", "dias": 9999, "es_trial": False, "banner_msg": "Panel Super Admin 🚀"}
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
        u = (request.form.get('username') or '').strip()
        p = (request.form.get('password') or '').strip()
        try:
            res = ejecutar_query("SELECT id, username, role, negocio_id FROM usuarios WHERE LOWER(username)=LOWER(?) AND password=?", (u, p), fetch=True)
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

@app.route('/cartera')
@login_required
def cartera_page():
    return render_template('cartera.html', session=session)

@app.route('/informes')
@login_required
def informes_page():
    return render_template('informes.html', session=session)

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
    nid = session['negocio_id']
    status = get_negocio_status_ext(nid)
    data = financiero_service.obtener_resumen_financiero(nid, request.args.get('mes'))
    
    count_prod = ejecutar_query("SELECT COUNT(*) FROM productos WHERE negocio_id=?", (nid,), fetch=True)[0][0]
    count_insumo = ejecutar_query("SELECT COUNT(*) FROM inventario WHERE negocio_id=?", (nid,), fetch=True)[0][0]
    count_receta = ejecutar_query("SELECT COUNT(*) FROM producto_insumo WHERE negocio_id=?", (nid,), fetch=True)[0][0]
    count_venta = ejecutar_query("SELECT COUNT(*) FROM ventas WHERE negocio_id=?", (nid,), fetch=True)[0][0]
    
    return jsonify({
        "ingresos": data['ingresos'],
        "utilidad": data['utilidad'],
        "margen": data['margen_contribucion'],
        "punto_equilibrio": data['punto_equilibrio'],
        "is_locked": (status['plan'] == 'FREE'),
        "cuotas": {
            "productos": count_prod,
            "productos_max": 10
        },
        "onboarding": {
            "negocio_configurado": True,
            "producto_creado": count_prod > 0,
            "insumo_creado": count_insumo > 0,
            "receta_creada": count_receta > 0,
            "venta_registrada": count_venta > 0
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
    metodo = d.get('metodo_pago', 'Efectivo')
    producto_id = int(d['producto_id'])
    cantidad = float(d['cantidad'])
    fecha = d.get('fecha')

    # Datos opcionales de crédito / cartera
    cliente = (d.get('cliente_nombre') or '').strip()
    fecha_limite = d.get('fecha_limite_pago')
    abono_inicial = float(d.get('abono_inicial', 0.0))
    observacion = (d.get('observacion') or '').strip()

    s, r = ventas_service.registrar_venta(
        producto_id, 
        cantidad, 
        metodo, 
        session['user_id'], 
        session['negocio_id'],
        fecha_custom=fecha
    )

    if s:
        # Si la venta es a Crédito o se proporcionaron datos de cliente/crédito
        if metodo == 'CRÉDITO' or cliente or fecha_limite or abono_inicial > 0:
            if cliente:
                cartera_service.crear_o_actualizar_cliente(cliente, session['negocio_id'])

            v_res = ejecutar_query(
                "SELECT id, total FROM ventas WHERE negocio_id=? ORDER BY id DESC LIMIT 1",
                (session['negocio_id'],), fetch=True
            )
            if v_res:
                v_id, total_v = v_res[0]
                total_v = float(total_v)

                if abono_inicial > 0:
                    saldo_p = max(0.0, total_v - abono_inicial)
                    estado_p = "PAGADO" if saldo_p <= 0.01 else "PARCIAL"
                else:
                    saldo_p = total_v
                    estado_p = "PENDIENTE"

                ejecutar_query(
                    """UPDATE ventas SET 
                       estado_pago=?, cliente_nombre=?, saldo_pendiente=?, fecha_limite_pago=?, observacion=?
                       WHERE id=? AND negocio_id=?""",
                    (estado_p, cliente if cliente else "Cliente Crédito", saldo_p, fecha_limite, observacion, v_id, session['negocio_id'])
                )

                if abono_inicial > 0:
                    cartera_service.registrar_abono(
                        v_id, abono_inicial, "Efectivo (Abono Inicial)", session['user_id'], session['negocio_id'],
                        observacion="Abono Inicial en Venta a Crédito", fecha_custom=fecha
                    )

        return jsonify({"message": "ok", "total": r})
    else:
        return jsonify({"error": r}), 400

@app.route('/api/inventario')
@login_required
def g_inv():
    res = inventario_service.obtener_inventario(session['negocio_id'])
    return jsonify([{"id": x[0], "nombre": x[2], "stock_actual": x[4], "unidad": x[3]} for x in res] if res else [])

@app.route('/api/inventario', methods=['POST'])
@login_required
def post_inventario():
    nid = session['negocio_id']
    d = request.json
    codigo = d.get('codigo', f"INS-{d['nombre'][:3].upper()}")
    ejecutar_query(
        "INSERT INTO inventario (negocio_id, codigo, nombre, unidad_base, costo_unitario_base, stock_inicial, stock_actual) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (nid, codigo, d['nombre'], d.get('unidad_base', 'unidades'), float(d.get('costo_unitario_base', 0)), float(d.get('stock_inicial', 0)), float(d.get('stock_inicial', 0)))
    )
    res = ejecutar_query("SELECT id FROM inventario WHERE nombre=? AND negocio_id=? ORDER BY id DESC LIMIT 1", (d['nombre'], nid), fetch=True)
    new_id = res[0][0] if res else None
    return jsonify({"message": "ok", "id": new_id})

@app.route('/api/recetas', methods=['POST'])
@login_required
def post_receta():
    nid = session['negocio_id']
    d = request.json
    ejecutar_query(
        "INSERT INTO producto_insumo (producto_id, insumo_id, cantidad_usada, negocio_id) VALUES (?, ?, ?, ?)",
        (int(d['producto_id']), int(d['insumo_id']), float(d['cantidad_usada']), nid)
    )
    return jsonify({"message": "ok"})

@app.route('/api/config/negocio', methods=['GET', 'POST'])
@login_required
def h_conf():
    nid = session['negocio_id']
    if request.method == 'POST':
        d = request.json
        nombre = (d.get('nombre') or 'Mi Negocio').strip()
        tipo = (d.get('tipo') or 'HÍBRIDO').strip()
        sheet_url = (d.get('sheet_url_ventas') or '').strip()
        color = (d.get('color_acento') or '#38bdf8').strip()
        maneja_cartera = int(d.get('maneja_cartera', 0))
        maneja_lotes = int(d.get('maneja_lotes', 0))
        metodo_salida_lotes = (d.get('metodo_salida_lotes') or 'FEFO').strip().upper()
        bloquear_vencidos = (d.get('bloquear_lotes_vencidos') or 'SI').strip().upper()

        c_res = ejecutar_query("SELECT id FROM configuracion_negocio WHERE negocio_id=?", (nid,), fetch=True)
        if c_res:
            ejecutar_query("UPDATE configuracion_negocio SET nombre_comercial=?, tipo_operacion=?, sheet_url_ventas=?, color_acento=?, maneja_cartera=?, maneja_lotes=?, metodo_salida_lotes=?, bloquear_lotes_vencidos=? WHERE negocio_id=?", 
                           (nombre, tipo, sheet_url, color, maneja_cartera, maneja_lotes, metodo_salida_lotes, bloquear_vencidos, nid))
        else:
            ejecutar_query("INSERT INTO configuracion_negocio (negocio_id, nombre_comercial, tipo_operacion, sheet_url_ventas, color_acento, maneja_cartera, maneja_lotes, metodo_salida_lotes, bloquear_lotes_vencidos) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                           (nid, nombre, tipo, sheet_url, color, maneja_cartera, maneja_lotes, metodo_salida_lotes, bloquear_vencidos))

        ejecutar_query("UPDATE negocios SET nombre=? WHERE id=?", (nombre, nid))
        return jsonify({"message": "ok"})
    else:
        res = ejecutar_query("SELECT nombre_comercial, tipo_operacion, sheet_url_ventas, color_acento, maneja_cartera, maneja_lotes, metodo_salida_lotes, bloquear_lotes_vencidos FROM configuracion_negocio WHERE negocio_id=?", (nid,), fetch=True)
        if res and res[0]:
            row = res[0]
            return jsonify({
                "nombre": row[0] or "Mi Negocio",
                "tipo": row[1] or "HÍBRIDO",
                "sheet_url_ventas": row[2] or "",
                "color_acento": row[3] or "#38bdf8",
                "maneja_cartera": row[4] if len(row) > 4 and row[4] is not None else 0,
                "maneja_lotes": row[5] if len(row) > 5 and row[5] is not None else 0,
                "metodo_salida_lotes": row[6] if len(row) > 6 and row[6] else "FEFO",
                "bloquear_lotes_vencidos": row[7] if len(row) > 7 and row[7] else "SI"
            })
        return jsonify({
            "nombre": "Mi Negocio", "tipo": "HÍBRIDO", "sheet_url_ventas": "",
            "color_acento": "#38bdf8", "maneja_cartera": 0, "maneja_lotes": 0,
            "metodo_salida_lotes": "FEFO", "bloquear_lotes_vencidos": "SI"
        })

# ==========================
# API: LOTES Y COMPRAS DE INVENTARIO
# ==========================

@app.route('/api/lotes', methods=['GET'])
@login_required
def get_lotes():
    nid = session['negocio_id']
    insumo_id = request.args.get('insumo_id')
    estado = request.args.get('estado')
    return jsonify(lotes_service.obtener_lotes(nid, insumo_id=insumo_id, estado_filtro=estado))

@app.route('/api/lotes/compra', methods=['POST'])
@login_required
def post_compra_lote():
    nid = session['negocio_id']
    uid = session['user_id']
    d = request.json or {}
    ok, res = lotes_service.registrar_compra_lote(
        insumo_id=d.get('insumo_id'),
        codigo_lote=d.get('codigo_lote'),
        cantidad=d.get('cantidad', 0),
        costo_unitario=d.get('costo_unitario', 0),
        negocio_id=nid,
        usuario_id=uid,
        fecha_vencimiento=d.get('fecha_vencimiento'),
        proveedor=d.get('proveedor', ''),
        numero_factura=d.get('numero_factura', ''),
        observaciones=d.get('observaciones', ''),
        fecha_compra=d.get('fecha_compra')
    )
    return jsonify({"message": "ok", "data": res}) if ok else (jsonify({"error": res}), 400)

# ==========================
# API: GENERADOR TRANSVERSAL DE INFORMES
# ==========================

@app.route('/api/informes/guardados', methods=['GET'])
@login_required
def get_informes_guardados():
    nid = session['negocio_id']
    return jsonify(lotes_service.obtener_informes_guardados(nid))

@app.route('/api/informes/guardar', methods=['POST'])
@login_required
def post_guardar_informe():
    nid = session['negocio_id']
    d = request.json or {}
    ok, res = lotes_service.guardar_configuracion_informe(
        negocio_id=nid,
        nombre_informe=d.get('nombre_informe'),
        tipo_objeto=d.get('tipo_objeto', 'VENTAS'),
        columnas=d.get('columnas', []),
        filtros=d.get('filtros', {}),
        agrupacion=d.get('agrupacion')
    )
    return jsonify({"message": res}) if ok else (jsonify({"error": res}), 400)

@app.route('/api/informes/generar', methods=['POST'])
@login_required
def post_generar_informe():
    nid = session['negocio_id']
    d = request.json or {}
    dim = (d.get('dimension') or 'VENTAS').upper()
    f_inicio = d.get('fecha_inicio')
    f_fin = d.get('fecha_fin')

    rows = []
    summary = {}

    if dim == 'VENTAS' or dim == 'RENTABILIDAD' or dim == 'PRODUCTOS':
        query = """
            SELECT v.fecha, p.nombre as producto, v.cantidad, v.precio_historico_unitario,
                   v.total as ingreso, v.costo_historico_total as costo,
                   (v.total - v.costo_historico_total) as utilidad,
                   v.metodo_pago, v.cliente_nombre
            FROM ventas v
            JOIN productos p ON v.producto_id = p.id
            WHERE v.negocio_id=?
        """
        params = [nid]
        if f_inicio:
            query += " AND v.fecha >= ?"
            params.append(f"{f_inicio} 00:00:00")
        if f_fin:
            query += " AND v.fecha <= ?"
            params.append(f"{f_fin} 23:59:59")
        query += " ORDER BY v.fecha DESC"
        raw = ejecutar_query(query, params, fetch=True) or []

        tot_ing = sum(r[4] or 0 for r in raw)
        tot_cos = sum(r[5] or 0 for r in raw)
        tot_uti = tot_ing - tot_cos
        tot_unid = sum(r[2] or 0 for r in raw)
        margen = (tot_uti / tot_ing * 100) if tot_ing > 0 else 0.0

        summary = {
            "unidades_vendidas": tot_unid,
            "ingresos_totales": tot_ing,
            "costo_total": tot_cos,
            "utilidad_neta": tot_uti,
            "margen_porcentaje": round(margen, 2)
        }
        for r in raw:
            f, p, cant, pr, ing, cos, uti, met, cli = r
            mg = (uti / ing * 100) if ing > 0 else 0.0
            rows.append({
                "fecha": f[:10] if f else '',
                "producto": p,
                "cantidad": cant,
                "precio_unitario": pr,
                "ingreso": ing,
                "costo": cos,
                "utilidad": uti,
                "margen": round(mg, 2),
                "metodo_pago": met or 'Efectivo',
                "cliente": cli or 'Cliente Ocasional'
            })

    elif dim == 'LOTES' or dim == 'COMPRAS':
        query = """
            SELECT c.fecha_compra, i.nombre as insumo, c.codigo_lote, c.proveedor,
                   c.numero_factura, c.cantidad_comprada, c.costo_unitario_compra,
                   c.costo_total_compra, c.fecha_vencimiento, l.cantidad_disponible, l.estado
            FROM compras_entradas c
            JOIN inventario i ON c.insumo_id = i.id
            LEFT JOIN lotes_inventario l ON c.codigo_lote = l.codigo_lote AND c.negocio_id = l.negocio_id
            WHERE c.negocio_id=?
        """
        params = [nid]
        if f_inicio:
            query += " AND c.fecha_compra >= ?"
            params.append(f"{f_inicio} 00:00:00")
        if f_fin:
            query += " AND c.fecha_compra <= ?"
            params.append(f"{f_fin} 23:59:59")
        query += " ORDER BY c.id DESC"
        raw = ejecutar_query(query, params, fetch=True) or []

        tot_comp = sum(r[7] or 0 for r in raw)
        tot_unid = sum(r[5] or 0 for r in raw)

        summary = {
            "registros_compras": len(raw),
            "unidades_compradas": tot_unid,
            "inversion_total": tot_comp
        }
        for r in raw:
            fc, ins, cod, prov, fact, cant_c, cost_u, cost_t, fv, cant_d, est = r
            rows.append({
                "fecha": fc[:10] if fc else '',
                "insumo": ins,
                "codigo_lote": cod,
                "proveedor": prov or 'N/A',
                "factura": fact or 'N/A',
                "cantidad_comprada": cant_c,
                "costo_unitario": cost_u,
                "costo_total": cost_t,
                "fecha_vencimiento": fv or 'Sin Vencimiento',
                "cantidad_disponible": cant_d if cant_d is not None else 0,
                "estado": est or 'ACTIVO'
            })

    elif dim == 'CARTERA' or dim == 'CLIENTES':
        query = """
            SELECT v.fecha, v.id as venta_id, v.cliente_nombre, v.total,
                   v.saldo_pendiente, v.estado_pago, v.fecha_limite_pago
            FROM ventas v
            WHERE v.negocio_id=? AND (v.estado_pago IN ('PENDIENTE', 'PARCIAL') OR v.saldo_pendiente > 0)
        """
        params = [nid]
        if f_inicio:
            query += " AND v.fecha >= ?"
            params.append(f"{f_inicio} 00:00:00")
        if f_fin:
            query += " AND v.fecha <= ?"
            params.append(f"{f_fin} 23:59:59")
        query += " ORDER BY v.fecha DESC"
        raw = ejecutar_query(query, params, fetch=True) or []

        tot_cart = sum(r[4] or 0 for r in raw)
        summary = {
            "cuentas_pendientes": len(raw),
            "cartera_total_pendiente": tot_cart
        }
        for r in raw:
            f, vid, cli, tot, sal, est, flim = r
            rows.append({
                "fecha": f[:10] if f else '',
                "venta_id": f"VENTA-{vid}",
                "cliente": cli or 'Sin Cliente',
                "total_venta": tot,
                "saldo_pendiente": sal,
                "estado_pago": est,
                "fecha_limite": flim or 'N/A'
            })
    else:
        # INVENTARIO GENERAl
        raw = ejecutar_query("SELECT id, nombre, unidad_base, costo_unitario_base, stock_actual, stock_minimo FROM inventario WHERE negocio_id=?", (nid,), fetch=True) or []
        summary = {"total_insumos": len(raw)}
        for r in raw:
            rows.append({
                "insumo": r[1],
                "unidad": r[2],
                "costo_unitario": r[3],
                "stock_actual": r[4],
                "valor_inventario": r[3] * r[4],
                "stock_minimo": r[5]
            })

    return jsonify({"dimension": dim, "resumen": summary, "filas": rows})

@app.route('/api/informes/exportar/excel', methods=['POST'])
@login_required
def post_exportar_informe_excel():
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    nid = session['negocio_id']
    d = request.json or {}
    titulo = d.get('titulo', 'Informe Configurado AS Platform')
    filas = d.get('filas', [])

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Informe"

    if not filas:
        ws.append(["Sin registros para exportar"])
    else:
        headers = list(filas[0].keys())
        ws.append([h.replace('_', ' ').title() for h in headers])

        header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='0EA5E9', end_color='0EA5E9', fill_type='solid')
        align_center = Alignment(horizontal='center', vertical='center')

        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_num)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = align_center

        for r in filas:
            ws.append(list(r.values()))

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    out_stream = io.BytesIO()
    wb.save(out_stream)
    out_stream.seek(0)

    filename = f"{titulo.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return Response(
        out_stream.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

# ==========================
# API: CARTERA Y CUENTAS POR COBRAR
# ==========================

@app.route('/api/cartera/resumen')
@login_required
def get_cartera_resumen():
    nid = session['negocio_id']
    mes = request.args.get('mes')
    resumen = cartera_service.obtener_resumen_cartera(nid, mes_filtro=mes)
    return jsonify(resumen)

@app.route('/api/cartera/cuentas')
@login_required
def get_cartera_cuentas():
    nid = session['negocio_id']
    cliente = request.args.get('cliente')
    estado = request.args.get('estado')
    cuentas = cartera_service.obtener_cuentas_por_cobrar(nid, cliente_filtro=cliente, estado_filtro=estado)
    return jsonify(cuentas)

@app.route('/api/cartera/abonos/<int:venta_id>')
@login_required
def get_cartera_abonos(venta_id):
    nid = session['negocio_id']
    abonos = cartera_service.obtener_historial_abonos(venta_id, nid)
    return jsonify(abonos)

@app.route('/api/cartera/abono', methods=['POST'])
@login_required
def post_cartera_abono():
    nid = session['negocio_id']
    uid = session['user_id']
    d = request.json
    venta_id = int(d['venta_id'])
    monto = float(d['monto'])
    metodo = d.get('metodo_pago', 'Efectivo')
    observacion = (d.get('observacion') or '').strip()
    fecha = d.get('fecha')

    ok, result = cartera_service.registrar_abono(venta_id, monto, metodo, uid, nid, observacion=observacion, fecha_custom=fecha)
    if ok:
        return jsonify({"message": "Abono registrado con éxito", "data": result})
    else:
        return jsonify({"error": result}), 400

@app.route('/api/clientes', methods=['GET', 'POST'])
@login_required
def h_clientes():
    nid = session['negocio_id']
    if request.method == 'POST':
        d = request.json
        ok, res = cartera_service.crear_o_actualizar_cliente(
            d.get('nombre'), nid,
            tipo=d.get('tipo', 'PERSONA'),
            documento=d.get('documento', ''),
            telefono=d.get('telefono', ''),
            whatsapp=d.get('whatsapp', ''),
            email=d.get('email', ''),
            direccion=d.get('direccion', ''),
            limite_credito=d.get('limite_credito', 0),
            dias_credito_predeterminado=d.get('dias_credito_predeterminado', 15)
        )
        return jsonify({"message": "ok", "id": res}) if ok else (jsonify({"error": res}), 400)
    else:
        return jsonify(cartera_service.obtener_clientes(nid))

@app.route('/api/diagnostico')
@login_required
def get_diagnostico():
    nid = session['negocio_id']
    diag = financiero_service.obtener_diagnostico_inteligencia(nid)
    return jsonify(diag)

# ==========================
# API: CARGUE MASIVO (PLANTILLAS, CSV Y GOOGLE SHEETS)
# ==========================

@app.route('/api/plantilla/<tipo>')
@login_required
def descargar_plantilla(tipo):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    fmt = request.args.get('fmt', 'xlsx').lower()

    if tipo == 'productos':
        headers = ['Nombre del Producto', 'Precio de Venta', 'Codigo', 'Categoria', 'Tipo']
        data_rows = [
            ['Hamburguesa Clasica', 18900, 'PROD-001', 'Comidas', 'TRANSFORMADO'],
            ['Gaseosa 350ml', 4500, 'PROD-002', 'Bebidas', 'DIRECTO']
        ]
        base_name = 'plantilla_cargue_productos'
    elif tipo == 'inventario':
        headers = ['Nombre del Insumo', 'Unidad de Medida', 'Costo Unitario Base', 'Stock Inicial', 'Stock Minimo']
        data_rows = [
            ['Carne de Res Molida', 'gramos', 25, 5000, 500],
            ['Pan de Hamburguesa', 'unidades', 800, 100, 10]
        ]
        base_name = 'plantilla_cargue_inventario'
    else:
        headers = ['Fecha (YYYY-MM-DD)', 'Producto Nombre', 'Cantidad', 'Metodo Pago', 'Total']
        data_rows = [
            [datetime.now().strftime("%Y-%m-%d"), 'Hamburguesa Clasica', 1, 'EFECTIVO', 18900]
        ]
        base_name = 'plantilla_cargue_ventas'

    if fmt == 'csv':
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow(headers)
        for row in data_rows:
            writer.writerow(row)
        output.seek(0)
        csv_bytes = ('\ufeff' + output.getvalue()).encode('utf-8')
        return Response(
            csv_bytes,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-disposition": f"attachment; filename={base_name}.csv"}
        )
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Cargue Masivo"

        header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='0EA5E9', end_color='0EA5E9', fill_type='solid')
        align_center = Alignment(horizontal='center', vertical='center')

        ws.append(headers)
        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_num)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = align_center

        for row in data_rows:
            ws.append(row)

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        out_stream = io.BytesIO()
        wb.save(out_stream)
        out_stream.seek(0)

        return Response(
            out_stream.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-disposition": f"attachment; filename={base_name}.xlsx"}
        )

@app.route('/api/importar/csv', methods=['POST'])
@login_required
def importar_csv():
    import openpyxl
    nid = session['negocio_id']
    tipo_importacion = request.form.get('tipo', 'productos')

    if 'file' not in request.files:
        return jsonify({"error": "No se adjuntó ningún archivo"}), 400

    file = request.files['file']
    filename = (file.filename or '').lower()

    rows = []
    try:
        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            wb = openpyxl.load_workbook(file.stream, data_only=True)
            ws = wb.active
            for r in ws.iter_rows(values_only=True):
                if r and any(cell is not None for cell in r):
                    rows.append([str(cell).strip() if cell is not None else '' for cell in r])
        else:
            content = file.stream.read().decode('utf-8-sig', errors='ignore')
            first_line = content.splitlines()[0] if content.splitlines() else ''
            delimiter = ';' if ';' in first_line else (',' if ',' in first_line else '\t')

            reader = csv.reader(io.StringIO(content), delimiter=delimiter)
            rows = list(reader)

        if len(rows) <= 1:
            return jsonify({"error": "El archivo está vacío o solo contiene la fila de encabezados"}), 400

        imported_count = 0
        for row in rows[1:]:
            if not row or not any(row): continue

            if tipo_importacion == 'productos':
                nombre = str(row[0]).strip() if len(row) > 0 else ''
                try:
                    precio = float(str(row[1]).replace('$', '').replace('.', '').replace(',', '.').strip()) if len(row) > 1 and str(row[1]).strip() else 0.0
                except:
                    precio = 0.0
                codigo = str(row[2]).strip() if len(row) > 2 else None
                cat = str(row[3]).strip() if len(row) > 3 else 'General'
                tipo_p = str(row[4]).strip() if len(row) > 4 else 'TRANSFORMADO'

                if nombre:
                    ejecutar_query(
                        "INSERT INTO productos (negocio_id, nombre, precio, codigo, categoria, tipo_producto) VALUES (?, ?, ?, ?, ?, ?)",
                        (nid, nombre, precio, codigo, cat, tipo_p)
                    )
                    imported_count += 1

            elif tipo_importacion == 'inventario':
                nombre = str(row[0]).strip() if len(row) > 0 else ''
                unidad = str(row[1]).strip() if len(row) > 1 else 'unidades'
                try:
                    costo = float(str(row[2]).replace('$', '').replace('.', '').replace(',', '.').strip()) if len(row) > 2 and str(row[2]).strip() else 0.0
                except:
                    costo = 0.0
                try:
                    stock = float(str(row[3]).strip()) if len(row) > 3 and str(row[3]).strip() else 0.0
                except:
                    stock = 0.0
                try:
                    st_min = float(str(row[4]).strip()) if len(row) > 4 and str(row[4]).strip() else 5.0
                except:
                    st_min = 5.0

                if nombre:
                    ejecutar_query(
                        "INSERT INTO inventario (negocio_id, nombre, unidad_base, costo_unitario_base, stock_actual, stock_inicial, stock_minimo) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (nid, nombre, unidad, costo, stock, stock, st_min)
                    )
                    imported_count += 1

            elif tipo_importacion == 'ventas':
                fecha_val = str(row[0]).strip() if len(row) > 0 and str(row[0]).strip() else datetime.now().strftime("%Y-%m-%d")
                prod_name = str(row[1]).strip() if len(row) > 1 else ''
                try:
                    cant_val = float(str(row[2]).strip()) if len(row) > 2 and str(row[2]).strip() else 1.0
                except:
                    cant_val = 1.0
                metodo_val = str(row[3]).strip() if len(row) > 3 and str(row[3]).strip() else 'Efectivo'

                if prod_name:
                    p_res = ejecutar_query("SELECT id FROM productos WHERE LOWER(nombre)=LOWER(?) AND negocio_id=?", (prod_name, nid), fetch=True)
                    if p_res:
                        pid = p_res[0][0]
                    else:
                        try:
                            total_val = float(str(row[4]).replace('$', '').replace('.', '').replace(',', '.').strip()) if len(row) > 4 and str(row[4]).strip() else 0.0
                        except:
                            total_val = 0.0
                        unit_price = total_val / cant_val if cant_val > 0 else total_val
                        ejecutar_query("INSERT INTO productos (negocio_id, nombre, precio, tipo_producto) VALUES (?, ?, ?, 'TRANSFORMADO')", (nid, prod_name, unit_price))
                        pid_res = ejecutar_query("SELECT id FROM productos WHERE nombre=? AND negocio_id=? ORDER BY id DESC LIMIT 1", (prod_name, nid), fetch=True)
                        pid = pid_res[0][0] if pid_res else 1

                    s, r = ventas_service.registrar_venta(pid, cant_val, metodo_val, session['user_id'], nid, fecha_custom=fecha_val)
                    if s:
                        imported_count += 1

        return jsonify({"message": f"¡Éxito! Se importaron {imported_count} registros correctamente."})
    except Exception as e:
        return jsonify({"error": f"Error procesando el archivo: {str(e)}"}), 500

@app.route('/api/importar/google-sheets', methods=['POST'])
@login_required
def importar_google_sheets():
    nid = session['negocio_id']
    d = request.json
    url = (d.get('url') or '').strip()
    tipo_importacion = d.get('tipo', 'productos')

    if not url:
        return jsonify({"error": "Debe proporcionar la URL de la hoja de Google Sheets"}), 400

    try:
        if 'docs.google.com/spreadsheets' in url and '/export?' not in url:
            sheet_id = url.split('/d/')[1].split('/')[0]
            csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        else:
            csv_url = url

        req = urllib.request.Request(csv_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            csv_data = response.read().decode('utf-8-sig', errors='ignore')

        reader = csv.reader(io.StringIO(csv_data))
        rows = list(reader)
        if len(rows) <= 1:
            return jsonify({"error": "La hoja de Google Sheets está vacía o no tiene acceso público"}), 400

        imported_count = 0
        for row in rows[1:]:
            if not row or not any(row): continue

            if tipo_importacion == 'productos':
                nombre = row[0].strip() if len(row) > 0 else ''
                try:
                    precio = float(row[1].replace('$', '').replace(',', '').strip()) if len(row) > 1 and row[1].strip() else 0.0
                except:
                    precio = 0.0
                codigo = row[2].strip() if len(row) > 2 else None
                cat = row[3].strip() if len(row) > 3 else 'General'

                if nombre:
                    ejecutar_query(
                        "INSERT INTO productos (negocio_id, nombre, precio, codigo, categoria) VALUES (?, ?, ?, ?, ?)",
                        (nid, nombre, precio, codigo, cat)
                    )
                    imported_count += 1
            elif tipo_importacion == 'inventario':
                nombre = row[0].strip() if len(row) > 0 else ''
                unidad = row[1].strip() if len(row) > 1 else 'unidades'
                try:
                    costo = float(row[2].replace('$', '').replace(',', '').strip()) if len(row) > 2 and row[2].strip() else 0.0
                except:
                    costo = 0.0
                try:
                    stock = float(row[3].strip()) if len(row) > 3 and row[3].strip() else 0.0
                except:
                    stock = 0.0

                if nombre:
                    ejecutar_query(
                        "INSERT INTO inventario (negocio_id, nombre, unidad_base, costo_unitario_base, stock_actual, stock_inicial) VALUES (?, ?, ?, ?, ?, ?)",
                        (nid, nombre, unidad, costo, stock, stock)
                    )
                    imported_count += 1
            elif tipo_importacion == 'ventas':
                fecha_val = row[0].strip() if len(row) > 0 and row[0].strip() else datetime.now().strftime("%Y-%m-%d")
                prod_name = row[1].strip() if len(row) > 1 else ''
                try:
                    cant_val = float(row[2].strip()) if len(row) > 2 and row[2].strip() else 1.0
                except:
                    cant_val = 1.0
                metodo_val = row[3].strip() if len(row) > 3 and row[3].strip() else 'Efectivo'

                if prod_name:
                    p_res = ejecutar_query("SELECT id FROM productos WHERE LOWER(nombre)=LOWER(?) AND negocio_id=?", (prod_name, nid), fetch=True)
                    if p_res:
                        pid = p_res[0][0]
                    else:
                        try:
                            total_val = float(row[4].replace('$', '').replace(',', '').strip()) if len(row) > 4 and row[4].strip() else 0.0
                        except:
                            total_val = 0.0
                        unit_price = total_val / cant_val if cant_val > 0 else total_val
                        ejecutar_query("INSERT INTO productos (negocio_id, nombre, precio, tipo_producto) VALUES (?, ?, ?, 'TRANSFORMADO')", (nid, prod_name, unit_price))
                        pid_res = ejecutar_query("SELECT id FROM productos WHERE nombre=? AND negocio_id=? ORDER BY id DESC LIMIT 1", (prod_name, nid), fetch=True)
                        pid = pid_res[0][0] if pid_res else 1

                    s, r = ventas_service.registrar_venta(pid, cant_val, metodo_val, session['user_id'], nid, fecha_custom=fecha_val)
                    if s:
                        imported_count += 1

        c_res = ejecutar_query("SELECT id FROM configuracion_negocio WHERE negocio_id=?", (nid,), fetch=True)
        if c_res:
            ejecutar_query("UPDATE configuracion_negocio SET sheet_url_ventas=? WHERE negocio_id=?", (url, nid))
        else:
            ejecutar_query("INSERT INTO configuracion_negocio (negocio_id, sheet_url_ventas, nombre_comercial, tipo_operacion) VALUES (?, ?, 'Mi Negocio', 'HÍBRIDO')", (nid, url))

        return jsonify({"message": f"¡Sincronización exitosa! Se cargaron {imported_count} filas desde Google Sheets."})
    except Exception as e:
        return jsonify({"error": f"No se pudo descargar la hoja de Google Sheets. Asegúrate de compartirla como pública ('Cualquier persona con el enlace'): {str(e)}"}), 500

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
    try:
        if request.method == 'POST':
            d = request.json
            plan = d.get('plan', 'FREE')
            hoy = datetime.now()
            vence = (hoy + timedelta(days=365 if plan == 'PRO' else 7)).strftime("%Y-%m-%d")

            ejecutar_query("INSERT INTO negocios (nombre, status, plan, fecha_registro, fecha_vencimiento, trial_activo) VALUES (?,?,?,?,?,?)",
                           (d['nombre'], 'ACTIVO', plan, hoy.strftime("%Y-%m-%d"), vence, 1 if plan == 'FREE' else 0))
            nid_res = ejecutar_query("SELECT id FROM negocios WHERE nombre=? ORDER BY id DESC LIMIT 1", (d['nombre'],), fetch=True)
            nid = nid_res[0][0] if nid_res else 1
            # Crear primer Admin
            admin_user = (d.get('admin_user') or '').strip()
            admin_pass = (d.get('admin_pass') or '').strip()
            ejecutar_query("INSERT INTO usuarios (negocio_id, username, password, role) VALUES (?,?,?,?)", (nid, admin_user, admin_pass, 'ADMIN'))
            # Crear config inicial
            ejecutar_query("INSERT INTO configuracion_negocio (negocio_id, nombre_comercial, tipo_operacion) VALUES (?, ?, 'HÍBRIDO')", (nid, d['nombre']))
            return jsonify({"message": "Nuevo cliente registrado exitosamente"})
        else:
            # Asegurar asignación de samuel_super a Empresa Maestra si no tiene usuario vinculado
            n_maestra = ejecutar_query("SELECT id FROM negocios WHERE LOWER(nombre)='empresa maestra' ORDER BY id ASC LIMIT 1", fetch=True)
            if n_maestra:
                nid_m = n_maestra[0][0]
                u_m = ejecutar_query("SELECT id FROM usuarios WHERE negocio_id=? LIMIT 1", (nid_m,), fetch=True)
                if not u_m:
                    ejecutar_query("UPDATE usuarios SET negocio_id=? WHERE LOWER(username)='samuel_super'", (nid_m,))

            res = ejecutar_query("""
                SELECT n.id, n.nombre, n.status, n.plan, n.fecha_vencimiento,
                       COALESCE(
                           (SELECT username FROM usuarios WHERE negocio_id = n.id AND role = 'ADMIN' LIMIT 1),
                           (SELECT username FROM usuarios WHERE negocio_id = n.id LIMIT 1),
                           'samuel_super'
                       ) as admin_user
                FROM negocios n
            """, fetch=True)
            if not res:
                return jsonify([])
            out = []
            for x in res:
                out.append({
                    "id": x[0],
                    "nombre": x[1] or "Sin nombre",
                    "status": x[2] or "ACTIVO",
                    "plan": x[3] or "FREE",
                    "fecha_vencimiento": x[4] if len(x) > 4 and x[4] else "N/A",
                    "admin_user": x[5] if len(x) > 5 and x[5] else "samuel_super"
                })
            return jsonify(out)
    except Exception as e:
        print(f"Error super negocios: {e}", file=sys.stderr)
        return jsonify({"error": str(e)}), 500

@app.route('/api/super/negocio/<int:negocio_id>/update', methods=['POST'])
@login_required
@super_required
def update_super_negocio(negocio_id):
    d = request.json
    plan = d.get('plan')
    status = d.get('status')
    dias_pro = d.get('dias_pro', 30)

    if plan:
        if plan == 'PRO':
            nueva_fecha = (datetime.now() + timedelta(days=int(dias_pro))).strftime("%Y-%m-%d")
            ejecutar_query("UPDATE negocios SET plan='PRO', fecha_vencimiento=?, trial_activo=0 WHERE id=?", (nueva_fecha, negocio_id))
        else:
            ejecutar_query("UPDATE negocios SET plan='FREE' WHERE id=?", (negocio_id,))

    if status:
        ejecutar_query("UPDATE negocios SET status=? WHERE id=?", (status, negocio_id))

    return jsonify({"message": "Negocio actualizado correctamente"})

@app.route('/api/super/negocio/<int:negocio_id>/reset_password', methods=['POST'])
@login_required
@super_required
def reset_admin_password(negocio_id):
    try:
        d = request.json
        new_pass = (d.get('new_password') or '').strip()
        new_user = (d.get('new_username') or '').strip()
        if not new_pass:
            return jsonify({"error": "Contraseña requerida"}), 400

        if new_user:
            ejecutar_query("UPDATE usuarios SET username=?, password=? WHERE negocio_id=? AND role='ADMIN'", (new_user, new_pass, negocio_id))
        else:
            ejecutar_query("UPDATE usuarios SET password=? WHERE negocio_id=? AND role='ADMIN'", (new_pass, negocio_id))

        return jsonify({"message": "Credenciales actualizadas exitosamente"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================
# API: TICKETS DE SOPORTE Y ESCALAMIENTO
# ==========================

@app.route('/api/soporte/ticket', methods=['POST'])
@login_required
def crear_ticket_soporte():
    try:
        nid = session['negocio_id']
        uid = session['user_id']
        d = request.json
        pregunta = (d.get('pregunta') or '').strip()
        modulo = (d.get('modulo') or '/').strip()
        respuesta_bot = (d.get('respuesta_bot') or '').strip()
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not pregunta:
            return jsonify({"error": "Debe ingresar una pregunta"}), 400

        ejecutar_query(
            """INSERT INTO tickets_soporte (negocio_id, usuario_id, fecha, modulo, pregunta, respuesta_bot, estado)
               VALUES (?, ?, ?, ?, ?, ?, 'PENDIENTE')""",
            (nid, uid, fecha, modulo, pregunta, respuesta_bot)
        )

        return jsonify({"message": "Ticket registrado con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/super/tickets')
@login_required
@super_required
def get_super_tickets():
    try:
        tickets = ejecutar_query(
            """SELECT t.id, n.nombre, u.username, t.fecha, t.modulo, t.pregunta, t.respuesta_bot, t.estado, t.respuesta_admin
               FROM tickets_soporte t
               LEFT JOIN negocios n ON t.negocio_id = n.id
               LEFT JOIN usuarios u ON t.usuario_id = u.id
               ORDER BY t.id DESC LIMIT 100""",
            fetch=True
        ) or []

        return jsonify([{
            "id": x[0],
            "negocio": x[1] or "Negocio",
            "usuario": x[2] or "Usuario",
            "fecha": x[3],
            "modulo": x[4],
            "pregunta": x[5],
            "respuesta_bot": x[6],
            "estado": x[7],
            "respuesta_admin": x[8] or ""
        } for x in tickets])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/super/ticket/<int:ticket_id>/responder', methods=['POST'])
@login_required
@super_required
def responder_ticket_soporte(ticket_id):
    try:
        d = request.json
        respuesta = (d.get('respuesta') or '').strip()
        if not respuesta:
            return jsonify({"error": "Debe ingresar una respuesta"}), 400

        ejecutar_query(
            "UPDATE tickets_soporte SET respuesta_admin=?, estado='RESUELTO' WHERE id=?",
            (respuesta, ticket_id)
        )
        return jsonify({"message": "Respuesta enviada y ticket resuelto"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.context_processor
def inject_global_info():
    if 'negocio_id' in session:
        return get_negocio_status_ext(session['negocio_id'])
    return {"plan": "FREE", "dias_restantes": 0, "es_trial": False}

if __name__ == '__main__':
    app.run(debug=True, port=5000)
