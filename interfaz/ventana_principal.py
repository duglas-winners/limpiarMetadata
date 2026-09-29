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
from limpiadores.proveedor import ProveedorLimpiadores
from nucleo import medios, preferencias
from nucleo.procesador import ProcesadorEnLote, ResultadoArchivo
from nucleo.registro import registro
from recursos import comprobar_ffmpeg

from .barras import BarraAcciones, BarraCompresion, BarraSeleccion, PanelProgreso
from .consola import Consola
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

        # Preferencias de la sesion anterior: la carpeta destino y la densidad
        # de vista se recuerdan para no tener que reelegirlas en cada arranque.
        self._preferencias = preferencias.cargar()
        self.carpeta_destino: Path = preferencias.carpeta_destino_valida(self._preferencias)

        self.opciones_en_proceso = OpcionesLimpieza()
        self._completados = 0
        self._total_lote = 0
        self._consola = None

        self._construir_interfaz()
        self._aplicar_preferencias()

        self.coordinador = CoordinadorTrabajo(
            self,
            ProcesadorEnLote(max_hilos=os.cpu_count() or 4),
            {
                "parcial": self._al_avanzar_archivo,
                "avance": self._al_avanzar,
                "fin": self._finalizar_procesamiento,
                "error": self._finalizar_con_error,
            },
        )

        self._comprobar_ffmpeg()

    # ------------------------------------------------------------------ UI --

    def _construir_interfaz(self):
        self.barra_acciones = BarraAcciones(
            self,
            al_agregar=self._agregar_archivos,
            al_elegir_destino=self._elegir_destino,
            al_vaciar=self._vaciar_cola,
            al_cambiar_vista=self._cambiar_vista,
            al_abrir_consola=self._abrir_consola,
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

        self.barra_compresion = BarraCompresion(
            self, al_cambiar=self._al_cambiar_compresion,
            nivel_inicial=self._preferencias.get("nivel_compresion", "Media"),
        )
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

    def _comprobar_ffmpeg(self):
        """
        Verifica al arrancar que FFmpeg no solo esta, sino que ARRANCA.

        Antes solo se comprobaba que el archivo existiera. Cuando el sistema no
        permitia ejecutarlo —lo que ocurria en macOS, porque el binario viajaba
        sin el bit de ejecucion— la aplicacion arrancaba sin avisar de nada y
        despues fallaban todos los videos, uno a uno, con un escueto "No se
        pudo procesar". Ahora el problema se detecta y se explica al principio.
        """
        funciona, detalle = comprobar_ffmpeg()

        if funciona:
            registro.info("FFmpeg disponible", detalle)
            return

        registro.error("FFmpeg no se puede usar", detalle)
        self.progreso.informar(
            "Aviso: FFmpeg no disponible, los videos no se podran procesar."
        )
        self.vista_cola.vaciar(
            aviso="AVISO: no se puede usar FFmpeg, asi que los videos fallaran.\n"
                  "Las imagenes si se pueden procesar.\n\n"
                  "Pulsa «Consola» para ver el detalle tecnico."
        )
        self._refrescar_consola()

    # ------------------------------------------------------------- Consola --

    def _abrir_consola(self):
        """Abre la consola de diagnostico, o la trae al frente si ya lo estaba."""
        if self._consola is not None and self._consola.winfo_exists():
            self._consola.deiconify()
            self._consola.lift()
            self._consola.focus_force()
            return

        self._consola = Consola(self)

    def _refrescar_consola(self):
        """Actualiza el contador de incidencias del boton."""
        self.barra_acciones.marcar_incidencias(registro.total_problemas)

    # --------------------------------------------------------- Acciones UI --

    def _cambiar_vista(self, valor: str):
        modo = "lista" if valor == "Lista" else "detalle"
        self.vista_cola.establecer_modo(modo)
        self._recordar("modo_vista", modo)

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
        """
        Cambia la carpeta destino y la recuerda para las proximas sesiones.

        El dialogo se abre en la carpeta actual, que tras la primera vez es la
        que el usuario eligio: normalmente querra una vecina, no empezar de
        nuevo desde su carpeta personal.
        """
        carpeta = filedialog.askdirectory(
            title="Seleccionar carpeta para guardar resultados",
            initialdir=str(self.carpeta_destino) if self.carpeta_destino.is_dir() else None,
        )
        if not carpeta:
            return

        self.carpeta_destino = Path(carpeta)
        self.etiqueta_destino.configure(text=f"Destino: {self.carpeta_destino}")
        self._recordar("carpeta_destino", str(self.carpeta_destino))

    # ---------------------------------------------------------- Preferencias --

    def _aplicar_preferencias(self):
        """Deja la ventana como quedo en la sesion anterior."""
        modo = self._preferencias.get("modo_vista", "lista")
        if modo == "detalle":
            self.barra_acciones.selector_vista.set("Detalle")
            self.vista_cola.establecer_modo("detalle")

    def _recordar(self, clave: str, valor):
        """
        Guarda una preferencia. Si el disco no deja escribir, la sesion actual
        funciona igual: solo se pierde el recuerdo para la proxima.
        """
        self._preferencias[clave] = valor
        preferencias.guardar(self._preferencias)

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

    def destroy(self):
        """Detiene los bombeos periodicos antes de cerrar.

        Sin esto, Tk intenta ejecutar los `after` ya programados sobre un
        interprete que ya no existe y escupe «invalid command name».
        """
        self.coordinador.detener()
        self.vista_cola.detener()
        super().destroy()

    # ------------------------------------------------------ Peso y compresion --

    def _al_cambiar_compresion(self):
        """La casilla o el nivel cambiaron: recuerda el nivel y refresca."""
        self._recordar("nivel_compresion", self.barra_compresion.nivel)
        self._actualizar_peso()

    def _actualizar_peso(self):
        """
        Refresca la nota y comunica a la lista el ajuste vigente. Cada fila
        calcula su propia estimacion; aqui no se agrega nada.
        """
        nivel = self.barra_compresion.nivel
        descripcion = medios.NIVELES.get(nivel, {}).get("descripcion", "")

        self.barra_compresion.mostrar_nota(self.vista_cola.tiene_videos, descripcion)
        self.vista_cola.establecer_compresion(self.barra_compresion.activada, nivel)

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
            comprimir_video=self.barra_compresion.activada,
            nivel_compresion=self.barra_compresion.nivel,
        )
        self._completados = 0
        self._total_lote = len(archivos)

        self._bloquear_controles(True)
        self.progreso.reiniciar(self._total_lote)
        self.vista_cola.reiniciar_estados()
        self.progreso.informar(
            "Comprimiendo: esto puede tardar varios minutos por video."
            if self.opciones_en_proceso.comprimir_video
            else "Procesando..."
        )

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

    def _al_avanzar_archivo(self, carga):
        """
        Avance dentro del archivo en curso. Mueve la barra individual y tambien
        la general, para que esta progrese de forma continua en vez de saltar
        solo cuando un archivo termina.
        """
        ruta, fraccion = carga
        self.progreso.mostrar_archivo(ruta.name, fraccion)
        self.progreso.mostrar_lote(
            self._completados, self._total_lote,
            self._fraccion_lote(fraccion),
        )

    def _al_avanzar(self, carga):
        """Un archivo mas terminado."""
        resultado, actual, total = carga
        self._completados = actual

        self.vista_cola.actualizar_resultado(resultado)
        self._refrescar_consola()
        self.progreso.mostrar_archivo(resultado.ruta_origen.name, 1.0)
        self.progreso.mostrar_lote(actual, total, self._fraccion_lote(0.0))
        # La linea de estado no repite aqui el archivo ni el recuento: ambos ya
        # estan sobre las barras. Repetirlos ademas los desincroniza, porque
        # este es el archivo que acaba de terminar y la barra ya muestra el
        # siguiente. Conserva el aviso puesto al arrancar la corrida.

    def _fraccion_lote(self, fraccion_actual: float) -> float:
        """
        Avance del lote: los archivos ya terminados mas lo que lleve el actual.

        Solo se suma la fraccion parcial cuando queda algo por procesar; si no,
        un archivo a medias podria empujar la barra por encima del 100%.
        """
        if not self._total_lote:
            return 0.0
        pendientes = self._total_lote - self._completados
        parcial = fraccion_actual if pendientes > 0 else 0.0
        return min((self._completados + parcial) / self._total_lote, 1.0)

    def _finalizar_procesamiento(self, resultados: List[ResultadoArchivo]):
        """Restaura la pantalla y muestra el resumen de la corrida."""
        limpiados = sum(1 for r in resultados if r.codigo == "limpiado")
        omitidos = sum(1 for r in resultados if r.codigo == "omitido")
        errores = sum(1 for r in resultados if r.codigo == "error")

        self._bloquear_controles(False)
        # Cierra ambas barras al 100%: si el ultimo archivo fallo temprano, su
        # avance parcial habria dejado la barra a medias con el lote terminado.
        self.progreso.mostrar_archivo("Completado", 1.0)
        self.progreso.mostrar_lote(len(resultados), len(resultados), 1.0)

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
