"""
Las tres barras de control de la ventana principal.

Cada una es un componente cerrado: construye sus widgets, expone metodos para
consultarlos o actualizarlos, y avisa de la interaccion mediante callbacks. No
conocen el procesador ni la cola; solo su propio trozo de pantalla.
"""

from typing import Callable, Optional

import customtkinter as ctk

from nucleo.medios import NIVELES as NIVELES_COMPRESION

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
        al_abrir_consola: Callable[[], None],
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

        # Sigue disponible mientras se procesa: es justo cuando hace falta
        # mirar por que esta fallando algo.
        self.boton_consola = ctk.CTkButton(
            self, text="Consola", width=100, fg_color="gray40",
            hover_color="gray30", command=al_abrir_consola,
        )
        self.boton_consola.pack(side="right", padx=(5, 12), pady=8)

    def marcar_incidencias(self, cuantas: int) -> None:
        """
        Refleja en el boton si hay algo que mirar.

        Se colorea solo cuando hay incidencias: un boton siempre rojo se vuelve
        invisible de tanto verlo, y deja de avisar cuando de verdad importa.
        """
        if cuantas:
            self.boton_consola.configure(
                text=f"Consola ({cuantas})",
                fg_color=COLOR_PELIGRO, hover_color=COLOR_PELIGRO_HOVER,
            )
        else:
            self.boton_consola.configure(
                text="Consola", fg_color="gray40", hover_color="gray30",
            )

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
    Zona 3b: casilla de compresion.

    El peso ya no se muestra aqui agregado, sino en cada fila de la lista: un
    total no dice cual de los archivos ocupa lo que ocupa, que es justo lo que
    hace falta para decidir si comprimir o cual quitar de la cola.
    """

    def __init__(self, maestro, al_cambiar: Callable[[], None], nivel_inicial: str):
        super().__init__(maestro, fg_color="transparent")

        self._al_cambiar = al_cambiar

        self.comprimir = ctk.CTkCheckBox(
            self, text="Comprimir videos", width=24, command=self._al_alternar
        )
        self.comprimir.pack(side="left", padx=(10, 10))

        # El selector de nivel solo aparece con la compresion marcada: sin ella
        # no hace nada, y un control inerte invita a probarlo sin efecto.
        self.selector_nivel = ctk.CTkSegmentedButton(
            self, values=list(NIVELES_COMPRESION), command=lambda _: al_cambiar(),
            width=320,
        )
        self.selector_nivel.set(
            nivel_inicial if nivel_inicial in NIVELES_COMPRESION else "Media"
        )

        self.etiqueta_nota = ctk.CTkLabel(
            self, text="", anchor="w", text_color=COLOR_TEXTO_TENUE,
            font=ctk.CTkFont(size=11),
        )
        self.etiqueta_nota.pack(side="left", padx=(6, 0))

    def _al_alternar(self) -> None:
        """Muestra u oculta el selector de nivel segun la casilla."""
        if self.activada:
            # Se inserta antes de la nota para que quede junto a la casilla
            self.selector_nivel.pack(side="left", padx=(4, 8), before=self.etiqueta_nota)
        else:
            self.selector_nivel.pack_forget()
        self._al_cambiar()

    @property
    def activada(self) -> bool:
        return bool(self.comprimir.get())

    @property
    def nivel(self) -> str:
        return self.selector_nivel.get()

    def mostrar_nota(self, hay_videos: bool, descripcion: str = "") -> None:
        if not self.activada:
            self.etiqueta_nota.configure(text="")
        elif not hay_videos:
            self.etiqueta_nota.configure(text="(no hay videos en la cola)")
        else:
            self.etiqueta_nota.configure(text=descripcion)

    def bloquear(self, bloquear: bool) -> None:
        estado = "disabled" if bloquear else "normal"
        self.comprimir.configure(state=estado)
        self.selector_nivel.configure(state=estado)


class PanelProgreso(ctk.CTkFrame):
    """
    Zona 5: dos barras de progreso y una linea de estado.

    Son dos porque responden a preguntas distintas, y con una sola no se puede
    contestar ninguna bien:

      - La de arriba, el archivo en curso. Sin ella, comprimir un video de
        varios GB deja la pantalla inmovil durante minutos y la aplicacion
        parece colgada.
      - La de abajo, el lote completo. Avanza de forma continua, sumando la
        fraccion del archivo actual a los ya terminados, en vez de saltar de
        golpe cada vez que uno acaba.
    """

    def __init__(self, maestro):
        super().__init__(maestro, fg_color="transparent")

        self.etiqueta_archivo = ctk.CTkLabel(
            self, text="", anchor="w", text_color=COLOR_TEXTO_SECUNDARIO,
            font=ctk.CTkFont(size=12),
        )
        self.etiqueta_archivo.pack(fill="x", padx=2)

        self.barra_archivo = ctk.CTkProgressBar(self, height=8)
        self.barra_archivo.set(0)
        self.barra_archivo.pack(fill="x", pady=(2, 8))

        self.etiqueta_lote = ctk.CTkLabel(
            self, text="", anchor="w", text_color=COLOR_TEXTO_SECUNDARIO,
            font=ctk.CTkFont(size=12),
        )
        self.etiqueta_lote.pack(fill="x", padx=2)

        self.barra_lote = ctk.CTkProgressBar(self, height=14)
        self.barra_lote.set(0)
        self.barra_lote.pack(fill="x", pady=(2, 4))

        self.etiqueta = ctk.CTkLabel(self, text="Agrega archivos para empezar.")
        self.etiqueta.pack(pady=4)

    def mostrar_archivo(self, nombre: str, fraccion: float) -> None:
        """Avance del archivo que se esta procesando ahora mismo."""
        self.etiqueta_archivo.configure(text=f"{nombre}  —  {fraccion * 100:.0f}%")
        self.barra_archivo.set(fraccion)

    def mostrar_lote(self, completados: int, total: int, fraccion: float) -> None:
        """Avance del lote entero, ya incluida la fraccion del archivo actual."""
        self.etiqueta_lote.configure(
            text=f"Progreso general: {completados} de {total}  —  {fraccion * 100:.0f}%"
        )
        self.barra_lote.set(fraccion)

    def reiniciar(self, total: int = 0) -> None:
        """Deja ambas barras a cero al empezar una corrida, o al vaciar la cola."""
        self.barra_archivo.set(0)
        self.barra_lote.set(0)
        if total:
            self.etiqueta_archivo.configure(text="Preparando...")
            self.etiqueta_lote.configure(text=f"Progreso general: 0 de {total}  —  0%")
        else:
            self.etiqueta_archivo.configure(text="")
            self.etiqueta_lote.configure(text="")

    def informar(self, texto: str) -> None:
        self.etiqueta.configure(text=texto)
