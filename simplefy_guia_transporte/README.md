# Guía de Despacho: Transporte (Res. 154)

Módulo de Odoo 19 que complementa el de Odoo **Chile - E-Invoicing Delivery Guide (Res. 154)**
(`l10n_cl_edi_stock_reform`, Enterprise). Depende de él y no reemplaza su código: Odoo sigue
armando y enviando el XML al SII; este módulo ordena cómo se registran los datos de transporte,
los revisa antes de emitir y presenta la guía impresa.

Desarrollado por **Simplefy by Simpledigital** — https://simpledigital.cl

## Qué agrega

| Dónde | Qué |
|---|---|
| Entregas, traslados internos y toda operación que emita guía | Sección «Transporte» bajo el encabezado, **una vez validada la operación**, con el tipo de transporte: **Flota propia** o **Transporte externo**. Odoo dejaba salida y llegada en el encabezado y transporte y chofer en la última pestaña, y solo en entregas. |
| Flota propia | Vehículo de la Flota (con su carga asignada y capacidad), transportista = la empresa dueña del vehículo, chofer = **empleado** marcado como «Chofer de la empresa» (su RUT es el Nº de identificación de su ficha), acompañantes. |
| Transporte externo | Transportista y chofer son **contactos** con las etiquetas «Transportista» y «Chofer externo». La patente y el carro se escriben en la operación: no se agregan vehículos a la Flota. Botones «Nuevo» para registrar un chofer o un transportista con solo nombre y RUT. |
| Alta rápida | Ordena mayúsculas y minúsculas («JUAN carlos DE la fuente» → «Juan Carlos de la Fuente»; «TRANSPORTES SUR SPA» → «Transportes Sur SpA»), guarda el RUT en el formato de la localización, completa país, tipo de identificación (RUT), tipo de contribuyente y etiqueta. Si el RUT ya existe, usa ese contacto (no duplica). |
| Datos independientes | Cada casilla se completa por separado. Elegir el vehículo completa su patente y, **solo si están vacíos**, el chofer y los acompañantes habituales; no borra lo ya escrito. Pasar a transporte externo quita el vehículo propio y la patente que trajo; lo escrito a mano se conserva. |
| Método de envío | «Transportista para la guía»: con él, las operaciones del método se emiten como transporte externo de esa empresa. |
| Revisión | Aviso en pantalla de lo pendiente. Un RUT con dígito verificador incorrecto o una patente de más de 8 caracteres siempre bloquean la emisión. Lo que falta bloquea solo si la empresa eligió «Bloquear la emisión» en Inventario › Ajustes; por defecto «Informar y emitir». Sin vehículo ni chofer la guía sale con «Sin Dato», como permite la norma. |
| Fechas | Salida y llegada vacías se completan al emitir (hora de Chile). Una copia o una entrega pendiente no arrastra los datos de transporte. |
| Guía impresa | Recuadro «Datos del transporte» de tres filas (transportista, RUT, motivo / vehículo, patente, carro / chofer, RUT chofer, salida y llegada). Títulos en el **color principal de la empresa** (Ajustes › Diseño del documento), datos en negro. |
| XML | Patente, carro, RUT del transportista y chofer salen de la operación (flota propia o externo), no del catálogo de transportes de la Res. 154, que queda solo en modo desarrollador. |
| Flota | Chofer habitual (empleado), acompañantes habituales, capacidad de carga y botón «Por despachar». |
| Empleados | Casilla «Chofer de la empresa» y filtro «Choferes». Al instalar se marcan los empleados con cargo de chofer o conductor. |
| Lote de entregas | El vehículo de una operación pasa a su lote, y el del lote pasa a sus operaciones de flota propia sin vehículo. |
| Flota › Configuración | Asistente «Traer datos de campos personalizados». |

## Empresas que ya tenían campos propios (Studio)

El asistente **Flota › Configuración › Traer datos de campos personalizados** (solo
administradores) propone, por tipo, qué campo personalizado corresponde a cada campo del
módulo. La persona revisa la propuesta y elige:

1. **Copiar los datos** (vehículo, acompañantes, acompañantes habituales; las operaciones
   enlazadas a mano a un vehículo toman ese vehículo si no tienen otro). En las operaciones
   abiertas se completa la patente, y si entre los acompañantes hay un solo chofer de la empresa,
   ese pasa a ser el chofer.
2. **Cambiar vistas y filtros guardados**: donde se usaba el campo personalizado se usa el del
   módulo. En el formulario, el campo que estaba arriba queda oculto solo para las operaciones
   que muestran la sección de transporte, sin moverlo, porque Studio ubica otros cambios por la
   posición de los campos.
3. **Quitar de la guía impresa** los bloques que mostraban esos campos.
4. **Archivar las automatizaciones** que se disparaban con ellos o los usaban en su código.
5. **Eliminar los campos personalizados** (opcional, apagado por defecto). Usa el borrado normal
   de Odoo: no elimina un campo que todavía use una vista, un filtro, una acción u otro campo.

Se puede correr más de una vez: no duplica datos. Lo recomendable es migrar sin eliminar,
revisar, y recién después volver a correrlo con «Eliminar».

## Dependencias

`l10n_cl_edi_stock_reform` (Enterprise), `fleet`, `hr`, `stock_delivery`, `stock_fleet`.

## Pruebas

`tests/test_guia_transporte.py` (21 pruebas). Corren contra el módulo Enterprise real o, en un
Odoo Community, contra réplicas mínimas de `l10n_cl_edi_stock` y `l10n_cl_edi_stock_reform`
armadas con las vistas leídas de un Odoo real (las réplicas no son parte del módulo y nunca van
al addons path de un Odoo con Enterprise).
