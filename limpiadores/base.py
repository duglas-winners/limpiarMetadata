from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


@dataclass(frozen=True)
class OpcionesLimpieza:
    """
    Ajustes que el usuario elige en la interfaz y que afectan a como se procesa
    cada archivo. Se pasan a todos los limpiadores; cada uno atiende los que le
    conciernen e ignora el resto.
    """

    comprimir_video: bool = False


OPCIONES_POR_DEFECTO = OpcionesLimpieza()


class LimpiadorBase(ABC):
    """
    Contrato base para cualquier algoritmo que elimine metadatos de un archivo.
    """

    @abstractmethod
    def limpiar(
        self,
        ruta_entrada: Path,
        ruta_salida: Path,
        opciones: OpcionesLimpieza = OPCIONES_POR_DEFECTO,
        al_progresar: Optional[Callable[[float], None]] = None,
    ) -> bool:
        """
        Lee el archivo de entrada, procesa el contenido sin metadatos
        y lo guarda en la ruta de salida.

        `al_progresar` recibe la fraccion completada, de 0 a 1, tantas veces
        como el limpiador pueda informar. Es opcional: un limpiador que trabaja
        en un solo paso puede no llamarlo nunca, y el procesador dara el archivo
        por completo al terminar.
        """

    @abstractmethod
    def esta_disponible(self) -> tuple[bool, str]:
        """
        Indica si las dependencias externas del limpiador estan presentes.
        Devuelve (disponible, motivo_si_no_lo_esta).
        """
