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

    const tipoNorm = (config.tipo || 'HÍBRIDO').toUpperCase();
    const lang = LENGUAJE_OPERATIVO[tipoNorm] || LENGUAJE_OPERATIVO['HÍBRIDO'];

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

    // Ocultar/Adaptar elementos que requieren recetas en negocios de Reventa pura
    if (tipoNorm === 'REVENTA' || tipoNorm === 'SERVICIOS') {
        document.querySelectorAll('[data-mode="receta"]').forEach(el => {
            el.style.display = 'none';
        });
        document.querySelectorAll('.receta-only').forEach(el => {
            el.style.display = 'none';
        });
    } else {
        document.querySelectorAll('[data-mode="receta"]').forEach(el => {
            el.style.display = '';
        });
        document.querySelectorAll('.receta-only').forEach(el => {
            el.style.display = '';
        });
    }

    console.log(`Sistema adaptado a modo: ${tipoNorm}`);

    // Mostrar u ocultar módulo de Cartera / Cuentas por Cobrar según configuración
    let navCartera = document.querySelector('a[href="/cartera"]');
    if (config.maneja_cartera == 1) {
        if (!navCartera) {
            const navContainer = document.querySelector('.nav-links') || document.querySelector('nav') || document.querySelector('header');
            if (navContainer) {
                const link = document.createElement('a');
                link.href = '/cartera';
                link.textContent = '📑 Cartera';
                link.style.fontWeight = '700';
                link.style.color = '#34d399';

                const linkConf = navContainer.querySelector('a[href="/configuracion"]');
                if (linkConf) {
                    navContainer.insertBefore(link, linkConf);
                } else {
                    navContainer.appendChild(link);
                }
            }
        } else {
            navCartera.style.display = '';
        }
    } else if (navCartera) {
        navCartera.style.display = 'none';
    }

    return config;
}
