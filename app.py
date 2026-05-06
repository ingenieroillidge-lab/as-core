from flask import Flask, jsonify, request, render_template, session, redirect, url_for
import services.ventas_service as ventas_service
import services.inventario_service as inventario_service
import services.financiero_service as financiero_service
from database import conectar, crear_tablas, ejecutar_query
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = "as_platform_high_conversion_2024"

crear_tablas()

# ==========================
# LÓGICA DE CONVERSIÓN REFINADA
# ==========================

def get_negocio_status_ext(negocio_id):
    res = ejecutar_query("SELECT plan, fecha_vencimiento, trial_activo FROM negocios WHERE id=?", (negocio_id,), fetch=True)
    if not res: return None
    plan, vence, trial = res[0]
    
    dias = 0
    if vence:
        dias = (datetime.strptime(vence, "%Y-%m-%d") - datetime.now()).days
    
    # Mensaje dinámico para el banner
    banner_msg = "Estás en PRO Trial 🚀"
    if dias <= 1: banner_msg = "Último día — desbloquea tu rentabilidad ⏳"
    elif dias <= 3: banner_msg = f"Te quedan {dias} días — no pierdas tu análisis 📊"
    
    return {
        "plan": plan, 
        "dias": max(0, dias), 
        "es_trial": bool(trial),
        "banner_msg": banner_msg
    }

@app.context_processor
def inject_global_info():
    if 'negocio_id' in session:
        return get_negocio_status_ext(session['negocio_id'])
    return {}

# ==========================
# API: SUPER ADMIN (ANÁLISIS MAESTRO)
# ==========================

@app.route('/api/super/stats')
@login_required
@super_required
def get_super_stats():
    # 1. Conteo de Negocios por Plan
    res_neg = ejecutar_query("SELECT plan, COUNT(*) FROM negocios GROUP BY plan", fetch=True)
    stats = {x[0]: x[1] for x in res_neg}
    
    # 2. Usuarios "Calientes" (Los que más chocan con el muro)
    hot_leads = ejecutar_query("""
        SELECT n.nombre, n.intentos_pro_bloqueados 
        FROM negocios n 
        ORDER BY n.intentos_pro_bloqueados DESC LIMIT 5
    """, fetch=True)
    
    # 3. Proyección de Ingresos (MRR)
    pro_clients = stats.get('PRO', 0)
    mrr = pro_clients * 24900
    
    return jsonify({
        "total_negocios": sum(stats.values()),
        "planes": stats,
        "mrr_proyectado": mrr,
        "hot_leads": [{"nombre": x[0], "intentos": x[1]} for x in hot_leads]
    })

# ==========================
# API: RESUMEN CON PREVIEW (BLUR)
# ==========================

@app.route('/api/resumen')
@login_required
def g_res():
    status = get_negocio_status_ext(session['negocio_id'])
    data = financiero_service.obtener_resumen_financiero(session['negocio_id'], request.args.get('mes'))
    
    # Contador de cuotas para las barras de tensión
    count_prod = ejecutar_query("SELECT COUNT(*) FROM productos WHERE negocio_id=?", (session['negocio_id'],), fetch=True)[0][0]
    
    response = {
        "ingresos": data['ingresos'],
        "utilidad": data['utilidad'],
        "margen": data['margen_contribucion'],
        "punto_equilibrio": data['punto_equilibrio'],
        "is_locked": (status['plan'] == 'FREE'),
        "cuotas": {
            "productos": count_prod,
            "productos_max": 10
        }
    }
    return jsonify(response)

# [El resto de rutas y webhooks se mantienen...]
if __name__ == '__main__':
    app.run(debug=True, port=5000)
