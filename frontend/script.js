document.addEventListener('DOMContentLoaded', () => {
    const runButton = document.getElementById('run_update_btn');
    const statusMessage = document.getElementById('status_message');
    const activityLog = document.getElementById('activity_log');
    const categoryNamesTextarea = document.getElementById('category_names');
    const forceRebootCheckbox = document.getElementById('force_reboot');

    // Función para añadir mensajes al log
    function logMessage(message) {
        const timestamp = new Date().toLocaleTimeString();
        activityLog.innerHTML += ;
        // Scroll al final del log
        activityLog.scrollTop = activityLog.scrollHeight;
    }

    // Función principal para ejecutar la actualización
    async function handleRunUpdate() {
        logMessage("Preparando la solicitud al servidor...");
        runButton.disabled = true;
        runButton.textContent = 'Procesando...';
        statusMessage.textContent = 'Enviando solicitud al backend...';
        statusMessage.className = 'status processing';
        
        // Limpiar log viejo
        activityLog.innerHTML = '';
        logMessage("--- INICIO DE NUEVA SESIÓN DE ACTUALIZACIÓN ---");

        // Recolectar datos del formulario
        const categoryNames = categoryNamesTextarea.value.trim().split(',').map(s => s.trim()).filter(s => s.length > 0);
        const forceReboot = forceRebootCheckbox.checked;

        try {
            const response = await fetch('/api/v1/run_update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    category_names: categoryNames.length > 0 ? categoryNames : None, // Enviamos la lista si hay contenido
                    force_reboot: forceReboot,
                }),
            });

            const data = await response.json();

            if (response.ok) {
                // Éxito en la ejecución del backend (simulación exitosa)
                statusMessage.textContent = '✅ Proceso Completado con Éxito.';
                statusMessage.className = 'status success';
                logMessage("SERVIDOR RESPONDIÓ: " + data.message);
            } else {
                // Error del backend
                statusMessage.textContent = ;
                statusMessage.className = 'status error';
                logMessage();
            }
        } catch (error) {
            // Error de red o CORS
            statusMessage.textContent = '🚨 Error de Conexión.';
            statusMessage.className = 'status error';
            logMessage("FALLO DE RED O CORS. Asegúrese de que el backend esté corriendo en el puerto 80.");
        } finally {
            // Limpiar estado
            runButton.disabled = false;
            runButton.textContent = 'Iniciar Proceso de Actualización';
        }
    }

    // Asignar el listener al botón
    runButton.addEventListener('click', handleRunUpdate);

    // Inicializar el log con un mensaje de bienvenida
    logMessage("Interfaz cargada. Listo para comunicarse con el backend.");
});
