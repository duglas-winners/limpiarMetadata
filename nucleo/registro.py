"""
Registro de diagnostico: lo que la consola de la aplicacion muestra.

Existe porque los limpiadores escriben sus errores tecnicos por stdout, y en
una aplicacion sin consola —que es como se distribuye— nadie los ve nunca. El
usuario solo recibia "No se pudo procesar", sin forma de saber por que.

Guarda en memoria las ultimas entradas, con dos niveles de detalle: un mensaje
claro para el usuario y el volcado tecnico completo para diagnosticar.
"""

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import List, Optional

MAXIMO_ENTRADAS = 500


@dataclass(frozen=True)
class Entrada:
    """Una linea del registro."""

    momento: float
    nivel: str          # "info", "aviso", "error"
    titulo: str         # lo que se lee de un vistazo
    detalle: str = ""   # volcado tecnico, puede ocupar varias lineas
    archivo: str = ""   # nombre del archivo implicado, si lo hay

    @property
    def hora(self) -> str:
        return time.strftime("%H:%M:%S", time.localtime(self.momento))

    def como_texto(self) -> str:
        cabecera = f"[{self.hora}] {self.nivel.upper():6s} "
        if self.archivo:
            cabecera += f"{self.archivo}: "
        lineas = [cabecera + self.titulo]
        if self.detalle:
            lineas += [f"           {l}" for l in self.detalle.strip().splitlines()]
        return "\n".join(lineas)


class Registro:
    """
    Buffer circular de entradas, seguro entre hilos.

    Se limita a `MAXIMO_ENTRADAS` porque un lote de miles de archivos con
    volcados de FFmpeg podria crecer sin fin; interesan las ultimas, que son
    las que el usuario esta mirando.
    """

    def __init__(self, maximo: int = MAXIMO_ENTRADAS):
        self._entradas: List[Entrada] = []
        self._maximo = maximo
        self._candado = Lock()
        self._version = 0  # sube con cada cambio; la consola lo usa para saber si repintar

    def anotar(self, nivel: str, titulo: str, detalle: str = "", archivo: str = "") -> None:
        with self._candado:
            self._entradas.append(Entrada(time.time(), nivel, titulo, detalle, archivo))
            if len(self._entradas) > self._maximo:
                del self._entradas[: len(self._entradas) - self._maximo]
            self._version += 1

    def info(self, titulo: str, detalle: str = "", archivo: str = "") -> None:
        self.anotar("info", titulo, detalle, archivo)

    def aviso(self, titulo: str, detalle: str = "", archivo: str = "") -> None:
        self.anotar("aviso", titulo, detalle, archivo)

    def error(self, titulo: str, detalle: str = "", archivo: str = "") -> None:
        self.anotar("error", titulo, detalle, archivo)

    def entradas(self, solo_problemas: bool = False) -> List[Entrada]:
        with self._candado:
            copia = list(self._entradas)
        if solo_problemas:
            return [e for e in copia if e.nivel in ("aviso", "error")]
        return copia

    def vaciar(self) -> None:
        with self._candado:
            self._entradas.clear()
            self._version += 1

    @property
    def version(self) -> int:
        with self._candado:
            return self._version

    @property
    def total_problemas(self) -> int:
        with self._candado:
            return sum(1 for e in self._entradas if e.nivel in ("aviso", "error"))

    def como_texto(self, solo_problemas: bool = False) -> str:
        entradas = self.entradas(solo_problemas)
        if not entradas:
            return ""
        return "\n".join(e.como_texto() for e in entradas)


# Registro unico de la aplicacion. Se importa directamente donde haga falta en
# vez de pasarlo por parametro a cada capa: es infraestructura, como un log.
registro = Registro()
