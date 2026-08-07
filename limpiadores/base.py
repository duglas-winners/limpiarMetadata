from abc import ABC, abstractmethod
from pathlib import Path


class LimpiadorBase(ABC):
    """
    Contrato base para cualquier algoritmo que elimine metadatos de un archivo.
    """

    @abstractmethod
    def limpiar(self, ruta_entrada: Path, ruta_salida: Path) -> bool:
        """
        Lee el archivo de entrada, procesa el contenido sin metadatos
        y lo guarda en la ruta de salida.
        """

    @abstractmethod
    def esta_disponible(self) -> tuple[bool, str]:
        """
        Indica si las dependencias externas del limpiador estan presentes.
        Devuelve (disponible, motivo_si_no_lo_esta).
        """
