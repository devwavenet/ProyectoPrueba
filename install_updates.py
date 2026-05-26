#!/usr/bin/env python3
"""
Windows Update Installer via WinRM
Se conecta a servidores Windows remotos, consulta, instala updates y maneja reinicios.
"""

import sys
import time
import socket
import getpass
from datetime import datetime

try:
    import winrm
except ImportError:
    print("ERROR: pywinrm no está instalado.")
    print("Ejecutá: pip install pywinrm")
    sys.exit(1)


# ─────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────

def ask(prompt, default=None):
    """Input interactivo con valor por defecto."""
    if default is not None:
        prompt = f"{prompt} [{default}]"
    value = input(f"{prompt}: ").strip()
    return value if value else (default if default is not None else "")


def wait_for_server(host: str, port: int = 5985, timeout: int = 600) -> bool:
    """
    Espera a que el servidor vuelva a estar disponible después de un reinicio.
    Prueba conexión TCP al puerto WinRM cada 30 segundos.
    """
    print(f"\n[*] Esperando que {host} vuelva a estar en línea...")
    print(f"    (timeout: {timeout}s, intervalo: 30s, pulso cada intento)")

    start = time.time()
    attempt = 0

    while time.time() - start < timeout:
        attempt += 1
        elapsed = int(time.time() - start)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                print(f"\n[✓] {host} volvió a estar en línea en ~{elapsed}s (intento {attempt})")
                # Damos un poco más de tiempo para que WinRM esté realmente listo
                print(f"    Esperando 15s extra para que el servicio WinRM esté disponible...")
                time.sleep(15)
                return True
        except Exception as e:
            pass  # sigue esperando

        remaining = timeout - int(time.time() - start)
        if remaining > 0:
            print(f"    [{elapsed}s] {host} aún no responde... ({remaining}s restantes) ", end="\r")
        time.sleep(30)

    print(f"\n[✗] Timeout esperando a {host} después de {timeout}s")
    return False


# ─────────────────────────────────────────────
# Conexión y ejecución PowerShell
# ─────────────────────────────────────────────

def connect(server: str, user: str, password: str):
    """Crea una sesión WinRM."""
    print(f"\n[*] Conectando a {server}...")
    try:
        session = winrm.Session(
            f"http://{server}:5985/wsman",
            auth=(user, password),
            transport="ntlm"
        )
        return session
    except Exception as e:
        print(f"[✗] Error creando sesión: {e}")
        sys.exit(1)


def run_ps(session, script: str) -> tuple[str, str, int]:
    """Ejecuta PowerShell y devuelve (stdout, stderr, rc)."""
    resp = session.run_ps(script)
    stdout = resp.std_out.decode("utf-8", errors="replace").strip() if resp.std_out else ""
    stderr = resp.std_err.decode("utf-8", errors="replace").strip() if resp.std_err else ""
    return stdout, stderr, resp.status_code


def get_pending_count(session) -> int:
    """Devuelve la cantidad de updates pendientes."""
    ps = """
    $UpdateSession = New-Object -ComObject Microsoft.Update.Session
    $UpdateSearcher = $UpdateSession.CreateUpdateSearcher()
    try {
        $Result = $UpdateSearcher.Search('IsInstalled=0')
        $Result.Updates.Count
    } catch {
        Write-Output -1
    }
    """
    stdout, stderr, rc = run_ps(session, ps)
    if stderr or rc != 0:
        return -1
    try:
        return int(stdout.strip())
    except:
        return -1


# ─────────────────────────────────────────────
# Paso 1: Consultar updates pendientes
# ─────────────────────────────────────────────

def step_query(session, server: str) -> int:
    print("\n" + "=" * 60)
    print("PASO 1 — Consultar actualizaciones pendientes")
    print("=" * 60)

    print(f"🖥️  Servidor: {server}")
    print(f"📅 Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n[*] Buscando updates pendientes...")

    count = get_pending_count(session)

    if count < 0:
        print("[✗] No se pudo consultar el servidor. ¿WinRM está habilitado?")
        return -1

    print(f"\n    Updates pendientes: {count}")

    if count == 0:
        print("\n✅ No hay actualizaciones pendientes. Nada por hacer.")
        return 0

    # Listar títulos
    ps_list = """
    $UpdateSession = New-Object -ComObject Microsoft.Update.Session
    $UpdateSearcher = $UpdateSession.CreateUpdateSearcher()
    $SearchResult = $UpdateSearcher.Search('IsInstalled=0')
    $i = 1
    foreach ($u in $SearchResult.Updates) {
        $kb = if ($u.KBArticleIDs) { $u.KBArticleIDs -join ', ' } else { '-' }
        $severity = if ($u.MsrcSeverity) { $u.MsrcSeverity } else { 'N/A' }
        Write-Output \"$($i). [$severity] $($u.Title) [KB: $kb]\"
        $i++
    }
    """
    stdout, _, _ = run_ps(session, ps_list)
    if stdout:
        print("\n--- Listado de updates ---")
        for line in stdout.splitlines():
            print(f"  {line}")

    return count


# ─────────────────────────────────────────────
# Paso 2: Confirmación
# ─────────────────────────────────────────────

def step_confirm(count: int) -> bool:
    print("\n" + "=" * 60)
    print("PASO 2 — Confirmar instalación")
    print("=" * 60)
    print(f"\nSe van a instalar {count} actualización(es).")
    print("ADVERTENCIA: Esto puede requerir uno o más reinicios.")
    print("El servidor quedará temporalmente no disponible.")
    response = input("\n¿Continuar con la instalación? (si/no): ").strip().lower()
    return response in ("si", "s", "y", "yes")


# ─────────────────────────────────────────────
# Paso 3: Descargar e instalar updates
# ─────────────────────────────────────────────

def step_install(session, server: str, user: str, password: str) -> dict:
    print("\n" + "=" * 60)
    print("PASO 3 — Instalando actualizaciones")
    print("=" * 60)
    print("\n[*] Iniciando descarga e instalación...")
    print("    (esto puede tardar varios minutos, tener paciencia)\n")

    # PowerShell: descargar e instalar todas las updates pendientes
    # reboot: $false para no reiniciar automáticamente aquí, lo manejamos nosotros
    ps_install = """
    $UpdateSession = New-Object -ComObject Microsoft.Update.Session
    $UpdateLoader = $UpdateSession.CreateUpdateLoader()
    $UpdateSearcher = $UpdateSession.CreateUpdateSearcher()

    Write-Output '--- Buscando updates ---'
    try {
        $SearchResult = $UpdateSearcher.Search('IsInstalled=0')
        Write-Output \"Updates encontradas: $($SearchResult.Updates.Count)\"
    } catch {
        Write-Error \"Error en búsqueda: $($_.Exception.Message)\"
        exit 1
    }

    if ($SearchResult.Updates.Count -eq 0) {
        Write-Output 'No hay updates para instalar.'
        exit 0
    }

    # Aceptar todos los EULAs automáticamente
    Write-Output '--- Aceptando licencias ---'
    foreach ($Update in $SearchResult.Updates) {
        if (-not $Update.EulaAccepted) {
            $Update.AcceptEula()
        }
    }

    # Crear colección de descargas
    Write-Output '--- Descargando ---'
    $Downloader = $UpdateSession.CreateUpdateDownloader()
    $Downloader.Updates = $SearchResult.Updates
    try {
        $DownloadResult = $Downloader.Download()
        Write-Output \"Estado de descarga: $($DownloadResult.ResultCode)\"
    } catch {
        Write-Error \"Error en descarga: $($_.Exception.Message)\"
        exit 1
    }

    # Crear colección de instalaciones
    Write-Output '--- Instalando ---'
    $Installer = $UpdateSession.CreateUpdateInstaller()
    $Installer.Updates = $SearchResult.Updates
    try {
        $InstallResult = $Installer.Install()
        Write-Output \"Estado de instalación: $($InstallResult.ResultCode)\"
        Write-Output \"Reboot requerido: $($InstallResult.RebootRequired)\"
        # Devolver el resultado para parsear
        Write-Output \"REBOOT_NEEDED=$($InstallResult.RebootRequired)\"
        Write-Output \"HRESULT=$($InstallResult.HResult)\"
        foreach ($r in $InstallResult.GetUpdateResult()) {
            Write-Output \"UPDATE_RESULT=$($r.ResultCode)|$($r.HResult)\"
        }
    } catch {
        Write-Error \"Error en instalación: $($_.Exception.Message)\"
        exit 1
    }
    """

    stdout, stderr, rc = run_ps(session, ps_install)

    print(stdout)
    if stderr:
        print(f"STDERR: {stderr}")

    reboot_needed = "REBOOT_NEEDED=True" in stdout
    install_ok = rc == 0 and "Estado de instalación:" in stdout

    return {
        "success": install_ok,
        "reboot_required": reboot_needed,
        "output": stdout,
        "stderr": stderr,
    }


# ─────────────────────────────────────────────
# Paso 4: Reinicio (si hace falta)
# ─────────────────────────────────────────────

def step_reboot(session, server: str, user: str, password: str):
    print("\n" + "=" * 60)
    print("PASO 4 — Reinicio del servidor")
    print("=" * 60)

    response = input("\n¿Desea reiniciar ahora? (si/no): ").strip().lower()
    if response not in ("si", "s", "y", "yes"):
        print("[*] Reinicio cancelado por el usuario.")
        return

    print("\n[*] Ejecutando reinicio...")
    ps_reboot = "Shutdown-Restart-Computer -Force -ErrorAction Stop; Write-Output 'REBOOT_DONE'"
    try:
        session.run_ps(ps_reboot)
    except Exception as e:
        # Puede dar error porque el servidor se va, es esperable
        print(f"    (respuesta esperada: el servidor se está reiniciando: {e})")

    print("[*] Reinicio iniciado. Esperando a que el servidor vuelva...")

    online = wait_for_server(server, port=5985, timeout=600)

    if online:
        print("\n✅ Servidor volvió a estar en línea.")
        # Verificar que WinRM responde con una nueva conexión
        session2 = connect(server, user, password)
        stdout, _, _ = run_ps(session2, "Write-Output 'WinRM OK'")
        if "WinRM OK" in stdout:
            print("✅ WinRM responde correctamente.")
        else:
            print("⚠️  WinRM no responde bien, posible problema.")
    else:
        print("\n[✗] El servidor no volvió en el tiempo esperado.")
        print("    Revisar manualmente.")


# ─────────────────────────────────────────────
# Paso 5: Verificación post-instalación
# ─────────────────────────────────────────────

def step_verify(session, server: str):
    print("\n" + "=" * 60)
    print("PASO 5 — Verificación post-instalación")
    print("=" * 60)

    print("\n[*] Verificando que no queden updates pendientes...")
    count = get_pending_count(session)

    if count < 0:
        print("[?] No se pudo verificar (¿servidor no respondió?).")
        return

    if count == 0:
        print(f"\n✅ Servidor {server}: sin actualizaciones pendientes. Instalación completa.")
    else:
        print(f"\n⚠️  Aún quedan {count} update(s) pendiente(s). Puede requerir otro ciclo de instalación+reinicio.")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Windows Update Installer — Instalación via WinRM")
    print("=" * 60)

    # Pedir datos de conexión
    print("\n--- Datos de conexión ---")
    server = ask("IP o hostname del servidor")
    if not server:
        print("No se proporcionó servidor. Saliendo.")
        sys.exit(1)

    user = ask("Usuario (ej: wavenet)")
    if not user:
        print("No se proporcionó usuario. Saliendo.")
        sys.exit(1)

    password = getpass.getpass("Contraseña: ")
    if not password:
        print("No se proporcionó contraseña. Saliendo.")
        sys.exit(1)

    # Crear sesión
    session = connect(server, user, password)

    # ── Paso 1: Consultar ──
    count = step_query(session, server)
    if count < 0:
        sys.exit(1)
    if count == 0:
        print("\n¡Listo! No había nada que hacer.")
        sys.exit(0)

    # ── Paso 2: Confirmar ──
    if not step_confirm(count):
        print("\nOperación cancelada por el usuario.")
        sys.exit(0)

    # ── Paso 3: Instalar ──
    result = step_install(session, server, user, password)

    if not result["success"]:
        print("\n[✗] La instalación falló. Revisar el output de arriba.")
        sys.exit(1)

    print("\n✅ Instalación completada.")

    # ── Paso 4: Reinicio ──
    if result["reboot_required"]:
        print("\n⚠️  El servidor requiere reinicio.")
        step_reboot(session, server, user, password)
    else:
        print("\nℹ️  No se requiere reinicio.")

    # ── Paso 5: Verificación ──
    # Reconectar por si el servidor volvió con nueva sesión
    session2 = connect(server, user, password)
    step_verify(session2, server)

    print("\n" + "=" * 60)
    print("PROCESO FINALIZADO")
    print("=" * 60)


if __name__ == "__main__":
    main()