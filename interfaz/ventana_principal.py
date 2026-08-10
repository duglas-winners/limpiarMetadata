"""
Ventana principal: ensambla los componentes y coordina lo que ocurre entre
ellos. La logica de cada zona vive en su propio modulo.

    barras.py       las cuatro barras de control
    vista_cola.py   la lista de archivos
    modelo_cola.py  el estado de esa lista
    coordinador.py  el trabajo en segundo plano
    estilos.py      colores y constantes visuales
"""

import os
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import List

import customtkinter as ctk

from limpiadores.base import OpcionesLimpieza
from limpiadores.limpiador_video import LimpiadorVideo
from limpiadores.proveedor import ProveedorLimpiadores
from nucleo import medios
from nucleo.procesador import ProcesadorEnLote, ResultadoArchivo

from .barras import BarraAcciones, BarraCompresion, BarraSeleccion, PanelProgreso
from .coordinador import CoordinadorTrabajo
from .estilos import COLOR_TEXTO_SECUNDARIO
from .vista_cola import VistaCola

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class VentanaPrincipal(ctk.CTk):
    """
    Pantalla unica de la aplicacion, en seis zonas apiladas:

      1. Barra de acciones   -> agregar archivos / destino / vaciar / vista
      2. Etiqueta de destino -> ruta donde se guardaran los resultados
      3. Barra de seleccion  -> marcar todo y quitar los marcados
      3b. Barra de compresion-> casilla de comprimir y peso de la cola
      4. Lista de archivos   -> filas seleccionables, en vista lista o detalle
      5. Indicadores         -> barra de progreso + linea de estado
      6. Boton principal     -> lanza el procesamiento
    """

    def __init__(self):
        super().__init__()
        self.title("Limpiador de Metadatos - Imagenes y Videos")
        self.geometry("900x700")
        self.minsize(720, 560)

        self.carpeta_destino: Path = Path.home() / "Archivos_Limpiados"
        self.opciones_en_proceso = OpcionesLimpieza()

        self._construir_interfaz()

        self.coordinador = CoordinadorTrabajo(
            self,
            ProcesadorEnLote(max_hilos=os.cpu_count() or 4),
            {
                "avance": self._al_avanzar,
                "peso": self._al_llegar_estimacion,
                "fin": self._finalizar_procesamiento,
                "error": self._finalizar_con_error,
            },
        )

        self._avisar_si_falta_ffmpeg()

    # ------------------------------------------------------------------ UI --

    def _construir_interfaz(self):
        self.barra_acciones = BarraAcciones(
            self,
            al_agregar=self._agregar_archivos,
            al_elegir_destino=self._elegir_destino,
            al_vaciar=self._vaciar_cola,
            al_cambiar_vista=self._cambiar_vista,
        )
        self.barra_acciones.pack(fill="x", padx=15, pady=(15, 8))

        self.etiqueta_destino = ctk.CTkLabel(
            self, text=f"Destino: {self.carpeta_destino}", anchor="w",
            text_color=COLOR_TEXTO_SECUNDARIO,
        )
        self.etiqueta_destino.pack(fill="x", padx=20)

        self.barra_seleccion = BarraSeleccion(
            self,
            al_marcar_todos=self._marcar_todos,
            al_quitar=self._quitar_marcados,
        )
        self.barra_seleccion.pack(fill="x", padx=15, pady=(8, 0))

        self.barra_compresion = BarraCompresion(self, al_cambiar=self._actualizar_peso)
        self.barra_compresion.pack(fill="x", padx=15, pady=(6, 0))

        self.vista_cola = VistaCola(self, al_cambiar_seleccion=self._al_cambiar_seleccion)
        self.vista_cola.pack(fill="both", expand=True, padx=15, pady=8)

        self.progreso = PanelProgreso(self)
        self.progreso.pack(fill="x", padx=15)

        self.boton_procesar = ctk.CTkButton(
            self, text="Limpiar metadatos", height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="green", hover_color="#1e7a1e",
            command=self._iniciar_procesamiento,
        )
        self.boton_procesar.pack(fill="x", padx=15, pady=(5, 15))

    def _avisar_si_falta_ffmpeg(self):
        """
        Advierte al abrir si FFmpeg no esta disponible. Se muestra dentro de la
        ventana y no como dialogo modal: las imagenes siguen siendo procesables
        y frenar el arranque seria desproporcionado.
        """
        disponible, motivo = LimpiadorVideo().esta_disponible()
        if not disponible:
            self.progreso.informar(
                "Aviso: FFmpeg no disponible, los videos no se podran procesar."
            )
            self.vista_cola.vaciar(
                aviso=f"AVISO: {motivo}\n\nLas imagenes si se pueden procesar."
            )

    # --------------------------------------------------------- Acciones UI --

    def _cambiar_vista(self, valor: str):
        self.vista_cola.establecer_modo("lista" if valor == "Lista" else "detalle")

    def _al_cambiar_seleccion(self, marcadas: int):
        """La cola cambio: refresca las barras que dependen de su contenido."""
        self.barra_seleccion.actualizar(marcadas, len(self.vista_cola.filas))
        self._actualizar_peso()

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

        self.progreso.reiniciar()
        if añadidos and repetidos:
            self.progreso.informar(
                f"{añadidos} agregados. {repetidos} ya estaban en la cola."
            )
        elif añadidos:
            self.progreso.informar(f"{añadidos} archivo(s) agregados.")
        else:
            self.progreso.informar("Esos archivos ya estaban en la cola.")

    def _elegir_destino(self):
        carpeta = filedialog.askdirectory(title="Seleccionar carpeta para guardar resultados")
        if carpeta:
            self.carpeta_destino = Path(carpeta)
            self.etiqueta_destino.configure(text=f"Destino: {self.carpeta_destino}")

    def _marcar_todos(self, marcar: bool):
        self.vista_cola.marcar_todas(marcar)

    def _quitar_marcados(self):
        quitados = self.vista_cola.quitar_marcados()
        if quitados:
            self.progreso.informar(f"{quitados} archivo(s) quitados de la cola.")

    def _vaciar_cola(self):
        self.vista_cola.vaciar()
        self.progreso.reiniciar()
        self.progreso.informar("Agrega archivos para empezar.")

    # ------------------------------------------------------ Peso y compresion --

    def _actualizar_peso(self):
        """
        Refresca la etiqueta de peso. Con la compresion marcada, delega el
        calculo del techo al coordinador, que lo hace en segundo plano.
        """
        total = self.vista_cola.peso_total
        texto_total = medios.formatear_peso(total)
        hay_videos = self.vista_cola.tiene_videos

        self.barra_compresion.mostrar_nota(hay_videos)

        if not self.barra_compresion.activada or not hay_videos:
            self.coordinador.invalidar_estimacion()
            self.barra_compresion.mostrar_peso(texto_total)
            return

        self.barra_compresion.mostrar_peso(texto_total, "calculando...")
        self.coordinador.estimar_peso(self.vista_cola.rutas, total)

    def _al_llegar_estimacion(self, carga):
        """Pinta la estimacion, si sigue correspondiendo a la cola actual."""
        peticion, total, estimado = carga
        if not self.coordinador.estimacion_vigente(peticion):
            return
        if not self.barra_compresion.activada:
            return

        ahorro = 100 * (total - estimado) / total if total else 0
        # Se anuncia como maximo, no como cifra exacta: el calculo es un techo
        # y el archivo real sale igual o mas pequeño, nunca mayor.
        self.barra_compresion.mostrar_peso(
            medios.formatear_peso(total),
            f"maximo {medios.formatear_peso(estimado)}  ({ahorro:.0f}% menos)",
        )

    # ----------------------------------------------------------- Proceso --

    def _iniciar_procesamiento(self):
        """Valida la cola y lanza el trabajo en segundo plano."""
        archivos = self.vista_cola.rutas
        if not archivos:
            messagebox.showwarning(
                "Cola vacia", "Agrega al menos un archivo antes de limpiar."
            )
            return

        # Las copias conservan el nombre original, asi que escribir en la
        # carpeta de los originales los sobrescribiria.
        if self.carpeta_destino.resolve() in {a.parent.resolve() for a in archivos}:
            messagebox.showerror(
                "Carpeta destino no valida",
                "La carpeta destino es la misma donde estan los originales.\n\n"
                "Como las copias limpias conservan el nombre original, se "
                "sobrescribirian. Elige otra carpeta destino.",
            )
            return

        self.opciones_en_proceso = OpcionesLimpieza(
            comprimir_video=self.barra_compresion.activada
        )
        self._bloquear_controles(True)
        self.progreso.reiniciar()
        self.vista_cola.reiniciar_estados()

        self.coordinador.procesar_lote(
            archivos, self.carpeta_destino, self.opciones_en_proceso
        )

    def _bloquear_controles(self, bloquear: bool):
        """
        Desactiva todo lo que modifique la cola mientras se procesa. Editarla a
        mitad de la corrida dejaria la vista describiendo un trabajo distinto
        del que se esta ejecutando.
        """
        self.barra_acciones.bloquear(bloquear)
        self.barra_seleccion.bloquear(bloquear)
        self.barra_compresion.bloquear(bloquear)
        self.vista_cola.bloquear(bloquear)

        if bloquear:
            self.boton_procesar.configure(state="disabled", text="Procesando...")
        else:
            self.boton_procesar.configure(state="normal", text="Limpiar metadatos")
            self.barra_seleccion.actualizar(
                self.vista_cola.total_marcadas, len(self.vista_cola.filas)
            )

    def _al_avanzar(self, carga):
        """Un archivo mas terminado."""
        resultado, actual, total = carga
        self.vista_cola.actualizar_resultado(resultado)
        self.progreso.avanzar(actual / total)
        self.progreso.informar(
            f"Procesando {actual} de {total}: {resultado.ruta_origen.name}"
        )

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

        self.progreso.informar(f"Listo: {resumen}.")
        messagebox.showinfo(
            "Proceso completado",
            f"{resumen}.\n\nLos archivos limpios conservan su nombre original y "
            f"estan en:\n{self.carpeta_destino}",
        )

    def _finalizar_con_error(self, detalle: str):
        """Restaura la pantalla tras un fallo global del lote."""
        self._bloquear_controles(False)
        self.progreso.informar("El procesamiento se interrumpio.")
        messagebox.showerror("Error", f"No se pudo completar el procesamiento:\n{detalle}")
