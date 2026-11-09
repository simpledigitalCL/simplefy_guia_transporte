{
    "name": "Guía de Despacho: Transporte (Res. 154)",
    "version": "18.0.1.0.0",
    "category": "Accounting/Localizations/EDI",
    "summary": "Vehículo, patente, chofer y transportista de la guía de despacho tomados de la "
               "Flota, en español y revisados antes de emitir.",
    "description": """
Guía de Despacho: Transporte (Res. 154)
=======================================

Complementa el módulo de Odoo *Chile - E-Invoicing Delivery Guide (Res. 154)*
(``l10n_cl_edi_stock_reform``), que exige en la guía de despacho los datos del traslado:
patente, transportista, chofer y fechas de salida y llegada.

- **Desde la Flota.** Cada vehículo de la Flota con patente tiene su transporte para la guía,
  creado y actualizado solo. Al elegir el vehículo en la entrega se completan la patente, el
  transportista (la propia empresa), el chofer designado y los acompañantes habituales del
  vehículo, y se ven su capacidad de carga y lo que ya tiene asignado.
- **Lotes de entregas.** El vehículo de una entrega pasa a su lote, y el vehículo elegido en
  un lote pasa a las entregas del lote que no tengan uno.
- **Couriers.** En el método de envío se indica la empresa que hace el traslado; su nombre y
  RUT pasan a la guía.
- **Todo en un solo lugar.** Los datos de transporte se presentan juntos en la entrega, bajo el
  encabezado, y no en la última pestaña. El RUT del chofer y del transportista se corrigen ahí
  mismo.
- **Revisión antes de emitir.** Al crear la guía se revisan el RUT del chofer y del
  transportista, el chofer de un vehículo propio y la dirección y comuna de destino. Un RUT
  mal escrito siempre bloquea; lo que falta bloquea o solo se avisa, según se elija en los
  ajustes de Inventario. Las fechas de salida y llegada, si están vacías, se completan con la
  fecha y hora de emisión.
- **Guía impresa en español**, con los datos de transporte del documento tributario.
- **Desde campos personalizados.** Si la empresa ya registraba el vehículo, los acompañantes o
  los pesos en campos propios (Studio), un asistente en Flota › Configuración propone a qué campo
  del módulo corresponde cada uno, copia los datos, cambia vistas, filtros y guía impresa, y
  archiva las automatizaciones que los usaban. Eliminar los campos viejos es opcional.

Desarrollado por **Simplefy by Simpledigital**. https://simpledigital.cl
""",
    "author": "Simplefy by Simpledigital",
    "company": "Simpledigital",
    "website": "https://simpledigital.cl",
    "license": "OPL-1",
    "depends": [
        "l10n_cl_edi_stock_reform",
        "fleet",
        "hr",
        "stock_delivery",
        "stock_fleet",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/l10n_cl_edi_vehicle_views.xml",
        "views/fleet_vehicle_views.xml",
        "views/stock_picking_views.xml",
        "views/delivery_carrier_views.xml",
        "views/res_config_settings_views.xml",
        "report/guia_despacho_templates.xml",
        "wizards/migracion_campos_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
