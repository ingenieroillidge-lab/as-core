/* 
   ESTE SCRIPT SE INCLUIRÁ EN TODAS LAS PÁGINAS 
   PARA ADAPTAR LA INTERFAZ SEGÚN EL NEGOCIO
*/

const LENGUAJE_OPERATIVO = {
    'PRODUCCIÓN': {
        insumos: 'Ingredientes',
        recetas: 'Recetas / Fórmulas',
        inventario: 'Inventario de Insumos',
        reponer: 'Registrar Compra / Ingreso',
        unidad: 'Unidad de Medida (g, ml)',
        stock: 'Stock Actual'
    },
    'REVENTA': {
        insumos: 'Mercancía / Productos',
        recetas: 'Vínculos de Producto',
        inventario: 'Stock de Tienda',
        reponer: 'Ingresar Mercancía',
        unidad: 'Unidad (Paca, Caja, Unid)',
        stock: 'Inventario'
    },
    'SERVICIOS': {
        insumos: 'Recursos / Servicios',
        recetas: 'Estructura de Servicio',
        inventario: 'Disponibilidad de Recursos',
        reponer: 'Actualizar Capacidad',
        unidad: 'Unidad de Tiempo / Sesión',
        stock: 'Capacidad Disponible'
    },
    'HÍBRIDO': {
        insumos: 'Insumos y Recursos',
        recetas: 'Modelos de Costo',
        inventario: 'Gestión de Inventario',
        reponer: 'Entrada de Almacén',
        unidad: 'Unidad Base',
        stock: 'Existencias'
    }
};

async function aplicarTraduccionOperativa() {
    const res = await fetch('/api/config/negocio');
    const config = await res.json();
    if (!config) return;

    const lang = LENGUAJE_OPERATIVO[config.tipo] || LENGUAJE_OPERATIVO['HÍBRIDO'];

    // Traducir navegación y encabezados comunes
    const navInsumos = document.querySelector('a[href="/inventario"]');
    if (navInsumos) navInsumos.textContent = lang.inventario;

    const navRecetas = document.querySelector('a[onclick*="sec-recetas"]');
    if (navRecetas) navRecetas.textContent = lang.recetas;

    // Traducir por etiquetas data-lang
    document.querySelectorAll('[data-lang]').forEach(el => {
        const key = el.getAttribute('data-lang');
        if (lang[key]) el.textContent = lang[key];
    });

    console.log(`Sistema adaptado a modo: ${config.tipo}`);
}
