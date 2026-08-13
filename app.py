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

        c_res = ejecutar_query("SELECT id FROM configuracion_negocio WHERE negocio_id=?", (nid,), fetch=True)
        if c_res:
            ejecutar_query("UPDATE configuracion_negocio SET nombre_comercial=?, tipo_operacion=?, sheet_url_ventas=?, color_acento=?, maneja_cartera=? WHERE negocio_id=?", 
                           (nombre, tipo, sheet_url, color, maneja_cartera, nid))
        else:
            ejecutar_query("INSERT INTO configuracion_negocio (negocio_id, nombre_comercial, tipo_operacion, sheet_url_ventas, color_acento, maneja_cartera) VALUES (?, ?, ?, ?, ?, ?)", 
                           (nid, nombre, tipo, sheet_url, color, maneja_cartera))

        ejecutar_query("UPDATE negocios SET nombre=? WHERE id=?", (nombre, nid))
        return jsonify({"message": "ok"})
    else:
        res = ejecutar_query("SELECT nombre_comercial, tipo_operacion, sheet_url_ventas, color_acento, maneja_cartera FROM configuracion_negocio WHERE negocio_id=?", (nid,), fetch=True)
        if res and res[0]:
            return jsonify({
                "nombre": res[0][0] or "Mi Negocio",
                "tipo": res[0][1] or "HÍBRIDO",
                "sheet_url_ventas": res[0][2] or "",
                "color_acento": res[0][3] or "#38bdf8",
                "maneja_cartera": res[0][4] if len(res[0]) > 4 and res[0][4] is not None else 0
            })
        return jsonify({"nombre": "Mi Negocio", "tipo": "HÍBRIDO", "sheet_url_ventas": "", "color_acento": "#38bdf8", "maneja_cartera": 0})

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

# ==========================
# API: CARGUE MASIVO (PLANTILLAS, CSV Y GOOGLE SHEETS)
# ==========================

@app.route('/api/plantilla/<tipo>')
@login_required
def descargar_plantilla(tipo):
    output = io.StringIO()
    writer = csv.writer(output)

    if tipo == 'productos':
        writer.writerow(['Nombre del Producto', 'Precio de Venta', 'Codigo', 'Categoria', 'Tipo'])
        writer.writerow(['Hamburguesa Clasica', '18900', 'PROD-001', 'Comidas', 'TRANSFORMADO'])
        writer.writerow(['Gaseosa 350ml', '4500', 'PROD-002', 'Bebidas', 'DIRECTO'])
        filename = 'plantilla_cargue_productos.csv'
    elif tipo == 'inventario':
        writer.writerow(['Nombre del Insumo', 'Unidad de Medida', 'Costo Unitario Base', 'Stock Inicial', 'Stock Minimo'])
        writer.writerow(['Carne de Res Molida', 'gramos', '25', '5000', '500'])
        writer.writerow(['Pan de Hamburguesa', 'unidades', '800', '100', '10'])
        filename = 'plantilla_cargue_inventario.csv'
    else:
        writer.writerow(['Fecha (YYYY-MM-DD)', 'Producto Nombre', 'Cantidad', 'Metodo Pago', 'Total'])
        writer.writerow([datetime.now().strftime("%Y-%m-%d"), 'Hamburguesa Clasica', '1', 'EFECTIVO', '18900'])
        filename = 'plantilla_cargue_ventas.csv'

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

@app.route('/api/importar/csv', methods=['POST'])
@login_required
def importar_csv():
    nid = session['negocio_id']
    tipo_importacion = request.form.get('tipo', 'productos')

    if 'file' not in request.files:
        return jsonify({"error": "No se adjuntó ningún archivo"}), 400

    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({"error": "Formato no válido. Debe ser un archivo .csv"}), 400

    try:
        content = file.stream.read().decode('utf-8-sig', errors='ignore')
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        if len(rows) <= 1:
            return jsonify({"error": "El archivo CSV está vacío o solo contiene la fila de encabezados"}), 400

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
                tipo_p = row[4].strip() if len(row) > 4 else 'TRANSFORMADO'

                if nombre:
                    ejecutar_query(
                        "INSERT INTO productos (negocio_id, nombre, precio, codigo, categoria, tipo_producto) VALUES (?, ?, ?, ?, ?, ?)",
                        (nid, nombre, precio, codigo, cat, tipo_p)
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
                try:
                    st_min = float(row[4].strip()) if len(row) > 4 and row[4].strip() else 5.0
                except:
                    st_min = 5.0

                if nombre:
                    ejecutar_query(
                        "INSERT INTO inventario (negocio_id, nombre, unidad_base, costo_unitario_base, stock_actual, stock_inicial, stock_minimo) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (nid, nombre, unidad, costo, stock, stock, st_min)
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

        return jsonify({"message": f"¡Éxito! Se importaron {imported_count} registros."})
    except Exception as e:
        return jsonify({"error": f"Error procesando archivo CSV: {str(e)}"}), 500

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
            res = ejecutar_query("""
                SELECT n.id, n.nombre, n.status, n.plan, n.fecha_vencimiento, u.username
                FROM negocios n
                LEFT JOIN usuarios u ON n.id = u.negocio_id AND u.role = 'ADMIN'
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
                    "admin_user": x[5] if len(x) > 5 and x[5] else "N/A"
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

@app.context_processor
def inject_global_info():
    if 'negocio_id' in session:
        return get_negocio_status_ext(session['negocio_id'])
    return {"plan": "FREE", "dias_restantes": 0, "es_trial": False}

if __name__ == '__main__':
    app.run(debug=True, port=5000)
