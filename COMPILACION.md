# Compilación — Limpiador de Metadatos

Cómo generar los ejecutables distribuibles. Dirigido a quien mantiene el proyecto, no al usuario final (ese solo necesita [INSTALACION.md](INSTALACION.md)).

---

## Regla que condiciona todo: no hay compilación cruzada

PyInstaller **no puede generar una aplicación de macOS desde Windows**, ni al revés. No es una limitación de configuración: el ejecutable resultante incrusta el intérprete de Python y el cargador nativo de la plataforma anfitriona.

Por tanto, hay exactamente dos caminos para tener las dos versiones:

| Camino | Qué necesitas | Recomendado para |
|---|---|---|
| **GitHub Actions** | Solo subir el código al repositorio | Uso normal — GitHub presta las máquinas Windows y Mac |
| **Compilar a mano** | Un PC con Windows **y** un Mac físico | Pruebas locales o compilaciones puntuales |

---

## Camino 1 — GitHub Actions (recomendado)

El workflow [`.github/workflows/compilar.yml`](.github/workflows/compilar.yml) compila ambas plataformas en paralelo en los servidores de GitHub. No necesitas un Mac.

### Cuándo se ejecuta

| Disparador | Qué produce |
|---|---|
| `push` a `main` | Artefactos descargables desde la pestaña Actions (para verificar que nada se rompió) |
| `push` de una etiqueta `v*` | Además, publica el `.exe` y el `.dmg` en la Release de esa versión |
| Botón "Run workflow" | Ejecución manual desde la pestaña Actions |

### Publicar una versión nueva

```bash
git tag v1.0.0
```

```bash
git push origin v1.0.0
```

En unos 10 minutos los dos archivos aparecen en la página de Releases, listos para que cualquiera los descargue.

### Qué hace el workflow en cada plataforma

1. Instala Python 3.12 y las dependencias.
2. Descarga FFmpeg (cacheado entre ejecuciones para no repetir 98 MB cada vez).
3. Ejecuta PyInstaller con `empaquetado/limpiador.spec`.
4. **Compila y ejecuta la autocomprobación**, que valida desde dentro del ejecutable que FFmpeg incrustado funciona y que un JPEG y un MP4 quedan realmente limpios. Si esto falla, el workflow falla y la versión no se publica.
5. Sube los artefactos y, si hay etiqueta, los adjunta a la Release.

---

## Camino 2 — Compilar a mano

### Windows

```bash
powershell -ExecutionPolicy Bypass -File empaquetado\construir_windows.ps1
```

Resultado: `dist\LimpiadorMetadatos.exe` (~55 MB).

### macOS

Debe ejecutarse **en un Mac**:

```bash
chmod +x empaquetado/construir_mac.sh && ./empaquetado/construir_mac.sh
```

Resultado: `dist/LimpiadorMetadatos.app` y `dist/LimpiadorMetadatos.dmg`.

Ambos scripts hacen lo mismo: instalar dependencias, obtener FFmpeg, borrar compilaciones previas y ejecutar PyInstaller. El de Mac añade la firma ad-hoc y el empaquetado en DMG.

---

## Los archivos de empaquetado

| Archivo | Función |
|---|---|
| `empaquetado/obtener_ffmpeg.py` | Descarga el binario de FFmpeg para la plataforma actual y lo deja en `recursos/`. Detecta si ya está y no repite la descarga. Solo corre en la máquina que compila. |
| `empaquetado/limpiador.spec` | Especificación de PyInstaller, común a ambas plataformas. Decide por `sys.platform` si genera un `.exe` de un solo archivo o un paquete `.app`. |
| `empaquetado/construir_windows.ps1` | Script de compilación de Windows, de principio a fin. |
| `empaquetado/construir_mac.sh` | Script de compilación de macOS, incluidos firma ad-hoc y DMG. |
| `empaquetado/verificar_paquete.py` | Autocomprobación que se compila igual que la app y valida el paquete desde dentro. No forma parte de lo que recibe el usuario. |
| `recursos.py` | (Raíz del proyecto) Resuelve rutas de archivos incrustados, tanto en desarrollo como dentro del ejecutable. |

### Por qué FFmpeg no está en el repositorio

Pesa 98 MB, muy cerca del límite duro de 100 MB por archivo de GitHub, e inflaría el historial para siempre. Está en `.gitignore` y cada compilación lo obtiene con `obtener_ffmpeg.py`. En CI se cachea, así que solo se descarga de verdad la primera vez.

---

## Decisiones de empaquetado y su porqué

**Un solo archivo en Windows, paquete `.app` en Mac.**
En Windows el modo de archivo único cumple literalmente el requisito de "descargar y hacer doble clic". El coste es que el arranque descomprime todo a una carpeta temporal: **medido en 2,2–2,6 segundos**, aceptable. En macOS un `.app` ya es una carpeta que el sistema presenta como una sola pieza, así que no hay nada que ganar comprimiendo.

**UPX desactivado.**
Comprime mal los binarios grandes y es una causa habitual de falsos positivos en antivirus. Un ejecutable que Defender bloquea es peor problema que unos MB de más.

**`-fflags +bitexact` en FFmpeg.**
Sin esa bandera, FFmpeg firma cada archivo de salida con su propia versión (`encoder: Lavf63.1.100`). En una herramienta de privacidad eso delata que el archivo fue procesado, así que se suprime.

**El icono es opcional.**
El `.spec` usa `recursos/icono.ico` (Windows) o `recursos/icono.icns` (Mac) si existen, y el icono por defecto de PyInstaller si no. Añadir los tuyos no requiere tocar el código.

---

## Firma de código: el límite honesto

Ninguna de las dos aplicaciones está firmada con un certificado comercial. Consecuencias reales para el usuario:

| Plataforma | Qué ve el usuario | Cómo lo resuelve | Coste de eliminarlo |
|---|---|---|---|
| Windows | Aviso de SmartScreen en el primer arranque | "Más información" → "Ejecutar de todas formas" | Certificado Authenticode, 200–400 USD/año |
| macOS | "Desarrollador no identificado" | Clic derecho → Abrir, la primera vez | Apple Developer Program, 99 USD/año |

No hay solución técnica que evite estos avisos. Cualquier método que prometa saltárselos sin firmar o bien no funciona o bien pide al usuario desactivar protecciones del sistema, lo que es peor que el aviso.

Si en algún momento se adquieren los certificados, los puntos de integración son: `signtool.exe` tras PyInstaller en `construir_windows.ps1`, y sustituir la firma ad-hoc de `construir_mac.sh` por `codesign` con el identificador de desarrollador más `xcrun notarytool`.

---

## Estado verificado

Compilado y comprobado en Windows 11, Python 3.14.6, PyInstaller 6.21.0:

- `LimpiadorMetadatos.exe` generado, 55,1 MB.
- Arranque en frío: 2,2 s y 2,6 s en dos mediciones.
- Autocomprobación dentro del paquete: FFmpeg incrustado localizado y funcional (versión 9.0), JPEG limpiado con EXIF verificado como eliminado, MP4 limpiado correctamente.

**No verificado:** la compilación de macOS. El script y el workflow están escritos siguiendo la documentación de PyInstaller, pero no se han ejecutado en un Mac — desde Windows es imposible. La primera ejecución del workflow en GitHub Actions será la prueba real.
