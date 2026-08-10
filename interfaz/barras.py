"""
Las tres barras de control de la ventana principal.

Cada una es un componente cerrado: construye sus widgets, expone metodos para
consultarlos o actualizarlos, y avisa de la interaccion mediante callbacks. No
conocen el procesador ni la cola; solo su propio trozo de pantalla.
"""

from typing import Callable, Optional

import customtkinter as ctk

from .estilos import (
    COLOR_PELIGRO,
    COLOR_PELIGRO_HOVER,
    COLOR_TEXTO_SECUNDARIO,
    COLOR_TEXTO_TENUE,
)


class BarraAcciones(ctk.CTkFrame):
    """
    Zona 1: agregar archivos, elegir destino, vaciar, y conmutar la vista.

    El conmutador va a la derecha, separado del resto, porque no ejecuta
    trabajo ni modifica la cola: solo cambia como se presenta lo que ya hay.
    """

    def __init__(
        self,
        maestro,
        al_agregar: Callable[[], None],
        al_elegir_destino: Callable[[], None],
        al_vaciar: Callable[[], None],
        al_cambiar_vista: Callable[[str], None],
    ):
        super().__init__(maestro)

        self.boton_agregar = ctk.CTkButton(self, text="Agregar archivos", command=al_agregar)
        self.boton_agregar.pack(side="left", padx=5, pady=8)

        self.boton_destino = ctk.CTkButton(
            self, text="Carpeta destino", command=al_elegir_destino
        )
        self.boton_destino.pack(side="left", padx=5, pady=8)

        self.boton_vaciar = ctk.CTkButton(
            self, text="Vaciar todo", fg_color="gray40",
            hover_color="gray30", command=al_vaciar,
        )
        self.boton_vaciar.pack(side="left", padx=5, pady=8)

        self.selector_vista = ctk.CTkSegmentedButton(
            self, values=["Lista", "Detalle"], command=al_cambiar_vista, width=170
        )
        self.selector_vista.set("Lista")
        self.selector_vista.pack(side="right", padx=5, pady=8)

    def bloquear(self, bloquear: bool) -> None:
        estado = "disabled" if bloquear else "normal"
        for boton in (self.boton_agregar, self.boton_destino, self.boton_vaciar):
            boton.configure(state=estado)


class BarraSeleccion(ctk.CTkFrame):
    """
    Zona 3: marcar todo, quitar los marcados y contar lo que hay.

    Existe para responder a "se me colo un archivo, ¿tengo que empezar de
    cero?". La respuesta debe ser no.
    """

    def __init__(
        self,
        maestro,
        al_marcar_todos: Callable[[bool], None],
        al_quitar: Callable[[], None],
    ):
        super().__init__(maestro, fg_color="transparent")

        self._al_marcar_todos = al_marcar_todos

        self.marcar_todo = ctk.CTkCheckBox(
            self, text="Marcar todos", width=24,
            command=lambda: self._al_marcar_todos(bool(self.marcar_todo.get())),
        )
        self.marcar_todo.pack(side="left", padx=(10, 12))

        # Rojo y deshabilitado por defecto: es la unica accion destructiva de
        # la pantalla, debe verse como tal pero no poder pulsarse en vacio.
        self.boton_quitar = ctk.CTkButton(
            self, text="Quitar de la cola", width=150,
            fg_color=COLOR_PELIGRO, hover_color=COLOR_PELIGRO_HOVER,
            state="disabled", command=al_quitar,
        )
        self.boton_quitar.pack(side="left")

        self.etiqueta_conteo = ctk.CTkLabel(
            self, text="0 archivos en la cola", anchor="e",
            text_color=COLOR_TEXTO_SECUNDARIO,
        )
        self.etiqueta_conteo.pack(side="right", padx=10)

    def actualizar(self, marcadas: int, total: int) -> None:
        """Refleja el estado real de la cola en los tres controles."""
        self.boton_quitar.configure(
            state="normal" if marcadas else "disabled",
            # El recuento va en el propio boton: confirma cuantos se van antes
            # de pulsar, sin necesidad de un dialogo.
            text=f"Quitar de la cola ({marcadas})" if marcadas else "Quitar de la cola",
        )

        if total == 0:
            texto = "0 archivos en la cola"
        elif marcadas:
            texto = f"{marcadas} de {total} marcados"
        else:
            texto = f"{total} archivo{'s' if total != 1 else ''} en la cola"
        self.etiqueta_conteo.configure(text=texto)

        # La casilla general solo se marca si lo estan todas las filas
        if total and marcadas == total:
            self.marcar_todo.select()
        else:
            self.marcar_todo.deselect()

    def bloquear(self, bloquear: bool) -> None:
        self.marcar_todo.configure(state="disabled" if bloquear else "normal")
        if bloquear:
            self.boton_quitar.configure(state="disabled")


class BarraCompresion(ctk.CTkFrame):
    """
    Zona 3b: casilla de compresion y peso de la cola.

    Muestra siempre el peso total y, con la compresion marcada, el techo al que
    bajaria. Se anuncia como maximo y no como cifra exacta porque la estimacion
    es un techo: el archivo real sale igual o mas pequeño, nunca mayor.
    """

    def __init__(self, maestro, al_cambiar: Callable[[], None]):
        super().__init__(maestro, fg_color="transparent")

        self.comprimir = ctk.CTkCheckBox(
            self, text="Comprimir videos", width=24, command=al_cambiar
        )
        self.comprimir.pack(side="left", padx=(10, 10))

        self.etiqueta_nota = ctk.CTkLabel(
            self, text="", anchor="w", text_color=COLOR_TEXTO_TENUE,
            font=ctk.CTkFont(size=11),
        )
        self.etiqueta_nota.pack(side="left")

        self.etiqueta_peso = ctk.CTkLabel(
            self, text="Peso total: 0 B", anchor="e",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.etiqueta_peso.pack(side="right", padx=10)

    @property
    def activada(self) -> bool:
        return bool(self.comprimir.get())

    def mostrar_nota(self, hay_videos: bool) -> None:
        if not self.activada:
            self.etiqueta_nota.configure(text="")
        elif hay_videos:
            self.etiqueta_nota.configure(
                text="Recodifica: mas lento y con algo de perdida de calidad."
            )
        else:
            self.etiqueta_nota.configure(text="(no hay videos en la cola)")

    def mostrar_peso(self, texto_total: str, sufijo: Optional[str] = None) -> None:
        texto = f"Peso total: {texto_total}"
        if sufijo:
            texto += f"  →  {sufijo}"
        self.etiqueta_peso.configure(text=texto)

    def bloquear(self, bloquear: bool) -> None:
        self.comprimir.configure(state="disabled" if bloquear else "normal")


class PanelProgreso(ctk.CTkFrame):
    """Zona 5: barra de progreso y linea de estado."""

    def __init__(self, maestro):
        super().__init__(maestro, fg_color="transparent")

        self.barra = ctk.CTkProgressBar(self)
        self.barra.set(0)
        self.barra.pack(fill="x", padx=0, pady=5)

        self.etiqueta = ctk.CTkLabel(self, text="Agrega archivos para empezar.")
        self.etiqueta.pack(pady=5)

    def avanzar(self, fraccion: float) -> None:
        self.barra.set(fraccion)

    def reiniciar(self) -> None:
        self.barra.set(0)

    def informar(self, texto: str) -> None:
        self.etiqueta.configure(text=texto)
