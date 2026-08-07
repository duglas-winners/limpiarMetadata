import os
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import List

import customtkinter as ctk

from limpiadores.limpiador_video import LimpiadorVideo
from limpiadores.proveedor import ProveedorLimpiadores
from nucleo.procesador import ProcesadorEnLote, ResultadoArchivo

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class VentanaPrincipal(ctk.CTk):
    """
    Pantalla unica de la aplicacion. Se compone de cinco zonas apiladas:

      1. Barra de acciones   -> seleccionar archivos / carpeta destino / limpiar cola
      2. Etiqueta de destino -> ruta donde se guardaran los resultados
      3. Visor de la cola    -> un renglon por archivo con su estado
      4. Indicadores         -> barra de progreso + linea de estado
      5. Boton principal     -> lanza el procesamiento

    Regla de hilos: el procesamiento corre en un hilo secundario, pero Tkinter
    solo admite llamadas desde el hilo principal. Por eso todo repintado se
    encola con `self.after(0, ...)`.
    """

    def __init__(self):
        super().__init__()
        self.title("Limpiador de Metadatos - Imagenes y Videos")
        self.geometry("780x600")
        self.minsize(640, 500)

        self.archivos_seleccionados: List[Path] = []
        self.carpeta_destino: Path = Path.home() / "Archivos_Limpiados"
        self.procesador = ProcesadorEnLote(max_hilos=os.cpu_count() or 4)

        self._construir_interfaz()
        self._avisar_si_falta_ffmpeg()

    # ------------------------------------------------------------------ UI --

    def _construir_interfaz(self):
        """Crea y coloca todos los widgets de la ventana."""
        # 1. Barra de acciones
        panel_superior = ctk.CTkFrame(self)
        panel_superior.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkButton(
            panel_superior,
            text="Seleccionar archivos",
            command=self._seleccionar_archivos,
        ).pack(side="left", padx=5, pady=8)

        ctk.CTkButton(
            panel_superior,
            text="Carpeta destino",
            command=self._seleccionar_carpeta_destino,
        ).pack(side="left", padx=5, pady=8)

        ctk.CTkButton(
            panel_superior,
            text="Vaciar cola",
            fg_color="gray40",
            hover_color="gray30",
            command=self._vaciar_cola,
        ).pack(side="left", padx=5, pady=8)

        # 2. Etiqueta de destino
        self.etiqueta_destino = ctk.CTkLabel(
            self, text=f"Destino: {self.carpeta_destino}", anchor="w"
        )
        self.etiqueta_destino.pack(fill="x", padx=20)

        # 3. Visor de la cola
        self.caja_lista = ctk.CTkTextbox(self, height=280, state="disabled")
        self.caja_lista.pack(fill="both", expand=True, padx=15, pady=10)

        # 4. Indicadores de estado
        self.barra_progreso = ctk.CTkProgressBar(self)
        self.barra_progreso.set(0)
        self.barra_progreso.pack(fill="x", padx=15, pady=5)

        self.etiqueta_estado = ctk.CTkLabel(self, text="Esperando archivos en cola...")
        self.etiqueta_estado.pack(padx=15, pady=5)

        # 5. Boton principal
        self.boton_procesar = ctk.CTkButton(
            self,
            text="Procesar cola de archivos",
            height=42,
            fg_color="green",
            hover_color="#1e7a1e",
            command=self._iniciar_procesamiento,
        )
        self.boton_procesar.pack(fill="x", padx=15, pady=(5, 15))

    def _escribir_en_cola(self, lineas: List[str]):
        """Reemplaza el contenido del visor de la cola (solo hilo principal)."""
        self.caja_lista.configure(state="normal")
        self.caja_lista.delete("1.0", "end")
        self.caja_lista.insert("end", "\n".join(lineas))
        self.caja_lista.configure(state="disabled")

    def _agregar_a_cola(self, linea: str):
        """Añade un renglon al visor de la cola (solo hilo principal)."""
        self.caja_lista.configure(state="normal")
        self.caja_lista.insert("end", f"\n{linea}")
        self.caja_lista.see("end")
        self.caja_lista.configure(state="disabled")

    # --------------------------------------------------------- Acciones UI --

    def _avisar_si_falta_ffmpeg(self):
        """
        Advierte al abrir la app si FFmpeg no esta disponible. Se muestra dentro
        de la ventana (no como dialogo modal) para no frenar el arranque: las
        imagenes siguen siendo procesables sin FFmpeg.
        """
        disponible, motivo = LimpiadorVideo().esta_disponible()
        if not disponible:
            self.etiqueta_estado.configure(
                text="Aviso: FFmpeg no disponible, los videos no se podran procesar."
            )
            self._escribir_en_cola([f"AVISO: {motivo}", "Las imagenes si se pueden procesar."])

    def _seleccionar_archivos(self):
        """Abre el dialogo de seleccion y carga los archivos elegidos en la cola."""
        archivos = filedialog.askopenfilenames(
            title="Selecciona imagenes o videos",
            filetypes=[
                ("Imagenes y videos", ProveedorLimpiadores.patron_dialogo()),
                ("Todos los archivos", "*.*"),
            ],
        )
        if not archivos:
            return

        self.archivos_seleccionados = [Path(f) for f in archivos]
        self._escribir_en_cola([f"[  ] {a.name}" for a in self.archivos_seleccionados])
        self.barra_progreso.set(0)
        self.etiqueta_estado.configure(
            text=f"{len(self.archivos_seleccionados)} archivos cargados en la cola."
        )

    def _seleccionar_carpeta_destino(self):
        """Permite elegir la carpeta donde se guardaran los archivos limpios."""
        carpeta = filedialog.askdirectory(title="Seleccionar carpeta para guardar resultados")
        if carpeta:
            self.carpeta_destino = Path(carpeta)
            self.etiqueta_destino.configure(text=f"Destino: {self.carpeta_destino}")

    def _vaciar_cola(self):
        """Descarta la seleccion actual y deja la pantalla en su estado inicial."""
        self.archivos_seleccionados = []
        self._escribir_en_cola([])
        self.barra_progreso.set(0)
        self.etiqueta_estado.configure(text="Esperando archivos en cola...")

    def _iniciar_procesamiento(self):
        """Valida la cola y lanza el trabajo en un hilo secundario."""
        if not self.archivos_seleccionados:
            messagebox.showwarning("Atencion", "Por favor selecciona al menos un archivo.")
            return

        self.boton_procesar.configure(state="disabled", text="Procesando...")
        self.barra_progreso.set(0)
        self._escribir_en_cola([])

        threading.Thread(target=self._procesar_en_segundo_plano, daemon=True).start()

    # ------------------------------------------------------ Hilo secundario --

    def _procesar_en_segundo_plano(self):
        """
        Cuerpo del hilo trabajador. No toca widgets directamente: todas las
        actualizaciones visuales se delegan al hilo principal con `after`.
        """

        def actualizar_progreso(resultado: ResultadoArchivo, actual: int, total: int):
            marca = "OK" if resultado.exito else "!!"
            linea = f"[{marca}] {resultado.ruta_origen.name} - {resultado.mensaje}"
            self.after(0, self._agregar_a_cola, linea)
            self.after(0, self.barra_progreso.set, actual / total)
            self.after(
                0,
                lambda: self.etiqueta_estado.configure(text=f"[{actual}/{total}] {linea}"),
            )

        try:
            resultados = self.procesador.procesar_archivos(
                self.archivos_seleccionados,
                self.carpeta_destino,
                actualizar_progreso,
            )
        except Exception as error:
            self.after(0, self._finalizar_con_error, str(error))
            return

        self.after(0, self._finalizar_procesamiento, resultados)

    # ------------------------------------------------------------- Cierres --

    def _finalizar_procesamiento(self, resultados: List[ResultadoArchivo]):
        """Restaura la pantalla y muestra el resumen de la corrida."""
        correctos = sum(1 for r in resultados if r.exito)
        fallidos = len(resultados) - correctos

        self.boton_procesar.configure(state="normal", text="Procesar cola de archivos")
        self.etiqueta_estado.configure(
            text=f"Completado: {correctos} correctos, {fallidos} con error."
        )
        messagebox.showinfo(
            "Completado",
            f"{correctos} archivo(s) limpiados y {fallidos} con error.\n\n"
            f"Guardados en:\n{self.carpeta_destino}",
        )

    def _finalizar_con_error(self, detalle: str):
        """Restaura la pantalla tras un fallo global del lote."""
        self.boton_procesar.configure(state="normal", text="Procesar cola de archivos")
        self.etiqueta_estado.configure(text="El procesamiento se interrumpio.")
        messagebox.showerror("Error", f"No se pudo completar el procesamiento:\n{detalle}")
