"""
Visor de la cola de archivos.

Es una lista de filas reales —no texto— en la que cada archivo se puede marcar
y quitar antes de procesar. Dos densidades intercambiables:

  - Lista:   fila compacta. Util para lotes grandes.
  - Detalle: la misma fila mas una miniatura y los datos del archivo.

El estado vive en `FilaArchivo`, de modo que alternar de vista o quitar
elementos no pierde ningun resultado.

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

from nucleo import miniaturas
from nucleo.procesador import ResultadoArchivo

LADO_MINIATURA = 56
INTERVALO_COLA_MS = 100

COLOR_FILA_NORMAL = ("gray86", "gray20")
COLOR_FILA_MARCADA = ("#cfe0f5", "#1d3550")  # azul tenue: "esto se va a quitar"

# Cada estado tiene simbolo, texto por defecto y color. Se muestran como una
# etiqueta con fondo propio, no como marcas de texto entre corchetes: el color
# se lee de un vistazo y el simbolo funciona aunque el usuario no distinga bien
# los colores.
ESTADOS = {
    "pendiente": {
        "simbolo": "•",
        "etiqueta": "En cola",
        "texto": ("gray30", "gray75"),
        "fondo": ("gray80", "gray28"),
    },
    "procesando": {
        "simbolo": "◐",
        "etiqueta": "Procesando",
        "texto": ("#0b4f9e", "#7cc4ff"),
        "fondo": ("#cfe4ff", "#16324f"),
    },
    "limpiado": {
        "simbolo": "✓",
        "etiqueta": "Limpiado",
        "texto": ("#0f5323", "#7ee787"),
        "fondo": ("#c7f0d2", "#123d1e"),
    },
    "omitido": {
        "simbolo": "!",
        "etiqueta": "Omitido",
        "texto": ("#7a4b00", "#f0c674"),
        "fondo": ("#ffe6b8", "#43310d"),
    },
    "error": {
        "simbolo": "✕",
        "etiqueta": "Error",
        "texto": ("#8c1d18", "#ffa198"),
        "fondo": ("#ffd6d2", "#4a1512"),
    },
}


class FilaArchivo:
    """Estado de un archivo en la cola, independiente de como se dibuje."""

    def __init__(self, ruta: Path):
        self.ruta = ruta
        self.estado = "pendiente"
        self.mensaje = ESTADOS["pendiente"]["etiqueta"]
        self.ruta_salida: Optional[Path] = None
        self.marcada = False

    def aplicar(self, resultado: ResultadoArchivo) -> None:
        self.estado = resultado.codigo
        self.mensaje = resultado.mensaje
        self.ruta_salida = resultado.ruta_salida

    def reiniciar(self) -> None:
        self.estado = "pendiente"
        self.mensaje = ESTADOS["pendiente"]["etiqueta"]
        self.ruta_salida = None

    @property
    def tamano_legible(self) -> str:
        try:
            bytes_ = float(self.ruta.stat().st_size)
        except OSError:
            return "?"
        for unidad in ("B", "KB", "MB", "GB"):
            if bytes_ < 1024 or unidad == "GB":
                return f"{bytes_:.0f} B" if unidad == "B" else f"{bytes_:.1f} {unidad}"
            bytes_ /= 1024
        return "?"


class VistaCola(ctk.CTkFrame):
    """
    Lista de archivos con seleccion multiple y dos densidades de vista.

    Todos los metodos publicos deben llamarse desde el hilo principal.
    """

    def __init__(self, maestro, al_cambiar_seleccion: Optional[Callable[[int], None]] = None):
        super().__init__(maestro, fg_color="transparent")

        self.filas: List[FilaArchivo] = []
        self.modo = "lista"
        self._al_cambiar_seleccion = al_cambiar_seleccion
        self._aviso: Optional[str] = None
        self._bloqueada = False  # durante el procesamiento no se puede editar

        # Widgets que este componente crea y por tanto puede destruir. No se usa
        # `winfo_children()` del marco desplazable: ahi viven tambien el lienzo y
        # la barra internos de CustomTkinter, y destruirlos rompe el contenedor.
        self._widgets_filas: List[ctk.CTkBaseClass] = []
        self._contenedores: Dict[int, ctk.CTkFrame] = {}  # id(fila) -> su marco
        self._widgets_miniatura: Dict[str, ctk.CTkLabel] = {}
        self._imagenes_vivas: List[ctk.CTkImage] = []  # evita que Tk las libere

        self._cola_miniaturas: queue.Queue = queue.Queue()
        self._generacion = 0  # invalida miniaturas de una cola ya descartada

        self.contenedor = ctk.CTkScrollableFrame(self, fg_color=("gray94", "gray14"))
        self.contenedor.pack(fill="both", expand=True)

        self.after(INTERVALO_COLA_MS, self._consumir_cola)

    # ------------------------------------------------------------- Publico --

    def establecer_modo(self, modo: str) -> None:
        """Alterna entre 'lista' y 'detalle' conservando el estado de la cola."""
        if modo == self.modo:
            return
        self.modo = modo
        self._redibujar()

    def cargar(self, rutas: List[Path]) -> None:
        """Sustituye la cola por una lista nueva de archivos pendientes."""
        self._generacion += 1
        self._aviso = None
        self.filas = [FilaArchivo(r) for r in rutas]
        self._redibujar()
        self._notificar_seleccion()

    def agregar(self, rutas: List[Path]) -> int:
        """
        Añade archivos a la cola sin descartar los que ya estaban, ignorando
        los repetidos. Devuelve cuantos se añadieron realmente.
        """
        existentes = {f.ruta for f in self.filas}
        nuevas = [r for r in rutas if r not in existentes]
        if not nuevas:
            return 0

        self._aviso = None
        self.filas.extend(FilaArchivo(r) for r in nuevas)
        self._redibujar()
        self._notificar_seleccion()
        return len(nuevas)

    def vaciar(self, aviso: Optional[str] = None) -> None:
        """Descarta la cola. Con `aviso`, lo muestra en lugar de las filas."""
        self._generacion += 1
        self.filas = []
        self._aviso = aviso
        miniaturas.limpiar_cache()
        self._redibujar()
        self._notificar_seleccion()

    def quitar_marcados(self) -> int:
        """Elimina de la cola las filas marcadas. Devuelve cuantas quito."""
        quitadas = [f for f in self.filas if f.marcada]
        if not quitadas:
            return 0

        self.filas = [f for f in self.filas if not f.marcada]
        self._redibujar()
        self._notificar_seleccion()
        return len(quitadas)

    def marcar_todas(self, marcar: bool) -> None:
        """Marca o desmarca todas las filas de golpe."""
        for fila in self.filas:
            fila.marcada = marcar
        self._redibujar()
        self._notificar_seleccion()

    def reiniciar_estados(self) -> None:
        """Devuelve todas las filas a 'pendiente' antes de una corrida nueva."""
        for fila in self.filas:
            fila.reiniciar()
        self._redibujar()

    def actualizar_resultado(self, resultado: ResultadoArchivo) -> None:
        """Aplica el desenlace de un archivo y refresca la vista."""
        for fila in self.filas:
            if fila.ruta == resultado.ruta_origen:
                fila.aplicar(resultado)
                break
        self._redibujar()

    def bloquear(self, bloqueada: bool) -> None:
        """
        Desactiva la edicion mientras se procesa. Quitar un archivo de la cola
        a mitad de la corrida dejaria la vista describiendo un trabajo distinto
        del que se esta ejecutando.
        """
        self._bloqueada = bloqueada
        self._redibujar()

    @property
    def rutas(self) -> List[Path]:
        """Archivos actualmente en la cola, en orden."""
        return [f.ruta for f in self.filas]

    @property
    def total_marcadas(self) -> int:
        return sum(1 for f in self.filas if f.marcada)

    # ------------------------------------------------------------- Dibujado --

    def _notificar_seleccion(self) -> None:
        if self._al_cambiar_seleccion:
            self._al_cambiar_seleccion(self.total_marcadas)

    def _redibujar(self) -> None:
        for widget in self._widgets_filas:
            if widget.winfo_exists():
                widget.destroy()
        self._widgets_filas.clear()
        self._contenedores.clear()
        self._widgets_miniatura.clear()
        self._imagenes_vivas.clear()

        if self._aviso:
            aviso = ctk.CTkLabel(self.contenedor, text=self._aviso,
                                 justify="left", anchor="w")
            aviso.pack(fill="x", padx=12, pady=12)
            self._widgets_filas.append(aviso)
            return

        if not self.filas:
            vacio = ctk.CTkLabel(
                self.contenedor,
                text="No hay archivos en la cola.\n\n"
                     "Pulsa «Agregar archivos» para elegir imagenes o videos.",
                justify="center", text_color=("gray45", "gray60"),
            )
            vacio.pack(expand=True, pady=40)
            self._widgets_filas.append(vacio)
            return

        for fila in self.filas:
            self._crear_fila(fila)

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
            etiqueta_imagen = ctk.CTkLabel(
                contenedor, text="", width=LADO_MINIATURA, height=LADO_MINIATURA,
                fg_color=("gray84", "gray25"), corner_radius=6,
            )
            etiqueta_imagen.pack(side="left", padx=6, pady=8)
            self._widgets_miniatura[str(fila.ruta)] = etiqueta_imagen
            self._pedir_miniatura(fila.ruta)

        # Chip de estado, a la derecha y con color propio
        self._crear_chip_estado(contenedor, fila)

        textos = ctk.CTkFrame(contenedor, fg_color="transparent")
        textos.pack(side="left", fill="both", expand=True, padx=(4, 8),
                    pady=6 if detalle else 4)

        ctk.CTkLabel(
            textos, text=fila.ruta.name, anchor="w",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(fill="x")

        if detalle:
            linea = f"{fila.tamano_legible}  ·  {fila.ruta.suffix.lstrip('.').upper()}"
            if fila.ruta_salida:
                linea += f"  ·  guardado como {fila.ruta_salida.name}"
            ctk.CTkLabel(textos, text=linea, anchor="w",
                         text_color=("gray40", "gray65")).pack(fill="x")

        # El mensaje solo se repite bajo el nombre si aporta mas que el chip
        if fila.mensaje != ESTADOS[fila.estado]["etiqueta"]:
            ctk.CTkLabel(
                textos, text=fila.mensaje, anchor="w", wraplength=430,
                justify="left", text_color=ESTADOS[fila.estado]["texto"],
            ).pack(fill="x")

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

        self._notificar_seleccion()

    # ----------------------------------------------------------- Miniaturas --

    def _pedir_miniatura(self, ruta: Path) -> None:
        """
        Lanza la generacion en un hilo. El hilo no toca Tkinter: deja el
        resultado en la cola que consume el hilo principal.
        """
        generacion = self._generacion

        def trabajar():
            imagen = miniaturas.obtener(ruta, LADO_MINIATURA)
            self._cola_miniaturas.put((ruta, imagen, generacion))

        threading.Thread(target=trabajar, daemon=True).start()

    def _consumir_cola(self) -> None:
        """Vacia la cola de miniaturas listas. Se reprograma a si mismo."""
        try:
            while True:
                ruta, imagen, generacion = self._cola_miniaturas.get_nowait()
                self._colocar_miniatura(ruta, imagen, generacion)
        except queue.Empty:
            pass

        if self.winfo_exists():
            self.after(INTERVALO_COLA_MS, self._consumir_cola)

    def _colocar_miniatura(self, ruta: Path, imagen, generacion: int) -> None:
        # La cola pudo cambiar mientras se generaba: descartar lo obsoleto
        if generacion != self._generacion:
            return

        etiqueta = self._widgets_miniatura.get(str(ruta))
        if etiqueta is None or not etiqueta.winfo_exists():
            return

        if imagen is None:
            etiqueta.configure(text="sin\nvista", font=ctk.CTkFont(size=10),
                               text_color=("gray45", "gray60"))
            return

        ctk_imagen = ctk.CTkImage(
            light_image=imagen, dark_image=imagen,
            size=(imagen.width, imagen.height),
        )
        self._imagenes_vivas.append(ctk_imagen)
        etiqueta.configure(image=ctk_imagen, text="")
