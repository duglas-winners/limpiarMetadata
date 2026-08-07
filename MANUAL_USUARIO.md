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

### Paso 1 — Agregar los archivos

Pulsa **Agregar archivos**. Se abre el explorador de Windows.

- Puedes elegir varios a la vez: mantén `Ctrl` pulsado y haz clic en cada uno, o `Shift` para un rango completo.
- El filtro muestra por defecto solo formatos compatibles. Si no ves tus archivos, cambia el desplegable a "Todos los archivos".
- **Puedes agregar en varias tandas.** Cada vez que pulses el botón, los archivos nuevos se suman a los que ya estaban; no se pierde la selección anterior. Si eliges uno que ya está en la cola, simplemente se ignora.

### Paso 2 — Quitar lo que se haya colado

Si agregaste algo por error, no hace falta empezar de cero:

1. **Marca la casilla** a la izquierda de cada archivo que quieras sacar. La fila se resalta en azul.
2. Pulsa **Quitar de la cola**, que muestra entre paréntesis cuántos vas a quitar.

Atajos útiles:

- **Marcar todos** (arriba a la izquierda) marca o desmarca la cola entera de golpe. Combínalo con quitar unos pocos para invertir la selección rápidamente.
- **Vaciar todo** descarta la cola completa sin necesidad de marcar nada.

> Quitar un archivo de la cola **no lo borra de tu disco**. Solo lo saca de la lista de trabajo.

Mientras se está procesando, la cola queda bloqueada: no se puede agregar ni quitar, para que la lista siempre describa el trabajo que realmente se está ejecutando.

### Paso 3 — Elegir cómo ver la cola (opcional)

Arriba a la derecha hay un conmutador con dos vistas. Puedes cambiar entre ellas en cualquier momento, incluso mientras se procesa, sin perder nada.

| Vista | Qué muestra | Cuándo conviene |
|---|---|---|
| **Lista** | Una línea por archivo | Lotes grandes, cuando solo quieres ver el avance |
| **Detalle** | Miniatura de cada archivo, tamaño, formato y resultado | Cuando quieres confirmar visualmente qué estás procesando |

En la vista **Detalle** verás una vista previa de cada imagen y, en los vídeos, un fotograma del primer segundo. Las miniaturas se generan en segundo plano: aparecen solas en un par de segundos, y la aplicación sigue respondiendo con normalidad mientras tanto.

Si un archivo no se puede previsualizar (está dañado, o es un formato que no admite vista previa), su recuadro dirá "sin vista". Eso **no** impide procesarlo.

### Paso 4 — Elegir dónde guardar los resultados

Pulsa **Carpeta destino** y elige una carpeta. La ruta actual siempre se muestra bajo los botones.

Si no eliges nada, se usa `C:\Users\TuUsuario\Archivos_Limpiados`, que se crea sola la primera vez.

> **Importante:** debe ser una carpeta **distinta** de donde están tus originales. Como las copias limpias conservan el nombre original, guardarlas en la misma carpeta sobrescribiría los archivos de partida. La aplicación lo detecta y no te dejará hacerlo.

### Paso 5 — Procesar

Pulsa el botón verde **Limpiar metadatos**.

- El botón se desactiva y cambia a "Procesando..." mientras trabaja.
- La barra azul avanza a medida que se completan archivos.
- Cada archivo terminado muestra su resultado, en cualquiera de las dos vistas.
- **La ventana sigue respondiendo**: puedes moverla, minimizarla o cambiar de vista sin problema. No la cierres hasta que termine.

Las imágenes tardan menos de un segundo cada una. Los vídeos suelen tardar unos segundos incluso si pesan varios GB, porque no se recodifican, solo se reempaquetan.

### Paso 6 — Revisar el resultado

Al terminar aparece un aviso con el recuento de limpiados, omitidos y con error, más la ruta donde quedaron.

**Los archivos limpios conservan exactamente el nombre original:**

```
foto vacaciones.jpg   →   foto vacaciones.jpg
```

Están en la carpeta destino, así que no hay confusión posible con los originales, que siguen intactos en su sitio.

Si procesas el mismo archivo dos veces sobre la misma carpeta destino, la segunda copia se guarda como `foto vacaciones_1.jpg`. **Nunca se sobrescribe un resultado anterior.**

### Paso 7 — Comprobarlo tú mismo (opcional)

Haz clic derecho en el archivo limpio → **Propiedades** → pestaña **Detalles**. Los campos de cámara, GPS y autor deben aparecer vacíos. Compáralo con el original: la diferencia se ve de inmediato.

---

## 4. Formatos compatibles

| Tipo | Extensiones |
|---|---|
| **Imágenes** | `.jpg` `.jpeg` `.png` `.webp` `.bmp` `.tif` `.tiff` |
| **Vídeos** | `.mp4` `.mkv` `.mov` `.avi` `.flv` `.webm` `.m4v` |

Cualquier otro archivo que agregues a la cola se marcará como **Omitido**, sin afectar al resto del lote.

---

## 5. Cómo leer los estados

Cada archivo muestra a su derecha una etiqueta de color con su estado. El color se lee de un vistazo y el símbolo funciona aunque no distingas bien los colores.

| Etiqueta | Color | Significado | Qué hacer |
|---|---|---|---|
| **• En cola** | Gris | Aún sin procesar | Nada, esperar |
| **✓ Limpiado** | Verde | Copia limpia creada correctamente | Nada, listo |
| **! Omitido** | Ámbar | No había nada que hacer con él | Ver abajo |
| **✕ Error** | Rojo | Se intentó y falló | Ver abajo |

**Omitido** no es un fallo tuyo ni de la aplicación: significa que ese archivo no le corresponde a esta herramienta. Bajo el nombre aparece el motivo:

| Motivo | Qué pasó |
|---|---|
| *No es una imagen ni un vídeo* | Es otro tipo de archivo. Quítalo de la cola si no lo querías |
| *FFmpeg no está disponible...* | Esa compilación no incluye FFmpeg. Descarga la versión oficial desde Releases |

**Error** sí indica un problema con ese archivo concreto:

| Motivo | Qué pasó | Qué hacer |
|---|---|---|
| *El archivo ya no existe* | Se movió o borró tras agregarlo | Volver a agregarlo |
| *La carpeta destino es la del original...* | Destino y origen coinciden | Elegir otra carpeta destino |
| *No se pudo procesar* | Archivo dañado o formato interno raro | Abrirlo para confirmar que no está corrupto |

En cualquier caso, **un archivo con problema nunca detiene el resto del lote**: los demás se procesan igual.

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
Mira la ruta que dice "Destino:" bajo los botones. Ahí están, con el mismo nombre que los originales.

**Dice que la carpeta destino no es válida**
Elegiste como destino la misma carpeta donde están los originales. Como las copias conservan el nombre original, los sobrescribiría. Elige otra carpeta.

**En la vista Detalle algunos recuadros dicen "sin vista"**
Ese archivo no se pudo previsualizar: puede estar dañado o ser un formato sin vista previa. No afecta al procesamiento; se limpiará igual.

**Las miniaturas tardan en aparecer**
Se generan en segundo plano, y los vídeos requieren extraer un fotograma, lo que lleva algo más. La aplicación funciona con normalidad mientras tanto.

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
