"""
Visor de la cola: dibuja `ColaArchivos` y gestiona la interaccion con las filas.

Es una lista de filas reales —no texto— en la que cada archivo se puede marcar
y quitar antes de procesar. Dos densidades intercambiables:

  - Lista:   fila compacta. Util para lotes grandes.
  - Detalle: la misma fila mas una miniatura y los datos del archivo.

Este modulo solo se ocupa de pintar y de recibir clics; el estado vive en
`modelo_cola`, y las operaciones sobre el se delegan alli.

Regla de hilos: Tkinter solo tolera llamadas desde el hilo principal, y eso
incluye `after()`, que registra un comando en el interprete Tcl. Los hilos que
generan miniaturas por tanto no tocan Tk en absoluto: depositan el resultado en
una cola que el hilo principal vacia periodicamente.
"""

import queue
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from nucleo import medios, miniaturas
from nucleo.procesador import ResultadoArchivo

from .estilos import (
    COLOR_FILA_MARCADA,
    COLOR_FILA_NORMAL,
    COLOR_FONDO_LISTA,
    COLOR_HUECO_MINIATURA,
    COLOR_TEXTO_TENUE,
    ESTADOS,
    INTERVALO_MINIATURAS_MS,
    LADO_MINIATURA,
)
from .modelo_cola import ColaArchivos, FilaArchivo

MENSAJE_VACIO = (
    "No hay archivos en la cola.\n\n"
    "Pulsa «Agregar archivos» para elegir imagenes o videos."
)


class VistaCola(ctk.CTkFrame):
    """
    Lista de archivos con seleccion multiple y dos densidades de vista.

    Todos los metodos publicos deben llamarse desde el hilo principal.
    """

    def __init__(self, maestro, al_cambiar_seleccion: Optional[Callable[[int], None]] = None):
        super().__init__(maestro, fg_color="transparent")

        self.cola = ColaArchivos()
        self.modo = "lista"
        self._al_cambiar_seleccion = al_cambiar_seleccion
        self._aviso: Optional[str] = None
        self._bloqueada = False  # durante el procesamiento no se puede editar
        self._comprimiendo = False
        self._nivel = medios.NIVEL_POR_DEFECTO

        # Widgets que este componente crea y por tanto puede destruir. No se usa
        # `winfo_children()` del marco desplazable: ahi viven tambien el lienzo y
        # la barra internos de CustomTkinter, y destruirlos rompe el contenedor.
        self._widgets_filas: List[ctk.CTkBaseClass] = []
        self._contenedores: Dict[int, ctk.CTkFrame] = {}  # id(fila) -> su marco
        self._widgets_miniatura: Dict[str, ctk.CTkLabel] = {}
        self._imagenes_vivas: List[ctk.CTkImage] = []  # evita que Tk las libere

        # Una sola cola para todo lo que se calcula en hilos —miniaturas y
        # estimaciones de peso— y se pinta desde el hilo principal.
        self._cola_calculos: queue.Queue = queue.Queue()
        self._generacion = 0  # invalida resultados de una cola ya descartada
        self._etiquetas_peso: Dict[str, ctk.CTkLabel] = {}
        self._activa = True
        self._tarea_pendiente = None

        self.contenedor = ctk.CTkScrollableFrame(self, fg_color=COLOR_FONDO_LISTA)
        self.contenedor.pack(fill="both", expand=True)

        self._redibujar()
        self._tarea_pendiente = self.after(INTERVALO_MINIATURAS_MS, self._consumir_cola)

    # ------------------------------------------------------------- Publico --

    @property
    def filas(self) -> List[FilaArchivo]:
        """Acceso directo a las filas, para consultas desde la ventana."""
        return self.cola.filas

    def establecer_modo(self, modo: str) -> None:
        """Alterna entre 'lista' y 'detalle' conservando el estado de la cola."""
        if modo != self.modo:
            self.modo = modo
            self._redibujar()

    def cargar(self, rutas: List[Path]) -> None:
        """Sustituye la cola por una lista nueva de archivos pendientes."""
        self._generacion += 1
        self._aviso = None
        self.cola.reemplazar(rutas)
        self._refrescar()

    def agregar(self, rutas: List[Path]) -> int:
        """
        Añade archivos sin descartar los que ya estaban, ignorando repetidos.
        Devuelve cuantos se añadieron realmente.
        """
        añadidos = self.cola.agregar(rutas)
        if añadidos:
            self._aviso = None
            self._refrescar()
        return añadidos

    def vaciar(self, aviso: Optional[str] = None) -> None:
        """Descarta la cola. Con `aviso`, lo muestra en lugar de las filas."""
        self._generacion += 1
        self.cola.vaciar()
        self._aviso = aviso
        miniaturas.limpiar_cache()
        medios.limpiar_cache()
        self._refrescar()

    def quitar_marcados(self) -> int:
        """Elimina de la cola las filas marcadas. Devuelve cuantas quito."""
        quitadas = self.cola.quitar_marcadas()
        if quitadas:
            self._refrescar()
        return quitadas

    def marcar_todas(self, marcar: bool) -> None:
        """Marca o desmarca todas las filas de golpe."""
        self.cola.marcar_todas(marcar)
        self._refrescar()

    def reiniciar_estados(self) -> None:
        """Devuelve todas las filas a 'pendiente' antes de una corrida nueva."""
        self.cola.reiniciar_estados()
        self._redibujar()

    def actualizar_resultado(self, resultado: ResultadoArchivo) -> None:
        """Aplica el desenlace de un archivo y refresca la vista."""
        self.cola.aplicar_resultado(resultado)
        self._redibujar()

    def bloquear(self, bloqueada: bool) -> None:
        """
        Desactiva la edicion mientras se procesa. Quitar un archivo de la cola
        a mitad de la corrida dejaria la vista describiendo un trabajo distinto
        del que se esta ejecutando.
        """
        self._bloqueada = bloqueada
        self._redibujar()

    def establecer_compresion(self, activa: bool, nivel: str) -> None:
        """
        Indica si la compresion esta marcada y con que nivel, para que cada
        fila muestre el techo al que bajaria su peso.

        Al cambiar el nivel se descartan las estimaciones ya calculadas: eran
        de otro ajuste y mostrarlas seria mentir. Se recalculan solas, y como
        el analisis del video esta cacheado, es cuestion de milisegundos.
        """
        if activa == self._comprimiendo and nivel == self._nivel:
            return

        if nivel != self._nivel:
            for fila in self.cola:
                fila.estimado = None

        self._comprimiendo = activa
        self._nivel = nivel
        self._redibujar()

    # Atajos que la ventana consulta para sus barras
    @property
    def rutas(self) -> List[Path]:
        return self.cola.rutas

    @property
    def total_marcadas(self) -> int:
        return self.cola.total_marcadas

    @property
    def peso_total(self) -> int:
        return self.cola.peso_total

    @property
    def tiene_videos(self) -> bool:
        return self.cola.tiene_videos

    # ------------------------------------------------------------- Dibujado --

    def _refrescar(self) -> None:
        """Redibuja y avisa de que la seleccion pudo cambiar."""
        self._redibujar()
        if self._al_cambiar_seleccion:
            self._al_cambiar_seleccion(self.cola.total_marcadas)

    def _redibujar(self) -> None:
        for widget in self._widgets_filas:
            if widget.winfo_exists():
                widget.destroy()
        self._widgets_filas.clear()
        self._contenedores.clear()
        self._widgets_miniatura.clear()
        self._etiquetas_peso.clear()
        self._imagenes_vivas.clear()

        if self._aviso:
            self._dibujar_mensaje(self._aviso, "left")
        elif not self.cola.filas:
            # Una zona vacia sin explicacion se lee como algo que fallo al cargar
            self._dibujar_mensaje(MENSAJE_VACIO, "center")
        else:
            for fila in self.cola:
                self._crear_fila(fila)

    def _dibujar_mensaje(self, texto: str, alineacion: str) -> None:
        etiqueta = ctk.CTkLabel(
            self.contenedor, text=texto, justify=alineacion,
            text_color=COLOR_TEXTO_TENUE if alineacion == "center" else None,
        )
        if alineacion == "center":
            etiqueta.pack(expand=True, pady=40)
        else:
            etiqueta.pack(fill="x", padx=12, pady=12)
        self._widgets_filas.append(etiqueta)

    def _crear_fila(self, fila: FilaArchivo) -> None:
        detalle = self.modo == "detalle"

        contenedor = ctk.CTkFrame(self.contenedor, corner_radius=8,
                                  fg_color=self._color_fila(fila))
        contenedor.pack(fill="x", padx=6, pady=3)
        self._widgets_filas.append(contenedor)
        self._contenedores[id(fila)] = contenedor

        # Casilla de seleccion: es la via para quitar archivos coleados
        casilla = ctk.CTkCheckBox(
            contenedor, text="", width=24,
            command=lambda f=fila: self._alternar_marca(f),
            state="disabled" if self._bloqueada else "normal",
        )
        if fila.marcada:
            casilla.select()
        casilla.pack(side="left", padx=(10, 4), pady=10 if detalle else 6)

        if detalle:
            self._crear_hueco_miniatura(contenedor, fila)

        self._crear_chip_estado(contenedor, fila)

        # El peso va a la derecha, antes del chip: en vista Lista mantiene la
        # fila en un solo renglon y deja todos los pesos alineados en columna.
        if not detalle:
            self._crear_etiqueta_peso(contenedor, fila, side="right")

        self._crear_textos(contenedor, fila, detalle)
        self._pedir_estimacion(fila)

    def _crear_hueco_miniatura(self, contenedor, fila: FilaArchivo) -> None:
        etiqueta = ctk.CTkLabel(
            contenedor, text="", width=LADO_MINIATURA, height=LADO_MINIATURA,
            fg_color=COLOR_HUECO_MINIATURA, corner_radius=6,
        )
        etiqueta.pack(side="left", padx=6, pady=8)
        self._widgets_miniatura[str(fila.ruta)] = etiqueta
        self._pedir_miniatura(fila.ruta)

    def _crear_chip_estado(self, contenedor, fila: FilaArchivo) -> None:
        estilo = ESTADOS[fila.estado]
        chip = ctk.CTkLabel(
            contenedor,
            text=f" {estilo['simbolo']}  {estilo['etiqueta']} ",
            fg_color=estilo["fondo"],
            text_color=estilo["texto"],
            corner_radius=10,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        chip.pack(side="right", padx=10)

    def _crear_textos(self, contenedor, fila: FilaArchivo, detalle: bool) -> None:
        textos = ctk.CTkFrame(contenedor, fg_color="transparent")
        textos.pack(side="left", fill="both", expand=True, padx=(4, 8),
                    pady=6 if detalle else 4)

        ctk.CTkLabel(
            textos, text=fila.ruta.name, anchor="w",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(fill="x")

        if detalle:
            self._crear_etiqueta_peso(textos, fila, side="top")

        # El mensaje solo se repite bajo el nombre si aporta mas que el chip
        if fila.mensaje != ESTADOS[fila.estado]["etiqueta"]:
            ctk.CTkLabel(
                textos, text=fila.mensaje, anchor="w", wraplength=430,
                justify="left", text_color=ESTADOS[fila.estado]["texto"],
            ).pack(fill="x")

    def _crear_etiqueta_peso(self, padre, fila: FilaArchivo, side: str) -> None:
        """
        Etiqueta con el peso del archivo, y el techo al que bajaria si se
        comprime. Se guarda su referencia para poder actualizarla cuando
        llegue la estimacion, sin redibujar la fila entera.
        """
        texto = fila.texto_peso(self._comprimiendo)
        if side == "top":
            # En vista Detalle acompaña al formato y al nombre de salida
            texto += f"  ·  {fila.ruta.suffix.lstrip('.').upper()}"
            if fila.ruta_salida:
                texto += f"  ·  guardado como {fila.ruta_salida.name}"

        etiqueta = ctk.CTkLabel(
            padre, text=texto, anchor="w", text_color=COLOR_TEXTO_TENUE,
            font=ctk.CTkFont(size=11) if side == "right" else None,
        )
        if side == "right":
            etiqueta.pack(side="right", padx=(6, 4))
        else:
            etiqueta.pack(fill="x")

        self._etiquetas_peso[str(fila.ruta)] = etiqueta

    @staticmethod
    def _color_fila(fila: FilaArchivo):
        """Fondo de la fila: resaltado cuando esta marcada para quitarse."""
        return COLOR_FILA_MARCADA if fila.marcada else COLOR_FILA_NORMAL

    def _alternar_marca(self, fila: FilaArchivo) -> None:
        """
        Marca o desmarca una fila. Solo recolorea el contenedor afectado en vez
        de redibujar la lista entera: redibujar reconstruiria todas las filas y
        haria parpadear las miniaturas en la vista de detalle.
        """
        fila.marcada = not fila.marcada

        contenedor = self._contenedores.get(id(fila))
        if contenedor is not None and contenedor.winfo_exists():
            contenedor.configure(fg_color=self._color_fila(fila))

        if self._al_cambiar_seleccion:
            self._al_cambiar_seleccion(self.cola.total_marcadas)

    # ----------------------------------------------------------- Miniaturas --

    def _pedir_miniatura(self, ruta: Path) -> None:
        """
        Lanza la generacion en un hilo. El hilo no toca Tkinter: deja el
        resultado en la cola que consume el hilo principal.
        """
        generacion = self._generacion

        def trabajar():
            imagen = miniaturas.obtener(ruta, LADO_MINIATURA)
            self._cola_calculos.put(("miniatura", ruta, imagen, generacion))

        threading.Thread(target=trabajar, daemon=True).start()

    def _pedir_estimacion(self, fila: FilaArchivo) -> None:
        """
        Calcula el peso comprimido de un video en segundo plano.

        Solo se pide cuando hace falta: si no se va a comprimir, si no es
        video, o si ya se calculo antes, no hay nada que hacer. `medios`
        cachea el analisis, asi que redibujar no repite el trabajo.
        """
        if not self._comprimiendo or not fila.es_video or fila.estimado is not None:
            return

        generacion = self._generacion
        ruta = fila.ruta
        nivel = self._nivel

        def trabajar():
            estimado = medios.estimar_comprimido(ruta, nivel)
            self._cola_calculos.put(("estimacion", ruta, estimado, generacion))

        threading.Thread(target=trabajar, daemon=True).start()

    def _consumir_cola(self) -> None:
        """Vacia la cola de calculos terminados. Se reprograma a si mismo."""
        try:
            while True:
                tipo, ruta, dato, generacion = self._cola_calculos.get_nowait()
                # La cola pudo cambiar mientras se calculaba: descartar lo obsoleto
                if generacion != self._generacion:
                    continue
                if tipo == "miniatura":
                    self._colocar_miniatura(ruta, dato)
                else:
                    self._colocar_estimacion(ruta, dato)
        except queue.Empty:
            pass

        if self._activa and self.winfo_exists():
            self._tarea_pendiente = self.after(INTERVALO_MINIATURAS_MS, self._consumir_cola)

    def detener(self) -> None:
        """Cancela el bombeo pendiente al cerrar la ventana."""
        self._activa = False
        if self._tarea_pendiente is not None:
            try:
                self.after_cancel(self._tarea_pendiente)
            except Exception:
                pass
            self._tarea_pendiente = None

    def _colocar_estimacion(self, ruta: Path, estimado: int) -> None:
        """Anota el techo calculado y refresca solo la etiqueta de esa fila."""
        for fila in self.cola:
            if fila.ruta == ruta:
                fila.estimado = estimado
                self._refrescar_peso(fila)
                return

    def _refrescar_peso(self, fila: FilaArchivo) -> None:
        etiqueta = self._etiquetas_peso.get(str(fila.ruta))
        if etiqueta is None or not etiqueta.winfo_exists():
            return

        texto = fila.texto_peso(self._comprimiendo)
        if self.modo == "detalle":
            texto += f"  ·  {fila.ruta.suffix.lstrip('.').upper()}"
            if fila.ruta_salida:
                texto += f"  ·  guardado como {fila.ruta_salida.name}"
        etiqueta.configure(text=texto)

    def _colocar_miniatura(self, ruta: Path, imagen) -> None:

        etiqueta = self._widgets_miniatura.get(str(ruta))
        if etiqueta is None or not etiqueta.winfo_exists():
            return

        if imagen is None:
            etiqueta.configure(text="sin\nvista", font=ctk.CTkFont(size=10),
                               text_color=COLOR_TEXTO_TENUE)
            return

        ctk_imagen = ctk.CTkImage(
            light_image=imagen, dark_image=imagen,
            size=(imagen.width, imagen.height),
        )
        self._imagenes_vivas.append(ctk_imagen)
        etiqueta.configure(image=ctk_imagen, text="")
