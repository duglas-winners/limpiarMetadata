"""
Modelo de la cola de archivos: el estado, sin nada de dibujo.

Separarlo de la vista es lo que permite alternar entre lista y detalle, quitar
filas o redibujar sin perder ningun resultado: los widgets se destruyen y
recrean, estos objetos no.
"""

from pathlib import Path
from typing import Iterable, List, Optional

from nucleo import medios
from nucleo.procesador import ResultadoArchivo

from .estilos import ESTADOS


class FilaArchivo:
    """Estado de un unico archivo en la cola."""

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
        return medios.formatear_peso(medios.peso(self.ruta))

    @property
    def es_video(self) -> bool:
        return medios.es_video(self.ruta)


class ColaArchivos:
    """
    Coleccion ordenada de `FilaArchivo`, con las operaciones que la interfaz
    necesita. No conoce widgets: es comprobable sin abrir una ventana.
    """

    def __init__(self):
        self.filas: List[FilaArchivo] = []

    def __len__(self) -> int:
        return len(self.filas)

    def __iter__(self):
        return iter(self.filas)

    def reemplazar(self, rutas: Iterable[Path]) -> None:
        self.filas = [FilaArchivo(r) for r in rutas]

    def agregar(self, rutas: Iterable[Path]) -> int:
        """Añade los que falten, ignorando repetidos. Devuelve cuantos entraron."""
        existentes = {f.ruta for f in self.filas}
        nuevas = [r for r in rutas if r not in existentes]
        self.filas.extend(FilaArchivo(r) for r in nuevas)
        return len(nuevas)

    def vaciar(self) -> None:
        self.filas = []

    def quitar_marcadas(self) -> int:
        """Elimina las filas marcadas. Devuelve cuantas se fueron."""
        antes = len(self.filas)
        self.filas = [f for f in self.filas if not f.marcada]
        return antes - len(self.filas)

    def marcar_todas(self, marcar: bool) -> None:
        for fila in self.filas:
            fila.marcada = marcar

    def reiniciar_estados(self) -> None:
        for fila in self.filas:
            fila.reiniciar()

    def aplicar_resultado(self, resultado: ResultadoArchivo) -> None:
        for fila in self.filas:
            if fila.ruta == resultado.ruta_origen:
                fila.aplicar(resultado)
                return

    # ----------------------------------------------------------- Consultas --

    @property
    def rutas(self) -> List[Path]:
        return [f.ruta for f in self.filas]

    @property
    def total_marcadas(self) -> int:
        return sum(1 for f in self.filas if f.marcada)

    @property
    def peso_total(self) -> int:
        return sum(medios.peso(f.ruta) for f in self.filas)

    @property
    def tiene_videos(self) -> bool:
        return any(f.es_video for f in self.filas)
