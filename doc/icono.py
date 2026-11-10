"""Íconos de los módulos de guía de despacho, al estilo de las apps de Odoo: planos, fondo transparente, la
paleta de Odoo y las zonas que se superponen en un tono más oscuro (como Simplefy Print).

- Transporte (Res. 154): un camión y, por delante, la guía de despacho.
- Carga del vehículo: el mismo camión con las cajas de la carga.

Uso, desde la raíz del repo (hace falta Pillow):

    python doc/icono.py
"""
import io
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

U = 20                      # grilla de 50 unidades, dibujada a 1000 px y reducida
S = 50 * U
MORADO, MORADO_OSC, MORADO_CLARO = (152, 81, 132), (104, 52, 92), (214, 178, 205)
VERDE, VERDE_OSC = (26, 211, 187), (0, 94, 122)
AMARILLO, NARANJA = (251, 185, 69), (214, 128, 52)
RAIZ = Path(__file__).resolve().parent.parent


def p(x, y):
    return (x * U, y * U)


def mascara(dibujar):
    m = Image.new("L", (S, S), 0)
    dibujar(ImageDraw.Draw(m))
    return m


def caja(x0, y0, x1, y1, radio):
    return mascara(lambda d: d.rounded_rectangle((*p(x0, y0), *p(x1, y1)), radius=radio * U, fill=255))


def circulo(cx, cy, r):
    return mascara(lambda d: d.ellipse((*p(cx - r, cy - r), *p(cx + r, cy + r)), fill=255))


def lienzo():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    def pintar(m, color):
        img.paste(Image.new("RGBA", (S, S), color + (255,)), (0, 0), m)

    return img, pintar


def camion(pintar):
    """El camión: furgón morado, cabina clara con su ventana y ruedas. Devuelve la silueta."""
    furgon = caja(2.5, 9, 32, 34.5, 2.6)
    cabina = caja(31, 17, 47.5, 34.5, 3.2)
    pintar(cabina, MORADO_CLARO)
    pintar(furgon, MORADO)
    pintar(caja(35.5, 20.5, 44, 26.5, 1.4), VERDE)                      # ventana
    for cx in (11.5, 39.5):                                            # ruedas con su centro vacío
        pintar(ImageChops.subtract(circulo(cx, 37, 5.6), circulo(cx, 37, 2.2)), VERDE_OSC)
    return ImageChops.lighter(furgon, cabina)


def icono_transporte():
    img, pintar = lienzo()
    silueta = camion(pintar)
    guia = caja(17.5, 18, 34, 46, 2.2)                                 # la guía, por delante
    pintar(guia, AMARILLO)
    pintar(ImageChops.multiply(guia, silueta), NARANJA)
    def lineas(d):
        for y, ancho in ((25.5, 9.5), (30.5, 9.5), (35.5, 6.5)):
            d.rounded_rectangle((*p(21, y), *p(21 + ancho, y + 2.1)), radius=1.0 * U, fill=255)
    pintar(mascara(lineas), VERDE_OSC)
    return img


def icono_carga():
    img, pintar = lienzo()
    silueta = camion(pintar)
    abajo = caja(16, 30, 33.5, 46, 1.8)                                # dos cajas apiladas, por delante
    arriba = caja(17.5, 16, 32, 30.8, 1.8)
    for c in (arriba, abajo):
        pintar(c, AMARILLO)
        pintar(ImageChops.multiply(c, silueta), NARANJA)
    pintar(caja(23.25, 16, 26.25, 46, 0.4), VERDE_OSC)                # la cinta de las dos cajas
    return img


def guardar(imagen, ruta, lado=256):
    salida = io.BytesIO()
    imagen.resize((lado, lado), Image.LANCZOS).save(salida, "PNG", optimize=True)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(salida.getvalue())


if __name__ == "__main__":
    guardar(icono_transporte(), RAIZ / "simplefy_guia_transporte/static/description/icon.png")
    guardar(icono_carga(), RAIZ / "simplefy_guia_transporte_carga/static/description/icon.png")
    print("ok")
