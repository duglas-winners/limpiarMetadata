import os
import queue
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import List

import customtkinter as ctk

from limpiadores.limpiador_video import LimpiadorVideo
from limpiadores.proveedor import ProveedorLimpiadores
from nucleo.procesador import ProcesadorEnLote, ResultadoArchivo

from .vista_cola import VistaCola

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# Cada cuanto revisa el hilo principal si el trabajador dejo novedades
INTERVALO_EVENTOS_MS = 80


class VentanaPrincipal(ctk.CTk):
    """
    Pantalla unica de la aplicacion. Se compone de cinco zonas apiladas:

      1. Barra de acciones   -> seleccionar archivos / carpeta destino / limpiar cola
      2. Etiqueta de destino -> ruta donde se guardaran los resultados
      3. Visor de la cola    -> lista compacta o detalle con miniaturas
      4. Indicadores         -> barra de progreso + linea de estado
      5. Boton principal     -> lanza el procesamiento

    Regla de hilos: el procesamiento corre en un hilo secundario, pero Tkinter
    solo admite llamadas desde el hilo principal. Por eso todo repintado se
    encola con `self.after(0, ...)`.
    """

    def __init__(self):
        super().__init__()
        self.title("Limpiador de Metadatos - Imagenes y Videos")
        self.geometry("820x640")
        self.minsize(680, 520)

        self.archivos_seleccionados: List[Path] = []
        self.carpeta_destino: Path = Path.home() / "Archivos_Limpiados"
        self.procesador = ProcesadorEnLote(max_hilos=os.cpu_count() or 4)
        self.cola_eventos: queue.Queue = queue.Queue()

        self._construir_interfaz()
        self._avisar_si_falta_ffmpeg()
        self.after(INTERVALO_EVENTOS_MS, self._consumir_eventos)

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

        # Conmutador de vista, alineado a la derecha porque no ejecuta trabajo:
        # solo cambia como se presenta lo que ya hay en pantalla.
        self.selector_vista = ctk.CTkSegmentedButton(
            panel_superior,
            values=["Lista", "Detalle"],
            command=self._cambiar_vista,
            width=170,
        )
        self.selector_vista.set("Lista")
        self.selector_vista.pack(side="right", padx=5, pady=8)

        # 2. Etiqueta de destino
        self.etiqueta_destino = ctk.CTkLabel(
            self, text=f"Destino: {self.carpeta_destino}", anchor="w"
        )
        self.etiqueta_destino.pack(fill="x", padx=20)

        # 3. Visor de la cola
        self.vista_cola = VistaCola(self)
        self.vista_cola.pack(fill="both", expand=True, padx=15, pady=10)

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

    # --------------------------------------------------------- Acciones UI --

    def _cambiar_vista(self, valor: str):
        """Alterna entre la vista compacta y la de miniaturas."""
        self.vista_cola.establecer_modo("lista" if valor == "Lista" else "detalle")

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
            self.vista_cola.vaciar(
                aviso=f"AVISO: {motivo}\nLas imagenes si se pueden procesar."
            )

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
        self.vista_cola.cargar(self.archivos_seleccionados)
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
        self.vista_cola.vaciar()
        self.barra_progreso.set(0)
        self.etiqueta_estado.configure(text="Esperando archivos en cola...")

    def _iniciar_procesamiento(self):
        """Valida la cola y lanza el trabajo en un hilo secundario."""
        if not self.archivos_seleccionados:
            messagebox.showwarning("Atencion", "Por favor selecciona al menos un archivo.")
            return

        # Las copias conservan el nombre original, asi que escribir en la carpeta
        # de los originales los sobrescribiria. Se detecta antes de empezar.
        origenes = {a.parent.resolve() for a in self.archivos_seleccionados}
        if self.carpeta_destino.resolve() in origenes:
            messagebox.showerror(
                "Carpeta destino no valida",
                "La carpeta destino es la misma donde estan los originales.\n\n"
                "Como las copias limpias conservan el nombre original, se "
                "sobrescribirian. Elige otra carpeta destino.",
            )
            return

        self.boton_procesar.configure(state="disabled", text="Procesando...")
        self.barra_progreso.set(0)
        self.vista_cola.reiniciar_estados()

        threading.Thread(target=self._procesar_en_segundo_plano, daemon=True).start()

    # ------------------------------------------------------ Hilo secundario --

    def _procesar_en_segundo_plano(self):
        """
        Cuerpo del hilo trabajador. No toca Tkinter en absoluto: deposita cada
        novedad en `self.cola_eventos`, que el hilo principal vacia con
        `_consumir_eventos`.
        """

        def actualizar_progreso(resultado: ResultadoArchivo, actual: int, total: int):
            self.cola_eventos.put(("avance", (resultado, actual, total)))

        try:
            resultados = self.procesador.procesar_archivos(
                self.archivos_seleccionados,
                self.carpeta_destino,
                actualizar_progreso,
            )
        except Exception as error:
            self.cola_eventos.put(("error", str(error)))
            return

        self.cola_eventos.put(("fin", resultados))

    def _consumir_eventos(self):
        """
        Aplica en el hilo principal las novedades que dejo el hilo trabajador.
        Se reprograma indefinidamente mientras la ventana exista.
        """
        try:
            while True:
                tipo, carga = self.cola_eventos.get_nowait()

                if tipo == "avance":
                    resultado, actual, total = carga
                    marca = "OK" if resultado.exito else "!!"
                    self.vista_cola.actualizar_resultado(resultado)
                    self.barra_progreso.set(actual / total)
                    self.etiqueta_estado.configure(
                        text=f"[{actual}/{total}] [{marca}] "
                             f"{resultado.ruta_origen.name} - {resultado.mensaje}"
                    )
                elif tipo == "fin":
                    self._finalizar_procesamiento(carga)
                elif tipo == "error":
                    self._finalizar_con_error(carga)
        except queue.Empty:
            pass

        if self.winfo_exists():
            self.after(INTERVALO_EVENTOS_MS, self._consumir_eventos)

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
            f"Guardados con su nombre original en:\n{self.carpeta_destino}",
        )

    def _finalizar_con_error(self, detalle: str):
        """Restaura la pantalla tras un fallo global del lote."""
        self.boton_procesar.configure(state="normal", text="Procesar cola de archivos")
        self.etiqueta_estado.configure(text="El procesamiento se interrumpio.")
        messagebox.showerror("Error", f"No se pudo completar el procesamiento:\n{detalle}")
