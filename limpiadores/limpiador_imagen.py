import io
from pathlib import Path
from typing import Callable, Optional

from PIL import Image

from .base import OPCIONES_POR_DEFECTO, LimpiadorBase, OpcionesLimpieza

# Formatos que no admiten canal alfa: si la imagen lo trae, hay que aplanarla.
FORMATOS_SIN_ALFA = {"JPEG", "BMP"}

# Formatos con perdida: en ellos la palanca principal es la calidad.
FORMATOS_CON_PERDIDA = {"JPEG", "WEBP"}

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

# Ajustes de compresion de imagen para cada nivel. Las claves son las mismas
# que las de `nucleo.medios.NIVELES`, que es quien las presenta al usuario.
#
# Igual que en video, se combinan dos palancas:
#
#   - `lado_max`: el lado mayor se reduce hasta este valor (None lo conserva).
#     Nunca se agranda una imagen pequeña.
#   - `calidad`: calidad de codificacion para JPEG y WebP. PNG, TIFF y BMP no
#     tienen calidad: en ellos solo actua la reduccion, y PNG y TIFF se
#     guardan ademas con la compresion sin perdida mas fuerte.
#
# Se definen aqui y no en `nucleo` porque es este limpiador quien los aplica;
# `nucleo` puede importar de `limpiadores`, pero no al reves.
AJUSTES_IMAGEN = {
    "Ligera": {"lado_max": None, "calidad": 85},
    "Media": {"lado_max": 2560, "calidad": 78},
    "Fuerte": {"lado_max": 1920, "calidad": 68},
    "Maxima": {"lado_max": 1280, "calidad": 55},
}

NIVEL_IMAGEN_POR_DEFECTO = "Media"


class LimpiadorImagen(LimpiadorBase):
    """
    Elimina datos EXIF, GPS, perfiles de color e historial de edicion
    recreando la imagen exclusivamente a partir de la matriz de pixeles puros.

    Con `comprimir_imagen` activo, ademas reduce la resolucion y la calidad
    segun el nivel elegido. Si el resultado no es mas pequeño que el original,
    se descarta y se guarda la copia limpia sin comprimir: comprimir nunca debe
    agrandar un archivo.

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
    ) -> tuple[bool, str]:
        # No se informa de progreso intermedio: una imagen se procesa en un
        # solo paso, en milisegundos. Repartirlo en fracciones seria inventar
        # un detalle que no existe.
        try:
            if opciones.comprimir_imagen:
                datos = self.comprimir_en_memoria(ruta_entrada, opciones.nivel_compresion)
                if datos is not None:
                    ruta_salida.write_bytes(datos)
                    return True, ""
                # Comprimir no ahorraba nada: se sigue con la copia limpia.

            with Image.open(ruta_entrada) as imagen:
                formato = self._formato(imagen, ruta_entrada)
                imagen_limpia = self._copiar_solo_pixeles(imagen, formato)
                imagen_limpia.save(ruta_salida, format=formato)
            return True, ""
        except Exception as error:
            return False, f"{type(error).__name__}: {error}"

    # ------------------------------------------------------------ Compresion --

    def comprimir_en_memoria(self, ruta: Path, nivel: str) -> Optional[bytes]:
        """
        Devuelve la imagen limpia y comprimida como bytes, o None si el
        resultado no es mas pequeño que el original.

        Es publica porque la usa tambien la estimacion de peso de la interfaz:
        en imagenes, comprimir en memoria cuesta milisegundos, asi que en vez
        de estimar se calcula el tamaño exacto.
        """
        original = ruta.stat().st_size

        with Image.open(ruta) as imagen:
            formato = self._formato(imagen, ruta)
            limpia = self._copiar_solo_pixeles(imagen, formato)

        ajustes = AJUSTES_IMAGEN.get(nivel, AJUSTES_IMAGEN[NIVEL_IMAGEN_POR_DEFECTO])
        limpia = self._reducir(limpia, ajustes["lado_max"])

        bufer = io.BytesIO()
        limpia.save(bufer, format=formato, **self._parametros_guardado(formato, ajustes))
        datos = bufer.getvalue()

        if original and len(datos) >= original:
            return None
        return datos

    @staticmethod
    def _reducir(imagen: Image.Image, lado_max: Optional[int]) -> Image.Image:
        """Reduce el lado mayor a `lado_max` conservando la proporcion."""
        if lado_max is None:
            return imagen
        ancho, alto = imagen.size
        mayor = max(ancho, alto)
        if mayor <= lado_max:
            return imagen

        escala = lado_max / mayor
        nuevo = (max(1, round(ancho * escala)), max(1, round(alto * escala)))
        # LANCZOS no admite el modo de 1 bit; ahi basta con el vecino cercano.
        filtro = Image.Resampling.NEAREST if imagen.mode == "1" else Image.Resampling.LANCZOS
        return imagen.resize(nuevo, filtro)

    @staticmethod
    def _parametros_guardado(formato: str, ajustes: dict) -> dict:
        """Argumentos de `Image.save` que comprimen en cada formato."""
        if formato == "JPEG":
            return {"quality": ajustes["calidad"], "optimize": True, "progressive": True}
        if formato == "WEBP":
            return {"quality": ajustes["calidad"], "method": 6}
        if formato == "PNG":
            return {"optimize": True, "compress_level": 9}
        if formato == "TIFF":
            return {"compression": "tiff_adobe_deflate"}
        return {}  # BMP no tiene compresion util: solo actua la reduccion

    # --------------------------------------------------------------- Comunes --

    @staticmethod
    def _formato(imagen: Image.Image, ruta: Path) -> str:
        formato = imagen.format or EXTENSION_A_FORMATO.get(ruta.suffix.lower(), "")
        if not formato:
            raise ValueError(
                f"Formato de imagen desconocido para {ruta.name}. "
                f"La extension no corresponde a ningun formato conocido y "
                f"el archivo tampoco declara el suyo."
            )
        return formato

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
