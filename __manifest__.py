{
    "name": "Guía de Despacho: Transporte (Res. 154)",
    "version": "18.0.2.1.0",
    "category": "Accounting/Localizations/EDI",
    "summary": "Transporte de la guía de despacho electrónica: flota propia o transporte externo, "
               "chofer, patente y transportista, revisados antes de emitir.",
    "description": """
Guía de Despacho: Transporte (Res. 154)
=======================================

Complemento del módulo de Odoo *Chile - E-Invoicing Delivery Guide (Res. 154)*
(``l10n_cl_edi_stock_reform``), del que depende. La Res. Ex. SII N° 154 exige en la guía de
despacho los datos del traslado: patente, transportista, chofer y fechas de salida y llegada.

- **Flota propia o transporte externo.** Cada operación indica quién realiza el traslado. Con
  flota propia, el vehículo se elige de la Flota y el chofer es un empleado de la empresa (su RUT
  es el número de identificación de su ficha). Con transporte externo, la patente se registra solo
  en la operación, sin agregar vehículos a la Flota, y el chofer y el transportista son contactos.
- **Datos independientes.** Cada dato se completa por separado. El vehículo completa su patente
  y, solo si están vacíos, el chofer y los acompañantes habituales: nunca borra lo ya ingresado.
- **Alta rápida de contactos.** Los botones «Nuevo» registran un chofer externo o un
  transportista con su nombre y RUT. El módulo ordena mayúsculas y minúsculas, da formato al RUT,
  completa el país, el tipo de identificación y el tipo de contribuyente, y asigna las etiquetas
  «Chofer externo» o «Transportista». Si el RUT ya existe, utiliza ese contacto.
- **Entregas y traslados.** La sección de transporte está en las entregas, en los traslados
  internos y en toda operación que emita guía de despacho, y aparece una vez validada la
  operación, que es cuando se emite la guía.
- **Revisión antes de emitir.** Un RUT mal escrito o una patente de más de 8 caracteres siempre
  bloquean la emisión; los datos faltantes la bloquean o solo se informan, según lo configurado
  en Inventario › Ajustes. Las fechas de salida y llegada vacías se completan al emitir.
- **Descuentos que cuadran.** El SII rechaza una guía con líneas de precio negativo. Los
  descuentos de la venta van en la guía como descuento global, con el mismo monto de la orden
  de venta (o en proporción, si se despacha una parte), y los totales cuadran con la venta.
- **Receptor correcto.** La razón social y el RUT del destinatario son los de la empresa, aunque
  la entrega vaya a una dirección de despacho sin nombre.
- **Guía impresa corporativa.** Los datos de transporte en un recuadro compacto, con los títulos
  en el color principal de la empresa y los datos en negro.
- **Lotes de entregas y Flota.** El vehículo de una operación pasa a su lote y viceversa. Cada
  vehículo indica su chofer habitual, sus acompañantes y su capacidad de carga.
- **Desde campos personalizados.** Un asistente en Flota › Configuración traspasa al módulo los
  datos que la empresa registraba en campos propios (Studio).

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
        "sale_stock",
        "stock_delivery",
        "stock_fleet",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/res_partner_category_data.xml",
        "views/l10n_cl_edi_vehicle_views.xml",
        "views/fleet_vehicle_views.xml",
        "views/hr_employee_views.xml",
        "views/stock_picking_views.xml",
        "views/delivery_carrier_views.xml",
        "views/res_config_settings_views.xml",
        "report/guia_despacho_templates.xml",
        "wizards/contacto_transporte_views.xml",
        "wizards/migracion_campos_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
