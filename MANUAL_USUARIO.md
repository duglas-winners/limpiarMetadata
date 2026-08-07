# Manual de usuario — Limpiador de Metadatos

Aplicación de escritorio para eliminar los datos ocultos que las fotos y los vídeos llevan dentro, antes de compartirlos.

---

## 1. ¿Qué son los metadatos y por qué borrarlos?

Cada foto que toma un teléfono y cada vídeo que graba una cámara guardan, **dentro del mismo archivo**, información que no se ve al abrirlo:

- **Ubicación GPS exacta** de dónde se tomó (calle y número, en la práctica).
- **Fecha y hora** exactas.
- **Marca y modelo** del dispositivo, y a veces su número de serie.
- **Nombre del autor**, software de edición usado e historial de cambios.
- En vídeos: título, dispositivo, capítulos, notas del editor.

Al subir un archivo a una web, enviarlo por correo o adjuntarlo a un documento, todo eso viaja con él. Esta aplicación genera una **copia limpia** de cada archivo, con la imagen o el vídeo intactos y sin ningún dato oculto.

> **El archivo original nunca se modifica ni se borra.** La aplicación siempre escribe copias nuevas en una carpeta aparte.

---

## 2. Instalación

**No necesitas instalar nada.** Ni Python, ni FFmpeg, ni ningún otro programa: todo viaja dentro de la aplicación.

| Plataforma | Qué descargas | Qué haces |
|---|---|---|
| Windows 10/11 | `LimpiadorMetadatos.exe` (55 MB) | Doble clic |
| macOS | `LimpiadorMetadatos.dmg` | Doble clic y arrastrar a Aplicaciones |

Los archivos están en la [página de Releases](https://github.com/duglas-winners/limpiarMetadata/releases).

La primera vez que la abras, Windows o macOS mostrarán un aviso de seguridad porque la aplicación no está firmada con un certificado comercial. Es esperable y se resuelve en dos clics: el procedimiento exacto de cada sistema está en **[INSTALACION.md](INSTALACION.md)**.

El primer arranque tarda 2 o 3 segundos mientras la aplicación se prepara.

---

## 3. Cómo usarla — paso a paso

### Paso 1 — Seleccionar los archivos

Pulsa **Seleccionar archivos**. Se abre el explorador de Windows.

- Puedes elegir varios a la vez: mantén `Ctrl` pulsado y haz clic en cada uno, o `Shift` para un rango completo.
- El filtro muestra por defecto solo formatos compatibles. Si no ves tus archivos, cambia el desplegable a "Todos los archivos".
- Los nombres aparecen listados en el recuadro central, cada uno precedido de `[  ]` (pendiente).

### Paso 2 — Elegir dónde guardar los resultados

Pulsa **Carpeta destino** y elige una carpeta. La ruta actual siempre se muestra bajo los botones.

Si no eliges nada, se usa `C:\Users\TuUsuario\Archivos_Limpiados`, que se crea sola la primera vez.

> Consejo: usa una carpeta distinta de la de los originales. Así nunca hay duda de cuál es cuál.

### Paso 3 — Procesar

Pulsa el botón verde **Procesar cola de archivos**.

- El botón se desactiva y cambia a "Procesando..." mientras trabaja.
- La barra azul avanza a medida que se completan archivos.
- Cada archivo terminado aparece en la lista con su resultado.
- **La ventana sigue respondiendo**: puedes moverla o minimizarla sin problema. No la cierres hasta que termine.

Las imágenes tardan menos de un segundo cada una. Los vídeos suelen tardar unos segundos incluso si pesan varios GB, porque no se recodifican, solo se reempaquetan.

### Paso 4 — Revisar el resultado

Al terminar aparece un aviso con el recuento de correctos y con error, y la ruta donde quedaron.

Los archivos limpios se llaman igual que los originales, con el prefijo **`sin_meta_`**:

```
foto_vacaciones.jpg   →   sin_meta_foto_vacaciones.jpg
```

Si procesas el mismo archivo dos veces, la segunda copia se guarda como `sin_meta_foto_vacaciones_1.jpg`. **Nunca se sobrescribe un resultado anterior.**

### Paso 5 — Comprobarlo tú mismo (opcional)

Haz clic derecho en el archivo limpio → **Propiedades** → pestaña **Detalles**. Los campos de cámara, GPS y autor deben aparecer vacíos. Compáralo con el original: la diferencia se ve de inmediato.

---

## 4. Formatos compatibles

| Tipo | Extensiones |
|---|---|
| **Imágenes** | `.jpg` `.jpeg` `.png` `.webp` `.bmp` `.tif` `.tiff` |
| **Vídeos** | `.mp4` `.mkv` `.mov` `.avi` `.flv` `.webm` `.m4v` |

Cualquier otro archivo que añadas a la cola se marcará como "Formato no soportado" y se omitirá, sin afectar al resto del lote.

---

## 5. Cómo leer la lista de resultados

| Marca | Significado | Qué hacer |
|---|---|---|
| `[  ] archivo.jpg` | En cola, aún sin procesar | Nada, esperar |
| `[OK] archivo.jpg - Limpiado` | Copia limpia creada correctamente | Nada, listo |
| `[!!] notas.txt - Formato no soportado` | No es imagen ni vídeo | Quitarlo de la selección |
| `[!!] video.mp4 - FFmpeg no está disponible...` | La aplicación no incluye FFmpeg | Descargar la versión oficial desde Releases |
| `[!!] archivo.jpg - El archivo ya no existe` | Se movió o borró tras seleccionarlo | Volver a seleccionarlo |
| `[!!] archivo.jpg - Fallo al limpiar` | Archivo dañado o formato interno raro | Abrirlo para confirmar que no está corrupto |

---

## 6. Problemas frecuentes

**Windows muestra un aviso azul de SmartScreen al abrirla**
Es normal en programas sin certificado comercial. Pulsa "Más información" → "Ejecutar de todas formas". Solo la primera vez. Detalle en [INSTALACION.md](INSTALACION.md).

**En Mac dice "desarrollador no identificado"**
Igual de normal. Clic derecho sobre la aplicación → "Abrir" → "Abrir". Solo la primera vez.

**Al abrir dice "FFmpeg no disponible"**
La versión oficial de Releases lo lleva incluido, así que esto solo pasa si estás ejecutando el código fuente sin haberlo descargado. Usa el ejecutable de Releases o consulta [COMPILACION.md](COMPILACION.md).

**Tarda unos segundos en abrirse**
Es esperado: la aplicación descomprime su contenido al arrancar. Son 2 o 3 segundos, iguales en cada apertura.

**No encuentro los archivos limpios**
Mira la ruta que dice "Destino:" bajo los botones, y busca ahí los archivos que empiezan por `sin_meta_`.

**El PNG transparente quedó con fondo blanco**
Ocurre solo si el archivo de salida es JPEG o BMP: esos formatos no admiten transparencia y hay que rellenarla. Los PNG y WebP conservan la transparencia intacta.

**Un vídeo dice error pero se ve bien**
Algunos formatos raros no admiten reempaquetado directo (por ejemplo, subtítulos incompatibles con el contenedor destino). Prueba convirtiéndolo antes a `.mp4`.

---

## 7. Lo que la aplicación **no** hace

Conviene tenerlo claro para no confiar de más:

- **No elimina marcas de agua ni información visible dentro de la propia imagen.** Si el nombre de una calle o una cara aparece en la foto, ahí sigue.
- **No borra los archivos originales.** Eso lo decides tú, manualmente.
- **No elimina huellas de identificación de la cámara a nivel de sensor** (patrones de ruido). Ninguna herramienta de este tipo lo hace; para eso hace falta reprocesar la imagen.
- **No procesa PDF, documentos de Office ni audio.** Solo imágenes y vídeos.
