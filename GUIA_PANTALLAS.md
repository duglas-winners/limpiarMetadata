# Guía de pantallas — Limpiador de Metadatos

Especificación de la interfaz: qué pantallas tiene la aplicación, qué va en cada una y cómo se comporta en cada estado. Sirve tanto para entender la interfaz actual como para reconstruirla o rediseñarla sin perder nada.

---

## Principio de diseño

**Una sola pantalla, cinco zonas apiladas.** El flujo de la aplicación es lineal —elegir archivos, elegir destino, procesar, ver resultado—, así que no se justifican pestañas, asistentes ni ventanas secundarias. Todo cabe en una ventana y el usuario ve el estado completo del trabajo de un vistazo.

Las únicas ventanas adicionales son diálogos del sistema operativo (selector de archivos, selector de carpeta) y avisos emergentes al terminar.

---

## Pantalla 1 — Ventana principal

Es la aplicación entera. Tamaño 780×600, mínimo 640×500.

```
┌──────────────────────────────────────────────────────────────────┐
│  Limpiador de Metadatos - Imagenes y Videos              _ □ ✕   │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ [Seleccionar] [Destino] [Vaciar]        [ Lista │ Detalle ]│  │  ← Zona 1
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Destino: C:\Users\Duglas\Archivos_Limpiados                     │  ← Zona 2
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ [  ] foto_playa.jpg                                        │  │
│  │ [  ] captura_pantalla.png                                  │  │  ← Zona 3
│  │ [  ] clip_boda.mp4                                         │  │    (vista Lista)
│  │                                                            │  │
│  │                                                            │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │  ← Zona 4
│                                                                  │
│                3 archivos cargados en la cola.                   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │            Procesar cola de archivos                       │  │  ← Zona 5
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

La Zona 3 en vista **Detalle**:

```
  ┌────────────────────────────────────────────────────────────┐
  │ ┌──────┐  foto_playa.jpg                                   │
  │ │ 🖼️   │  2.4 MB  ·  JPG  ·  guardado como foto_playa.jpg  │
  │ └──────┘  [OK] Limpiado                                    │
  ├────────────────────────────────────────────────────────────┤
  │ ┌──────┐  clip_boda.mp4                                    │
  │ │ 🎞️   │  184.2 MB  ·  MP4                                 │
  │ └──────┘  [  ] En cola                                     │
  ├────────────────────────────────────────────────────────────┤
  │ ┌──────┐  documento.tif                                    │
  │ │ sin  │  1.1 MB  ·  TIF                                   │
  │ │ vista│  [!!] Formato no soportado                        │
  │ └──────┘                                                   │
  └────────────────────────────────────────────────────────────┘
```

### Zona 1 — Barra de acciones

Un marco horizontal con tres botones alineados a la izquierda, en el orden natural de uso.

| Botón | Color | Función | Regla |
|---|---|---|---|
| **Seleccionar archivos** | Azul (primario) | Abre el selector de archivos | Siempre activo salvo durante el procesamiento |
| **Carpeta destino** | Azul (primario) | Abre el selector de carpeta | Siempre activo salvo durante el procesamiento |
| **Vaciar cola** | Gris (secundario) | Descarta la selección | Deliberadamente gris: es destructivo y no debe competir visualmente con las acciones principales |

A la **derecha** de la misma barra, separado del grupo anterior, va el conmutador de vista (`CTkSegmentedButton` con "Lista" y "Detalle"). Está alineado a la derecha a propósito: no ejecuta trabajo ni modifica la cola, solo cambia cómo se presenta lo que ya hay en pantalla. Agruparlo con los botones de acción sugeriría que hace algo al archivo.

### Zona 2 — Etiqueta de destino

Una línea de texto alineada a la izquierda, siempre visible: `Destino: <ruta completa>`.

Debe mostrarse **siempre**, incluso con la ruta por defecto. Es la respuesta a la pregunta más frecuente del usuario —"¿dónde quedaron mis archivos?"— y tenerla permanentemente en pantalla la elimina de raíz.

### Zona 3 — Visor de la cola

Ocupa todo el espacio sobrante al redimensionar la ventana. Tiene **dos presentaciones intercambiables de los mismos datos**; solo cambia la densidad de información.

#### Vista Lista (por defecto)

Caja de texto de solo lectura. Un renglón por archivo, con prefijo de estado de ancho fijo para que los nombres queden alineados:

```
[  ] pendiente
[OK] procesado correctamente
[!!] error, seguido del motivo
```

- El usuario **no puede escribir** en ella (`state="disabled"`); solo el programa la actualiza.
- Hace **auto-scroll** al último renglón durante el procesamiento.

#### Vista Detalle

Marco desplazable con una tarjeta por archivo. Cada tarjeta tiene, de izquierda a derecha:

| Elemento | Contenido |
|---|---|
| Miniatura | 56×56 px. Imágenes: reducidas con Pillow. Vídeos: un fotograma del segundo 1, extraído con FFmpeg |
| Nombre | En negrita, primera línea |
| Metadatos | Tamaño legible · formato · nombre con el que se guardó (solo si ya se procesó) |
| Estado | Símbolo y mensaje, **coloreado**: gris pendiente, verde correcto, rojo error |

Estados del hueco de miniatura, en orden:

1. `...` sobre fondo gris — se está generando.
2. La miniatura — lista.
3. `sin vista` — no se pudo previsualizar (archivo dañado, formato sin vista previa, FFmpeg ausente). **Nunca impide procesar el archivo.**

#### Reglas comunes a ambas vistas

- **El estado vive en el modelo, no en los widgets.** Alternar de vista redibuja desde `FilaArchivo`, así que no se pierde ningún resultado ni siquiera a mitad de una corrida.
- **Las miniaturas se generan fuera del hilo de la interfaz** y se cachean. La ventana nunca se congela esperándolas.
- **Al vaciar la cola se descarta la caché** de miniaturas, para no retener en memoria imágenes de archivos que ya no interesan.
- Cada carga de cola incrementa un contador de generación: una miniatura que termina de generarse tarde, cuando su archivo ya no está en la cola, **se descarta en vez de pintarse** sobre la fila equivocada.

### Zona 4 — Indicadores de estado

Dos elementos apilados que responden a preguntas distintas:

| Elemento | Responde a | Contenido |
|---|---|---|
| **Barra de progreso** | "¿Cuánto falta?" | De 0 a 1. Se reinicia a 0 en cada corrida nueva |
| **Etiqueta de estado** | "¿Qué está pasando ahora mismo?" | Una sola línea, centrada, que cambia según el momento |

Textos de la etiqueta según el momento:

| Momento | Texto |
|---|---|
| Al abrir | `Esperando archivos en cola...` |
| Al abrir sin FFmpeg | `Aviso: FFmpeg no encontrado, los videos no se podran procesar.` |
| Tras seleccionar | `N archivos cargados en la cola.` |
| Durante el proceso | `[2/7] [OK] foto.jpg - Limpiado` |
| Al terminar | `Completado: 6 correctos, 1 con error.` |
| Tras un fallo global | `El procesamiento se interrumpio.` |

### Zona 5 — Botón principal

Ancho completo, altura 42 px (mayor que los demás), color verde. Es la única acción que ejecuta trabajo real, y su tamaño y color lo dejan claro sin necesidad de instrucciones.

---

## Estados de la ventana principal

La misma pantalla, cuatro configuraciones. Toda la interfaz debe reflejar sin ambigüedad en cuál está.

### Estado A — Inicial (recién abierta)

| Elemento | Valor |
|---|---|
| Visor de la cola | Vacío (o con el aviso de FFmpeg) |
| Barra de progreso | En 0 |
| Etiqueta de estado | `Esperando archivos en cola...` |
| Botón verde | Activo, texto `Procesar cola de archivos` |

Pulsar el botón verde en este estado **no arranca nada**: muestra el aviso *"Por favor selecciona al menos un archivo"* y no cambia nada más.

### Estado B — Cola cargada

| Elemento | Valor |
|---|---|
| Visor de la cola | Un renglón `[  ]` por archivo |
| Barra de progreso | Reiniciada a 0 |
| Etiqueta de estado | `N archivos cargados en la cola.` |
| Botón verde | Activo |

### Estado C — Procesando

| Elemento | Valor |
|---|---|
| Visor de la cola | Se rellena renglón a renglón con los resultados |
| Barra de progreso | Avanza |
| Etiqueta de estado | `[actual/total] [marca] nombre - mensaje` |
| Botón verde | **Desactivado**, texto `Procesando...` |

Dos reglas irrenunciables en este estado:

1. **El botón debe desactivarse.** Impide lanzar dos lotes simultáneos sobre la misma carpeta destino.
2. **La ventana debe seguir respondiendo.** El trabajo va en un hilo secundario y todo repintado se devuelve al hilo principal. Una ventana congelada se lee como aplicación colgada, y el usuario la cierra a media corrida.

### Estado D — Terminado

Vuelve visualmente al Estado B, pero con el visor lleno de resultados, la barra al 100 % y la etiqueta con el recuento. El botón verde vuelve a estar activo, listo para otra corrida.

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
| Arrastrar y soltar archivos | Sobre el visor de la cola (Zona 3) | Requiere `tkinterdnd2`; el filtro de extensiones ya está disponible en `ProveedorLimpiadores.extensiones_soportadas()` |
| Botón "Abrir carpeta destino" | Zona 1, junto a "Carpeta destino" | `os.startfile(self.carpeta_destino)` |
| Casilla "Borrar originales al terminar" | Entre las zonas 4 y 5 | Debe exigir confirmación explícita antes de ejecutarse |
| Selector de número de hilos | Zona 1, como desplegable | Solo si aparece la necesidad real; por defecto ya usa todos los núcleos |
| Informe exportable de la corrida | Botón en el diálogo de resumen (pantalla 5) | `ProcesadorEnLote.procesar_archivos` ya devuelve la lista completa de `ResultadoArchivo` |

Añadir un formato nuevo (PDF, audio, documentos de Office) **no requiere ningún cambio en la interfaz**: el filtro del diálogo se genera solo a partir del proveedor de limpiadores.
