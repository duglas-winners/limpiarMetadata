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
    Pantalla unica de la aplicacion, en seis zonas apiladas:

      1. Barra de acciones   -> agregar archivos / carpeta destino / vaciar
      2. Etiqueta de destino -> ruta donde se guardaran los resultados
      3. Barra de seleccion  -> marcar todo y quitar los archivos marcados
      4. Lista de archivos   -> filas seleccionables, en vista lista o detalle
      5. Indicadores         -> barra de progreso + linea de estado
      6. Boton principal     -> lanza el procesamiento

    Regla de hilos: el procesamiento corre en un hilo secundario, pero Tkinter
    solo admite llamadas desde el hilo principal, `after()` incluido. El
    trabajador deposita sus novedades en `self.cola_eventos` y el hilo principal
    la vacia con `_consumir_eventos`.
    """

    def __init__(self):
        super().__init__()
        self.title("Limpiador de Metadatos - Imagenes y Videos")
        self.geometry("880x680")
        self.minsize(720, 560)

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
        panel_superior.pack(fill="x", padx=15, pady=(15, 8))

        self.boton_agregar = ctk.CTkButton(
            panel_superior, text="Agregar archivos", command=self._agregar_archivos
        )
        self.boton_agregar.pack(side="left", padx=5, pady=8)

        self.boton_destino = ctk.CTkButton(
            panel_superior, text="Carpeta destino",
            command=self._seleccionar_carpeta_destino,
        )
        self.boton_destino.pack(side="left", padx=5, pady=8)

        self.boton_vaciar = ctk.CTkButton(
            panel_superior, text="Vaciar todo", fg_color="gray40",
            hover_color="gray30", command=self._vaciar_cola,
        )
        self.boton_vaciar.pack(side="left", padx=5, pady=8)

        # Conmutador de densidad. A la derecha porque no ejecuta trabajo ni
        # modifica la cola: solo cambia como se presenta lo que ya hay.
        self.selector_vista = ctk.CTkSegmentedButton(
            panel_superior, values=["Lista", "Detalle"],
            command=self._cambiar_vista, width=170,
        )
        self.selector_vista.set("Lista")
        self.selector_vista.pack(side="right", padx=5, pady=8)

        # 2. Etiqueta de destino
        self.etiqueta_destino = ctk.CTkLabel(
            self, text=f"Destino: {self.carpeta_destino}", anchor="w",
            text_color=("gray35", "gray70"),
        )
        self.etiqueta_destino.pack(fill="x", padx=20)

        # 3. Barra de seleccion
        barra_seleccion = ctk.CTkFrame(self, fg_color="transparent")
        barra_seleccion.pack(fill="x", padx=15, pady=(8, 0))

        self.marcar_todo = ctk.CTkCheckBox(
            barra_seleccion, text="Marcar todos", command=self._marcar_todos, width=24
        )
        self.marcar_todo.pack(side="left", padx=(10, 12))

        self.boton_quitar = ctk.CTkButton(
            barra_seleccion, text="Quitar de la cola", width=150,
            fg_color=("#b3261e", "#8c1d18"), hover_color=("#8c1d18", "#6d1512"),
            state="disabled", command=self._quitar_marcados,
        )
        self.boton_quitar.pack(side="left")

        self.etiqueta_conteo = ctk.CTkLabel(
            barra_seleccion, text="0 archivos en la cola", anchor="e",
            text_color=("gray35", "gray70"),
        )
        self.etiqueta_conteo.pack(side="right", padx=10)

        # 4. Lista de archivos
        self.vista_cola = VistaCola(self, al_cambiar_seleccion=self._al_cambiar_seleccion)
        self.vista_cola.pack(fill="both", expand=True, padx=15, pady=8)

        # 5. Indicadores de estado
        self.barra_progreso = ctk.CTkProgressBar(self)
        self.barra_progreso.set(0)
        self.barra_progreso.pack(fill="x", padx=15, pady=5)

        self.etiqueta_estado = ctk.CTkLabel(self, text="Agrega archivos para empezar.")
        self.etiqueta_estado.pack(padx=15, pady=5)

        # 6. Boton principal
        self.boton_procesar = ctk.CTkButton(
            self, text="Limpiar metadatos", height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="green", hover_color="#1e7a1e",
            command=self._iniciar_procesamiento,
        )
        self.boton_procesar.pack(fill="x", padx=15, pady=(5, 15))

    # --------------------------------------------------------- Acciones UI --

    def _cambiar_vista(self, valor: str):
        """Alterna entre la vista compacta y la de miniaturas."""
        self.vista_cola.establecer_modo("lista" if valor == "Lista" else "detalle")

    def _al_cambiar_seleccion(self, marcadas: int):
        """Mantiene la barra de seleccion al dia con el estado de la cola."""
        total = len(self.vista_cola.filas)

        self.boton_quitar.configure(
            state="normal" if marcadas else "disabled",
            text=f"Quitar de la cola ({marcadas})" if marcadas else "Quitar de la cola",
        )

        if total == 0:
            texto = "0 archivos en la cola"
        elif marcadas:
            texto = f"{marcadas} de {total} marcados"
        else:
            texto = f"{total} archivo{'s' if total != 1 else ''} en la cola"
        self.etiqueta_conteo.configure(text=texto)

        # La casilla general refleja el estado real de la lista
        if total and marcadas == total:
            self.marcar_todo.select()
        else:
            self.marcar_todo.deselect()

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
                aviso=f"AVISO: {motivo}\n\nLas imagenes si se pueden procesar."
            )

    def _agregar_archivos(self):
        """
        Añade archivos a la cola sin descartar los que ya estaban, de modo que
        se pueda componer una seleccion en varias tandas.
        """
        archivos = filedialog.askopenfilenames(
            title="Selecciona imagenes o videos",
            filetypes=[
                ("Imagenes y videos", ProveedorLimpiadores.patron_dialogo()),
                ("Todos los archivos", "*.*"),
            ],
        )
        if not archivos:
            return

        rutas = [Path(f) for f in archivos]
        añadidos = self.vista_cola.agregar(rutas)
        repetidos = len(rutas) - añadidos

        self.barra_progreso.set(0)
        if añadidos and repetidos:
            self.etiqueta_estado.configure(
                text=f"{añadidos} agregados. {repetidos} ya estaban en la cola."
            )
        elif añadidos:
            self.etiqueta_estado.configure(text=f"{añadidos} archivo(s) agregados.")
        else:
            self.etiqueta_estado.configure(text="Esos archivos ya estaban en la cola.")

    def _seleccionar_carpeta_destino(self):
        """Permite elegir la carpeta donde se guardaran los archivos limpios."""
        carpeta = filedialog.askdirectory(title="Seleccionar carpeta para guardar resultados")
        if carpeta:
            self.carpeta_destino = Path(carpeta)
            self.etiqueta_destino.configure(text=f"Destino: {self.carpeta_destino}")

    def _marcar_todos(self):
        """Marca o desmarca la cola entera desde la casilla general."""
        self.vista_cola.marcar_todas(bool(self.marcar_todo.get()))

    def _quitar_marcados(self):
        """Saca de la cola los archivos marcados."""
        quitados = self.vista_cola.quitar_marcados()
        if quitados:
            self.etiqueta_estado.configure(
                text=f"{quitados} archivo(s) quitados de la cola."
            )

    def _vaciar_cola(self):
        """Descarta la seleccion actual y deja la pantalla en su estado inicial."""
        self.vista_cola.vaciar()
        self.barra_progreso.set(0)
        self.etiqueta_estado.configure(text="Agrega archivos para empezar.")

    def _iniciar_procesamiento(self):
        """Valida la cola y lanza el trabajo en un hilo secundario."""
        archivos = self.vista_cola.rutas
        if not archivos:
            messagebox.showwarning(
                "Cola vacia", "Agrega al menos un archivo antes de limpiar."
            )
            return

        # Las copias conservan el nombre original, asi que escribir en la carpeta
        # de los originales los sobrescribiria. Se detecta antes de empezar.
        if self.carpeta_destino.resolve() in {a.parent.resolve() for a in archivos}:
            messagebox.showerror(
                "Carpeta destino no valida",
                "La carpeta destino es la misma donde estan los originales.\n\n"
                "Como las copias limpias conservan el nombre original, se "
                "sobrescribirian. Elige otra carpeta destino.",
            )
            return

        self.archivos_en_proceso = archivos
        self._bloquear_controles(True)
        self.barra_progreso.set(0)
        self.vista_cola.reiniciar_estados()

        threading.Thread(target=self._procesar_en_segundo_plano, daemon=True).start()

    def _bloquear_controles(self, bloquear: bool):
        """
        Desactiva todo lo que modifique la cola mientras se procesa. Editarla a
        mitad de la corrida dejaria la vista describiendo un trabajo distinto
        del que se esta ejecutando.
        """
        estado = "disabled" if bloquear else "normal"
        for boton in (self.boton_agregar, self.boton_vaciar, self.boton_destino):
            boton.configure(state=estado)
        self.marcar_todo.configure(state=estado)
        self.vista_cola.bloquear(bloquear)

        if bloquear:
            self.boton_quitar.configure(state="disabled")
            self.boton_procesar.configure(state="disabled", text="Procesando...")
        else:
            self.boton_procesar.configure(state="normal", text="Limpiar metadatos")
            self._al_cambiar_seleccion(self.vista_cola.total_marcadas)

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
                self.archivos_en_proceso, self.carpeta_destino, actualizar_progreso
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
                    self.vista_cola.actualizar_resultado(resultado)
                    self.barra_progreso.set(actual / total)
                    self.etiqueta_estado.configure(
                        text=f"Procesando {actual} de {total}: {resultado.ruta_origen.name}"
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
        limpiados = sum(1 for r in resultados if r.codigo == "limpiado")
        omitidos = sum(1 for r in resultados if r.codigo == "omitido")
        errores = sum(1 for r in resultados if r.codigo == "error")

        self._bloquear_controles(False)

        partes = [f"{limpiados} limpiado" + ("s" if limpiados != 1 else "")]
        if omitidos:
            partes.append(f"{omitidos} omitido" + ("s" if omitidos != 1 else ""))
        if errores:
            partes.append(f"{errores} con error" + ("es" if errores != 1 else ""))
        resumen = ", ".join(partes)

        self.etiqueta_estado.configure(text=f"Listo: {resumen}.")
        messagebox.showinfo(
            "Proceso completado",
            f"{resumen}.\n\nLos archivos limpios conservan su nombre original y "
            f"estan en:\n{self.carpeta_destino}",
        )

    def _finalizar_con_error(self, detalle: str):
        """Restaura la pantalla tras un fallo global del lote."""
        self._bloquear_controles(False)
        self.etiqueta_estado.configure(text="El procesamiento se interrumpio.")
        messagebox.showerror("Error", f"No se pudo completar el procesamiento:\n{detalle}")
