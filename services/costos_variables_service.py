from database import ejecutar_query

def obtener_costos_variables(negocio_id, incluir_inactivos=False):
    sql = "SELECT id, concepto, tipo_calculo, base_calculo, valor, estado, observaciones FROM costos_variables WHERE negocio_id=?"
    if not incluir_inactivos:
        sql += " AND estado = 'ACTIVO'"
    sql += " ORDER BY id DESC"
    
    res = ejecutar_query(sql, (negocio_id,), fetch=True) or []
    return [{
        "id": x[0],
        "concepto": x[1],
        "tipo_calculo": x[2] or "POR_UNIDAD",
        "base_calculo": x[3] or "COSTO",
        "valor": x[4] or 0.0,
        "estado": x[5] or "ACTIVO",
        "observaciones": x[6] or ""
    } for x in res]

def crear_costo_variable(negocio_id, concepto, tipo_calculo, base_calculo, valor, observaciones=""):
    concepto = (concepto or '').strip()
    if not concepto:
        return False, "El concepto del costo variable es obligatorio"
    
    valor = float(valor or 0.0)
    tipo_calculo = (tipo_calculo or 'POR_UNIDAD').strip().upper()
    base_calculo = (base_calculo or 'COSTO').strip().upper()

    ejecutar_query(
        """INSERT INTO costos_variables (negocio_id, concepto, tipo_calculo, base_calculo, valor, estado, observaciones)
           VALUES (?, ?, ?, ?, ?, 'ACTIVO', ?)""",
        (negocio_id, concepto, tipo_calculo, base_calculo, valor, observaciones)
    )
    return True, "Costo variable registrado con éxito"

def actualizar_costo_variable(costo_id, negocio_id, concepto, tipo_calculo, base_calculo, valor, estado="ACTIVO", observaciones=""):
    res = ejecutar_query("SELECT id FROM costos_variables WHERE id=? AND negocio_id=?", (costo_id, negocio_id), fetch=True)
    if not res:
        return False, "Costo variable no encontrado"

    concepto = (concepto or '').strip()
    valor = float(valor or 0.0)

    ejecutar_query(
        """UPDATE costos_variables 
           SET concepto=?, tipo_calculo=?, base_calculo=?, valor=?, estado=?, observaciones=?
           WHERE id=? AND negocio_id=?""",
        (concepto, tipo_calculo, base_calculo, valor, estado, observaciones, costo_id, negocio_id)
    )
    return True, "Costo variable actualizado con éxito"

def desactivar_o_eliminar_costo_variable(costo_id, negocio_id):
    """
    Si el costo variable tiene trazabilidad histórica o asociaciones, realiza un borrado lógico (estado = INACTIVO).
    """
    res = ejecutar_query("SELECT id, concepto FROM costos_variables WHERE id=? AND negocio_id=?", (costo_id, negocio_id), fetch=True)
    if not res:
        return False, "Costo variable no encontrado"

    # Soft-delete por seguridad contable
    ejecutar_query("UPDATE costos_variables SET estado='INACTIVO' WHERE id=? AND negocio_id=?", (costo_id, negocio_id))
    return True, f"Costo variable '{res[0][1]}' desactivado exitosamente (conservado para historial)"

def calcular_costo_variable_unitario(costo_obj, costo_base_unitario=0.0, precio_venta_unitario=0.0, unidades_lote=1.0):
    """
    Calcula el impacto unitario según método (POR_UNIDAD, POR_PEDIDO, PORCENTAJE, VALOR_FIJO)
    y base de cálculo (COSTO, VENTA, PEDIDO).
    """
    tipo = (costo_obj.get('tipo_calculo') or 'POR_UNIDAD').upper()
    base = (costo_obj.get('base_calculo') or 'COSTO').upper()
    val = float(costo_obj.get('valor', 0.0))
    unidades = max(1.0, float(unidades_lote or 1.0))

    if tipo == 'POR_UNIDAD' or tipo == 'VALOR_FIJO':
        return val
    elif tipo == 'POR_PEDIDO':
        # Distribuido entre el total de unidades del pedido/lote
        return val / unidades
    elif tipo == 'PORCENTAJE':
        base_val = costo_base_unitario if base == 'COSTO' else precio_venta_unitario
        return base_val * (val / 100.0)
    return val
