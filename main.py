from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import time

# --- SIMULACIÓN DE LA LÓGICA DE ANSIBLE ---
# En un escenario real, esta función llamaría a un motor que ejecute la lógica compleja
# del playbook (@updates.yaml). Aquí la simulamos.
def execute_windows_update_logic(category_filter: str = None, force_reboot: bool = True) -> dict:
    """
    Simula la ejecución del playbook Ansible para actualizaciones de Windows.
    """
    print(f"--- Ejecutando actualización de Windows ---")
    if category_filter:
        print(f"Filtro aplicado: {category_filter}")
    else:
        print("Aplicando todas las categorías de actualización.")
        
    print("Iniciando proceso de instalación de parches...")
    # Simulación de trabajo que lleva tiempo
    time.sleep(3) 
    
    if force_reboot:
        print("Marcado para reiniciar después de la actualización.")
        
    print("Proceso simulado completado exitosamente.")
    return {"status": "success", "message": "Todas las actualizaciones han sido instaladas y el sistema está listo para reiniciar si aplica."}
# --- FIN DE LA SIMULACIÓN ---

app = FastAPI(
    title="Ansible-to-Web-Migrator",
    description="Servicio web que encapsula la lógica de actualización de Windows."
)

# Modelo de datos entrantes para el endpoint
class UpdateRequest(BaseModel):
    category_names: list[str] | None = None
    force_reboot: bool = True

# Endpoint principal para iniciar la actualización
@app.post("/api/v1/run_update")
async def run_update(request: UpdateRequest):
    """
    Recibe la solicitud y desencadena la lógica de actualización.
    """
    # Mapear los filtros de la UI a los nombres de categoría de Ansible (simulado)
    category_filter = ",".join(request.category_names) if request.category_names else None
    
    # Llamada al motor de ejecución
    try:
        result = execute_windows_update_logic(
            category_filter=category_filter, 
            force_reboot=request.force_reboot
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al ejecutar la actualización: {str(e)}")

# Endpoint de salud para verificar que el servicio está vivo
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "running"}

# Endpoint de versión
@app.get("/version")
def get_version():
    return {"version": "1.0.0", "name": "ProyectoPrueba"}

