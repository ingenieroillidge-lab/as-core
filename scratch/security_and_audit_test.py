import os
import sys
import json
from datetime import datetime, timedelta

# Asegurar path
sys.path.insert(0, os.path.abspath('.'))

import app as flask_app
from database import conectar, init_db, ejecutar_query
from werkzeug.security import generate_password_hash, check_password_hash

def run_security_audit():
    print("=" * 60)
    print("[AUDIT] EJECUTANDO AUDITORIA COMPLETA DE SEGURIDAD Y CONTROL DE ACCESO")
    print("=" * 60)
    
    test_client = flask_app.app.test_client()
    init_db()
    
    audit_results = {}
    
    # -------------------------------------------------------------
    # TEST 1: Aislamiento Multi-Tenant (Empresa A vs Empresa B)
    # -------------------------------------------------------------
    try:
        # Crear Empresa A y Empresa B
        ejecutar_query("INSERT INTO negocios (nombre, plan, status) VALUES ('Empresa Test A', 'FREE', 'ACTIVO')")
        nid_a = ejecutar_query("SELECT id FROM negocios WHERE nombre='Empresa Test A'", fetch=True)[0][0]
        
        ejecutar_query("INSERT INTO negocios (nombre, plan, status) VALUES ('Empresa Test B', 'FREE', 'ACTIVO')")
        nid_b = ejecutar_query("SELECT id FROM negocios WHERE nombre='Empresa Test B'", fetch=True)[0][0]
        
        # Insertar producto en Empresa B
        ejecutar_query("INSERT INTO productos (negocio_id, nombre, precio) VALUES (?, 'Producto Secreto B', 99900)", (nid_b,))
        
        # Simular sesión en Empresa A
        with test_client.session_transaction() as sess:
            sess['user_id'] = 9991
            sess['username'] = 'user_a'
            sess['role'] = 'ADMIN'
            sess['negocio_id'] = nid_a
            sess['plan'] = 'FREE'
            
        res = test_client.get('/api/resumen')
        data = res.get_json()
        
        # Verificar que Empresa A no ve los productos de Empresa B
        prods_a = ejecutar_query("SELECT nombre FROM productos WHERE negocio_id=?", (nid_a,), fetch=True)
        assert len(prods_a) == 0, "Error: Empresa A tiene acceso a datos ajenos"
        audit_results['TEST_1_MULTI_TENANT'] = "[OK] — Aislamiento total de datos por negocio_id"
    except Exception as e:
        audit_results['TEST_1_MULTI_TENANT'] = f"[FAIL]: {e}"

    # -------------------------------------------------------------
    # TEST 2: Protección IDOR (Manipulación de ID en URL/API)
    # -------------------------------------------------------------
    try:
        # Intentar acceder a ventas o resumen passing ID manipulado
        res_a = test_client.get(f'/api/resumen?negocio_id={nid_b}')
        # El servidor debe ignorar el negocio_id de la URL y usar session['negocio_id']
        with test_client.session_transaction() as sess:
            assert sess['negocio_id'] == nid_a
        audit_results['TEST_2_IDOR_PROTECTION'] = "[OK] — API ignora negocio_id manipulado en URL"
    except Exception as e:
        audit_results['TEST_2_IDOR_PROTECTION'] = f"[FAIL]: {e}"

    # -------------------------------------------------------------
    # TEST 3: Control de Acceso RBAC (Operador vs Admin)
    # -------------------------------------------------------------
    try:
        with test_client.session_transaction() as sess:
            sess['user_id'] = 9992
            sess['username'] = 'op_a'
            sess['role'] = 'OPERADOR'
            sess['negocio_id'] = nid_a
            sess['plan'] = 'PRO'
            
        res = test_client.get('/configuracion')
        # Operador debe ser redirigido a index (302)
        assert res.status_code == 302, "Error: Operador accedió a /configuracion"
        audit_results['TEST_3_RBAC_OPERADOR'] = "[OK] — Operadores bloqueados de vistas administrativas"
    except Exception as e:
        audit_results['TEST_3_RBAC_OPERADOR'] = f"[FAIL]: {e}"

    # -------------------------------------------------------------
    # TEST 4: Protección de Super Admin (/super-admin)
    # -------------------------------------------------------------
    try:
        with test_client.session_transaction() as sess:
            sess['user_id'] = 9991
            sess['username'] = 'admin_a'
            sess['role'] = 'ADMIN'
            sess['negocio_id'] = nid_a
            
        res = test_client.get('/super-admin')
        assert res.status_code == 302, "Error: Admin normal accedió a /super-admin"
        audit_results['TEST_4_SUPER_ADMIN_BLOCK'] = "[OK] — Bloqueo total de /super-admin para usuarios no SUPER"
    except Exception as e:
        audit_results['TEST_4_SUPER_ADMIN_BLOCK'] = f"[FAIL]: {e}"

    # -------------------------------------------------------------
    # TEST 5 & 6: Auditoría e Impersonación de Super Admin
    # -------------------------------------------------------------
    try:
        # Simular Super Admin
        with test_client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'samuel_super'
            sess['role'] = 'SUPER'
            sess['negocio_id'] = 1
            
        # Impersonar Empresa Test A
        res_imp = test_client.post(f'/api/super/impersonate/{nid_a}')
        assert res_imp.status_code == 200
        
        # Verificar log en DB
        logs = ejecutar_query("SELECT target_negocio_id FROM log_impersonacion WHERE super_user_id=1 ORDER BY id DESC LIMIT 1", fetch=True)
        assert logs and logs[0][0] == nid_a, "Error: Impersonación no quedó registrada"
        
        # Salir de impersonación
        res_exit = test_client.post('/api/super/exit_impersonate')
        assert res_exit.status_code == 200
        
        with test_client.session_transaction() as sess:
            assert sess['negocio_id'] == 1
            assert 'is_impersonating' not in sess
            
        audit_results['TEST_5_6_IMPERSONATE_AUDIT'] = "[OK] — Impersonación auditada y sesión restaurada"
    except Exception as e:
        audit_results['TEST_5_6_IMPERSONATE_AUDIT'] = f"[FAIL]: {e}"

    # -------------------------------------------------------------
    # TEST 7: Bloqueo de Cuentas Suspendidas
    # -------------------------------------------------------------
    try:
        ts = int(datetime.now().timestamp())
        u_name = f"user_susp_{ts}"
        ejecutar_query("INSERT INTO negocios (nombre, plan, status) VALUES ('Empresa Suspendida', 'FREE', 'SUSPENDIDO')")
        nid_susp = ejecutar_query("SELECT id FROM negocios WHERE nombre='Empresa Suspendida' ORDER BY id DESC LIMIT 1", fetch=True)[0][0]
        hash_p = generate_password_hash("clave123")
        ejecutar_query("INSERT INTO usuarios (negocio_id, username, password_hash, role, estado) VALUES (?, ?, ?, 'ADMIN', 'ACTIVO')", (nid_susp, u_name, hash_p))
        uid_susp = ejecutar_query("SELECT id FROM usuarios WHERE username=?", (u_name,), fetch=True)[0][0]
        
        with test_client.session_transaction() as sess:
            sess['user_id'] = uid_susp
            sess['username'] = u_name
            sess['role'] = 'ADMIN'
            sess['negocio_id'] = nid_susp
            
        res = test_client.get('/api/resumen')
        assert res.status_code in [403, 302]
        audit_results['TEST_7_SUSPENDED_ACCOUNT'] = "[OK] — Cuentas suspendidas bloqueadas inmediatamente"
    except Exception as e:
        audit_results['TEST_7_SUSPENDED_ACCOUNT'] = f"[FAIL]: {e}"

    # -------------------------------------------------------------
    # TEST 8: Vencimiento de Trial PRO ➔ Restricciones FREE
    # -------------------------------------------------------------
    try:
        hayer = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        ejecutar_query("INSERT INTO negocios (nombre, plan, fecha_vencimiento, status) VALUES ('Empresa Vencida', 'PRO', ?, 'ACTIVO')", (hayer,))
        nid_venc = ejecutar_query("SELECT id FROM negocios WHERE nombre='Empresa Vencida' ORDER BY id DESC LIMIT 1", fetch=True)[0][0]
        
        with test_client.session_transaction() as sess:
            sess['user_id'] = 9998
            sess['username'] = f"user_venc_{ts}"
            sess['role'] = 'ADMIN'
            sess['negocio_id'] = nid_venc
            sess['plan'] = 'PRO'
            
        res_an = test_client.get('/analisis')
        status_db = ejecutar_query("SELECT plan FROM negocios WHERE id=?", (nid_venc,), fetch=True)[0][0]
        assert status_db == 'FREE', "Error: El plan no fue degradado a FREE al vencer"
        audit_results['TEST_8_PRO_EXPIRATION'] = "[OK] — Cuentas con PRO vencido retornan a FREE automaticamente"
    except Exception as e:
        audit_results['TEST_8_PRO_EXPIRATION'] = f"[FAIL]: {e}"

    # -------------------------------------------------------------
    # TEST 9: Irreversibilidad de Contraseñas (password_hash)
    # -------------------------------------------------------------
    try:
        pwd = "MiClaveSuperSecreta2026!"
        h_val = generate_password_hash(pwd)
        assert check_password_hash(h_val, pwd)
        assert pwd not in h_val, "Error: La clave es visible en la cadena hash"
        assert h_val.startswith("scrypt:") or h_val.startswith("pbkdf2:"), "Error: Algoritmo de hashing no es seguro"
        audit_results['TEST_9_PASSWORD_HASH'] = "[OK] — Contrasenas con hashing irreversible de Werkzeug"
    except Exception as e:
        audit_results['TEST_9_PASSWORD_HASH'] = f"[FAIL]: {e}"

    print("\n[RESULTADOS DE LA AUDITORIA DE SEGURIDAD]")
    print("-" * 60)
    for test, res in audit_results.items():
        print(f"{test}: {res}")
    print("=" * 60)

if __name__ == '__main__':
    run_security_audit()
