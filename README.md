# Guía de Despacho: Transporte (Res. 154)

Módulo de Odoo 18 que completa el de Odoo **Chile - E-Invoicing Delivery Guide (Res. 154)**
(`l10n_cl_edi_stock_reform`, Enterprise). Lo instala como dependencia y no reemplaza su código:
Odoo sigue armando y enviando el XML al SII; este módulo hace que los datos de transporte se
llenen rápido, en español, desde la Flota, y se revisen antes de emitir.

Desarrollado por **Simplefy by Simpledigital** — https://simpledigital.cl

## Qué agrega

| Dónde | Qué |
|---|---|
| Entrega | Sección «Transporte para la guía de despacho» bajo el encabezado: Vehículo (Flota), carga asignada y capacidad, Patente, Transportista y su RUT, Chofer y su RUT, Acompañantes, Salida y Llegada. Odoo dejaba salida y llegada en el encabezado y transporte y chofer en la última pestaña. |
| Entrega | Al elegir el vehículo se completan patente, transportista (la propia empresa), chofer designado y acompañantes habituales. Con un courier, el transportista sale del método de envío. |
| Entrega | Aviso en pantalla de lo que falta, y bloqueo al emitir si el RUT del chofer o del transportista no es válido, si un vehículo propio no tiene chofer o si la dirección de destino no tiene calle o comuna. Sin vehículo ni transportista solo se avisa: la guía sale con «Sin Dato», como permite la norma. |
| Entrega | Salida y llegada vacías se completan al emitir (hora de Chile). Una copia o una entrega pendiente no arrastra los datos de transporte. |
| Lote de entregas | El vehículo de una entrega pasa a su lote, y el del lote pasa a las entregas que no tengan uno. |
| Flota | Cada vehículo con patente tiene su transporte para la guía, creado y actualizado solo. Botón «Entregas», acompañantes habituales y capacidad de carga. |
| Método de envío | «Transportista para la guía»: el courier y su RUT. |
| Guía impresa | Bloque de transporte en español. |
| XML | El RUT del transportista sale del transportista de la entrega (vehículo propio o courier). |
| Flota › Configuración | «Transportes (guía de despacho)» y el asistente «Traer datos de campos personalizados». |

## Empresas que ya tenían campos propios (Studio)

El asistente **Flota › Configuración › Traer datos de campos personalizados** (solo
administradores) propone, por tipo, qué campo personalizado corresponde a cada campo del
módulo. La persona revisa la propuesta y elige:

1. **Copiar los datos** (vehículo, acompañantes, acompañantes habituales; las entregas enlazadas
   a mano a un vehículo toman ese vehículo si no tienen otro).
2. **Cambiar vistas y filtros guardados**: donde se usaba el campo personalizado se usa el del
   módulo. En el formulario de la entrega, el campo que estaba arriba queda oculto solo para las
   entregas que muestran la sección de transporte, sin moverlo, porque Studio ubica otros cambios
   por la posición de los campos.
3. **Quitar de la guía impresa** los bloques que mostraban esos campos.
4. **Archivar las automatizaciones** que se disparaban con ellos o los usaban en su código.
5. **Eliminar los campos personalizados** (opcional, apagado por defecto). Usa el borrado normal
   de Odoo: no elimina un campo que todavía use una vista, un filtro, una acción u otro campo.

Se puede correr más de una vez: no duplica datos. Lo recomendable es migrar sin eliminar,
revisar, y recién después volver a correrlo con «Eliminar».

Las entregas ya despachadas reciben el vehículo pero no la patente ni el chofer: su guía se
emitió sin esos datos y la guía impresa tiene que seguir coincidiendo con el XML enviado.

## Dependencias

`l10n_cl_edi_stock_reform` (Enterprise), `fleet`, `hr`, `stock_delivery`, `stock_fleet`.

## Pruebas

`tests/test_guia_transporte.py` (19 pruebas). Corren contra el módulo Enterprise real o, en un
Odoo Community, contra réplicas mínimas de `l10n_cl_edi_stock` y `l10n_cl_edi_stock_reform`
armadas con las vistas leídas de un Odoo real (las réplicas no son parte del módulo y nunca van
al addons path de un Odoo con Enterprise).
