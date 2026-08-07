# Limpiador de Metadatos

Aplicación de escritorio para eliminar metadatos (EXIF, GPS, autor, dispositivo, capítulos) de imágenes y vídeos en lote, generando copias limpias sin tocar los originales.

Todo el procesamiento ocurre en el equipo del usuario. La aplicación nunca envía nada a ningún servidor.

---

## Para usar la aplicación

Descarga y doble clic. No hace falta instalar Python ni FFmpeg: van dentro.

| Plataforma | Archivo | Tamaño |
|---|---|---|
| Windows 10/11 | `LimpiadorMetadatos.exe` | 55 MB |
| macOS | `LimpiadorMetadatos.dmg` | ~70 MB |

Descárgalos desde [Releases](https://github.com/duglas-winners/limpiarMetadata/releases). Los detalles, incluido cómo pasar el aviso de SmartScreen o Gatekeeper la primera vez, están en [INSTALACION.md](INSTALACION.md).

---

## Para trabajar sobre el código

```bash
python -m pip install -r requerimientos.txt
```

```bash
python principal.py
```

En modo desarrollo, FFmpeg debe estar en el PATH (`winget install Gyan.FFmpeg`) o descargado con `python empaquetado/obtener_ffmpeg.py`. Sin él, la aplicación procesa imágenes y avisa de que los vídeos no están disponibles.

Para generar los ejecutables, ver [COMPILACION.md](COMPILACION.md).

---

## Documentación

| Documento | Para quién |
|---|---|
| [Instalación](INSTALACION.md) | El usuario final que solo quiere usarla |
| [Manual de usuario](MANUAL_USUARIO.md) | Cómo usarla, paso a paso |
| [Guía de pantallas](GUIA_PANTALLAS.md) | Quien diseña o modifica la interfaz |
| [Documentación técnica](DOCUMENTACION_TECNICA.md) | Quien mantiene o amplía el código |
| [Compilación](COMPILACION.md) | Quien genera y publica las versiones |

---

## Estructura

```
limpiarMetadata/
├── limpiadores/              # Algoritmos de limpieza, uno por tipo de archivo
│   ├── base.py               # Contrato abstracto LimpiadorBase
│   ├── limpiador_imagen.py   # Recrea la imagen desde la matriz de píxeles (Pillow)
│   ├── limpiador_video.py    # Remux sin recodificar (FFmpeg)
│   └── proveedor.py          # Resuelve el limpiador según la extensión
├── nucleo/
│   └── procesador.py         # Cola en paralelo con grupo de hilos
├── interfaz/
│   └── ventana_principal.py  # Ventana única (CustomTkinter)
├── empaquetado/              # Todo lo relativo a generar los ejecutables
│   ├── obtener_ffmpeg.py     # Descarga FFmpeg para incrustarlo
│   ├── limpiador.spec        # Especificación de PyInstaller (Windows y Mac)
│   ├── construir_windows.ps1
│   ├── construir_mac.sh
│   └── verificar_paquete.py  # Autocomprobación del ejecutable ya compilado
├── recursos.py               # Localiza archivos incrustados en el ejecutable
├── principal.py              # Punto de entrada
└── requerimientos.txt
```

---

## Formatos soportados

- **Imágenes:** `.jpg` `.jpeg` `.png` `.webp` `.bmp` `.tif` `.tiff`
- **Vídeos:** `.mp4` `.mkv` `.mov` `.avi` `.flv` `.webm` `.m4v`

## Licencia de terceros

Incluye una compilación de [FFmpeg](https://ffmpeg.org) (LGPL/GPL). Al distribuir la aplicación se distribuye también FFmpeg, con las obligaciones de licencia que ello implica.
