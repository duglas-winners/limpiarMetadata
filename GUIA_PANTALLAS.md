# Guía de pantallas — Limpiador de Metadatos

Especificación de la interfaz: qué pantallas tiene la aplicación, qué va en cada una y cómo se comporta en cada estado. Sirve tanto para entender la interfaz actual como para reconstruirla o rediseñarla sin perder nada.

---

## Principio de diseño

**Una sola pantalla, seis zonas apiladas.** El flujo de la aplicación es lineal —elegir archivos, elegir destino, procesar, ver resultado—, así que no se justifican pestañas, asistentes ni ventanas secundarias. Todo cabe en una ventana y el usuario ve el estado completo del trabajo de un vistazo.

Las únicas ventanas adicionales son diálogos del sistema operativo (selector de archivos, selector de carpeta) y avisos emergentes al terminar.

---

## Pantalla 1 — Ventana principal

Es la aplicación entera. Tamaño 880×680, mínimo 720×560.

```
┌────────────────────────────────────────────────────────────────────┐
│  Limpiador de Metadatos - Imagenes y Videos                _ □ ✕   │
├────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ [Agregar archivos] [Carpeta destino] [Vaciar]  [Lista│Detalle]│  │ ← Zona 1
│  └──────────────────────────────────────────────────────────────┘  │
│  Destino: C:\Users\Duglas\Archivos_Limpiados                       │ ← Zona 2
│                                                                    │
│  ☐ Marcar todos   [ Quitar de la cola (1) ]      1 de 3 marcados   │ ← Zona 3
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ ☐  foto_playa.jpg                             (• En cola  )  │  │
│  │ ☑  captura.png              ← resaltada       (• En cola  )  │  │ ← Zona 4
│  │ ☐  clip_boda.mp4                              (• En cola  )  │  │  (vista Lista)
│  │                                                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  fiesta.mp4 — 42%                                                  │
│  ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │ ← Zona 5
│  Progreso general: 1 de 3 — 48%                                    │
│  ████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │
│         Comprimiendo: esto puede tardar varios minutos.            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Limpiar metadatos                         │  │ ← Zona 6
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

La Zona 4 en vista **Detalle**, ya procesada:

```
  ┌────────────────────────────────────────────────────────────────┐
  │ ☐ ┌──────┐ foto_playa.jpg                      ( ✓ Limpiado )  │
  │   │ 🖼️   │ 2.4 MB · JPG · guardado como foto_playa.jpg        │
  │   └──────┘ Metadatos eliminados                                │
  ├────────────────────────────────────────────────────────────────┤
  │ ☐ ┌──────┐ clip_boda.mp4                       ( ✓ Limpiado )  │
  │   │ 🎞️   │ 184.2 MB · MP4 · guardado como clip_boda.mp4       │
  │   └──────┘ Metadatos eliminados                                │
  ├────────────────────────────────────────────────────────────────┤
  │ ☐ ┌──────┐ notas.txt                           ( ! Omitido  )  │
  │   │ sin  │ 4 B · TXT                                           │
  │   │ vista│ No es una imagen ni un video                        │
  │   └──────┘                                                     │
  └────────────────────────────────────────────────────────────────┘
```

### Zona 1 — Barra de acciones

Un marco horizontal con tres botones alineados a la izquierda, en el orden natural de uso.

| Botón | Color | Función | Regla |
|---|---|---|---|
| **Agregar archivos** | Azul (primario) | Abre el selector; **suma** a la cola en vez de reemplazarla | Siempre activo salvo durante el procesamiento |
| **Carpeta destino** | Azul (primario) | Abre el selector de carpeta | Siempre activo salvo durante el procesamiento |
| **Vaciar todo** | Gris (secundario) | Descarta la cola entera | Deliberadamente gris: es destructivo y no debe competir visualmente con las acciones principales |

El botón dice "Agregar", no "Seleccionar", porque su comportamiento cambió: **acumula**. Permite componer una cola en varias tandas desde carpetas distintas, y los repetidos se ignoran solos. El nombre tiene que reflejar eso o el usuario esperará que reemplace.

A la **derecha** de la misma barra, separado del grupo anterior, va el conmutador de vista (`CTkSegmentedButton` con "Lista" y "Detalle"). Está alineado a la derecha a propósito: no ejecuta trabajo ni modifica la cola, solo cambia cómo se presenta lo que ya hay en pantalla. Agruparlo con los botones de acción sugeriría que hace algo al archivo.

### Zona 2 — Etiqueta de destino

Una línea de texto alineada a la izquierda, siempre visible: `Destino: <ruta completa>`.

Debe mostrarse **siempre**, incluso con la ruta por defecto. Es la respuesta a la pregunta más frecuente del usuario —"¿dónde quedaron mis archivos?"— y tenerla permanentemente en pantalla la elimina de raíz.

### Zona 3 — Barra de selección

Existe para responder a un problema concreto: *"se me coló un archivo, ¿tengo que empezar de cero?"*. La respuesta debe ser no, y esta barra es la que lo hace posible.

| Elemento | Posición | Comportamiento |
|---|---|---|
| **Marcar todos** | Izquierda | Casilla que marca o desmarca la cola entera. **Refleja el estado real**: si el usuario marca las filas una a una hasta completarlas todas, esta casilla se marca sola |
| **Quitar de la cola** | Izquierda, junto a la anterior | Rojo. **Deshabilitado mientras no haya nada marcado.** Su texto incluye el recuento: "Quitar de la cola (3)" |
| **Contador** | Derecha | "3 archivos en la cola" o, si hay marcados, "1 de 3 marcados" |

Tres decisiones deliberadas:

1. **El botón de quitar es rojo y está deshabilitado por defecto.** Es la única acción destructiva de la pantalla; debe verse como tal, pero no debe poder pulsarse en vacío.
2. **El recuento va en el propio botón.** "Quitar de la cola (3)" confirma cuántos se van antes de pulsar, sin necesidad de un diálogo.
3. **Quitar de la cola no borra del disco.** Se dice explícitamente en el manual, porque un botón rojo llamado "Quitar" junto a una lista de archivos puede leerse como borrado.

### Zona 3b — Barra de compresión

| Elemento | Cuándo se ve | Contenido |
|---|---|---|
| Casilla **Comprimir vídeos** | Siempre | Activa la recodificación |
| Selector de nivel | **Solo con la casilla marcada** | Ligera · Media · Fuerte · Máxima |
| Nota | Solo con la casilla marcada | Describe el nivel elegido |

**El selector aparece y desaparece con la casilla.** Sin compresión activa no hace nada, y un control inerte invita a manipularlo esperando un efecto que no llega.

**Cambiar de nivel repinta las estimaciones de todas las filas al instante.** Las cifras ya calculadas se descartan —eran de otro ajuste y mostrarlas sería mentir— y se recalculan; como el análisis del vídeo está cacheado, es cuestión de milisegundos. Eso convierte al selector en una herramienta de exploración: el usuario prueba los cuatro y elige por el número que quiere ver, sin procesar nada.

No lleva ninguna cifra agregada. El peso vive en las filas (ver Zona 4).

Si no hay vídeos en la cola, la nota lo dice —*"(no hay vídeos en la cola)"*— en lugar de dejar la casilla sugiriendo un efecto que no tendría.

### Zona 4 — Lista de archivos

Marco desplazable con una fila por archivo. Ocupa todo el espacio sobrante al redimensionar. **Ya no es una caja de texto**: son filas reales, porque el usuario tiene que poder interactuar con cada una.

Tiene **dos densidades del mismo contenido**:

| | Vista Lista | Vista Detalle |
|---|---|---|
| Casilla de selección | ✓ | ✓ |
| Nombre del archivo | ✓ | ✓ |
| Chip de estado | ✓ | ✓ |
| Mensaje (si aporta más que el chip) | ✓ | ✓ |
| **Peso del archivo** | ✓ (derecha) | ✓ (bajo el nombre) |
| Miniatura 56×56 | — | ✓ |
| Formato · nombre de salida | — | ✓ |

#### El peso va por archivo, no agregado

Una versión anterior mostraba el peso **total** de la cola en la barra superior. Se movió a cada fila porque un total no responde la pregunta que el usuario se hace al mirarlo: *¿cuál de estos archivos es el pesado?* — que es justo lo que hace falta para decidir si comprimir, o cuál quitar de la cola.

Con la compresión marcada, cada vídeo muestra también su techo: `24.4 MB → max. 3.9 MB`. Las imágenes no lo muestran, porque no se comprimen.

En vista **Lista** el peso va a la derecha, antes del chip: mantiene la fila en un solo renglón y deja todos los pesos alineados en columna. En **Detalle** acompaña al formato bajo el nombre.

Mientras se calcula la estimación —requiere analizar el vídeo con FFmpeg— la fila dice `calculando...`, para que el hueco no parezca un dato que falta.

#### Chips de estado

Cada fila lleva a la derecha una etiqueta con fondo propio. **Sustituyen a los marcadores de texto `[OK]` y `[!!]` de versiones anteriores**, que obligaban a leer y descifrar en lugar de reconocer.

| Estado | Símbolo | Etiqueta | Color |
|---|---|---|---|
| `pendiente` | `•` | En cola | Gris |
| `procesando` | `◐` | Procesando | Azul |
| `limpiado` | `✓` | Limpiado | Verde |
| `omitido` | `!` | Omitido | Ámbar |
| `error` | `✕` | Error | Rojo |

Reglas de los chips:

- **Símbolo y color juntos, siempre.** El color se reconoce de un vistazo; el símbolo hace que la información siga estando disponible para quien no distingue bien los colores. Ninguno de los dos basta por sí solo.
- **"Omitido" es un estado propio, distinto de "error".** Un `.txt` en la cola no es un fallo: no había nada que hacer con él. Pintarlo de rojo haría que el usuario buscara un problema inexistente. El ámbar dice "míralo, pero no está roto".
- **El mensaje bajo el nombre solo aparece si añade información** al chip. "Limpiado" + "Limpiado" sería ruido; "Omitido" + "No es una imagen ni un vídeo" sí aporta.

#### Selección

- Casilla a la izquierda de cada fila.
- La fila marcada **se resalta con fondo azul tenue**. La casilla sola es un objetivo pequeño; el fondo hace que la selección se lea sin buscarla.
- Marcar una fila **no redibuja la lista entera**, solo recolorea ese contenedor: redibujar haría parpadear las miniaturas en la vista de detalle.

#### Estados del hueco de miniatura

1. Vacío sobre fondo gris — se está generando.
2. La miniatura — lista.
3. `sin vista` — no se pudo previsualizar (archivo dañado, formato sin vista previa, FFmpeg ausente). **Nunca impide procesar el archivo.**

#### Estado vacío

Cuando no hay archivos, la lista no se queda en blanco: muestra *"No hay archivos en la cola. Pulsa «Agregar archivos» para elegir imágenes o vídeos."* Una zona vacía sin explicación se lee como algo que falló al cargar.

#### Reglas comunes

- **El estado vive en el modelo, no en los widgets.** Alternar de vista, quitar filas o redibujar parte de `FilaArchivo`, así que no se pierde ningún resultado ni siquiera a mitad de una corrida.
- **Las miniaturas se generan fuera del hilo de la interfaz** y se cachean. La ventana nunca se congela esperándolas.
- **Al vaciar la cola se descarta la caché** de miniaturas, para no retener en memoria imágenes de archivos que ya no interesan.
- Cada carga de cola incrementa un contador de generación: una miniatura que termina de generarse tarde, cuando su archivo ya no está en la cola, **se descarta en vez de pintarse** sobre la fila equivocada.

### Zona 5 — Indicadores de estado

**Dos** barras de progreso, no una, más una línea de estado:

| Elemento | Responde a | Contenido |
|---|---|---|
| **Barra del archivo** (fina, arriba) | "¿Este archivo avanza?" | Nombre y porcentaje del archivo en curso |
| **Barra del lote** (gruesa, abajo) | "¿Cuánto falta en total?" | "Progreso general: 2 de 5 — 48%" |
| **Etiqueta de estado** | "¿Qué está pasando?" | Una línea centrada, con el contexto de la corrida |

**Por qué dos y no una.** Con una sola barra que solo avanza al completarse archivos, comprimir un único vídeo de 1,9 GB deja la pantalla inmóvil en 0% durante varios minutos, y la aplicación parece colgada. Fue un fallo real reportado en uso. La barra individual demuestra que el trabajo avanza; la general responde cuánto queda.

La barra del lote **no salta de golpe** al terminar cada archivo: suma la fracción del archivo en curso a los ya completados, así que avanza de forma continua.

**La línea de estado no repite lo que dicen las barras.** Nombrar ahí el archivo actual lo desincroniza — cuando uno termina, la barra ya muestra el siguiente. Durante la corrida conserva el aviso puesto al arrancar (por ejemplo, que comprimir puede tardar).

Textos de la etiqueta según el momento:

| Momento | Texto |
|---|---|
| Al abrir | `Agrega archivos para empezar.` |
| Al abrir sin FFmpeg | `Aviso: FFmpeg no disponible, los videos no se podran procesar.` |
| Tras agregar | `3 archivo(s) agregados.` o `3 agregados. 2 ya estaban en la cola.` |
| Tras quitar | `2 archivo(s) quitados de la cola.` |
| Al arrancar sin comprimir | `Procesando...` |
| Al arrancar comprimiendo | `Comprimiendo: esto puede tardar varios minutos por video.` |
| Al terminar | `Listo: 6 limpiados, 1 omitido.` |
| Tras un fallo global | `El procesamiento se interrumpio.` |

El texto de progreso ya no repite el estado de cada archivo: eso lo dice el chip de su fila, con más claridad. Aquí solo va lo que la fila no puede decir — **por dónde va el lote**.

### Zona 6 — Botón principal

Ancho completo, altura 44 px (mayor que los demás), negrita, color verde. Es la única acción que ejecuta trabajo real, y su tamaño y color lo dejan claro sin necesidad de instrucciones. Su texto es **"Limpiar metadatos"**: nombra el resultado que el usuario quiere, no el mecanismo interno ("procesar la cola").

---

## Estados de la ventana principal

La misma pantalla, cinco configuraciones. Toda la interfaz debe reflejar sin ambigüedad en cuál está.

### Estado A — Inicial (recién abierta)

| Elemento | Valor |
|---|---|
| Lista | Mensaje de estado vacío, o el aviso de FFmpeg |
| Barra de selección | Contador `0 archivos en la cola`, "Quitar" deshabilitado |
| Barra de progreso | En 0 |
| Etiqueta de estado | `Agrega archivos para empezar.` |
| Botón verde | Activo, texto `Limpiar metadatos` |

Pulsar el botón verde en este estado **no arranca nada**: muestra el aviso *"Agrega al menos un archivo antes de limpiar"* y no cambia nada más.

### Estado B — Cola cargada

| Elemento | Valor |
|---|---|
| Lista | Una fila por archivo, chip `• En cola` |
| Barra de selección | `N archivos en la cola`, "Quitar" deshabilitado |
| Barra de progreso | Reiniciada a 0 |
| Botón verde | Activo |

### Estado C — Con archivos marcados

Igual que B, pero:

| Elemento | Valor |
|---|---|
| Filas marcadas | Resaltadas en azul tenue |
| Barra de selección | `1 de 3 marcados`, botón `Quitar de la cola (1)` **activo y rojo** |
| Casilla "Marcar todos" | Marcada solo si lo están **todas** las filas |

### Estado D — Procesando

| Elemento | Valor |
|---|---|
| Lista | Los chips van cambiando a `✓ Limpiado`, `! Omitido` o `✕ Error` |
| Casillas de las filas | **Desactivadas** |
| Barra de acciones | Agregar, Destino y Vaciar **desactivados** |
| Barra de selección | "Marcar todos" y "Quitar" **desactivados** |
| Barra del archivo | Avanza dentro del archivo en curso |
| Barra del lote | Avanza de forma continua |
| Etiqueta de estado | El aviso puesto al arrancar la corrida |
| Botón verde | **Desactivado**, texto `Procesando...` |

Tres reglas irrenunciables en este estado:

1. **El botón verde debe desactivarse.** Impide lanzar dos lotes simultáneos sobre la misma carpeta destino.
2. **La cola debe quedar bloqueada.** Quitar o agregar archivos a mitad de la corrida dejaría la lista describiendo un trabajo distinto del que se está ejecutando.
3. **La ventana debe seguir respondiendo.** El trabajo va en un hilo secundario y ningún hilo toca Tkinter. Una ventana congelada se lee como aplicación colgada, y el usuario la cierra a media corrida.

### Estado E — Terminado

Vuelve a B, pero con los chips resueltos, la barra al 100 % y el recuento en la etiqueta. Todos los controles se reactivan. **Cualquier ruta de fallo debe llegar también aquí**: una interfaz que se queda con todo desactivado obliga a reiniciar la aplicación.

---

## Pantallas secundarias (diálogos)

Ninguna es una ventana propia de la aplicación: son diálogos del sistema o avisos emergentes.

| # | Diálogo | Se abre desde | Contenido |
|---|---|---|---|
| 2 | **Selector de archivos** | Botón "Seleccionar archivos" | Diálogo nativo de Windows, selección múltiple activada. Dos filtros: "Imágenes y videos" (por defecto) y "Todos los archivos" |
| 3 | **Selector de carpeta** | Botón "Carpeta destino" | Diálogo nativo de carpeta, título *"Seleccionar carpeta para guardar resultados"* |
| 4 | **Aviso: cola vacía** | Botón verde sin archivos | Advertencia. Título "Atencion", texto *"Por favor selecciona al menos un archivo."* |
| 5 | **Error: destino no válido** | Botón verde con destino = carpeta de los originales | Error. Explica que las copias conservan el nombre original y sobrescribirían los archivos de partida |
| 6 | **Resumen final** | Al terminar la corrida | Información. Recuento de correctos y con error, más la ruta de destino completa |
| 7 | **Error global** | Fallo del lote entero | Error. Título "Error" y el detalle técnico |

El diálogo 5 es una salvaguarda añadida al pasar a conservar el nombre original: sin prefijo que distinga la copia, escribir en la carpeta de origen destruiría el archivo de partida. Se comprueba **antes** de empezar el lote, y el núcleo lo verifica otra vez por archivo, de modo que ninguna ruta de ejecución puede saltárselo.

**El aviso de FFmpeg faltante no es un diálogo.** Se muestra dentro de la ventana, en la etiqueta de estado y en el visor. Razón: las imágenes sí se pueden procesar sin FFmpeg, así que frenar el arranque con un modal que hay que cerrar cada vez sería desproporcionado para un problema que solo afecta a la mitad de los casos de uso.

---

## Reglas transversales

Aplican a cualquier rediseño o ampliación de la interfaz.

1. **Un solo mensaje de estado a la vez.** La etiqueta se sobrescribe, no se acumula. El historial vive en el visor.
2. **Nada de rutas truncadas con "...".** El usuario necesita la ruta completa para encontrar sus archivos.
3. **Ningún estado de error deja la interfaz bloqueada.** Toda ruta de fallo reactiva el botón verde. Un botón permanentemente desactivado obliga a reiniciar la aplicación.
4. **El color codifica intención, no decoración.** Verde = ejecutar, azul = navegar/elegir, gris = descartar.
5. **El texto del botón principal indica el estado.** `Procesar cola de archivos` frente a `Procesando...`: se lee sin mirar la barra de progreso.
6. **Tema claro/oscuro automático.** `appearance_mode` en `"System"` sigue la configuración de Windows; no se ofrece un selector manual porque no aporta nada aquí.
7. **Ningún hilo secundario toca Tkinter, ni siquiera con `after()`.** Registrar una llamada diferida crea un comando en el intérprete Tcl, lo cual no es seguro entre hilos. Los trabajadores depositan sus novedades en una `queue.Queue` y el hilo principal la vacía cada 80–100 ms. Es la regla que hace que la ventana nunca se cuelgue de forma intermitente.
8. **Una vista previa que falla nunca bloquea el trabajo.** La miniatura es una comodidad; su ausencia se muestra y se sigue adelante.

---

## Ampliaciones previstas y dónde encajarían

Si la aplicación crece, estas son las adiciones naturales y su ubicación, sin romper el modelo de pantalla única:

| Función | Dónde | Nota |
|---|---|---|
| Arrastrar y soltar archivos | Sobre la lista de archivos (Zona 4) | Requiere `tkinterdnd2`; el filtro de extensiones ya está disponible en `ProveedorLimpiadores.extensiones_soportadas()` |
| Botón "Abrir carpeta destino" | Zona 1, junto a "Carpeta destino" | `os.startfile(self.carpeta_destino)` |
| Casilla "Borrar originales al terminar" | Entre las zonas 4 y 5 | Debe exigir confirmación explícita antes de ejecutarse |
| Selector de número de hilos | Zona 1, como desplegable | Solo si aparece la necesidad real; por defecto ya usa todos los núcleos |
| Informe exportable de la corrida | Botón en el diálogo de resumen (pantalla 5) | `ProcesadorEnLote.procesar_archivos` ya devuelve la lista completa de `ResultadoArchivo` |

Añadir un formato nuevo (PDF, audio, documentos de Office) **no requiere ningún cambio en la interfaz**: el filtro del diálogo se genera solo a partir del proveedor de limpiadores.
