#!/usr/bin/env bash
# Compila la aplicacion de macOS. Debe ejecutarse EN un Mac: PyInstaller no
# admite compilacion cruzada desde Windows o Linux.
#
#   chmod +x empaquetado/construir_mac.sh
#   ./empaquetado/construir_mac.sh
#
# Resultado: dist/LimpiadorMetadatos.app  y  dist/LimpiadorMetadatos.dmg

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

NOMBRE="LimpiadorMetadatos"

echo "== 1/5 Dependencias =="
python3 -m pip install -q -r requerimientos.txt
python3 -m pip install -q pyinstaller

echo "== 2/5 FFmpeg =="
python3 empaquetado/obtener_ffmpeg.py

echo "== 3/5 Limpieza de compilaciones previas =="
rm -rf build dist

echo "== 4/5 PyInstaller =="
python3 -m PyInstaller empaquetado/limpiador.spec --noconfirm --distpath dist --workpath build

APP="dist/${NOMBRE}.app"
[ -d "$APP" ] || { echo "No se genero $APP" >&2; exit 1; }

# Firma local ad-hoc. No evita el aviso de Gatekeeper al descargar (eso exige
# una cuenta de desarrollador de Apple), pero si evita que macOS mate el
# proceso por tener una firma invalida tras incrustar FFmpeg.
echo "   Firmando ad-hoc..."
codesign --force --deep --sign - "$APP" 2>/dev/null || echo "   (aviso: codesign fallo, la app puede requerir permiso manual)"

echo "== 5/5 Empaquetando DMG =="
DMG="dist/${NOMBRE}.dmg"
STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Aplicaciones"
hdiutil create -volname "Limpiador de Metadatos" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$STAGE"

echo ""
echo "Listo:"
echo "  $APP"
echo "  $DMG  ($(du -h "$DMG" | cut -f1))"
