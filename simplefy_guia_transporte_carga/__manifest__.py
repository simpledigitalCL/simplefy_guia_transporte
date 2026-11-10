{
    "name": "Guía de Despacho: Carga del Vehículo",
    "version": "19.0.1.0.0",
    "category": "Inventory/Delivery",
    "summary": "Planificación de la carga de los vehículos de la flota propia: peso por día, "
               "sobrecarga, carga lista y carga entregada.",
    "description": """
Guía de Despacho: Carga del Vehículo
====================================

Complemento opcional de *Guía de Despacho: Transporte (Res. 154)*, del que depende.

- **Vehículo desde la preparación.** En las entregas y traslados con flota propia, el vehículo se
  asigna desde que la operación se prepara. Es el mismo vehículo de la guía de despacho: se elige
  una sola vez, y un cambio en un lugar se ve en el otro.
- **Carga por día.** Cada operación ocupa el vehículo desde su día de salida hasta su día de
  llegada. La carga del día suma el peso de todas las operaciones del vehículo en esas fechas; al
  día siguiente de la llegada, ese espacio queda disponible.
- **Avisos.** Sobrecarga cuando el peso del día supera la capacidad del vehículo; carga lista
  cuando todas las operaciones del día están validadas; carga entregada cuando ya pasó su día de
  llegada.
- **En la Flota.** Cada vehículo muestra su carga de hoy y el acceso a las operaciones del día.

Desarrollado por **Simplefy by Simpledigital**. https://simpledigital.cl
""",
    "author": "Simplefy by Simpledigital",
    "company": "Simpledigital",
    "website": "https://simpledigital.cl",
    "license": "OPL-1",
    "depends": ["simplefy_guia_transporte"],
    "data": [
        "views/stock_picking_views.xml",
        "views/fleet_vehicle_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
