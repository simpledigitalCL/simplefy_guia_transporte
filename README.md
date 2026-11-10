# Guía de Despacho · Simplefy para Odoo

Módulos de Odoo 19 para la guía de despacho electrónica chilena (Res. Ex. SII N° 154). Desarrollados
por **Simplefy by Simpledigital** — https://simpledigital.cl

| Módulo | Qué hace | Instalación |
|---|---|---|
| [`simplefy_guia_transporte`](simplefy_guia_transporte) | **Guía de Despacho: Transporte (Res. 154).** Flota propia o transporte externo, chofer, patente y transportista; revisión antes de emitir; descuentos como descuento global; guía impresa corporativa. | Principal. Depende de `l10n_cl_edi_stock_reform` (Enterprise). |
| [`simplefy_guia_transporte_carga`](simplefy_guia_transporte_carga) | **Guía de Despacho: Carga del Vehículo.** Vehículo asignado desde la preparación, carga por día (de la salida a la llegada), avisos de sobrecarga, carga lista y carga entregada. | Opcional. Depende del principal. |

Manual de uso: [`simplefy_guia_transporte/doc/manual`](simplefy_guia_transporte/doc/manual).
Íconos: `python doc/icono.py` (Pillow) los genera en `static/description/icon.png` de cada módulo.

Ramas: `main` y `19` (Odoo 19), `18.0` (Odoo 18).

En Odoo.sh el repo entra como submódulo; cada carpeta es un módulo y aparece por separado en Aplicaciones.
