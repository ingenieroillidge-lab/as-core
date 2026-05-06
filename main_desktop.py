import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from database import conectar, crear_tablas
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from services.financiero_service import obtener_resumen_financiero
from services.ventas_service import registrar_venta
from services.inventario_service import (
    obtener_stock_bajo,
    reponer_stock,
    obtener_inventario,
    obtener_movimientos
)
# crear_tablas() se llamará solo si es ejecución directa


# =====================================================
# 🔹 UTILIDADES BASE DE DATOS
# =====================================================

def ejecutar_query(query, params=(), fetch=False):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(query, params)

    data = None
    if fetch:
        data = cursor.fetchall()

    conn.commit()
    conn.close()
    return data


# =====================================================
# 🔹 FUNCIONES FINANCIERAS
# =====================================================

def obtener_unidades_totales():
    data = ejecutar_query("SELECT SUM(cantidad) FROM ventas", fetch=True)
    return data[0][0] or 0


def calcular_margen_promedio():
    data = ejecutar_query("""
        SELECT 
            SUM(productos.precio * ventas.cantidad),
            SUM(productos.costo_variable * ventas.cantidad)
        FROM ventas
        JOIN productos ON ventas.producto_id = productos.id
    """, fetch=True)

    if not data or not data[0][0]:
        return 0

    ingresos = data[0][0]
    costos = data[0][1]
    unidades = obtener_unidades_totales()

    if unidades == 0:
        return 0

    return (ingresos - costos) / unidades

def verificar_stock_bajo_ui():

    datos = obtener_stock_bajo()

    if not datos:
        messagebox.showinfo("Inventario", "No hay productos con stock bajo.")
        return

    mensaje = "Productos con stock bajo:\n\n"

    for nombre, stock, minimo in datos:
        mensaje += f"{nombre} → {stock} (mínimo {minimo})\n"

    messagebox.showwarning("⚠ Stock Bajo", mensaje)
def registrar_venta_ui():

    if not combo_pago.get():
        messagebox.showwarning("Atención", "Selecciona método de pago")
        return

    producto_id = combo_productos.get().split(" - ")[0]
    cantidad = float(entry_cantidad.get())

    exito, resultado = registrar_venta(
        producto_id,
        cantidad,
        combo_pago.get()
    )

    if not exito:
        messagebox.showerror("Error", resultado)
    else:
        messagebox.showinfo("Venta registrada", f"Total: ${resultado}")
# =====================================================
# 🔹 CRUD PRODUCTOS
# =====================================================

def agregar_producto():
    ejecutar_query(
        "INSERT INTO productos (nombre, precio) VALUES (?, ?)",
        (entry_nombre.get(), float(entry_precio.get()))
    )
    limpiar_campos()
    cargar_productos()
    cargar_tabla_productos()


def limpiar_campos():
    entry_nombre.delete(0, tk.END)
    entry_precio.delete(0, tk.END)
    entry_costo.delete(0, tk.END)


def eliminar_producto():
    selected = tree.selection()
    if not selected:
        messagebox.showwarning("Atención", "Selecciona un producto")
        return

    producto_id = tree.item(selected[0])["values"][0]
    ejecutar_query("DELETE FROM productos WHERE id=?", (producto_id,))
    cargar_tabla_productos()
    cargar_productos()


def editar_producto():
    selected = tree.selection()
    if not selected:
        messagebox.showwarning("Atención", "Selecciona un producto")
        return

    producto_id = tree.item(selected[0])["values"][0]

    ejecutar_query("""
        UPDATE productos
        SET nombre=?, precio=?
        WHERE id=?
    """, (entry_nombre.get(), float(entry_precio.get()), producto_id))

    cargar_tabla_productos()
    cargar_productos()


def cargar_productos():
    data = ejecutar_query("SELECT id, nombre FROM productos", fetch=True)
    combo_productos["values"] = [f"{p[0]} - {p[1]}" for p in data]


def cargar_tabla_productos():
    for row in tree.get_children():
        tree.delete(row)

    data = ejecutar_query("SELECT id, nombre, precio FROM productos", fetch=True)
    for p in data:
        tree.insert("", "end", values=(p[0], p[1], p[2]))

# =====================================================
# 🔹 REPORTES
# =====================================================

def mostrar_resumen():
    ingresos, cv, cf, utilidad, margen, pe = obtener_resumen_financiero()

    label_resumen.config(text=(
        f"Ingresos: ${ingresos}\n"
        f"Costos Variables: ${cv}\n"
        f"Costos Fijos: ${cf}\n"
        f"Utilidad: ${utilidad}\n\n"
        f"Margen Promedio: ${round(margen,2)}\n"
        f"Punto Equilibrio: {round(pe,2)} unidades"
    ))
def cargar_combo_inventario():
    data = ejecutar_query(
        "SELECT id, nombre FROM inventario",
        fetch=True
    )
    combo_reponer["values"] = [f"{i[0]} - {i[1]}" for i in data]

# =====================================================
# 🔹 GRÁFICOS (MULTIPLES)
# =====================================================

def mostrar_grafico_resumen():
    ingresos, cv, cf, utilidad, _, _ = obtener_resumen_financiero()
    costos_totales = cv + cf

    fig = Figure(figsize=(5,3))
    ax = fig.add_subplot(111)

    ax.bar(["Ingresos", "Costos", "Utilidad"],
           [ingresos, costos_totales, utilidad])

    canvas = FigureCanvasTkAgg(fig, master=frame_graficos)
    canvas.draw()
    canvas.get_tk_widget().pack(side="left", padx=10)


def mostrar_tendencia_mensual():
    data = ejecutar_query("""
        SELECT SUBSTR(fecha,1,7), SUM(total)
        FROM ventas
        GROUP BY SUBSTR(fecha,1,7)
        ORDER BY SUBSTR(fecha,1,7)
    """, fetch=True)

    if not data:
        messagebox.showinfo("Info", "No hay datos suficientes")
        return

    meses = [d[0] for d in data]
    ingresos = [d[1] for d in data]

    fig = Figure(figsize=(5,3))
    ax = fig.add_subplot(111)
    ax.plot(meses, ingresos, marker='o')

    canvas = FigureCanvasTkAgg(fig, master=frame_graficos)
    canvas.draw()
    canvas.get_tk_widget().pack(side="left", padx=10)
def cargar_tabla_inventario():

    for row in tree_inv.get_children():
        tree_inv.delete(row)

    data = obtener_inventario()

    for item in data:
        tree_inv.insert("", "end", values=item)
def agregar_insumo():
    ejecutar_query("""
        INSERT INTO inventario 
        (nombre, unidad, stock_actual, stock_minimo, costo_unitario)
        VALUES (?, ?, ?, ?, ?)
    """, (
        entry_inv_nombre.get(),
        entry_inv_unidad.get(),
        float(entry_inv_stock.get()),
        float(entry_inv_min.get()),
        float(entry_inv_costo.get())
    ))

    cargar_tabla_inventario()

def reponer_stock_ui():

    if not combo_reponer.get():
        messagebox.showwarning("Atención", "Selecciona un insumo")
        return

    try:
        cantidad = float(entry_reponer.get())
    except:
        messagebox.showerror("Error", "Cantidad inválida")
        return

    insumo_id = combo_reponer.get().split(" - ")[0]

    reponer_stock(insumo_id, cantidad)

    entry_reponer.delete(0, tk.END)
    cargar_tabla_inventario()

    messagebox.showinfo("Éxito", "Stock actualizado correctamente")
def cargar_combo_movimientos():
    data = ejecutar_query(
        "SELECT id, nombre FROM inventario",
        fetch=True
    )
    combo_filtro_mov["values"] = ["Todos"] + [f"{i[0]} - {i[1]}" for i in data]
    combo_filtro_mov.set("Todos")
def cargar_movimientos_ui():

    for row in tree_mov.get_children():
        tree_mov.delete(row)

    if combo_filtro_mov.get() == "Todos":
        data = obtener_movimientos()
    else:
        insumo_id = combo_filtro_mov.get().split(" - ")[0]
        data = obtener_movimientos(insumo_id)

    for row in data:
        tree_mov.insert("", "end", values=row)
def cargar_combo_productos_rel():
    data = ejecutar_query("SELECT id, nombre FROM productos", fetch=True)
    combo_producto_rel["values"] = [f"{p[0]} - {p[1]}" for p in data]

def cargar_combo_insumos_rel():
    data = ejecutar_query("SELECT id, nombre FROM inventario", fetch=True)
    combo_insumo_rel["values"] = [f"{i[0]} - {i[1]}" for i in data]
def agregar_relacion():
    if not combo_producto_rel.get() or not combo_insumo_rel.get():
        messagebox.showwarning("Atención", "Selecciona producto e insumo")
        return

    try:
        cantidad = float(entry_cantidad_rel.get())
    except:
        messagebox.showerror("Error", "Cantidad inválida")
        return

    producto_id = combo_producto_rel.get().split(" - ")[0]
    insumo_id = combo_insumo_rel.get().split(" - ")[0]

    ejecutar_query("""
        INSERT INTO producto_insumo (producto_id, insumo_id, cantidad_usada)
        VALUES (?, ?, ?)
    """, (producto_id, insumo_id, cantidad))

    entry_cantidad_rel.delete(0, tk.END)

    messagebox.showinfo("Éxito", "Relación creada correctamente")
def actualizar_dashboard():

    # ==========================
    # ESTADO FINANCIERO
    # ==========================

    ingresos, cv, cf, utilidad, margen, pe = obtener_resumen_financiero()

    if utilidad < 0:
        color_fin = "red"
        texto_fin = "🔴 Utilidad Negativa"
    elif utilidad < 100000:
        color_fin = "orange"
        texto_fin = "🟡 Utilidad Baja"
    else:
        color_fin = "green"
        texto_fin = "🟢 Utilidad Saludable"

    label_estado_financiero.config(
        text=f"{texto_fin}\nUtilidad actual: ${round(utilidad,2)}",
        fg=color_fin
    )

    # ==========================
    # ESTADO INVENTARIO
    # ==========================

    data = ejecutar_query("""
        SELECT COUNT(*)
        FROM inventario
        WHERE stock_actual <= stock_minimo
    """, fetch=True)

    productos_criticos = data[0][0]

    if productos_criticos > 0:
        color_inv = "red"
        texto_inv = f"🔴 {productos_criticos} productos en estado crítico"
    else:
        color_inv = "green"
        texto_inv = "🟢 Inventario estable"

    label_estado_inventario.config(
        text=texto_inv,
        fg=color_inv
    )
def generar_cierre():

    fecha = entry_fecha_caja.get()

    for row in tree_caja.get_children():
        tree_caja.delete(row)

    data = ejecutar_query("""
        SELECT metodo_pago, SUM(total)
        FROM ventas
        WHERE fecha = ?
        GROUP BY metodo_pago
    """, (fecha,), fetch=True)

    total_general = 0

    for metodo, total in data:
        tree_caja.insert("", "end", values=(metodo, round(total,2)))
        total_general += total

    label_total_dia.config(
        text=f"Total del día: ${round(total_general,2)}"
    )
def agregar_costo_fijo():
    concepto = entry_cf_concepto.get()
    valor = float(entry_cf_valor.get())
    mes = datetime.now().strftime("%Y-%m")

    ejecutar_query("""
        INSERT INTO costos_fijos (concepto, valor, mes)
        VALUES (?, ?, ?)
    """, (concepto, valor, mes))

    cargar_tabla_costos_fijos()
def cargar_tabla_costos_fijos():
    for row in tree_cf.get_children():
        tree_cf.delete(row)

    mes = datetime.now().strftime("%Y-%m")

    data = ejecutar_query("""
        SELECT concepto, valor, mes
        FROM costos_fijos
        WHERE mes = ?
    """, (mes,), fetch=True)

    for row in data:
        tree_cf.insert("", "end", values=row)
# =====================================================
# 🔹 INTERFAZ
# =====================================================

root = tk.Tk()
root.title("Sistema Contable Pro")
root.geometry("900x600")

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

# ==========================
# COSTOS FIJOS
# ==========================

frame_costos = tk.Frame(notebook)
notebook.add(frame_costos, text="Costos Fijos")

tk.Label(frame_costos, text="Concepto").pack()
entry_cf_concepto = tk.Entry(frame_costos)
entry_cf_concepto.pack(pady=3)

tk.Label(frame_costos, text="Valor").pack()
entry_cf_valor = tk.Entry(frame_costos)
entry_cf_valor.pack(pady=3)

tk.Button(frame_costos, text="Agregar Costo Fijo", command=lambda: agregar_costo_fijo()).pack(pady=5)

tree_cf = ttk.Treeview(frame_costos, columns=("Concepto","Valor","Mes"), show="headings")
tree_cf.heading("Concepto", text="Concepto")
tree_cf.heading("Valor", text="Valor")
tree_cf.heading("Mes", text="Mes")
tree_cf.pack(fill="both", expand=True)

# PRODUCTOS
frame_productos = tk.Frame(notebook)
notebook.add(frame_productos, text="Productos")

tk.Label(frame_productos, text="Nombre del producto").pack()
entry_nombre = tk.Entry(frame_productos)
entry_nombre.pack(pady=3)

tk.Label(frame_productos, text="Precio de venta").pack()
entry_precio = tk.Entry(frame_productos)
entry_precio.pack(pady=3)


tk.Button(frame_productos, text="Agregar", command=agregar_producto).pack()

tree = ttk.Treeview(frame_productos, columns=("ID","Nombre","Precio","Costo","Margen"), show="headings")
for col in ("ID","Nombre","Precio","Costo","Margen"):
    tree.heading(col, text=col)
tree.pack(fill="both", expand=True)

tk.Button(frame_productos, text="Editar", command=editar_producto).pack()
tk.Button(frame_productos, text="Eliminar", command=eliminar_producto).pack()
# ==========================
# PRODUCTO - INSUMO
# ==========================

frame_relaciones = tk.Frame(notebook)
notebook.add(frame_relaciones, text="Recetas / Relaciones")
tk.Label(frame_relaciones, text="Producto").pack()
combo_producto_rel = ttk.Combobox(frame_relaciones)
combo_producto_rel.pack(pady=5)

tk.Label(frame_relaciones, text="Insumo").pack()
combo_insumo_rel = ttk.Combobox(frame_relaciones)
combo_insumo_rel.pack(pady=5)

tk.Label(frame_relaciones, text="Cantidad utilizada").pack()
entry_cantidad_rel = tk.Entry(frame_relaciones)
entry_cantidad_rel.pack(pady=5)

tk.Button(frame_relaciones, text="Agregar Relación", command=lambda: agregar_relacion()).pack(pady=5)

# VENTAS
frame_ventas = tk.Frame(notebook)
notebook.add(frame_ventas, text="Ventas")

combo_productos = ttk.Combobox(frame_ventas)
combo_productos.pack()
entry_cantidad = tk.Entry(frame_ventas)
entry_cantidad.pack()
tk.Button(frame_ventas, text="Registrar", command=registrar_venta_ui).pack()
tk.Label(frame_ventas, text="Método de Pago").pack()
combo_pago = ttk.Combobox(frame_ventas)
combo_pago["values"] = ("Efectivo", "Transferencia", "Tarjeta Crédito", "Tarjeta Débito", "Nequi", "Daviplata")
combo_pago.pack(pady=5)
# ==========================
# INVENTARIO
# ==========================

frame_inventario = tk.Frame(notebook)
notebook.add(frame_inventario, text="Inventario")

tk.Label(frame_inventario, text="Nombre insumo").pack()
entry_inv_nombre = tk.Entry(frame_inventario)
entry_inv_nombre.pack(pady=3)

tk.Label(frame_inventario, text="Unidad (ej: unidad, kg, litro)").pack()
entry_inv_unidad = tk.Entry(frame_inventario)
entry_inv_unidad.pack(pady=3)

tk.Label(frame_inventario, text="Costo unitario").pack()
entry_inv_costo = tk.Entry(frame_inventario)
entry_inv_costo.pack(pady=3)

tk.Label(frame_inventario, text="Stock inicial").pack()
entry_inv_stock = tk.Entry(frame_inventario)
entry_inv_stock.pack(pady=3)

tk.Label(frame_inventario, text="Stock mínimo").pack()
entry_inv_min = tk.Entry(frame_inventario)
entry_inv_min.pack(pady=3)

tk.Button(frame_inventario, text="Agregar Insumo", command=agregar_insumo).pack(pady=5)

tree_inv = ttk.Treeview(
    frame_inventario,
    columns=("ID","Nombre","Unidad","Stock","Minimo","Costo"),
    show="headings"
)

for col in ("ID","Nombre","Unidad","Stock","Minimo","Costo"):
    tree_inv.heading(col, text=col)

tree_inv.pack(fill="both", expand=True, pady=10)
tk.Label(frame_inventario, text="--- Reposición de Stock ---").pack(pady=10)

tk.Label(frame_inventario, text="Seleccionar insumo").pack()
combo_reponer = ttk.Combobox(frame_inventario)
combo_reponer.pack(pady=3)

tk.Label(frame_inventario, text="Cantidad a agregar").pack()
entry_reponer = tk.Entry(frame_inventario)
entry_reponer.pack(pady=3)

tk.Button(frame_inventario, text="Agregar Stock", command=lambda: reponer_stock_ui()).pack(pady=5)

# ==========================
# MOVIMIENTOS INVENTARIO
# ==========================

frame_movimientos = tk.Frame(notebook)
notebook.add(frame_movimientos, text="Movimientos")

tk.Label(frame_movimientos, text="Filtrar por insumo").pack()

combo_filtro_mov = ttk.Combobox(frame_movimientos)
combo_filtro_mov.pack(pady=5)

tk.Button(frame_movimientos, text="Ver Movimientos", command=lambda: cargar_movimientos()).pack(pady=5)

tree_mov = ttk.Treeview(
    frame_movimientos,
    columns=("Fecha","Insumo","Tipo","Cantidad","Referencia"),
    show="headings"
)

for col in ("Fecha","Insumo","Tipo","Cantidad","Referencia"):
    tree_mov.heading(col, text=col)

tree_mov.pack(fill="both", expand=True, pady=10)
# ==========================
# DASHBOARD
# ==========================

frame_dashboard = tk.Frame(notebook)
notebook.add(frame_dashboard, text="Dashboard")

label_estado_financiero = tk.Label(frame_dashboard, font=("Arial", 14))
label_estado_financiero.pack(pady=10)

label_estado_inventario = tk.Label(frame_dashboard, font=("Arial", 14))
label_estado_inventario.pack(pady=10)

tk.Button(frame_dashboard, text="Actualizar Dashboard", command=lambda: actualizar_dashboard()).pack(pady=10)
# ==========================
# CIERRE DE CAJA
# ==========================

frame_caja = tk.Frame(notebook)
notebook.add(frame_caja, text="Caja")

tk.Label(frame_caja, text="Fecha (YYYY-MM-DD)").pack()
entry_fecha_caja = tk.Entry(frame_caja)
entry_fecha_caja.pack(pady=5)

entry_fecha_caja.insert(0, datetime.now().strftime("%Y-%m-%d"))

tk.Button(frame_caja, text="Generar Cierre", command=lambda: generar_cierre()).pack(pady=5)

tree_caja = ttk.Treeview(
    frame_caja,
    columns=("Metodo", "Total"),
    show="headings"
)

tree_caja.heading("Metodo", text="Método de Pago")
tree_caja.heading("Total", text="Total")

tree_caja.pack(fill="both", expand=True, pady=10)

label_total_dia = tk.Label(frame_caja, font=("Arial", 14))
label_total_dia.pack(pady=10)
# REPORTES
frame_reportes = tk.Frame(notebook)
notebook.add(frame_reportes, text="Reportes")

frame_controles = tk.Frame(frame_reportes)
frame_controles.pack(side="top", fill="x")

frame_graficos = tk.Frame(frame_reportes)
frame_graficos.pack(side="bottom", fill="both", expand=True)

label_resumen = tk.Label(frame_controles)
label_resumen.pack()

tk.Button(frame_controles, text="Resumen", command=mostrar_resumen).pack(side="left")
tk.Button(frame_controles, text="Gráfico Resumen", command=mostrar_grafico_resumen).pack(side="left")
tk.Button(frame_controles, text="Tendencia Mensual", command=mostrar_tendencia_mensual).pack(side="left")
tk.Button(frame_controles, text="Ver Stock Bajo", command=verificar_stock_bajo_ui).pack(side="left")
cargar_productos()
cargar_tabla_productos()
cargar_tabla_inventario()
cargar_combo_inventario()
cargar_combo_movimientos()
cargar_combo_productos_rel()
cargar_combo_insumos_rel()

root.mainloop()