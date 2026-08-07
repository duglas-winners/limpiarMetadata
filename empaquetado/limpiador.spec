# -*- mode: python ; coding: utf-8 -*-
"""
Especificacion de PyInstaller para el Limpiador de Metadatos.

Genera:
  - Windows: un unico .exe autocontenido (doble clic, sin instalacion)
  - macOS:   un paquete .app listo para arrastrar a Aplicaciones

Se invoca desde los scripts de `empaquetado/`, no directamente:
    pyinstaller empaquetado/limpiador.spec --noconfirm
"""

import sys
from pathlib import Path

import customtkinter

RAIZ = Path(SPECPATH).parent
ES_MAC = sys.platform == "darwin"
NOMBRE = "LimpiadorMetadatos"

# CustomTkinter carga sus temas y fuentes desde disco en tiempo de ejecucion,
# asi que su carpeta de datos debe viajar dentro del paquete.
datos = [(str(Path(customtkinter.__file__).parent), "customtkinter")]

# FFmpeg incrustado: sin el, la aplicacion solo procesa imagenes.
nombre_ffmpeg = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
binario_ffmpeg = RAIZ / "recursos" / nombre_ffmpeg
if binario_ffmpeg.is_file():
    datos.append((str(binario_ffmpeg), "recursos"))
    print(f"[spec] FFmpeg incrustado desde {binario_ffmpeg}")
else:
    print(f"[spec] AVISO: no se encontro {binario_ffmpeg}; el paquete no procesara videos.")

icono = RAIZ / "recursos" / ("icono.icns" if ES_MAC else "icono.ico")

a = Analysis(
    [str(RAIZ / "principal.py")],
    pathex=[str(RAIZ)],
    binaries=[],
    datas=datos,
    hiddenimports=["PIL._tkinter_finder"],
    hookspath=[],
    runtime_hooks=[],
    # Modulos pesados que Pillow y Tkinter arrastran sin que esta app los use
    excludes=["numpy", "scipy", "matplotlib", "pytest", "tkinter.test", "test"],
    noarchive=False,
)

pyz = PYZ(a.pure)

if ES_MAC:
    # En macOS el ejecutable va en modo carpeta y se envuelve en un .app,
    # que el sistema trata como una sola pieza para el usuario.
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=NOMBRE,
        console=False,
        icon=str(icono) if icono.is_file() else None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        name=NOMBRE,
    )
    app = BUNDLE(
        coll,
        name=f"{NOMBRE}.app",
        icon=str(icono) if icono.is_file() else None,
        bundle_identifier="com.grupowinners.limpiadormetadatos",
        info_plist={
            "CFBundleName": "Limpiador de Metadatos",
            "CFBundleDisplayName": "Limpiador de Metadatos",
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1.0.0",
            "NSHighResolutionCapable": True,
            # Requerido desde macOS 13 para leer archivos que elige el usuario
            "NSDesktopFolderUsageDescription": "Para leer y guardar los archivos que selecciones.",
            "NSDocumentsFolderUsageDescription": "Para leer y guardar los archivos que selecciones.",
            "NSDownloadsFolderUsageDescription": "Para leer y guardar los archivos que selecciones.",
        },
    )
else:
    # En Windows todo se funde en un unico .exe: el usuario descarga un archivo
    # y hace doble clic, sin descomprimir ni instalar nada.
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=NOMBRE,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        # UPX desactivado: comprime mal los binarios grandes y dispara falsos
        # positivos en los antivirus, que es peor problema que el tamaño.
        upx=False,
        runtime_tmpdir=None,
        console=False,
        icon=str(icono) if icono.is_file() else None,
    )
