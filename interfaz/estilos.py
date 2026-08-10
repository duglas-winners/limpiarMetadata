"""
Constantes visuales de la aplicacion, en un solo sitio.

Cada color se declara como par `(claro, oscuro)`: CustomTkinter elige el que
corresponda al tema del sistema. Tener la tabla aqui permite cambiar el aspecto
sin tocar la logica de ninguna vista, y garantiza que dos componentes que
representan lo mismo se vean igual.
"""

LADO_MINIATURA = 56

# Cada cuanto vacia el hilo principal las colas de eventos, en milisegundos
INTERVALO_EVENTOS_MS = 80
INTERVALO_MINIATURAS_MS = 100

COLOR_FILA_NORMAL = ("gray86", "gray20")
COLOR_FILA_MARCADA = ("#cfe0f5", "#1d3550")  # azul tenue: "esto se va a quitar"
COLOR_FONDO_LISTA = ("gray94", "gray14")
COLOR_HUECO_MINIATURA = ("gray84", "gray25")
COLOR_TEXTO_TENUE = ("gray45", "gray60")
COLOR_TEXTO_SECUNDARIO = ("gray35", "gray70")
COLOR_PELIGRO = ("#b3261e", "#8c1d18")
COLOR_PELIGRO_HOVER = ("#8c1d18", "#6d1512")

# Estado -> aspecto de su etiqueta. Se muestran como una etiqueta con fondo
# propio, no como marcas de texto entre corchetes: el color se lee de un
# vistazo y el simbolo funciona aunque el usuario no distinga bien los colores.
ESTADOS = {
    "pendiente": {
        "simbolo": "•",
        "etiqueta": "En cola",
        "texto": ("gray30", "gray75"),
        "fondo": ("gray80", "gray28"),
    },
    "procesando": {
        "simbolo": "◐",
        "etiqueta": "Procesando",
        "texto": ("#0b4f9e", "#7cc4ff"),
        "fondo": ("#cfe4ff", "#16324f"),
    },
    "limpiado": {
        "simbolo": "✓",
        "etiqueta": "Limpiado",
        "texto": ("#0f5323", "#7ee787"),
        "fondo": ("#c7f0d2", "#123d1e"),
    },
    "omitido": {
        "simbolo": "!",
        "etiqueta": "Omitido",
        "texto": ("#7a4b00", "#f0c674"),
        "fondo": ("#ffe6b8", "#43310d"),
    },
    "error": {
        "simbolo": "✕",
        "etiqueta": "Error",
        "texto": ("#8c1d18", "#ffa198"),
        "fondo": ("#ffd6d2", "#4a1512"),
    },
}
