# Documentación técnica — Limpiador de Metadatos

Referencia de cada módulo, clase y función del proyecto.

---

## 1. Visión general de la arquitectura

Tres capas independientes, con dependencias en una sola dirección:

```
interfaz/  (CustomTkinter)     ← lo que ve el usuario
    ↓ llama a
nucleo/    (hilos)             ← orquesta la cola de trabajo
    ↓ llama a
limpiadores/ (Pillow, FFmpeg)  ← hace la limpieza real de un archivo
```

- `limpiadores/` no sabe que existe una interfaz gráfica.
- `nucleo/` no sabe qué formato está limpiando; solo pide un limpiador al proveedor.
- `interfaz/` no sabe cómo se limpia nada; solo entrega una lista de rutas y recibe avisos de progreso.

Consecuencia práctica: para soportar un formato nuevo (PDF, audio, documentos de Office) basta con crear una clase nueva en `limpiadores/` y registrarla en el proveedor. Ni el núcleo ni la interfaz cambian.

**Flujo completo de una corrida:**

```
Usuario pulsa "Procesar"
  → VentanaPrincipal._iniciar_procesamiento()   [hilo principal]
      → lanza hilo secundario
        → ProcesadorEnLote.procesar_archivos()
            → ThreadPoolExecutor reparte N archivos entre N hilos
              → _tarea_individual(ruta)
                  → ProveedorLimpiadores.obtener_segun_archivo(ruta)
                  → limpiador.esta_disponible()
                  → limpiador.limpiar(entrada, salida)
                  → devuelve ResultadoArchivo
              → notificar_progreso(resultado, actual, total)
                  → self.after(0, ...)  devuelve el repintado al hilo principal
  → _finalizar_procesamiento(resultados)        [hilo principal]
```

---

## 2. Módulo `limpiadores/`

Contiene los algoritmos que eliminan metadatos. Cada limpiador es intercambiable porque todos cumplen el mismo contrato.

### 2.1 `limpiadores/base.py`

#### Clase `LimpiadorBase(ABC)`
Contrato base para cualquier algoritmo que elimine metadatos. Es una clase abstracta: no se instancia, se hereda. Define las dos únicas cosas que el núcleo necesita saber de un limpiador.

| Método | Firma | Qué hace |
|---|---|---|
| `limpiar` | `(ruta_entrada: Path, ruta_salida: Path) -> bool` | Lee el archivo de entrada, genera una copia sin metadatos y la escribe en la ruta de salida. Devuelve `True` si terminó bien. **Nunca lanza excepción**: captura el error, lo imprime y devuelve `False`, para que un archivo corrupto no tumbe el lote completo. |
| `esta_disponible` | `() -> tuple[bool, str]` | Indica si las dependencias externas del limpiador están presentes. Devuelve `(True, "")` si puede trabajar, o `(False, motivo)` con un mensaje legible para el usuario. Permite avisar "falta FFmpeg" antes de intentar procesar, en vez de fallar archivo por archivo. |

---

### 2.2 `limpiadores/limpiador_imagen.py`

Depende solo de Pillow, por lo que siempre está disponible.

**Constantes del módulo:**

| Constante | Contenido | Para qué |
|---|---|---|
| `FORMATOS_SIN_ALFA` | `{"JPEG", "BMP"}` | Formatos que no admiten canal de transparencia. Si la imagen lo trae, hay que aplanarla antes de guardar o Pillow falla. |
| `EXTENSION_A_FORMATO` | `{".jpg": "JPEG", ...}` | Mapa de respaldo para deducir el formato cuando el archivo no lo declara (ocurre con imágenes generadas en memoria o con cabeceras dañadas). |

#### Clase `LimpiadorImagen(LimpiadorBase)`
Elimina EXIF, GPS, perfiles de color ICC, comentarios XMP e historial de edición **recreando la imagen desde cero a partir de la matriz de píxeles pura**. No "borra" campos uno por uno (enfoque frágil, siempre queda alguno): construye una imagen nueva que nunca tuvo metadatos.

| Método | Firma | Qué hace |
|---|---|---|
| `esta_disponible` | `() -> tuple[bool, str]` | Siempre devuelve `(True, "")`. Pillow es una dependencia de Python, ya instalada si la app arranca. |
| `limpiar` | `(ruta_entrada, ruta_salida) -> bool` | Abre la imagen, determina el formato de salida (el declarado por el archivo o, si falta, el deducido de la extensión), delega la copia limpia a `_copiar_solo_pixeles` y la guarda. Si el formato no se puede determinar, devuelve `False`. |
| `_copiar_solo_pixeles` | `(imagen: Image, formato: str) -> Image` *(estático)* | El corazón del limpiador. Devuelve una imagen nueva con los mismos píxeles y **sin ningún contenedor de metadatos**. Tres casos: (1) modo paleta `P`/`PA` → convierte a `RGB`/`RGBA`, porque la paleta viaja fuera de la matriz de píxeles; (2) formato de destino sin alfa pero imagen con transparencia → aplana sobre fondo blanco; (3) caso general → `Image.frombytes(modo, tamaño, imagen.tobytes())`, que copia la matriz cruda sin arrastrar el diccionario `.info`. |

**Nota sobre lo que sí permanece:** en un JPEG limpio queda la cabecera JFIF (`jfif_version`, `jfif_density`). No es metadato del usuario: es parte estructural del formato y no revela nada sobre origen, cámara ni ubicación.

---

### 2.3 `limpiadores/limpiador_video.py`

#### Clase `LimpiadorVideo(LimpiadorBase)`
Elimina metadatos globales, por stream y capítulos mediante FFmpeg. Usa **remux** (`-c copy`): copia los flujos de audio y vídeo tal cual, sin recodificar. Un archivo de 2 GB se procesa en segundos y sin ninguna pérdida de calidad.

| Método | Firma | Qué hace |
|---|---|---|
| `esta_disponible` | `() -> tuple[bool, str]` | Delega en `recursos.ruta_ffmpeg()`, que prioriza el FFmpeg incrustado en la aplicación y recurre al del sistema si no lo hay. Devuelve el motivo legible si no encuentra ninguno. |
| `limpiar` | `(ruta_entrada, ruta_salida) -> bool` | Verifica la disponibilidad, arma el comando y lo ejecuta con `subprocess.run`. Devuelve `False` si el código de salida no es 0, imprimiendo el `stderr` de FFmpeg. En Windows usa `CREATE_NO_WINDOW` para que no parpadee una consola negra por cada vídeo. |

**Comando construido y significado de cada bandera:**

| Bandera | Efecto |
|---|---|
| `-hide_banner -loglevel error` | Solo imprime errores reales, no la cabecera de versión. |
| `-y` | Sobrescribe la salida sin preguntar (el núcleo ya garantizó un nombre libre). |
| `-map 0` | Conserva **todos** los streams: vídeo, audio, subtítulos, pistas alternativas. Sin esto FFmpeg elegiría solo uno de cada tipo y se perderían pistas. |
| `-map_metadata -1` | Descarta los metadatos del contenedor (título, autor, GPS, dispositivo, fecha de grabación). |
| `-map_chapters -1` | Descarta los marcadores de capítulo. |
| `-c copy` | Remux sin recodificar. |
| `-fflags +bitexact` y `-flags:v/-flags:a +bitexact` | Impide que FFmpeg firme el archivo de salida con su propia versión (`encoder: Lavf63.1.100`). En una herramienta de privacidad, ese campo delata que el archivo fue procesado. |

---

### 2.4 `limpiadores/proveedor.py`

#### Clase `ProveedorLimpiadores`
Resuelve qué limpiador corresponde a cada archivo según su extensión. Las instancias se crean una sola vez como atributos de clase y se reutilizan: los limpiadores no guardan estado, así que compartirlos entre hilos es seguro.

**Atributos de clase:**

| Atributo | Contenido |
|---|---|
| `FORMATOS_IMAGEN` | `.jpg .jpeg .png .webp .bmp .tif .tiff` |
| `FORMATOS_VIDEO` | `.mp4 .mkv .mov .avi .flv .webm .m4v` |
| `_limpiador_imagen` / `_limpiador_video` | Instancias únicas y compartidas. |

**Métodos (todos de clase):**

| Método | Firma | Qué hace |
|---|---|---|
| `obtener_segun_archivo` | `(ruta_archivo: Path) -> Optional[LimpiadorBase]` | Normaliza la extensión a minúsculas y devuelve la instancia adecuada, o `None` si el formato no está soportado. `None` no es un error: el núcleo lo traduce a "Formato no soportado" en el informe. |
| `extensiones_soportadas` | `() -> set[str]` | Unión de ambos conjuntos. Útil para validaciones y para el filtro de arrastrar-y-soltar si se añade. |
| `patron_dialogo` | `() -> str` | Genera la cadena de comodines (`*.avi *.bmp *.flv ...`) que consume el filtro del diálogo de selección de archivos. Se calcula en vez de escribirse a mano, para que al añadir un formato el diálogo se actualice solo. |

**Cómo añadir un formato nuevo:** crear la clase heredando de `LimpiadorBase`, añadir su conjunto de extensiones y una rama en `obtener_segun_archivo`. Nada más cambia.

---

## 3. Módulo `nucleo/`

### 3.1 `nucleo/procesador.py`

#### Clase `ResultadoArchivo` (dataclass congelada)
El informe de un único archivo. Es inmutable (`frozen=True`) para poder cruzar fronteras de hilos sin riesgo de que alguien lo modifique a medias.

| Campo | Tipo | Significado |
|---|---|---|
| `ruta_origen` | `Path` | Archivo que se intentó limpiar. |
| `ruta_salida` | `Path \| None` | Dónde quedó el resultado. `None` si falló. |
| `exito` | `bool` | Si la operación terminó bien. |
| `mensaje` | `str` | Texto legible para mostrar en pantalla ("Limpiado", "Formato no soportado", "FFmpeg no está instalado..."). |

#### Clase `ProcesadorEnLote`
Administra la cola de procesamiento en paralelo mediante un grupo de hilos. Se usan hilos y no procesos porque el trabajo real —Pillow al codificar, FFmpeg como proceso externo— libera el GIL, de modo que los hilos dan paralelismo real sin el coste de arrancar intérpretes nuevos.

| Método | Firma | Qué hace |
|---|---|---|
| `__init__` | `(max_hilos: int = 4)` | Guarda el tamaño del grupo de hilos, con mínimo de 1 para evitar un `ThreadPoolExecutor` inválido. La interfaz le pasa `os.cpu_count()`. |
| `procesar_archivos` | `(lista_archivos, carpeta_destino, notificar_progreso) -> List[ResultadoArchivo]` | Método principal. Crea la carpeta destino si no existe, envía cada archivo al grupo de hilos con `submit`, y consume los resultados con `as_completed` a medida que terminan. Envuelve `futuro.result()` en un `try/except` que convierte cualquier excepción imprevista en un `ResultadoArchivo` fallido: **la cola nunca se rompe a la mitad**. Llama a `notificar_progreso(resultado, completados, total)` una vez por archivo terminado, desde el hilo trabajador. Devuelve la lista completa de resultados. |
| `_tarea_individual` | `(ruta, carpeta_destino) -> ResultadoArchivo` *(estático)* | Lo que ejecuta cada hilo para un archivo. Encadena cuatro comprobaciones y devuelve un resultado descriptivo en cada punto de salida: ¿el archivo sigue existiendo? → ¿hay limpiador para su extensión? → ¿están sus dependencias? → ejecutar `limpiar`. |
| `_ruta_salida_libre` | `(ruta, carpeta_destino) -> Path` *(estático)* | Construye `sin_meta_<nombre>` en la carpeta destino. Si ya existe, añade un sufijo numérico (`sin_meta_foto_1.jpg`) hasta encontrar un nombre libre, de modo que procesar dos veces el mismo lote no destruye la corrida anterior. |

**Sobre `notificar_progreso`:** es un `Callable[[ResultadoArchivo, int, int], None]`. Al recibirlo como parámetro, el núcleo no depende de la interfaz: en una versión de línea de comandos bastaría con pasarle un `print`.

**Por qué `submit` + `as_completed` y no `executor.map`:** con `map`, si una tarea lanza una excepción y nadie itera el resultado, el fallo se pierde en silencio. `as_completed` obliga a llamar a `.result()`, donde el error sí se ve y se puede convertir en un informe.

---

## 4. Módulo `interfaz/`

### 4.1 `interfaz/ventana_principal.py`

**Configuración del módulo:** `ctk.set_appearance_mode("System")` sigue el tema claro/oscuro de Windows; `ctk.set_default_color_theme("blue")` fija la paleta.

#### Clase `VentanaPrincipal(ctk.CTk)`
Ventana única de la aplicación (hereda de la ventana raíz de CustomTkinter).

**Regla de hilos, la más importante del módulo:** el procesamiento corre en un hilo secundario para que la ventana no se congele, pero **Tkinter solo admite llamadas desde el hilo principal**. Tocar un widget desde un hilo trabajador produce cuelgues intermitentes muy difíciles de diagnosticar. Por eso todo repintado se encola con `self.after(0, funcion, *args)`, que ejecuta la función en el hilo principal en el siguiente ciclo del bucle de eventos.

**Estado de la instancia:**

| Atributo | Tipo | Significado |
|---|---|---|
| `archivos_seleccionados` | `List[Path]` | La cola actual. |
| `carpeta_destino` | `Path` | Por defecto `~/Archivos_Limpiados`. |
| `procesador` | `ProcesadorEnLote` | Configurado con `os.cpu_count()` hilos. |

**Métodos — construcción:**

| Método | Qué hace |
|---|---|
| `__init__` | Fija título, tamaño (780×600) y tamaño mínimo (640×500), inicializa el estado, construye los widgets y comprueba FFmpeg. |
| `_construir_interfaz` | Crea y coloca todos los widgets, en las cinco zonas apiladas descritas abajo. |
| `_escribir_en_cola(lineas)` | Reemplaza por completo el contenido del visor. Alterna `state` entre `normal` y `disabled` para que la caja sea de solo lectura para el usuario pero escribible por el programa. Solo hilo principal. |
| `_agregar_a_cola(linea)` | Añade un renglón al final y hace auto-scroll con `see("end")`. Solo hilo principal. |

**Métodos — acciones del usuario:**

| Método | Disparador | Qué hace |
|---|---|---|
| `_avisar_si_falta_ffmpeg` | Arranque | Comprueba FFmpeg y, si falta, lo avisa **dentro de la ventana** (etiqueta de estado + visor), no con un diálogo modal: las imágenes siguen siendo procesables y frenar el arranque sería desproporcionado. |
| `_seleccionar_archivos` | Botón "Seleccionar archivos" | Abre `askopenfilenames` con el filtro generado por `ProveedorLimpiadores.patron_dialogo()`, guarda las rutas y pinta la cola con estado pendiente `[  ]`. Si el usuario cancela, no toca nada. |
| `_seleccionar_carpeta_destino` | Botón "Carpeta destino" | Abre `askdirectory` y actualiza la ruta y su etiqueta. |
| `_vaciar_cola` | Botón "Vaciar cola" | Descarta la selección y devuelve la pantalla a su estado inicial. |
| `_iniciar_procesamiento` | Botón verde | Valida que haya archivos (si no, aviso y retorno), deshabilita el botón para impedir un doble lanzamiento, limpia el visor y arranca el hilo trabajador como `daemon=True` para que no impida cerrar la app. |

**Métodos — hilo secundario y cierre:**

| Método | Contexto | Qué hace |
|---|---|---|
| `_procesar_en_segundo_plano` | Hilo trabajador | Cuerpo del hilo. Define la función interna `actualizar_progreso`, que formatea cada renglón (`[OK]` / `[!!]` + nombre + mensaje) y delega los tres repintados —renglón, barra, etiqueta— al hilo principal vía `after`. Llama a `procesar_archivos` y, al terminar, delega el cierre. Un `try/except` global desvía cualquier fallo del lote a `_finalizar_con_error`. |
| `_finalizar_procesamiento(resultados)` | Hilo principal | Cuenta correctos y fallidos, reactiva el botón, escribe el resumen en la etiqueta y muestra el diálogo final con la ruta de destino. |
| `_finalizar_con_error(detalle)` | Hilo principal | Reactiva el botón y muestra un diálogo de error. Garantiza que la interfaz nunca se quede bloqueada con el botón deshabilitado. |

---

## 4bis. `recursos.py` (raíz del proyecto)

Aísla una única diferencia: en desarrollo los archivos auxiliares están junto al código fuente, pero dentro de un ejecutable de PyInstaller viven en una carpeta temporal cuya ruta llega en `sys._MEIPASS`. Gracias a este módulo, el resto del código no tiene que saberlo.

Vive en la raíz y no dentro de `nucleo/` o `limpiadores/` a propósito: lo consumen ambas capas, y meterlo en una de ellas invertiría la dirección de dependencias descrita en la sección 1.

| Función | Firma | Qué hace |
|---|---|---|
| `esta_empaquetado` | `() -> bool` | `True` si el proceso corre como ejecutable compilado (comprueba `sys.frozen` y `sys._MEIPASS`). |
| `raiz_recursos` | `() -> Path` | Carpeta base desde la que resolver archivos incluidos: la temporal de PyInstaller, o la raíz del proyecto en desarrollo. |
| `ruta_recurso` | `(nombre_relativo: str) -> Path` | Ruta absoluta a un archivo incluido en el paquete. |
| `ruta_ffmpeg` | `() -> str \| None` | Devuelve qué FFmpeg usar, en este orden: (1) la copia incrustada en la aplicación —caso del usuario final, que no instaló nada—; (2) uno del PATH del sistema —caso del desarrollador—. `None` si no hay ninguno. |

---

## 4ter. Módulo `empaquetado/`

Herramientas que solo se ejecutan en la máquina que compila. **Nada de aquí llega al usuario final.** Documentado en detalle en [COMPILACION.md](COMPILACION.md).

| Archivo | Contenido |
|---|---|
| `obtener_ffmpeg.py` | `descargar(url)`, `extraer(datos, tipo, nombre, destino)` y `main()`. Descarga la compilación estática de FFmpeg de la plataforma actual y la deja en `recursos/`. Busca el ejecutable dentro del comprimido sin depender de en qué subcarpeta lo haya puesto quien lo publica, y restaura el permiso de ejecución en macOS y Linux, que no sobrevive al ZIP. |
| `limpiador.spec` | Especificación de PyInstaller común a ambas plataformas; ramifica por `sys.platform` entre un `.exe` de archivo único y un paquete `.app`. Incluye la carpeta de datos de CustomTkinter (que carga temas desde disco en tiempo de ejecución) y `PIL._tkinter_finder` como importación oculta. |
| `construir_windows.ps1` / `construir_mac.sh` | Compilación de principio a fin en cada plataforma. |
| `verificar_paquete.py` | Autocomprobación que se compila con la misma configuración que la app y valida **desde dentro del ejecutable** que Pillow y CustomTkinter cargan, que el FFmpeg incrustado se localiza y responde, y que un JPEG y un MP4 quedan realmente limpios. Devuelve código 1 si algo falla, de modo que el workflow de CI puede bloquear una publicación defectuosa. |

---

## 5. `principal.py`

Punto de entrada. Expone `main()`, que instancia `VentanaPrincipal` y entra en `mainloop()`. La función existe separada del bloque `if __name__ == "__main__"` para que un empaquetador (PyInstaller) o un test puedan invocarla directamente.

---

## 6. `requerimientos.txt`

| Dependencia | Para qué |
|---|---|
| `customtkinter>=5.2.0` | Widgets de la interfaz. |
| `Pillow>=10.0.0` | Lectura y reescritura de imágenes. |

FFmpeg **no** es una dependencia de Python: es un ejecutable del sistema, se instala aparte y solo hace falta para vídeo.

> El plan original incluía `ffmpeg-python`. Se sustituyó por `subprocess` de la biblioteca estándar: ese paquete es un envoltorio fino, lleva años sin mantenimiento activo, y llamar a FFmpeg directamente permite controlar las banderas exactas (`-map 0`, `-map_chapters -1`) y leer el `stderr` real cuando algo falla.

---

## 7. Estado verificado

Probado en Windows 11 con Python 3.14.6, Pillow 12.3.0, CustomTkinter 6.0.0 y FFmpeg 9.0.

**Imágenes:**
- JPEG con EXIF (marca, modelo, software) → salida con `exif={}`.
- PNG con metadatos de texto (autor, comentario) → salida con `info={}`, transparencia intacta.

**Vídeo:**
- MP4 con `title`, `artist`, `comment` y `location` (coordenadas GPS) → todos eliminados. En la salida solo permanecen campos estructurales del contenedor (`major_brand`, `handler_name` genéricos), que no identifican nada.
- Tamaño y contenido preservados: 30 553 → 30 351 bytes, sin recodificar.

**Cola:**
- Archivo `.txt` mezclado en el lote → reportado como "Formato no soportado" sin interrumpir el resto.

**Empaquetado:**
- `LimpiadorMetadatos.exe` de 55,1 MB generado con PyInstaller 6.21.0.
- Arranque en frío medido en 2,2 s y 2,6 s.
- Autocomprobación ejecutada dentro del propio ejecutable: FFmpeg incrustado localizado y funcional, JPEG y MP4 limpiados, ausencia de EXIF verificada.

**No verificado:** la compilación de macOS. No es posible hacerla desde Windows (PyInstaller no admite compilación cruzada); el script y el workflow están escritos, y la primera ejecución en GitHub Actions será su prueba real.
