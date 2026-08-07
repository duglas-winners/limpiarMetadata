"""
Visor de la cola de archivos, con dos presentaciones intercambiables.

  - Lista:   una linea de texto por archivo. Compacta, util para lotes grandes.
  - Detalle: cada archivo con su miniatura, tamaño y ruta de salida.

Ambas muestran los mismos datos; solo cambia la densidad. El estado vive en
`FilaArchivo`, de modo que alternar de vista no pierde ningun resultado.

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

COLORES_ESTADO = {
    "pendiente": ("gray45", "gray60"),
    "ok": ("#1a7f37", "#3fb950"),
    "error": ("#b3261e", "#f85149"),
}

SIMBOLOS = {"pendiente": "[  ]", "ok": "[OK]", "error": "[!!]"}


class FilaArchivo:
    """Estado de un archivo en la cola, independiente de como se dibuje."""

    def __init__(self, ruta: Path):
        self.ruta = ruta
        self.estado = "pendiente"
        self.mensaje = "En cola"
        self.ruta_salida: Optional[Path] = None

    def aplicar(self, resultado: ResultadoArchivo) -> None:
        self.estado = "ok" if resultado.exito else "error"
        self.mensaje = resultado.mensaje
        self.ruta_salida = resultado.ruta_salida

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
    Contenedor que alterna entre la vista de lista y la de detalle.

    Todos los metodos publicos deben llamarse desde el hilo principal.
    """

    def __init__(self, maestro, al_cambiar_modo: Optional[Callable[[str], None]] = None):
        super().__init__(maestro, fg_color="transparent")

        self.filas: List[FilaArchivo] = []
        self.modo = "lista"
        self._al_cambiar_modo = al_cambiar_modo
        self._aviso: Optional[str] = None

        # Widgets que este componente crea y por tanto puede destruir. No se usa
        # `winfo_children()` del marco desplazable: ahi viven tambien el lienzo y
        # la barra internos de CustomTkinter, y destruirlos rompe el contenedor.
        self._widgets_filas: List[ctk.CTkFrame] = []
        self._widgets_miniatura: Dict[str, ctk.CTkLabel] = {}
        self._imagenes_vivas: List[ctk.CTkImage] = []  # evita que Tk las libere

        self._cola_miniaturas: queue.Queue = queue.Queue()
        self._generacion = 0  # invalida miniaturas de una cola ya descartada

        self.caja_texto = ctk.CTkTextbox(self, state="disabled", activate_scrollbars=True)
        self.marco_detalle = ctk.CTkScrollableFrame(self, fg_color=("gray92", "gray14"))

        self.caja_texto.pack(fill="both", expand=True)
        self.after(INTERVALO_COLA_MS, self._consumir_cola)

    # ------------------------------------------------------------- Publico --

    def establecer_modo(self, modo: str) -> None:
        """Cambia entre 'lista' y 'detalle' conservando el estado de la cola."""
        if modo == self.modo:
            return
        self.modo = modo

        self.caja_texto.pack_forget()
        self.marco_detalle.pack_forget()

        if modo == "lista":
            self.caja_texto.pack(fill="both", expand=True)
        else:
            self.marco_detalle.pack(fill="both", expand=True)

        self._redibujar()
        if self._al_cambiar_modo:
            self._al_cambiar_modo(modo)

    def cargar(self, rutas: List[Path]) -> None:
        """Sustituye la cola por una lista nueva de archivos pendientes."""
        self._generacion += 1
        self._aviso = None
        self.filas = [FilaArchivo(r) for r in rutas]
        self._redibujar()

    def vaciar(self, aviso: Optional[str] = None) -> None:
        """Descarta la cola. Con `aviso`, lo muestra en lugar de las filas."""
        self._generacion += 1
        self.filas = []
        self._aviso = aviso
        miniaturas.limpiar_cache()
        self._redibujar()

    def reiniciar_estados(self) -> None:
        """Devuelve todas las filas a 'pendiente' antes de una corrida nueva."""
        for fila in self.filas:
            fila.estado = "pendiente"
            fila.mensaje = "En cola"
            fila.ruta_salida = None
        self._redibujar()

    def actualizar_resultado(self, resultado: ResultadoArchivo) -> None:
        """Aplica el desenlace de un archivo y refresca la vista."""
        for fila in self.filas:
            if fila.ruta == resultado.ruta_origen:
                fila.aplicar(resultado)
                break
        self._redibujar()

    # ------------------------------------------------------------- Dibujado --

    def _redibujar(self) -> None:
        if self.modo == "lista":
            self._dibujar_lista()
        else:
            self._dibujar_detalle()

    def _dibujar_lista(self) -> None:
        self.caja_texto.configure(state="normal")
        self.caja_texto.delete("1.0", "end")

        if self._aviso:
            self.caja_texto.insert("end", self._aviso)
        else:
            lineas = [
                f"{SIMBOLOS[f.estado]} {f.ruta.name}"
                + (f" - {f.mensaje}" if f.estado != "pendiente" else "")
                for f in self.filas
            ]
            self.caja_texto.insert("end", "\n".join(lineas))

        self.caja_texto.see("end")
        self.caja_texto.configure(state="disabled")

    def _dibujar_detalle(self) -> None:
        for widget in self._widgets_filas:
            if widget.winfo_exists():
                widget.destroy()
        self._widgets_filas.clear()
        self._widgets_miniatura.clear()
        self._imagenes_vivas.clear()

        if self._aviso:
            aviso = ctk.CTkLabel(self.marco_detalle, text=self._aviso,
                                 justify="left", anchor="w")
            aviso.pack(fill="x", padx=10, pady=10)
            self._widgets_filas.append(aviso)
            return

        for fila in self.filas:
            self._crear_fila_detalle(fila)

    def _crear_fila_detalle(self, fila: FilaArchivo) -> None:
        contenedor = ctk.CTkFrame(self.marco_detalle)
        contenedor.pack(fill="x", padx=5, pady=3)
        self._widgets_filas.append(contenedor)

        # Hueco de la miniatura, con marcador mientras se genera
        etiqueta_imagen = ctk.CTkLabel(
            contenedor, text="...", width=LADO_MINIATURA, height=LADO_MINIATURA,
            fg_color=("gray82", "gray25"), corner_radius=6,
        )
        etiqueta_imagen.pack(side="left", padx=8, pady=8)
        self._widgets_miniatura[str(fila.ruta)] = etiqueta_imagen
        self._pedir_miniatura(fila.ruta)

        textos = ctk.CTkFrame(contenedor, fg_color="transparent")
        textos.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=6)

        ctk.CTkLabel(
            textos, text=fila.ruta.name, anchor="w",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(fill="x")

        detalle = f"{fila.tamano_legible}  ·  {fila.ruta.suffix.lstrip('.').upper()}"
        if fila.ruta_salida:
            detalle += f"  ·  guardado como {fila.ruta_salida.name}"
        ctk.CTkLabel(textos, text=detalle, anchor="w",
                     text_color=("gray40", "gray65")).pack(fill="x")

        ctk.CTkLabel(
            textos, text=f"{SIMBOLOS[fila.estado]} {fila.mensaje}", anchor="w",
            text_color=COLORES_ESTADO[fila.estado],
        ).pack(fill="x")

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
            etiqueta.configure(text="sin\nvista", font=ctk.CTkFont(size=10))
            return

        ctk_imagen = ctk.CTkImage(
            light_image=imagen, dark_image=imagen,
            size=(imagen.width, imagen.height),
        )
        self._imagenes_vivas.append(ctk_imagen)
        etiqueta.configure(image=ctk_imagen, text="")
