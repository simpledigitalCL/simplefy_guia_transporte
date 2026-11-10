from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .rut import normalizar_patente, rut_canonico, rut_con_puntos, rut_es_valido

# Estados de la guía en los que los datos de transporte todavía se pueden cambiar (como en Odoo).
ESTADOS_ABIERTOS = (False, "cancelled")

# Niveles de un problema de transporte (ver _l10n_cl_transport_problems).
SIEMPRE, ESTRICTO, AVISO = "siempre", "estricto", "aviso"

CAMPOS_PATENTE = ("l10n_cl_license_plate", "l10n_cl_trailer_license_plate")


class StockPicking(models.Model):
    _inherit = "stock.picking"

    l10n_cl_transport_mode = fields.Selection(
        [("own", "Flota propia"), ("external", "Transporte externo")],
        string="Tipo de transporte",
        default="own",
        required=True,
        copy=False,
        help="Flota propia: vehículo de la Flota y chofer empleado de la empresa. Transporte "
             "externo: un transportista o courier, con su propio vehículo y chofer; su patente se "
             "registra solo en este documento y no se agrega a la Flota.",
    )
    l10n_cl_transport_locked = fields.Boolean(compute="_compute_l10n_cl_transport_locked")

    # ---- Vehículo
    l10n_cl_fleet_vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Vehículo",
        copy=False,
        index="btree_not_null",
        help="Vehículo de la Flota que realiza el traslado. Completa la patente y, si están "
             "vacíos, el chofer y los acompañantes habituales.",
    )
    l10n_cl_license_plate = fields.Char(
        string="Patente",
        copy=False,
        help="Patente del vehículo que realiza el traslado. Con flota propia se toma del vehículo.",
    )
    l10n_cl_trailer_license_plate = fields.Char(
        string="Patente del carro", copy=False, help="Patente del carro o semirremolque, si lo hay."
    )
    l10n_cl_vehicle_weight_capacity = fields.Float(
        string="Capacidad del vehículo",
        related="l10n_cl_fleet_vehicle_id.l10n_cl_weight_capacity",
    )
    l10n_cl_vehicle_load_weight = fields.Float(
        string="Carga asignada",
        compute="_compute_l10n_cl_vehicle_load_weight",
        digits="Stock Weight",
        help="Peso de las operaciones listas para despachar que tienen asignado este vehículo.",
    )

    # ---- Transportista
    l10n_cl_transport_partner_id = fields.Many2one(
        "res.partner",
        string="Transportista",
        copy=False,
        help="Empresa externa que realiza el traslado. Su nombre y RUT van en la guía de despacho.",
    )
    l10n_cl_own_transport_partner_id = fields.Many2one(
        "res.partner",
        string="Transportista (flota propia)",
        compute="_compute_l10n_cl_own_transport_partner_id",
        help="Con flota propia, el transportista es la empresa dueña del vehículo.",
    )
    l10n_cl_transport_vat = fields.Char(
        string="RUT transportista",
        compute="_compute_l10n_cl_transport_vat",
        inverse="_inverse_l10n_cl_transport_vat",
    )

    # ---- Chofer y acompañantes
    l10n_cl_driver_employee_id = fields.Many2one(
        "hr.employee",
        string="Chofer",
        copy=False,
        domain="[('l10n_cl_is_driver', '=', True)]",
        help="Empleado que conduce el vehículo. Su RUT es el número de identificación de su ficha.",
    )
    # Campo de l10n_cl_edi_stock_reform: con transporte externo, el chofer es un contacto.
    l10n_cl_edi_driver_id = fields.Many2one(string="Chofer externo", copy=False)
    l10n_cl_driver_vat = fields.Char(
        string="RUT chofer",
        compute="_compute_l10n_cl_driver_vat",
        inverse="_inverse_l10n_cl_driver_vat",
    )
    l10n_cl_crew_employee_ids = fields.Many2many(
        "hr.employee",
        "stock_picking_l10n_cl_crew_rel",
        "picking_id",
        "employee_id",
        string="Acompañantes",
        copy=False,
        help="Peonetas u otros empleados que van en el vehículo.",
    )

    # ---- Fechas (campos de l10n_cl_edi_stock_reform)
    l10n_cl_edi_departure_date = fields.Datetime(
        string="Salida",
        copy=False,
        help="Fecha y hora efectivas de inicio del traslado. Si se deja vacía, se registra la de "
             "emisión de la guía.",
    )
    l10n_cl_edi_arrival_date = fields.Date(
        string="Llegada",
        copy=False,
        help="Fecha de llegada a destino. Si se deja vacía, se registra el día de la salida.",
    )

    l10n_cl_transport_issues = fields.Html(
        string="Datos de transporte pendientes",
        compute="_compute_l10n_cl_transport_issues",
        sanitize=False,
    )

    # ------------------------------------------------------------------ lo que va en la guía

    def _l10n_cl_transport_locked(self):
        """Con la guía ya emitida, los datos de transporte se conservan tal cual."""
        self.ensure_one()
        return self.l10n_cl_dte_status not in ESTADOS_ABIERTOS

    def _l10n_cl_is_own_fleet(self):
        self.ensure_one()
        return self.l10n_cl_transport_mode != "external"

    def _l10n_cl_transportista(self):
        """La empresa que realiza el traslado: la dueña del vehículo con flota propia, o el
        transportista indicado con transporte externo."""
        self.ensure_one()
        if self._l10n_cl_is_own_fleet():
            return (self.l10n_cl_fleet_vehicle_id.company_id or self.company_id).partner_id
        return self.l10n_cl_transport_partner_id

    def _l10n_cl_chofer(self):
        """Nombre y RUT del chofer: el empleado con flota propia, el contacto con transporte
        externo."""
        self.ensure_one()
        if self._l10n_cl_is_own_fleet():
            empleado = self.l10n_cl_driver_employee_id.sudo()
            return {"name": empleado.name or "", "vat": empleado.identification_id or ""}
        contacto = self.l10n_cl_edi_driver_id
        return {"name": contacto.name or "", "vat": contacto.vat or ""}

    def _l10n_cl_rut_impreso(self, rut):
        """RUT con puntos para la guía impresa."""
        return rut_con_puntos(rut) if rut else ""

    @api.model
    def _l10n_cl_rut_en_pantalla(self, rut):
        """RUT con puntos si es válido; si no, tal como está escrito, para que se vea el error."""
        if not rut:
            return False
        return rut_con_puntos(rut) if rut_es_valido(rut) else rut

    # ------------------------------------------------------------------ cálculos

    @api.depends("l10n_cl_dte_status")
    def _compute_l10n_cl_transport_locked(self):
        for picking in self:
            picking.l10n_cl_transport_locked = picking._l10n_cl_transport_locked()

    @api.depends("l10n_cl_fleet_vehicle_id", "company_id")
    def _compute_l10n_cl_own_transport_partner_id(self):
        for picking in self:
            picking.l10n_cl_own_transport_partner_id = (
                picking.l10n_cl_fleet_vehicle_id.company_id or picking.company_id).partner_id

    @api.depends("l10n_cl_transport_mode", "l10n_cl_fleet_vehicle_id", "company_id",
                 "l10n_cl_transport_partner_id.vat")
    def _compute_l10n_cl_transport_vat(self):
        for picking in self:
            picking.l10n_cl_transport_vat = picking._l10n_cl_rut_en_pantalla(picking._l10n_cl_transportista().vat)

    @api.model
    def _l10n_cl_set_partner_vat(self, contacto, valor):
        """Guarda en el contacto el RUT escrito en la operación, solo si cambió.

        La pantalla muestra el RUT con puntos y el formulario lo vuelve a enviar al guardar
        aunque nadie lo haya tocado: compararlo en su forma canónica evita escribir en el
        contacto sin necesidad (el contacto de un usuario de Odoo solo lo puede modificar quien
        administra usuarios)."""
        nuevo = (rut_canonico(valor) if rut_es_valido(valor) else valor) or False
        actual = contacto.vat or False
        if (rut_canonico(actual) or actual) == (rut_canonico(nuevo) or nuevo):
            return
        if contacto.user_ids:
            raise UserError(_(
                "%s es un usuario de Odoo: su RUT se modifica en su ficha de contacto, con permiso "
                "de administración de usuarios.", contacto.display_name))
        contacto.vat = nuevo

    def _inverse_l10n_cl_transport_vat(self):
        for picking in self:
            transportista = picking.l10n_cl_transport_partner_id
            if picking._l10n_cl_is_own_fleet() or not transportista:
                continue
            self._l10n_cl_set_partner_vat(transportista, picking.l10n_cl_transport_vat)

    @api.depends("l10n_cl_transport_mode", "l10n_cl_driver_employee_id", "l10n_cl_edi_driver_id.vat")
    def _compute_l10n_cl_driver_vat(self):
        for picking in self:
            picking.l10n_cl_driver_vat = picking._l10n_cl_rut_en_pantalla(picking._l10n_cl_chofer()["vat"])

    def _inverse_l10n_cl_driver_vat(self):
        for picking in self:
            chofer = picking.l10n_cl_edi_driver_id
            if picking._l10n_cl_is_own_fleet() or not chofer:
                continue  # el RUT de un empleado se cambia en su ficha
            self._l10n_cl_set_partner_vat(chofer, picking.l10n_cl_driver_vat)

    @api.depends("l10n_cl_fleet_vehicle_id")
    def _compute_l10n_cl_vehicle_load_weight(self):
        vehiculos = self.l10n_cl_fleet_vehicle_id
        cargas = dict(self.env["stock.picking"].sudo()._read_group(
            [("l10n_cl_fleet_vehicle_id", "in", vehiculos.ids), ("state", "=", "assigned")],
            ["l10n_cl_fleet_vehicle_id"], ["weight:sum"],
        )) if vehiculos else {}
        for picking in self:
            picking.l10n_cl_vehicle_load_weight = cargas.get(picking.l10n_cl_fleet_vehicle_id, 0.0)

    # ------------------------------------------------------------------ completar sin borrar

    def _l10n_cl_fill_from_vehicle(self):
        """El vehículo elegido completa su patente y, solo si están vacíos, el chofer y los
        acompañantes. Nunca borra lo que ya se escribió."""
        for picking in self:
            vehiculo = picking.l10n_cl_fleet_vehicle_id
            if not vehiculo or picking._l10n_cl_transport_locked():
                continue
            vals = {}
            if picking.l10n_cl_transport_mode != "own":
                vals["l10n_cl_transport_mode"] = "own"
            patente = normalizar_patente(vehiculo.license_plate)
            if patente and patente != picking.l10n_cl_license_plate:
                vals["l10n_cl_license_plate"] = patente
            if not picking.l10n_cl_driver_employee_id and vehiculo.l10n_cl_driver_employee_id:
                vals["l10n_cl_driver_employee_id"] = vehiculo.l10n_cl_driver_employee_id.id
            if not picking.l10n_cl_crew_employee_ids and vehiculo.l10n_cl_crew_employee_ids:
                vals["l10n_cl_crew_employee_ids"] = [(6, 0, vehiculo.l10n_cl_crew_employee_ids.ids)]
            if vals:
                picking.update(vals)

    def _l10n_cl_fill_from_carrier(self):
        """Un método de envío con transportista externo deja la operación como transporte
        externo y propone ese transportista, si no hay uno."""
        for picking in self:
            transportista = picking.carrier_id.l10n_cl_transport_partner_id
            if (not transportista or picking.l10n_cl_fleet_vehicle_id
                    or picking._l10n_cl_transport_locked()):
                continue
            vals = {}
            if picking.l10n_cl_transport_mode != "external":
                vals["l10n_cl_transport_mode"] = "external"
            if not picking.l10n_cl_transport_partner_id:
                vals["l10n_cl_transport_partner_id"] = transportista.id
            if vals:
                picking.update(vals)

    @api.onchange("l10n_cl_fleet_vehicle_id")
    def _onchange_l10n_cl_fleet_vehicle_id(self):
        self._l10n_cl_fill_from_vehicle()

    @api.onchange("carrier_id")
    def _onchange_l10n_cl_carrier_id(self):
        self._l10n_cl_fill_from_carrier()

    @api.onchange("l10n_cl_transport_mode")
    def _onchange_l10n_cl_transport_mode(self):
        for picking in self:
            if picking.l10n_cl_transport_mode != "external":
                continue
            # El vehículo de la Flota no realiza un traslado externo: se quita, junto con la
            # patente que trajo. Una patente escrita a mano se conserva.
            vehiculo = picking.l10n_cl_fleet_vehicle_id
            if vehiculo:
                if picking.l10n_cl_license_plate == normalizar_patente(vehiculo.license_plate):
                    picking.l10n_cl_license_plate = False
                picking.l10n_cl_fleet_vehicle_id = False
            # Se propone el transportista del método de envío.
            if not picking.l10n_cl_transport_partner_id:
                picking.l10n_cl_transport_partner_id = picking.carrier_id.l10n_cl_transport_partner_id

    @api.onchange(*CAMPOS_PATENTE)
    def _onchange_l10n_cl_license_plate(self):
        for picking in self:
            for campo in CAMPOS_PATENTE:
                if picking[campo]:
                    picking[campo] = normalizar_patente(picking[campo])

    # ------------------------------------------------------------------ revisión

    def _l10n_cl_transport_applies(self):
        """Operación chilena que suele llevar guía de despacho: una entrega o un traslado."""
        self.ensure_one()
        return self.country_code == "CL" and (
            self.picking_type_code in ("outgoing", "internal") or self.l10n_cl_dte_status)

    def _l10n_cl_transport_problems(self):
        """Lo que falta o está mal para emitir la guía con los datos de la Res. 154, como pares
        (frase dirigida a quien completa la operación, nivel): SIEMPRE bloquea la emisión (la
        guía saldría con datos errados), ESTRICTO bloquea solo si la empresa lo pidió y AVISO
        nunca."""
        self.ensure_one()
        problemas = []
        destino = self.partner_id
        if destino and not (destino.commercial_partner_id.vat or destino.vat):
            # Sin RUT del destinatario el SII rechaza la guía.
            problemas.append((_(
                "El destinatario %s no tiene RUT.", destino.commercial_partner_id.display_name), SIEMPRE))
        if destino and not (destino.street or destino.street2):
            problemas.append((
                _("La dirección de destino de %s no tiene calle.", destino.display_name), ESTRICTO))
        if destino and not self._l10n_cl_get_comuna_recep():
            # Sin comuna del destinatario el SII rechaza la guía por error de esquema.
            problemas.append((
                _("La dirección de destino de %s no tiene comuna.", destino.display_name), SIEMPRE))

        propia = self._l10n_cl_is_own_fleet()
        vehiculo = self.l10n_cl_fleet_vehicle_id
        patente = self.l10n_cl_license_plate
        transportista = self._l10n_cl_transportista()
        chofer = self._l10n_cl_chofer()
        hay_chofer = self.l10n_cl_driver_employee_id if propia else self.l10n_cl_edi_driver_id
        en_uso = vehiculo or patente or hay_chofer or (not propia and transportista)

        # Vehículo
        if propia and vehiculo and not patente:
            problemas.append((_(
                "El vehículo %s no tiene patente registrada en la Flota.", vehiculo.display_name,
            ), ESTRICTO))
        elif en_uso and not patente:
            problemas.append((_("Indique la patente del vehículo."), ESTRICTO))
        for valor in (patente, self.l10n_cl_trailer_license_plate):
            if valor and len(valor) > 8:
                problemas.append((_("La patente %s tiene más de 8 caracteres.", valor), SIEMPRE))

        # Transportista
        if not propia and en_uso and not transportista:
            problemas.append((_("Indique el transportista."), ESTRICTO))
        if transportista and en_uso and not transportista.vat:
            problemas.append((
                _("Ingrese el RUT del transportista %s.", transportista.display_name), ESTRICTO))
        elif transportista and transportista.vat and not rut_es_valido(transportista.vat):
            problemas.append((_(
                "El RUT del transportista %(nombre)s (%(rut)s) no es válido.",
                nombre=transportista.display_name, rut=transportista.vat,
            ), SIEMPRE))

        # Chofer
        if propia and (vehiculo or patente) and not hay_chofer:
            problemas.append((_("Indique el chofer."), ESTRICTO))
        elif not propia and en_uso and not hay_chofer:
            problemas.append((_("No se indicó el chofer: la guía se emitirá con «Sin Dato»."), AVISO))
        if hay_chofer and not chofer["vat"]:
            if propia:
                problemas.append((_(
                    "Ingrese el RUT de %s en su ficha de empleado (Nº de identificación).",
                    chofer["name"]), ESTRICTO))
            else:
                problemas.append((_("Ingrese el RUT del chofer %s.", chofer["name"]), ESTRICTO))
        elif hay_chofer and not rut_es_valido(chofer["vat"]):
            problemas.append((_(
                "El RUT del chofer %(chofer)s (%(rut)s) no es válido.",
                chofer=chofer["name"], rut=chofer["vat"],
            ), SIEMPRE))

        if not en_uso:
            # La guía sale con «Sin Dato», que la norma admite cuando no se conoce el vehículo
            # (por ejemplo, si retira el destinatario): se avisa, no se bloquea.
            problemas.append((_(
                "No se indicaron el vehículo ni el chofer: la guía se emitirá con «Sin Dato»."
            ), AVISO))
        return problemas

    def _l10n_cl_transport_blockers(self):
        """Los problemas que impiden emitir la guía, según lo configurado por la empresa."""
        self.ensure_one()
        estricto = self.company_id.l10n_cl_transport_check == "block"
        return [texto for texto, nivel in self._l10n_cl_transport_problems()
                if nivel == SIEMPRE or (nivel == ESTRICTO and estricto)]

    @api.depends(
        "state", "country_code", "picking_type_code", "l10n_cl_dte_status",
        "partner_id.street", "partner_id.street2", "partner_id.city",
        "l10n_cl_transport_mode", "l10n_cl_fleet_vehicle_id", "l10n_cl_license_plate",
        "l10n_cl_trailer_license_plate", "l10n_cl_driver_employee_id", "l10n_cl_edi_driver_id",
        "l10n_cl_edi_driver_id.vat", "l10n_cl_transport_partner_id",
        "l10n_cl_transport_partner_id.vat", "carrier_id",
    )
    def _compute_l10n_cl_transport_issues(self):
        for picking in self:
            # El aviso aparece con la operación validada, que es cuando se emite la guía.
            avisar = (
                picking.state == "done"
                and picking._l10n_cl_transport_applies()
                and not picking._l10n_cl_transport_locked()
            )
            problemas = picking._l10n_cl_transport_problems() if avisar else []
            picking.l10n_cl_transport_issues = (
                Markup("<strong>%s</strong><ul class='mb-0'>%s</ul>") % (
                    _("Antes de emitir la guía de despacho:"),
                    Markup("").join(Markup("<li>%s</li>") % escape(texto) for texto, _b in problemas),
                )
                if problemas else False
            )

    # ------------------------------------------------------------------ alta rápida de contactos

    def _l10n_cl_open_contact_wizard(self, tipo):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Nuevo chofer externo") if tipo == "driver" else _("Nuevo transportista"),
            "res_model": "l10n_cl.transport.contact.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_picking_id": self.id, "default_contact_type": tipo},
        }

    def action_l10n_cl_new_driver(self):
        return self._l10n_cl_open_contact_wizard("driver")

    def action_l10n_cl_new_carrier(self):
        return self._l10n_cl_open_contact_wizard("carrier")

    # ------------------------------------------------------------------ altas y cambios

    @api.model
    def _l10n_cl_normalizar_vals(self, vals):
        for campo in CAMPOS_PATENTE:
            if vals.get(campo):
                vals[campo] = normalizar_patente(vals[campo])
        return vals

    def _l10n_cl_sync_batch_vehicle(self):
        """El vehículo de la operación pasa a su lote."""
        for picking in self:
            lote = picking.batch_id
            if lote and picking.l10n_cl_fleet_vehicle_id and lote.vehicle_id != picking.l10n_cl_fleet_vehicle_id:
                lote.sudo().vehicle_id = picking.l10n_cl_fleet_vehicle_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._l10n_cl_normalizar_vals(vals)
        pickings = super().create(vals_list)
        con_vehiculo = pickings.filtered("l10n_cl_fleet_vehicle_id")
        con_vehiculo._l10n_cl_fill_from_vehicle()
        con_vehiculo._l10n_cl_sync_batch_vehicle()
        (pickings - con_vehiculo).filtered("carrier_id")._l10n_cl_fill_from_carrier()
        return pickings

    def write(self, vals):
        res = super().write(self._l10n_cl_normalizar_vals(dict(vals)))
        if vals.get("l10n_cl_fleet_vehicle_id"):
            self._l10n_cl_fill_from_vehicle()
        if vals.get("carrier_id"):
            self._l10n_cl_fill_from_carrier()
        if "l10n_cl_fleet_vehicle_id" in vals or "batch_id" in vals:
            self._l10n_cl_sync_batch_vehicle()
        return res

    # ------------------------------------------------------------------ descuentos de la venta

    @api.model
    def _l10n_cl_es_descuento(self, move):
        """Una línea de descuento (precio negativo en la venta o en el producto) que llegó a la
        bodega porque el producto de descuento no es un servicio."""
        precio = move.sale_line_id.price_unit if move.sale_line_id else move.product_id.lst_price
        return precio < 0

    def _l10n_cl_dte_moves(self):
        """Los ítems de la guía: el SII no acepta líneas con precio negativo, así que un descuento
        nunca va como ítem; va como descuento global."""
        self.ensure_one()
        return self.move_ids.filtered(lambda m: m.quantity > 0 and not self._l10n_cl_es_descuento(m))

    def _l10n_cl_lineas_descuento_venta(self):
        self.ensure_one()
        if not self.sale_id:
            return self.env["sale.order.line"]
        return self.sale_id.order_line.filtered(lambda l: not l.display_type and l.price_subtotal < 0)

    def _l10n_cl_get_tax_amounts(self):
        totals, retentions, line_amounts = super()._l10n_cl_get_tax_amounts()
        self._l10n_cl_aplicar_descuento_global(totals, line_amounts)
        return totals, retentions, line_amounts

    def _l10n_cl_aplicar_descuento_global(self, totals, line_amounts):
        """Lleva a la guía el descuento de la venta como descuento global (DscRcgGlobal), para que
        sus montos cuadren con la orden de venta. Si la guía despacha solo parte de la venta, el
        descuento se aplica en la misma proporción."""
        self.ensure_one()
        moneda = self.company_id.currency_id

        # 1. Las líneas de descuento que Odoo sumó como ítem salen de los totales.
        for move in [m for m in list(line_amounts) if self._l10n_cl_es_descuento(m)]:
            vals = line_amounts.pop(move)
            if vals.get("exempt"):
                totals["subtotal_amount_exempt"] -= vals["total_amount"]
            else:
                totals["subtotal_amount_taxable"] -= vals["total_amount"]
                totals["vat_amount"] -= vals["value"] - vals["total_amount"]
            totals["total_amount"] -= vals["value"]

        # 2. El descuento de la venta, en proporción a lo que despacha esta guía.
        lineas = self._l10n_cl_lineas_descuento_venta()
        if not lineas or self.partner_id.l10n_cl_delivery_guide_price != "sale_order":
            return
        descuento_venta = -sum(lineas.mapped("price_subtotal"))
        valor_venta = sum(self.sale_id.order_line.filtered(
            lambda l: not l.display_type and l.price_subtotal > 0 and l.product_id.type == "consu"
        ).mapped("price_subtotal"))
        afecto = totals["subtotal_amount_taxable"] > 0
        base = totals["subtotal_amount_taxable"] if afecto else totals["subtotal_amount_exempt"]
        if not valor_venta or base <= 0:
            return
        if moneda.compare_amounts(base, valor_venta) >= 0:
            monto = descuento_venta
        else:
            monto = descuento_venta * base / valor_venta
        monto = moneda.round(min(monto, base))
        if moneda.is_zero(monto):
            return

        if afecto:
            neto = base - monto
            porcentaje = float(totals.get("vat_percent") or 0.0)
            iva = moneda.round(neto * porcentaje / 100.0) if porcentaje else 0.0
            totals["total_amount"] += (neto - base) + (iva - totals["vat_amount"])
            totals["subtotal_amount_taxable"] = neto
            totals["vat_amount"] = iva
        else:
            totals["subtotal_amount_exempt"] -= monto
            totals["total_amount"] -= monto
        totals["l10n_cl_global_discounts"] = [{
            "glosa": ", ".join(dict.fromkeys(lineas.mapped("product_id.name"))) or _("Descuento"),
            "amount": monto,
            "exempt": not afecto,
        }]

    # ------------------------------------------------------------------ emisión

    def _l10n_cl_prepare_transport_data(self):
        """Antes de crear la guía: revisa los datos de transporte y completa las fechas."""
        errores = []
        for picking in self.filtered(
                lambda p: p.country_code == "CL" and not p._l10n_cl_transport_locked()):
            bloqueos = picking._l10n_cl_transport_blockers()
            if bloqueos:
                errores.append("%s\n%s" % (picking.name, "\n".join("• %s" % p for p in bloqueos)))
                continue
            if not picking.l10n_cl_edi_departure_date:
                picking.l10n_cl_edi_departure_date = fields.Datetime.now()
            if not picking.l10n_cl_edi_arrival_date:
                # La misma fecha que va en FchSalida del XML: hora de Chile, no la del usuario.
                picking.l10n_cl_edi_arrival_date = picking._l10n_cl_edi_get_departure_datetime().date()
        if errores:
            raise UserError(_(
                "No es posible emitir la guía de despacho: el SII la rechazaría o faltan datos "
                "exigidos por la Res. Ex. SII N° 154.\n\n%s", "\n\n".join(errores)
            ))

    def create_delivery_guide(self):
        self._l10n_cl_prepare_transport_data()
        return super().create_delivery_guide()
