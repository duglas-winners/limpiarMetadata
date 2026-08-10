# Documentación técnica — Limpiador de Metadatos

Referencia de cada módulo, clase y función del proyecto.

---

## 1. Visión general de la arquitectura

Tres capas independientes, con dependencias en una sola dirección:

```
interfaz/  (CustomTkinter)     ← lo que ve el usuario
    ↓ llama a
nucleo/    (hilos, análisis)   ← orquesta la cola y analiza los archivos
    ↓ llama a
limpiadores/ (Pillow, FFmpeg)  ← hace la limpieza real de un archivo
```

La única excepción a esa dirección es `limpiadores/limpiador_video.py`, que
importa `nucleo.medios` **dentro de la función** que calcula el bitrate. Es una
importación diferida y deliberada: hacerla arriba crearía un ciclo entre ambos
paquetes, porque `nucleo.medios` importa a su vez `limpiadores.proveedor`.

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
                  → coordinador.emitir("avance", ...)  el hilo NO toca Tkinter
  → CoordinadorTrabajo._consumir()  cada 80 ms  [hilo principal]
      → vista_cola.actualizar_resultado(), barra, etiqueta
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
| `limpiar` | `(ruta_entrada, ruta_salida, opciones, al_progresar) -> bool` | Lee el archivo de entrada, genera una copia sin metadatos y la escribe en la ruta de salida. Devuelve `True` si terminó bien. **Nunca lanza excepción**: captura el error, lo imprime y devuelve `False`, para que un archivo corrupto no tumbe el lote completo. |
| `esta_disponible` | `() -> tuple[bool, str]` | Indica si las dependencias externas del limpiador están presentes. Devuelve `(True, "")` si puede trabajar, o `(False, motivo)` con un mensaje legible para el usuario. Permite avisar "falta FFmpeg" antes de intentar procesar, en vez de fallar archivo por archivo. |

`al_progresar` recibe la fracción completada, de 0 a 1, tantas veces como el limpiador pueda informar. Es opcional: uno que trabaja en un solo paso —como el de imágenes— puede no llamarlo nunca, y el procesador da el archivo por completo al terminar.

#### Dataclass `OpcionesLimpieza`
Ajustes que el usuario elige en la interfaz y que afectan a cómo se procesa cada archivo. Se pasan a **todos** los limpiadores; cada uno atiende los que le conciernen e ignora el resto — `LimpiadorImagen` ignora `comprimir_video`.

| Campo | Por defecto | Efecto |
|---|---|---|
| `comprimir_video` | `False` | Recodifica el vídeo a bitrate objetivo en lugar de remuxear |

Existe para que añadir un ajuste nuevo no obligue a cambiar la firma del contrato ni la del procesador.

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
| `-c copy` | Remux sin recodificar (solo en modo sin comprimir). |
| `-metadata:s:v:0 encoder=` | Borra la firma que **el codificador** escribe al recodificar (`encoder: Lavc libx264`). `-map_metadata` no la toca, porque no viene del contenedor de entrada. |
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
| `ruta_salida` | `Path \| None` | Dónde quedó el resultado. `None` si no se generó. |
| `exito` | `bool` | Atajo para "hay un archivo de salida". |
| `mensaje` | `str` | Texto legible para mostrar en pantalla. |
| `codigo` | `str` | `"limpiado"`, `"omitido"` o `"error"`. |

**Por qué `codigo` y no solo `exito`:** para el usuario, un `.txt` en la cola y un JPEG corrupto no son lo mismo. El primero es un archivo que no le correspondía a esta herramienta; el segundo es un fallo real. Un booleano los agrupa y obliga a la interfaz a pintar ambos de rojo, haciendo que el usuario busque un problema donde no lo hay. Los tres códigos permiten a la interfaz dar a cada uno su color y su lenguaje.

| Código | Cuándo | Color en la interfaz |
|---|---|---|
| `limpiado` | Se procesó correctamente | Verde |
| `omitido` | No había nada que hacer: formato no soportado, o FFmpeg ausente | Ámbar |
| `error` | Se intentó y falló: archivo desaparecido, destino inválido, fallo del limpiador | Rojo |

#### Clase `ProcesadorEnLote`
Administra la cola de procesamiento en paralelo mediante un grupo de hilos. Se usan hilos y no procesos porque el trabajo real —Pillow al codificar, FFmpeg como proceso externo— libera el GIL, de modo que los hilos dan paralelismo real sin el coste de arrancar intérpretes nuevos.

| Método | Firma | Qué hace |
|---|---|---|
| `__init__` | `(max_hilos: int = 4)` | Guarda el tamaño del grupo de hilos, con mínimo de 1 para evitar un `ThreadPoolExecutor` inválido. La interfaz le pasa `os.cpu_count()`. |
| `_hilos_para` | `(opciones) -> int` | Cuántos archivos procesar a la vez. **Al comprimir baja a uno solo**, por dos razones: x264 ya reparte su trabajo entre todos los núcleos, así que varias compresiones simultáneas compiten sin acelerar nada; y con un único archivo en curso, el progreso individual que muestra la interfaz es inequívoco. |
| `procesar_archivos` | `(lista_archivos, carpeta_destino, notificar_progreso) -> List[ResultadoArchivo]` | Método principal. Crea la carpeta destino si no existe, envía cada archivo al grupo de hilos con `submit`, y consume los resultados con `as_completed` a medida que terminan. Envuelve `futuro.result()` en un `try/except` que convierte cualquier excepción imprevista en un `ResultadoArchivo` fallido: **la cola nunca se rompe a la mitad**. Llama a `notificar_progreso(resultado, completados, total)` una vez por archivo terminado, desde el hilo trabajador. Devuelve la lista completa de resultados. |
| `_tarea_individual` | `(ruta, carpeta_destino) -> ResultadoArchivo` *(estático)* | Lo que ejecuta cada hilo para un archivo. Encadena cuatro comprobaciones y devuelve un resultado descriptivo en cada punto de salida: ¿el archivo sigue existiendo? → ¿hay limpiador para su extensión? → ¿están sus dependencias? → ejecutar `limpiar`. |
| `_ruta_salida_libre` | `(ruta, carpeta_destino) -> Path` *(estático)* | **La copia limpia conserva el nombre original.** Como eso hace que el nombre de salida pueda coincidir con el de entrada, aplica dos salvaguardas: si la ruta calculada resuelve al mismo archivo de origen, lanza `DestinoInvalido` en vez de destruirlo; si ya existe *otro* archivo con ese nombre (corrida anterior), añade sufijo numérico (`foto_1.jpg`). |

#### Excepción `DestinoInvalido`
Señala que la ruta de salida calculada pondría en riesgo el archivo original. La captura `_tarea_individual` y la convierte en un `ResultadoArchivo` fallido con mensaje legible, de modo que el resto del lote continúa.

> **Por qué existe:** la versión inicial prefijaba las copias con `sin_meta_`, lo que hacía imposible la colisión. Al pasar a conservar el nombre original a petición del usuario, esa garantía desapareció y hubo que reponerla explícitamente. La interfaz comprueba lo mismo antes de arrancar el lote; esta es la segunda barrera, para que ninguna ruta de ejecución pueda saltársela.

**Sobre `notificar_progreso`:** es un `Callable[[ResultadoArchivo, int, int], None]`. Al recibirlo como parámetro, el núcleo no depende de la interfaz: en una versión de línea de comandos bastaría con pasarle un `print`.

**Por qué `submit` + `as_completed` y no `executor.map`:** con `map`, si una tarea lanza una excepción y nadie itera el resultado, el fallo se pierde en silencio. `as_completed` obliga a llamar a `.result()`, donde el error sí se ve y se puede convertir en un informe.

---

### 3.2 `nucleo/miniaturas.py`

Genera las vistas previas de la vista de detalle. Vive en `nucleo/` y no en `interfaz/` porque no depende de Tkinter: produce objetos `PIL.Image`, y quien los pinta decide cómo.

**Estado del módulo:** una caché `dict` protegida por un `Lock`, indexada por `(ruta, lado)`. La misma miniatura no se genera dos veces aunque se pida desde varios hilos a la vez.

| Función | Firma | Qué hace |
|---|---|---|
| `obtener` | `(ruta: Path, lado: int = 64) -> Image \| None` | Punto de entrada. Consulta la caché, genera si falta, y guarda. Devuelve `None` si el archivo no admite vista previa. Seguro entre hilos. |
| `_generar` | `(ruta, lado) -> Image \| None` | Despacha a imagen o vídeo según la extensión. Captura cualquier excepción y devuelve `None`: **una vista previa fallida nunca debe impedir procesar el archivo**. |
| `_encajar` | `(imagen, lado) -> Image` | Reduce con `thumbnail` (LANCZOS) y centra el resultado sobre un lienzo cuadrado transparente, para que todas las filas queden alineadas sea cual sea la proporción del original. |
| `_desde_imagen` | `(ruta, lado) -> Image` | Abre con Pillow y encaja. |
| `_desde_video` | `(ruta, lado) -> Image \| None` | Extrae un fotograma con FFmpeg volcándolo a PNG por `stdout`, sin archivo temporal. Busca en el **segundo 1** para evitar los fundidos en negro que abren muchos vídeos, y reintenta desde el inicio si el clip es más corto. |
| `limpiar_cache` | `() -> None` | Libera las miniaturas guardadas. Se llama al vaciar la cola. |

#### Niveles de compresión

`NIVELES` asocia cada nombre visible con dos palancas: cuánto bitrate se concede (`factor`) y hasta qué altura se reduce la imagen (`altura_max`).

| Nivel | `altura_max` | `factor` | Sobre 1080p |
|---|---|---|---|
| Ligera | — | 1.00 | 1080p @ 3000 kbps |
| Media | 1080 | 0.55 | 1080p @ 1650 kbps |
| Fuerte | 720 | 0.80 | 720p @ 1200 kbps |
| Máxima | 480 | 0.90 | 480p @ 720 kbps |

**Por qué dos palancas y no solo el bitrate.** A bitrates bajos, un 720p limpio se ve claramente mejor que un 1080p lleno de artefactos: el codificador reparte los mismos bits entre menos píxeles. Sin la palanca de resolución, los niveles fuertes producirían archivos pequeños pero feos.

`bitrate_objetivo` parte del valor de referencia de la altura **resultante**, no de la original — si se va a escalar hacen falta menos bits — y le aplica el factor. `altura_objetivo` nunca agranda: un vídeo 480p se queda en 480p en todos los niveles.

Medido sobre 1080p a 8 Mbps, el resultado real cae entre un 1% y un 5% por debajo del techo estimado en los cuatro niveles.

---

### 3.3 `nucleo/preferencias.py`

Ajustes que sobreviven al cierre de la aplicación. Se guardan en un JSON dentro de la carpeta que cada sistema destina a configuración:

| Sistema | Ruta |
|---|---|
| Windows | `%APPDATA%\LimpiadorMetadatos\preferencias.json` |
| macOS | `~/Library/Application Support/LimpiadorMetadatos/preferencias.json` |
| Linux | `~/.config/LimpiadorMetadatos/preferencias.json` |

**No se guardan junto al ejecutable** a propósito: en Windows suele estar en una ruta sin permiso de escritura, y en macOS dentro del propio paquete `.app`, que no debe modificarse.

| Función | Qué hace |
|---|---|
| `carpeta_configuracion` | Resuelve la carpeta correcta según la plataforma |
| `cargar` | Lee lo guardado, completado con los valores por defecto. Un archivo ausente o ilegible significa primera ejecución, no error. **Solo acepta claves conocidas**, para que un archivo escrito por una versión posterior no inyecte ajustes que esta no entiende |
| `guardar` | Escribe primero en un `.tmp` y luego lo reemplaza, de modo que un corte a mitad de la escritura no deje el JSON ilegible |
| `carpeta_destino_valida` | Devuelve la carpeta guardada, o la de por defecto si ya no existe |

**Ninguna operación puede tumbar la aplicación.** Permisos, disco lleno, JSON corrupto: todo se traga y se sigue con los valores por defecto. Perder una preferencia es un inconveniente; no arrancar es un fallo.

`carpeta_destino_valida` existe por un caso concreto: la carpeta pudo desaparecer entre dos sesiones —un disco externo desconectado, una unidad de red caída, una carpeta borrada—. Sin la comprobación, la aplicación arrancaría apuntando a una ruta muerta y fallaría al procesar.

**Qué se recuerda y qué no:** la carpeta destino y la densidad de vista. **La casilla de compresión no**, deliberadamente: recodifica con pérdida de calidad, y debe ser una decisión consciente en cada sesión, no algo heredado que el usuario descubra cuando ya ha procesado.

---

---

## 4. Módulo `interfaz/`

La interfaz está dividida por responsabilidad, no por pantalla: todo vive en una sola ventana, pero cada pieza hace una cosa.

| Archivo | Responsabilidad | Líneas |
|---|---|---|
| `estilos.py` | Colores, símbolos de estado e intervalos. Sin lógica | 59 |
| `modelo_cola.py` | El estado de la cola. **No importa Tkinter** | 111 |
| `coordinador.py` | Puente entre hilos de trabajo y la interfaz | 123 |
| `barras.py` | Las cuatro barras de control | 206 |
| `ventana_principal.py` | Ensambla los componentes y coordina entre ellos | 310 |
| `vista_cola.py` | Dibuja la cola y gestiona la interacción con las filas | 341 |

**Por qué esta división.** `ventana_principal.py` había llegado a 446 líneas mezclando cinco cosas: construir widgets, manipular la cola, calcular pesos, lanzar hilos y presentar resultados. El criterio del corte fue *qué cambia junto*: retocar colores no debe obligar a leer lógica de hilos, y cambiar cómo se estima el peso no debe tocar el dibujo de una fila.

Dos consecuencias que valen más que el recuento de líneas:

1. **`modelo_cola.py` no importa Tkinter.** El estado de la cola —qué archivos hay, cuáles están marcados, cuánto pesan— se puede probar sin abrir una ventana.
2. **`coordinador.py` concentra la regla de hilos.** Antes, cada sitio que lanzaba trabajo en segundo plano tenía que acordarse de no tocar Tk. Ahora quien añada una tarea usa `ejecutar` o `emitir` y la restricción se cumple sola.

### 4.0 `interfaz/estilos.py`

Constantes visuales en un solo sitio. Cada color se declara como par `(claro, oscuro)`; CustomTkinter elige según el tema del sistema. Contiene la tabla `ESTADOS`, única fuente de verdad del aspecto de los chips: añadir un estado nuevo es añadir una entrada.

### 4.0b `interfaz/modelo_cola.py`

| Clase | Qué es |
|---|---|
| `FilaArchivo` | Estado de un archivo: ruta, estado, mensaje, ruta de salida, si está marcado |
| `ColaArchivos` | Colección ordenada de filas, con las operaciones que la interfaz necesita: `agregar` (ignora repetidos), `quitar_marcadas`, `marcar_todas`, `reiniciar_estados`, `aplicar_resultado`, y las consultas `rutas`, `total_marcadas`, `peso_total`, `tiene_videos` |

### 4.0c `interfaz/coordinador.py`

#### Clase `CoordinadorTrabajo`
Lanza tareas en hilos y entrega sus resultados en el hilo principal. Recibe un diccionario `manejadores` que asocia el nombre de cada evento con la función que lo atiende.

| Método | Qué hace |
|---|---|
| `ejecutar(funcion)` | Corre algo en un hilo `daemon` |
| `emitir(tipo, carga)` | Encola un evento para el hilo principal |
| `procesar_lote(...)` | Limpia el lote emitiendo `avance` por archivo y `fin` o `error` al acabar |
| `estimar_peso(...)` | Calcula el techo de peso en segundo plano y emite `peso` |
| `estimacion_vigente(n)` | Si esa estimación sigue correspondiendo a la cola actual |
| `_consumir` | Vacía la cola cada 80 ms y se reprograma mientras la ventana exista |

### 4.0d `interfaz/barras.py`

Cuatro componentes cerrados. Construyen sus widgets, exponen métodos para consultarlos, y avisan de la interacción mediante callbacks. **No conocen el procesador ni la cola**, solo su trozo de pantalla.

| Clase | Zona | Contenido |
|---|---|---|
| `BarraAcciones` | 1 | Agregar, destino, vaciar, conmutador de vista |
| `BarraSeleccion` | 3 | Marcar todos, quitar los marcados, contador |
| `BarraCompresion` | 3b | Casilla de comprimir, nota y peso |
| `PanelProgreso` | 5 | Barra de progreso y línea de estado |

Todas exponen `bloquear(bool)`, que la ventana llama en bloque al empezar y terminar una corrida.

### 4.0e `interfaz/vista_cola.py`

Componente que encapsula el visor de la cola con sus dos presentaciones. Existe como módulo aparte porque la lógica de dos vistas, miniaturas asíncronas y estado por fila desbordaba la ventana principal.

**Constante de módulo `ESTADOS`:** diccionario que asocia cada código de estado con su símbolo, etiqueta, color de texto y color de fondo. Es la única fuente de verdad del aspecto de los chips; añadir un estado nuevo es añadir una entrada.

#### Clase `FilaArchivo`
Estado de un archivo en la cola, **independiente de cómo se dibuje**. Es lo que permite alternar de vista, quitar filas o redibujar sin perder resultados: los widgets se destruyen y recrean, este objeto no.

| Miembro | Tipo | Significado |
|---|---|---|
| `ruta` | `Path` | Archivo de origen |
| `estado` | `str` | Clave de `ESTADOS`: `pendiente`, `limpiado`, `omitido`, `error` |
| `mensaje` | `str` | Texto legible del desenlace |
| `ruta_salida` | `Path \| None` | Dónde quedó la copia limpia |
| `marcada` | `bool` | Si el usuario la seleccionó para quitarla |
| `aplicar(resultado)` | método | Vuelca un `ResultadoArchivo` sobre la fila |
| `reiniciar()` | método | La devuelve a pendiente |
| `tamano_legible` | propiedad | Tamaño formateado (`2.4 MB`), o `?` si el archivo ya no es accesible |

#### Clase `VistaCola(ctk.CTkFrame)`

Recibe un callback `al_cambiar_seleccion(marcadas: int)` con el que la ventana principal mantiene al día su barra de selección. La vista no conoce esos widgets; solo avisa de que algo cambió.

**Métodos públicos** (todos desde el hilo principal):

| Método | Qué hace |
|---|---|
| `establecer_modo(modo)` | Alterna entre `"lista"` y `"detalle"`, conservando el estado |
| `cargar(rutas)` | Sustituye la cola entera |
| `agregar(rutas)` | **Suma** a la cola ignorando repetidos; devuelve cuántos añadió |
| `quitar_marcados()` | Elimina las filas marcadas; devuelve cuántas quitó |
| `marcar_todas(marcar)` | Marca o desmarca todas de golpe |
| `vaciar(aviso=None)` | Descarta la cola; con `aviso`, lo muestra en lugar de las filas |
| `reiniciar_estados()` | Devuelve todas las filas a pendiente |
| `actualizar_resultado(resultado)` | Aplica el desenlace de un archivo y refresca |
| `bloquear(bloqueada)` | Desactiva las casillas mientras se procesa |
| `rutas` | Propiedad: archivos actualmente en la cola, en orden |
| `total_marcadas` | Propiedad: cuántas filas están marcadas |

**Métodos internos relevantes:**

| Método | Qué hace |
|---|---|
| `_redibujar` | Destruye lo que creó y reconstruye la lista; también pinta el estado vacío |
| `_crear_fila` | Construye una fila completa. Un solo método para ambas vistas: el modo solo decide si añade miniatura y línea de datos |
| `_crear_chip_estado` | Etiqueta coloreada con símbolo y texto, a la derecha de la fila |
| `_alternar_marca` | Cambia la marca y **recolorea solo esa fila** |
| `_pedir_miniatura` | Lanza un hilo que genera la miniatura y **deposita el resultado en una cola** |
| `_consumir_cola` | Vacía esa cola en el hilo principal y se reprograma cada 100 ms |
| `_colocar_miniatura` | Coloca la imagen, o el texto "sin vista" si no hubo |

**Cuatro decisiones que evitan fallos concretos:**

1. **`_widgets_filas` en vez de `winfo_children()`.** Al redibujar hay que destruir las filas anteriores, pero `winfo_children()` sobre un `CTkScrollableFrame` devuelve también el lienzo y la barra de desplazamiento internos de CustomTkinter. Destruirlos rompe el contenedor. El componente lleva su propia lista de lo que él creó y solo destruye eso.

2. **`_imagenes_vivas`.** Tkinter no retiene referencias a las imágenes que muestra; sin una lista que las mantenga vivas, el recolector de basura las libera y los recuadros aparecen en blanco.

3. **`_generacion`.** Un contador que sube en cada `cargar` o `vaciar`. Una miniatura que termina de generarse cuando su archivo ya no está en la cola se descarta, en lugar de pintarse sobre la fila equivocada.

4. **`_contenedores`, indexado por `id(fila)`.** Marcar una casilla solo recolorea su propio marco. Redibujar la lista entera reconstruiría todas las filas y haría parpadear las miniaturas en la vista de detalle en cada clic.

---

### 4.1 `interfaz/ventana_principal.py`

**Configuración del módulo:** `ctk.set_appearance_mode("System")` sigue el tema claro/oscuro de Windows; `ctk.set_default_color_theme("blue")` fija la paleta.

#### Clase `VentanaPrincipal(ctk.CTk)`
Ventana única de la aplicación (hereda de la ventana raíz de CustomTkinter).

**Regla de hilos, la más importante del módulo:** el procesamiento corre en un hilo secundario para que la ventana no se congele, pero **Tkinter solo admite llamadas desde el hilo principal**, y eso **incluye `after()`**: registrar una llamada diferida crea un comando en el intérprete Tcl, operación que no es segura entre hilos.

Por eso el hilo trabajador no toca Tkinter en absoluto. Deposita cada novedad en `self.cola_eventos` (una `queue.Queue`), y el hilo principal la vacía cada 80 ms con `_consumir_eventos`. Los eventos son tuplas `(tipo, carga)` con tres tipos: `"avance"`, `"fin"` y `"error"`.

> **Por qué no `after()` desde el hilo:** es un patrón extendido y funciona *casi* siempre, lo que lo hace especialmente traicionero. Al probar la vista de detalle apareció como `RuntimeError: main thread is not in main loop`. El patrón de cola elimina la clase entera de fallo en lugar de ocultarla.

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
| `_cambiar_vista` | Conmutador Lista/Detalle | Traduce la etiqueta del botón al modo interno y lo delega a `VistaCola`. |
| `_al_cambiar_seleccion` | Callback de `VistaCola` | Sincroniza la barra de selección: activa o desactiva "Quitar", le pone el recuento, actualiza el contador y marca la casilla general **solo si lo están todas** las filas. |
| `_agregar_archivos` | Botón "Agregar archivos" | Suma a la cola en vez de reemplazarla, e informa de cuántos se añadieron y cuántos ya estaban. |
| `_marcar_todos` | Casilla "Marcar todos" | Propaga el valor de la casilla a toda la cola. |
| `_quitar_marcados` | Botón "Quitar de la cola" | Saca las filas marcadas e informa de cuántas fueron. |
| `_bloquear_controles` | Inicio y fin del proceso | Desactiva o reactiva de una vez todo lo que modifica la cola. Centralizado en un método para que **ninguna ruta de salida deje la interfaz a medio bloquear**. |
| `_avisar_si_falta_ffmpeg` | Arranque | Comprueba FFmpeg y, si falta, lo avisa **dentro de la ventana** (etiqueta de estado + visor), no con un diálogo modal: las imágenes siguen siendo procesables y frenar el arranque sería desproporcionado. |
| `_seleccionar_archivos` | Botón "Seleccionar archivos" | Abre `askopenfilenames` con el filtro generado por `ProveedorLimpiadores.patron_dialogo()`, guarda las rutas y carga la cola. Si el usuario cancela, no toca nada. |
| `_seleccionar_carpeta_destino` | Botón "Carpeta destino" | Abre `askdirectory` y actualiza la ruta y su etiqueta. |
| `_vaciar_cola` | Botón "Vaciar cola" | Descarta la selección y devuelve la pantalla a su estado inicial. |
| `_iniciar_procesamiento` | Botón verde | Valida que haya archivos y que **la carpeta destino no sea la de ningún original** (si lo es, muestra un error y no arranca), deshabilita el botón para impedir un doble lanzamiento, reinicia los estados y arranca el hilo trabajador como `daemon=True`. |
| `_consumir_eventos` | Temporizador cada 80 ms | Aplica en el hilo principal las novedades depositadas por el trabajador. Se reprograma mientras la ventana exista. |

**Métodos — hilo secundario y cierre:**

| Método | Contexto | Qué hace |
|---|---|---|
| `_procesar_en_segundo_plano` | Hilo trabajador | Cuerpo del hilo. No toca Tkinter: su `actualizar_progreso` solo hace `cola_eventos.put(("avance", ...))`. Llama a `procesar_archivos` y encola `"fin"` con los resultados; un `try/except` global encola `"error"`. |
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

**Nombre de salida (v1.1):**
- Los tres archivos de prueba salen con nombre idéntico al original, espacios incluidos.
- Segunda corrida sobre la misma carpeta destino → `captura_1.png`, `clip_1.mp4`, `foto vacaciones_1.jpg`; ninguna copia anterior se pierde.
- Destino igual a la carpeta de los originales → los tres archivos se rechazan con mensaje explícito, los originales quedan intactos y su EXIF sigue presente (comprobado leyéndolo después).

**Interfaz (v1.1):**
- Conmutar Lista → Detalle → Lista → Detalle conserva las 3 filas del modelo y el contenedor desplazable sigue sano en cada paso.
- Las 3 miniaturas (JPEG, PNG y fotograma de MP4) se generan y colocan; la caché devuelve el mismo objeto en la segunda petición.
- Procesamiento completo lanzado desde la interfaz: 3 correctos, barra al 100 %, nombres idénticos a los originales.
- Intentar procesar con destino = origen deja el botón activo y muestra el diálogo de error.

**Selección y estados (v1.2):**
- Agregar en dos tandas acumula (2 + 2 = 4) en vez de reemplazar; volver a agregar los mismos devuelve 0 añadidos y la cola no cambia.
- Marcar una fila deja el contador en "1 de 4 marcados" y el botón en "Quitar de la cola (1)"; quitarla deja 3 filas, sin el archivo colado, y el botón vuelve a deshabilitarse.
- "Marcar todos" marca las 3 y desmarcarlo las libera.
- Tras procesar un lote con un `.txt` mezclado: los tres medios quedan en `limpiado` y el `.txt` en **`omitido`** (no `error`), con mensaje "No es una imagen ni un vídeo".
- Los controles bloqueados durante el proceso vuelven a activarse al terminar.
- Verificado además visualmente sobre capturas de la ventana real, en las tres situaciones: cola cargada, vista de detalle con miniaturas y lote ya procesado con estados mixtos.

**Empaquetado:**
- `LimpiadorMetadatos.exe` de 55,1 MB generado con PyInstaller 6.21.0.
- Arranque en frío medido en 2,2 s y 2,6 s.
- Autocomprobación ejecutada dentro del propio ejecutable: FFmpeg incrustado localizado y funcional, JPEG y MP4 limpiados, ausencia de EXIF verificada.

**No verificado:** la compilación de macOS. No es posible hacerla desde Windows (PyInstaller no admite compilación cruzada); el script y el workflow están escritos, y la primera ejecución en GitHub Actions será su prueba real.
