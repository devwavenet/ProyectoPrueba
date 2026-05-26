#!/usr/bin/env python3
"""
Windows Update Checker via WinRM
Se conecta a servidores Windows remotos y consulta actualizaciones pendientes.
"""

import sys
import readline  # para input con history
from datetime import datetime

try:
    import winrm
except ImportError:
    print("ERROR: pywinrm no está instalado.")
    print("Ejecutá: pip install pywinrm")
    sys.exit(1)


def ask(prompt, default=None):
    """Input interactivo con valor por defecto."""
    if default:
        prompt = f"{prompt} [{default}]"
    value = input(f"{prompt}: ").strip()
    return value if value else (default or "")


def get_pending_updates(server: str, user: str, password: str) -> dict:
    """
    Se conecta via WinRM al servidor y consulta updates pendientes.
    Usa PowerShell con el módulo pswindowsupdate (o equivalente).
    """
    print(f"\n[*] Conectando a {server}...")

    try:
        session = winrm.Session(f"http://{server}:5985/wsman", auth=(user, password), transport='ntlm')
    except Exception as e:
        return {"error": f"Error de conexión: {e}"}

    # PowerShell: listar updates pendientes usando Windows Update API vía COM
    # Este comando no necesita módulos externos, usa dism y el built-in de Windows
    ps_script = """
    $UpdateSession = New-Object -ComObject Microsoft.Update.Session
    $UpdateSearcher = $UpdateSession.CreateUpdateSearcher()
    try {
        $SearchResult = $UpdateSearcher.Search("IsInstalled=0")
        $Updates = @()
        foreach ($update in $SearchResult.Updates) {
            $Updates += [PSCustomObject]@{
                Title = $update.Title
                Muted = $update.IsMuted
                KBArticleIDs = $update.KBArticleIDs -join ", "
                MsrcSeverity = if ($update.MsrcSeverity) { $update.MsrcSeverity } else { "N/A" }
                IsMandatory = $update.IsMandatory
                UninstallationNotes = if ($update.UninstallationNotes) { $update.UninstallationNotes } else { "" }
            }
        }
        $Updates | Format-Table -AutoSize | Out-String
    } catch {
        Write-Error $_.Exception.Message
    }
    """

    print(f"[*] Consultando actualizaciones pendientes en {server}...")
    try:
        response = session.run_ps(ps_script)
    except Exception as e:
        return {"error": f"Error ejecutando comando: {e}"}

    stdout = response.std_out.decode("utf-8", errors="replace") if response.std_out else ""
    stderr = response.std_err.decode("utf-8", errors="replace") if response.std_err else ""

    if stderr and "error" in stderr.lower():
        return {"error": stderr}

    return {
        "server": server,
        "timestamp": datetime.now().isoformat(),
        "output": stdout,
        "has_updates": "Update" in stdout and "IsInstalled=0" not in stdout.replace("IsInstalled=0", ""),
        "rc": response.status_code,
    }


def main():
    print("=" * 60)
    print("Windows Update Checker - Consulta de Updates Pendientes")
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

    import getpass
    password = getpass.getpass("Contraseña: ")
    if not password:
        print("No se proporcionó contraseña. Saliendo.")
        sys.exit(1)

    # Ejecutar consulta
    result = get_pending_updates(server, user, password)

    # Mostrar resultado
    print("\n" + "=" * 60)
    print("RESULTADO")
    print("=" * 60)

    if "error" in result:
        print(f"\n❌ ERROR: {result['error']}")
    else:
        print(f"\n📅 Consulta realizada: {result['timestamp']}")
        print(f"🖥️  Servidor: {result['server']}")
        print(f"\n--- Salida ---\n")
        print(result["output"] if result["output"] else "(sin salida)")

        if not result["output"] or "0" in result["output"].split():
            print("✅ No hay actualizaciones pendientes o no se pudieron listar.")
        else:
            print("⚠️  Hay actualizaciones pendientes (ver listado arriba).")

    print()


if __name__ == "__main__":
    main()