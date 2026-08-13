/*
   MOTOR DEL ASISTENTE VIRTUAL AS & AYUDA CONTEXTUAL PERMANENTE
   Incluido globalmente en toda la aplicación
*/

(function() {
    // 1. Inyectar HTML del Asistente Flotante al cargar la página
    document.addEventListener('DOMContentLoaded', () => {
        if (document.getElementById('as-assistant-root')) return;

        const container = document.createElement('div');
        container.id = 'as-assistant-root';
        container.innerHTML = `
            <button class="as-assistant-btn" onclick="toggleAsAssistant()">
                🤖 <span>Asistente AS</span>
            </button>

            <div class="as-assistant-drawer" id="as-assistant-drawer">
                <div class="as-assistant-header">
                    <h3>🤖 Asistente AS — Guía y Ayuda</h3>
                    <button class="as-assistant-close" onclick="toggleAsAssistant()">✕</button>
                </div>

                <div class="as-assistant-body" id="as-chat-body">
                    <div class="as-msg-bot">
                        👋 ¡Hola! Soy tu asistente de <strong>AS Platform</strong>.<br>
                        Puedo guiarte paso a paso para configurar tu negocio, resolver dudas sobre recetas, márgenes o cargue masivo.
                    </div>

                    <div style="font-size: 0.75rem; color: #94a3b8; font-weight: 700; margin-top: 4px;">PREGUNTAS FRECUENTES DEL MÓDULO ACTUAL:</div>
                    <div id="as-quick-questions" style="display: flex; flex-direction: column; gap: 6px;"></div>
                </div>

                <div class="as-assistant-footer">
                    <input type="text" id="as-user-input" class="as-assistant-input" placeholder="Escribe tu duda aquí..." onkeypress="handleAsKeyPress(event)">
                    <button class="as-assistant-send" onclick="sendAsMessage()">Enviar</button>
                </div>
            </div>
        `;
        document.body.appendChild(container);
        loadContextualQuestions();
    });

    window.toggleAsAssistant = function() {
        const drawer = document.getElementById('as-assistant-drawer');
        if (!drawer) return;
        const isVisible = drawer.style.display === 'flex';
        drawer.style.display = isVisible ? 'none' : 'flex';
    };

    window.handleAsKeyPress = function(e) {
        if (e.key === 'Enter') sendAsMessage();
    };

    // 2. Preguntas Frecuentes Contextuales según el módulo actual
    function loadContextualQuestions() {
        const path = window.location.pathname;
        const container = document.getElementById('as-quick-questions');
        if (!container) return;

        let questions = [
            { text: "📑 ¿Cómo creo una receta o vinculo insumos?", key: "recetas" },
            { text: "📊 ¿Por qué mi producto aparece sin margen?", key: "margen" },
            { text: "📥 ¿Cómo cargo productos desde Excel o Google Sheets?", key: "masivo" },
            { text: "📅 ¿Puedo registrar ventas de fechas pasadas?", key: "retroactivas" },
            { text: "💳 ¿Cómo funcionan las ventas a crédito y los abonos?", key: "cartera" },
            { text: "📩 Necesito ayuda de un Administrador Humano", key: "escalar" }
        ];

        if (path === '/ventas') {
            questions.unshift({ text: "🛒 ¿Por qué no puedo registrar esta venta?", key: "error_venta" });
        } else if (path === '/inventario') {
            questions.unshift({ text: "📦 ¿Cómo registro una compra o ingreso de mercancía?", key: "ingreso_stock" });
        } else if (path === '/cartera') {
            questions.unshift({ text: "💵 ¿Cómo registro un abono de un cliente?", key: "registrar_abono" });
        }

        container.innerHTML = questions.map(q => `
            <button class="as-quick-btn" onclick="askAsQuestion('${q.key}')">${q.text}</button>
        `).join('');
    }

    window.askAsQuestion = function(key) {
        let userText = "";
        let botReply = "";

        if (key === "recetas") {
            userText = "¿Cómo creo una receta o vinculo insumos?";
            botReply = `
                <strong>Para crear una receta:</strong><br>
                1. Ve a <strong>Configuración → Perfil y Marca</strong>.<br>
                2. Asegúrate de que el tipo de negocio sea <strong>PRODUCCIÓN</strong> o <strong>HÍBRIDO</strong>.<br>
                3. Ve a la pestaña de <strong>Recetas / Fórmulas</strong>, elige el producto, selecciona el ingrediente y la cantidad usada.<br><br>
                <a href="/configuracion" class="as-action-link">👉 Ir a Configuración</a>
            `;
        } else if (key === "margen") {
            userText = "¿Por qué mi producto aparece sin margen?";
            botReply = `
                El <strong>Margen de Contribución</strong> requiere dos datos:<br>
                - Un <strong>Precio de Venta</strong> mayor a cero.<br>
                - El <strong>Costo del Insumo</strong> vinculado en la receta.<br><br>
                Si no vinculas insumos o el costo base está en $0, la utilidad no se podrá calcular.<br><br>
                <a href="/inventario" class="as-action-link">👉 Revisar Costos de Insumos</a>
            `;
        } else if (key === "masivo") {
            userText = "¿Cómo cargo productos desde Excel o Google Sheets?";
            botReply = `
                <strong>Cargue Masivo en 3 pasos:</strong><br>
                1. Ve a <strong>Configuración → Cargue Masivo</strong>.<br>
                2. Descarga la plantilla CSV oficial o conecta tu hoja pública de Google Sheets.<br>
                3. Diligencia los datos y haz clic en <strong>Subir / Sincronizar</strong>.<br><br>
                <a href="/api/plantilla/productos" class="as-action-link" style="background:#34d399; color:black;">📥 Bajar Plantilla CSV</a>
                <a href="/configuracion" class="as-action-link">👉 Ir a Cargue Masivo</a>
            `;
        } else if (key === "retroactivas") {
            userText = "¿Puedo registrar ventas de fechas pasadas?";
            botReply = `
                <strong>¡Sí!</strong> En el formulario de <strong>Ventas</strong> hay un campo opcional llamado <strong>Fecha de Venta</strong>.<br>
                Si lo dejas en blanco se guarda con la fecha de HOY. Si seleccionas un día pasado, se registrará retroactivamente actualizando los reportes de ese mes.
            `;
        } else if (key === "cartera") {
            userText = "¿Cómo funcionan las ventas a crédito y abonos?";
            botReply = `
                1. Activa <strong>Ventas a Crédito</strong> en <em>Configuración</em>.<br>
                2. Al registrar una venta, elige <strong>💳 Crédito / Cta por Cobrar</strong> e ingresa el cliente.<br>
                3. En el módulo de <strong>Cartera</strong> podrás registrar abonos parciales hasta saldar la deuda.<br><br>
                <a href="/cartera" class="as-action-link" style="background:#34d399; color:black;">👉 Ir a Cartera</a>
            `;
        } else if (key === "error_venta") {
            userText = "¿Por qué no puedo registrar esta venta?";
            botReply = `
                Si el sistema te bloquea al vender, verifica:<br>
                - Que hayas creado al menos 1 producto.<br>
                - Que los ingredientes de la receta tengan <strong>Stock disponible</strong>.<br>
                - Que hayas seleccionado un método de pago.
            `;
        } else if (key === "ingreso_stock") {
            userText = "¿Cómo registro compra de mercancía?";
            botReply = `
                En <strong>Inventario</strong>, haz clic en el botón <strong>+ Nuevo Insumo</strong> o actualiza el stock inicial para reponer existencias.
            `;
        } else if (key === "registrar_abono") {
            userText = "¿Cómo registro un abono?";
            botReply = `
                En la tabla de <strong>Cartera</strong>, haz clic en el botón verde <strong>💵 Abonar</strong> en la fila del cliente. Podrás ingresar el valor abonado y el método de pago.
            `;
        } else if (key === "escalar") {
            userText = "Necesito ayuda de un Administrador Humano";
            botReply = renderEscalationForm();
        }

        appendChatMsg(userText, true);
        appendChatMsg(botReply, false);
    };

    window.sendAsMessage = function() {
        const input = document.getElementById('as-user-input');
        if (!input) return;
        const text = input.value.trim();
        if (!text) return;

        appendChatMsg(text, true);
        input.value = '';

        const textLower = text.toLowerCase();
        let reply = "";

        if (textLower.includes("receta") || textLower.includes("ingrediente")) {
            reply = "Para gestionar recetas ve a <strong>Configuración → Recetas</strong>. Recuerda primero ingresar los insumos en el Inventario. <a href='/configuracion' class='as-action-link'>👉 Ir a Configuración</a>";
        } else if (textLower.includes("excel") || textLower.includes("csv") || textLower.includes("drive") || textLower.includes("sheet")) {
            reply = "Puedes importar masivamente desde Excel/CSV o Google Sheets en <strong>Configuración → Cargue Masivo</strong>. <a href='/configuracion' class='as-action-link'>👉 Ir a Cargue Masivo</a>";
        } else if (textLower.includes("cartera") || textLower.includes("crédito") || textLower.includes("credito") || textLower.includes("deuda") || textLower.includes("abono")) {
            reply = "Las ventas a crédito y los abonos trazables se gestionan en el menú <strong>Cartera</strong>. <a href='/cartera' class='as-action-link'>👉 Ir a Cartera</a>";
        } else if (textLower.includes("precio") || textLower.includes("costo") || textLower.includes("margen")) {
            reply = "Revisa los precios de tus productos y los costos de tus insumos para asegurar márgenes positivos.";
        } else {
            reply = `Entiendo tu inquietud sobre: "<em>${text}</em>".<br><br>Si deseas que el desarrollador/administrador revise tu caso personalmente, haz clic abajo:<br>` + renderEscalationForm(text);
        }

        setTimeout(() => appendChatMsg(reply, false), 400);
    };

    function appendChatMsg(htmlContent, isUser) {
        const body = document.getElementById('as-chat-body');
        if (!body) return;
        const div = document.createElement('div');
        div.className = isUser ? 'as-msg-user' : 'as-msg-bot';
        div.innerHTML = htmlContent;
        body.appendChild(div);
        body.scrollTop = body.scrollHeight;
    }

    function renderEscalationForm(userQuestion = "") {
        const qEscaped = userQuestion.replace(/"/g, '&quot;');
        return `
            <div style="background: rgba(14, 165, 233, 0.1); border: 1px solid rgba(14, 165, 233, 0.3); border-radius: 10px; padding: 10px; margin-top: 6px;">
                <div style="font-weight: 700; color: #38bdf8; margin-bottom: 4px;">📩 Enviar Consulta al Administrador</div>
                <div style="font-size: 0.78rem; color: #cbd5e1; margin-bottom: 8px;">Un administrador revisará tu pregunta y te responderá a la brevedad.</div>
                <input type="text" id="as-ticket-q" value="${qEscaped}" placeholder="Escribe tu consulta detallada..." style="width: 100%; padding: 6px; background: #000; border: 1px solid #333; border-radius: 6px; color: white; font-size: 0.8rem; margin-bottom: 8px;">
                <button onclick="submitAsTicket()" style="width: 100%; background: #38bdf8; color: black; font-weight: 800; padding: 8px; border-radius: 6px; border: none; cursor: pointer; font-size: 0.8rem;">
                    🚀 Enviar Ticket de Soporte
                </button>
            </div>
        `;
    }

    window.submitAsTicket = async function() {
        const input = document.getElementById('as-ticket-q');
        const pregunta = input ? input.value.trim() : '';
        if (!pregunta) return alert('Por favor ingresa la pregunta que deseas enviar al administrador.');

        const modulo = window.location.pathname;

        const res = await fetch('/api/soporte/ticket', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pregunta, modulo, respuesta_bot: 'Escalado desde Asistente Virtual AS' })
        });

        if (res.ok) {
            appendChatMsg("✅ <strong>Ticket de Soporte Enviado</strong>. El administrador ha sido notificado y revisará tu inquietud.", false);
        } else {
            alert('Ocurrió un error al enviar el ticket.');
        }
    };
})();
