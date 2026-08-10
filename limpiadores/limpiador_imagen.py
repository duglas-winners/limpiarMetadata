from pathlib import Path
from typing import Callable, Optional

from PIL import Image

from .base import OPCIONES_POR_DEFECTO, LimpiadorBase, OpcionesLimpieza

# Formatos que no admiten canal alfa: si la imagen lo trae, hay que aplanarla.
FORMATOS_SIN_ALFA = {"JPEG", "BMP"}

# Extension -> formato Pillow, para cuando el archivo no declara su formato.
EXTENSION_A_FORMATO = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
    ".bmp": "BMP",
    ".tif": "TIFF",
    ".tiff": "TIFF",
}


class LimpiadorImagen(LimpiadorBase):
    """
    Elimina datos EXIF, GPS, perfiles de color e historial de edicion
    recreando la imagen exclusivamente a partir de la matriz de pixeles puros.

    Solo depende de Pillow, por lo que siempre esta disponible.
    """

    def esta_disponible(self) -> tuple[bool, str]:
        return True, ""

    def limpiar(
        self,
        ruta_entrada: Path,
        ruta_salida: Path,
        opciones: OpcionesLimpieza = OPCIONES_POR_DEFECTO,
        al_progresar: Optional[Callable[[float], None]] = None,
    ) -> bool:
        # `opciones` solo contiene ajustes de video por ahora; las imagenes se
        # recrean siempre igual, sin recompresion con perdida.
        #
        # No se informa de progreso intermedio: una imagen se procesa en un
        # solo paso, en milisegundos. Repartirlo en fracciones seria inventar
        # un detalle que no existe.
        try:
            with Image.open(ruta_entrada) as imagen:
                formato = imagen.format or EXTENSION_A_FORMATO.get(
                    ruta_entrada.suffix.lower(), ""
                )
                if not formato:
                    print(f"Formato de imagen desconocido: {ruta_entrada.name}")
                    return False

                imagen_limpia = self._copiar_solo_pixeles(imagen, formato)
                imagen_limpia.save(ruta_salida, format=formato)
            return True
        except Exception as error:
            print(f"Error procesando la imagen {ruta_entrada.name}: {error}")
            return False

    @staticmethod
    def _copiar_solo_pixeles(imagen: Image.Image, formato: str) -> Image.Image:
        """
        Devuelve una imagen nueva con los mismos pixeles pero sin ningun
        contenedor de metadatos (info, exif, icc_profile, XMP, etc.).

        Las imagenes en modo paleta ('P') se convierten a RGB/RGBA porque la
        paleta viaja fuera de la matriz de pixeles. Si el formato de destino no
        admite transparencia, se aplana sobre fondo blanco.
        """
        origen = imagen
        if origen.mode in ("P", "PA"):
            origen = origen.convert("RGBA" if "transparency" in origen.info else "RGB")

        if formato in FORMATOS_SIN_ALFA and origen.mode in ("RGBA", "LA"):
            fondo = Image.new("RGB", origen.size, (255, 255, 255))
            fondo.paste(origen, mask=origen.split()[-1])
            return fondo

        # frombytes/tobytes copia la matriz cruda sin arrastrar el diccionario .info
        return Image.frombytes(origen.mode, origen.size, origen.tobytes())
