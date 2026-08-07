# Instalación — Limpiador de Metadatos

Guía para el usuario final. **No hace falta instalar Python, ni FFmpeg, ni nada más.** Todo viaja dentro de la aplicación.

---

## Windows

1. Descarga **`LimpiadorMetadatos.exe`** (55 MB) desde la sección [Releases](https://github.com/duglas-winners/limpiarMetadata/releases) del repositorio.
2. Haz doble clic. Listo.

No hay instalador ni carpeta que descomprimir: es un único archivo. Puedes dejarlo en el Escritorio, en Descargas o donde prefieras, y moverlo cuando quieras.

El primer arranque tarda unos **2 o 3 segundos** porque la aplicación descomprime su contenido; los siguientes son iguales de rápidos.

### Si Windows muestra un aviso azul

Al abrirlo por primera vez puede aparecer:

> **Windows protegió su PC** — Microsoft Defender SmartScreen impidió el inicio de una aplicación desconocida.

Es normal y no significa que el archivo sea peligroso. SmartScreen avisa de cualquier programa que no esté firmado con un certificado de empresa. Para continuar:

1. Pulsa **Más información**.
2. Pulsa **Ejecutar de todas formas**.

Solo hay que hacerlo la primera vez.

> **Para eliminar el aviso definitivamente** hace falta un certificado de firma de código (Authenticode), que cuesta entre 200 y 400 USD al año y se emite a nombre de la empresa. Es la única forma; no existe un truco técnico que lo evite.

---

## macOS

1. Descarga **`LimpiadorMetadatos.dmg`** desde [Releases](https://github.com/duglas-winners/limpiarMetadata/releases).
2. Haz doble clic en el `.dmg`.
3. Arrastra **Limpiador de Metadatos** sobre la carpeta **Aplicaciones**.
4. Ábrelo desde Aplicaciones.

### La primera vez: cómo abrirlo

macOS bloquea las aplicaciones descargadas que no están firmadas por un desarrollador registrado en Apple. Verás un aviso del tipo *"no se puede abrir porque proviene de un desarrollador no identificado"*.

Para abrirla la primera vez:

1. Haz **clic derecho** sobre la aplicación en la carpeta Aplicaciones.
2. Elige **Abrir** en el menú.
3. En el aviso que aparece, pulsa **Abrir** de nuevo.

A partir de ahí se abre con doble clic normal.

Si macOS Sequoia (15) o posterior no ofrece esa opción: **Ajustes del Sistema → Privacidad y Seguridad**, baja hasta el aviso sobre la aplicación bloqueada y pulsa **Abrir de todos modos**.

> **Para eliminar este paso definitivamente** hace falta una cuenta de Apple Developer (99 USD al año) para firmar y notarizar la aplicación. Igual que en Windows, no hay atajo técnico.

### Nota sobre Mac con chip Apple (M1, M2, M3, M4)

El FFmpeg incluido está compilado para Intel, así que la primera vez que proceses un **vídeo** macOS puede pedirte instalar **Rosetta 2**. Acepta: es un componente de Apple, la instalación es automática y solo ocurre una vez. Las **imágenes** no lo necesitan.

---

## Preguntas frecuentes sobre la instalación

**¿Necesito instalar Python?**
No. La aplicación lleva Python dentro.

**¿Necesito instalar FFmpeg?**
No. Va incrustado. Es la razón de que el archivo pese 55 MB.

**¿Funciona sin conexión a internet?**
Sí, por completo. La aplicación nunca envía nada a ningún sitio; todo el procesamiento ocurre en tu equipo.

**¿Puedo copiarlo a otro ordenador con un USB?**
Sí. En Windows basta con copiar el `.exe`. En Mac, copia la aplicación desde Aplicaciones.

**¿Por qué pesa tanto para lo que hace?**
Los 55 MB son casi todos FFmpeg (98 MB sin comprimir) y el intérprete de Python. Es el precio de que el usuario no tenga que instalar nada.

**¿Mi antivirus lo marca como sospechoso?**
Puede pasar con ejecutables de PyInstaller sin firmar; es un falso positivo conocido de esta tecnología, no algo específico de esta aplicación. Si tu antivirus lo bloquea, añade una excepción o compílalo tú mismo desde el código fuente siguiendo [COMPILACION.md](COMPILACION.md).
