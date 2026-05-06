/* 
   THEME ENGINE PRO - AS CORE
   Este script aplica la identidad visual de la marca en tiempo real
*/

async function aplicarTemaVisual() {
    try {
        const res = await fetch('/api/config/negocio');
        const config = await res.json();
        
        if (config && config.color_acento) {
            const root = document.documentElement;
            
            // Aplicamos los colores de la marca AS Solutions
            root.style.setProperty('--accent-color', config.color_acento);
            root.style.setProperty('--accent-glow', config.color_acento + '44'); // Color con transparencia para brillos
            
            if (config.color_primario) {
                root.style.setProperty('--card-bg', config.color_primario + 'dd'); // Fondo de tarjetas levemente transparente
            }

            // Actualizar el nombre en el logo si es AS CORE
            const logo = document.getElementById('main-logo');
            if (logo && config.nombre_negocio) {
                // Si el nombre es AS CORE o el configurado
                logo.innerHTML = `${config.nombre_negocio} <span id="tag-operacion" style="font-size: 0.6rem; background: var(--accent-color); color: black; padding: 2px 5px; border-radius: 4px; vertical-align: middle; margin-left: 5px;">PRO</span>`;
            }
        }
    } catch (e) {
        console.error("Error aplicando tema visual:", e);
    }
}

// Ejecutar al cargar
aplicarTemaVisual();
