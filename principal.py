"""Punto de entrada de la aplicacion Limpiador de Metadatos."""

from interfaz.ventana_principal import VentanaPrincipal


def main() -> None:
    aplicacion = VentanaPrincipal()
    aplicacion.mainloop()


if __name__ == "__main__":
    main()
