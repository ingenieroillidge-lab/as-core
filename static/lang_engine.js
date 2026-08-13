/* 
   ESTE SCRIPT SE INCLUIRÁ EN TODAS LAS PÁGINAS 
   PARA ADAPTAR LA INTERFAZ SEGÚN EL NEGOCIO Y MOSTRAR LA IDENTIDAD COMERCIAL
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
    try {
        const res = await fetch('/api/config/negocio');
        const config = await res.json();
        if (!config) return;

        const nombreNegocio = config.nombre || 'Mi Negocio';
        const tipoNorm = (config.tipo || 'HÍBRIDO').toUpperCase();
        const lang = LENGUAJE_OPERATIVO[tipoNorm] || LENGUAJE_OPERATIVO['HÍBRIDO'];

        // 1. ACTUALIZAR ENCABEZADO / LOGO DE LA BARRA NAVEGADORA CON EL NOMBRE DE LA EMPRESA
        const logoContainer = document.querySelector('.navbar .logo') || document.querySelector('header .logo') || document.querySelector('.logo');
        if (logoContainer) {
            logoContainer.innerHTML = `
                <div style="display: flex; flex-direction: column; justify-content: center; line-height: 1.1;">
                    <span style="font-size: 1.2rem; font-weight: 800; color: #ffffff; letter-spacing: -0.3px; font-family: 'Outfit', 'Inter', sans-serif;">
                        ${nombreNegocio}
                    </span>
                    <span style="font-size: 0.65rem; font-weight: 700; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.8px; margin-top: 2px; opacity: 0.95;">
                        ⚡ AS Platform
                    </span>
                </div>
            `;
        }

        // 2. Traducir navegación y encabezados comunes
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

        // Helper seguro para insertar links de navegación respetando estructura <li> o <a>
        function insertarLinkNavegacion(href, texto, color) {
            if (document.querySelector(`a[href="${href}"]`)) return;

            const linkConf = document.querySelector('a[href="/configuracion"]');
            const navContainer = document.querySelector('.nav-links') || document.querySelector('nav') || document.querySelector('header');

            const link = document.createElement('a');
            link.href = href;
            link.textContent = texto;
            link.style.fontWeight = '700';
            if (color) link.style.color = color;

            if (linkConf && linkConf.parentNode) {
                if (linkConf.parentNode.tagName === 'LI') {
                    const li = document.createElement('li');
                    li.appendChild(link);
                    linkConf.parentNode.parentNode.insertBefore(li, linkConf.parentNode);
                } else {
                    linkConf.parentNode.insertBefore(link, linkConf);
                }
            } else if (navContainer) {
                navContainer.appendChild(link);
            }
        }

        // Mostrar u ocultar módulo de Cartera / Cuentas por Cobrar según configuración
        let navCartera = document.querySelector('a[href="/cartera"]');
        if (config.maneja_cartera == 1) {
            insertarLinkNavegacion('/cartera', '📑 Cartera', '#34d399');
            navCartera = document.querySelector('a[href="/cartera"]');
            if (navCartera) navCartera.style.display = '';
        } else if (navCartera) {
            navCartera.style.display = 'none';
        }

        // Mostrar módulo de Informes Configurable siempre en el menú
        insertarLinkNavegacion('/informes', '📊 Informes', '#38bdf8');

        // Si el usuario es SUPER ADMIN, insertar enlace directo al panel Super Admin
        if (config.user_role === 'SUPER') {
            insertarLinkNavegacion('/super-admin', '⚡ Super Admin', '#a855f7');
        }

        return config;
    } catch(e) {
        console.error("Error al aplicar la identidad comercial:", e);
    }
}

// Ejecutar automáticamente al cargar cualquier página
document.addEventListener('DOMContentLoaded', aplicarTraduccionOperativa);
