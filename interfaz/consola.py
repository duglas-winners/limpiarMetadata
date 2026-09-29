"""
Consola de diagnostico: la ventana que explica por que fallo algo.

Hasta ahora los errores tecnicos se escribian por stdout, que en una
aplicacion sin consola no lee nadie: el usuario solo veia "No se pudo
procesar" repetido y sin forma de averiguar la causa.

Se abre desde un boton de la ventana principal y se refresca sola mientras
esta abierta.
"""

import time
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from nucleo.registro import registro

from .estilos import COLOR_TEXTO_TENUE

INTERVALO_REFRESCO_MS = 400

COLORES_NIVEL = {
    "info": ("gray35", "gray65"),
    "aviso": ("#7a4b00", "#f0c674"),
    "error": ("#8c1d18", "#ffa198"),
}

MENSAJE_SIN_PROBLEMAS = (
    "No hay incidencias registradas.\n\n"
    "Si un archivo falla, aqui apareceran la causa y el detalle tecnico."
)


class Consola(ctk.CTkToplevel):
    """
    Ventana secundaria con el registro de la sesion.

    Solo debe existir una: la ventana principal guarda la referencia y la trae
    al frente si ya estaba abierta, en vez de apilar copias.
    """

    def __init__(self, maestro):
        super().__init__(maestro)

        self.title("Consola de diagnostico")
        self.geometry("860x520")
        self.minsize(560, 360)

        self._ultima_version = -1
        self._solo_problemas = ctk.BooleanVar(value=True)
        self._activa = True
        self._tarea = None

        self._construir()
        self._refrescar(forzar=True)
        self._tarea = self.after(INTERVALO_REFRESCO_MS, self._tic)

        self.protocol("WM_DELETE_WINDOW", self.cerrar)

    # ------------------------------------------------------------------ UI --

    def _construir(self):
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", padx=12, pady=(12, 6))

        ctk.CTkCheckBox(
            barra, text="Solo problemas", variable=self._solo_problemas,
            command=lambda: self._refrescar(forzar=True), width=24,
        ).pack(side="left", padx=(4, 12))

        ctk.CTkButton(barra, text="Copiar", width=90,
                      command=self._copiar).pack(side="left", padx=4)
        ctk.CTkButton(barra, text="Guardar...", width=110,
                      command=self._guardar).pack(side="left", padx=4)
        ctk.CTkButton(barra, text="Vaciar", width=90, fg_color="gray40",
                      hover_color="gray30", command=self._vaciar).pack(side="left", padx=4)

        self.etiqueta_resumen = ctk.CTkLabel(
            barra, text="", anchor="e", text_color=COLOR_TEXTO_TENUE
        )
        self.etiqueta_resumen.pack(side="right", padx=8)

        self.caja = ctk.CTkTextbox(self, wrap="word", font=ctk.CTkFont(family="Consolas", size=12))
        self.caja.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.caja.configure(state="disabled")

    # ------------------------------------------------------------ Contenido --

    def _tic(self):
        """Refresca si el registro cambio. Se reprograma mientras este abierta."""
        self._refrescar()
        if self._activa and self.winfo_exists():
            self._tarea = self.after(INTERVALO_REFRESCO_MS, self._tic)

    def _refrescar(self, forzar: bool = False):
        version = registro.version
        if not forzar and version == self._ultima_version:
            return
        self._ultima_version = version

        entradas = registro.entradas(solo_problemas=self._solo_problemas.get())

        # Conserva la posicion si el usuario estaba leyendo mas arriba; solo
        # sigue el final cuando ya estaba abajo del todo.
        al_final = self.caja.yview()[1] >= 0.999

        self.caja.configure(state="normal")
        self.caja.delete("1.0", "end")

        if not entradas:
            self.caja.insert("end", MENSAJE_SIN_PROBLEMAS)
        else:
            for entrada in entradas:
                self.caja.insert("end", entrada.como_texto() + "\n")

        self.caja.configure(state="disabled")
        if al_final:
            self.caja.see("end")

        problemas = registro.total_problemas
        total = len(registro.entradas())
        self.etiqueta_resumen.configure(
            text=f"{problemas} incidencia(s) de {total} eventos"
        )

    # ------------------------------------------------------------- Acciones --

    def _texto_actual(self) -> str:
        return registro.como_texto(solo_problemas=self._solo_problemas.get())

    def _copiar(self):
        texto = self._texto_actual()
        if not texto:
            return
        self.clipboard_clear()
        self.clipboard_append(texto)
        self.etiqueta_resumen.configure(text="Copiado al portapapeles")

    def _guardar(self):
        texto = self._texto_actual()
        if not texto:
            messagebox.showinfo("Nada que guardar", "El registro esta vacio.", parent=self)
            return

        nombre = f"diagnostico_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        destino = filedialog.asksaveasfilename(
            parent=self, title="Guardar registro", initialfile=nombre,
            defaultextension=".txt", filetypes=[("Texto", "*.txt")],
        )
        if not destino:
            return

        try:
            Path(destino).write_text(texto, encoding="utf-8")
            self.etiqueta_resumen.configure(text=f"Guardado en {Path(destino).name}")
        except OSError as error:
            messagebox.showerror("No se pudo guardar", str(error), parent=self)

    def _vaciar(self):
        registro.vaciar()
        self._refrescar(forzar=True)

    def cerrar(self):
        """Cancela el refresco antes de destruirse, para no dejar `after` sueltos."""
        self._activa = False
        if self._tarea is not None:
            try:
                self.after_cancel(self._tarea)
            except Exception:
                pass
            self._tarea = None
        self.destroy()
