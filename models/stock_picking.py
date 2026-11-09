from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .rut import rut_es_valido

# Estados de la guía en los que los datos de transporte ya no se cambian (como en Odoo).
ESTADOS_ABIERTOS = (False, "cancelled")

# Niveles de un problema de transporte (ver _l10n_cl_transport_problems).
SIEMPRE, ESTRICTO, AVISO = "siempre", "estricto", "aviso"


class StockPicking(models.Model):
    _inherit = "stock.picking"

    l10n_cl_fleet_vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Vehículo",
        copy=False,
        index="btree_not_null",
        check_company=True,
        help="Vehículo de la Flota que hace el traslado. Completa la patente, el transportista y "
             "el chofer designado.",
    )
    # Campos de l10n_cl_edi_stock_reform: se completan desde la Flota y el método de envío, y se
    # pueden corregir a mano mientras la guía no se haya emitido.
    l10n_cl_edi_transport_id = fields.Many2one(
        string="Patente",
        compute="_compute_l10n_cl_edi_transport_id",
        store=True,
        readonly=False,
        copy=False,
    )
    l10n_cl_edi_driver_id = fields.Many2one(
        string="Chofer",
        compute="_compute_l10n_cl_edi_driver_id",
        store=True,
        readonly=False,
        copy=False,
    )
    l10n_cl_edi_departure_date = fields.Datetime(
        string="Salida",
        copy=False,
        help="Fecha y hora efectivas de inicio del traslado. Si se deja vacía, es la de emisión "
             "de la guía.",
    )
    l10n_cl_edi_arrival_date = fields.Date(
        string="Llegada",
        copy=False,
        help="Fecha de llegada a destino. Si se deja vacía, es el mismo día de la salida.",
    )
    l10n_cl_transport_partner_id = fields.Many2one(
        "res.partner",
        string="Transportista",
        compute="_compute_l10n_cl_transport_partner_id",
        store=True,
        readonly=False,
        copy=False,
        help="Empresa que hace el traslado: la propia empresa con un vehículo de la Flota, o el "
             "courier del método de envío.",
    )
    l10n_cl_transport_vat = fields.Char(
        string="RUT transportista", related="l10n_cl_transport_partner_id.vat", readonly=False
    )
    l10n_cl_driver_vat = fields.Char(
        string="RUT chofer", related="l10n_cl_edi_driver_id.vat", readonly=False
    )
    l10n_cl_trailer_license_plate = fields.Char(
        string="Patente del carro", related="l10n_cl_edi_transport_id.trailer_license_plate"
    )
    l10n_cl_crew_employee_ids = fields.Many2many(
        "hr.employee",
        "stock_picking_l10n_cl_crew_rel",
        "picking_id",
        "employee_id",
        string="Acompañantes",
        compute="_compute_l10n_cl_crew_employee_ids",
        store=True,
        readonly=False,
        copy=False,
        help="Peonetas u otros empleados que van en el vehículo. Se proponen los habituales del "
             "vehículo.",
    )
    l10n_cl_vehicle_weight_capacity = fields.Float(
        string="Capacidad del vehículo",
        related="l10n_cl_fleet_vehicle_id.l10n_cl_weight_capacity",
    )
    l10n_cl_vehicle_load_weight = fields.Float(
        string="Carga asignada",
        compute="_compute_l10n_cl_vehicle_load_weight",
        digits="Stock Weight",
        help="Peso de las entregas listas para despachar que tienen asignado este vehículo.",
    )
    l10n_cl_transport_issues = fields.Html(
        string="Datos de transporte pendientes",
        compute="_compute_l10n_cl_transport_issues",
        sanitize=False,
    )

    # ------------------------------------------------------------------ cálculos

    def _l10n_cl_transport_locked(self):
        """Con la guía ya emitida, los datos de transporte se conservan tal cual."""
        self.ensure_one()
        return self.l10n_cl_dte_status not in ESTADOS_ABIERTOS

    @api.depends("l10n_cl_fleet_vehicle_id")
    def _compute_l10n_cl_edi_transport_id(self):
        for picking in self:
            if picking._l10n_cl_transport_locked() or not picking.l10n_cl_fleet_vehicle_id:
                continue
            transporte = picking.l10n_cl_fleet_vehicle_id._l10n_cl_get_transport()
            if transporte:
                picking.l10n_cl_edi_transport_id = transporte

    @api.depends("l10n_cl_fleet_vehicle_id", "l10n_cl_edi_transport_id")
    def _compute_l10n_cl_edi_driver_id(self):
        for picking in self:
            if picking._l10n_cl_transport_locked():
                continue
            chofer = (
                picking.l10n_cl_fleet_vehicle_id.driver_id
                or picking.l10n_cl_edi_transport_id.operator_id
            )
            if chofer:
                picking.l10n_cl_edi_driver_id = chofer

    @api.depends("l10n_cl_fleet_vehicle_id")
    def _compute_l10n_cl_crew_employee_ids(self):
        for picking in self:
            if picking._l10n_cl_transport_locked():
                continue
            habituales = picking.l10n_cl_fleet_vehicle_id.l10n_cl_crew_employee_ids
            if habituales:
                picking.l10n_cl_crew_employee_ids = habituales

    @api.depends("l10n_cl_fleet_vehicle_id")
    def _compute_l10n_cl_vehicle_load_weight(self):
        vehiculos = self.l10n_cl_fleet_vehicle_id
        cargas = dict(self.env["stock.picking"].sudo()._read_group(
            [("l10n_cl_fleet_vehicle_id", "in", vehiculos.ids), ("state", "=", "assigned")],
            ["l10n_cl_fleet_vehicle_id"], ["weight:sum"],
        )) if vehiculos else {}
        for picking in self:
            picking.l10n_cl_vehicle_load_weight = cargas.get(picking.l10n_cl_fleet_vehicle_id, 0.0)

    @api.depends("l10n_cl_edi_transport_id", "carrier_id")
    def _compute_l10n_cl_transport_partner_id(self):
        for picking in self:
            if picking._l10n_cl_transport_locked():
                continue
            transportista = (
                picking.l10n_cl_edi_transport_id.transport_company_id
                or picking.carrier_id.l10n_cl_transport_partner_id
            )
            if transportista:
                picking.l10n_cl_transport_partner_id = transportista

    def _l10n_cl_needs_transport(self):
        """Entrega chilena hacia afuera que todavía no tiene guía emitida."""
        self.ensure_one()
        return (
            self.country_code == "CL"
            and self.picking_type_code == "outgoing"
            and not self._l10n_cl_transport_locked()
        )

    def _l10n_cl_transport_problems(self):
        """Lo que falta o está mal para emitir la guía con los datos de la Res. 154, como pares
        (frase dirigida a quien llena la entrega, nivel): SIEMPRE bloquea la emisión (la guía
        saldría con datos errados), ESTRICTO bloquea solo si la empresa lo pidió y AVISO nunca."""
        self.ensure_one()
        problemas = []
        destino = self.partner_id
        if destino and not (destino.street or destino.street2):
            problemas.append((
                _("La dirección de entrega de %s no tiene calle.", destino.display_name), ESTRICTO))
        if destino and not self._l10n_cl_get_comuna_recep():
            problemas.append((
                _("La dirección de entrega de %s no tiene comuna.", destino.display_name), ESTRICTO))

        if self.l10n_cl_fleet_vehicle_id and not self.l10n_cl_edi_transport_id:
            problemas.append((_(
                "El vehículo %s no tiene patente en la Flota.",
                self.l10n_cl_fleet_vehicle_id.display_name,
            ), ESTRICTO))
        patente = self.l10n_cl_edi_transport_id.license_plate
        if patente and len(patente) > 8:
            problemas.append((_("La patente %s tiene más de 8 caracteres.", patente), SIEMPRE))

        transportista = self.l10n_cl_transport_partner_id
        propio = bool(transportista) and transportista == self.company_id.partner_id
        chofer = self.l10n_cl_edi_driver_id
        if (self.l10n_cl_fleet_vehicle_id or propio) and not chofer:
            problemas.append((_("Indique el chofer del vehículo."), ESTRICTO))
        if chofer and not chofer.vat:
            problemas.append((_("Ingrese el RUT del chofer %s.", chofer.name), ESTRICTO))
        elif chofer and not rut_es_valido(chofer.vat):
            problemas.append((_(
                "El RUT del chofer %(chofer)s (%(rut)s) no es válido.",
                chofer=chofer.name, rut=chofer.vat,
            ), SIEMPRE))

        if transportista and not transportista.vat:
            problemas.append((
                _("Ingrese el RUT del transportista %s.", transportista.display_name), ESTRICTO))
        elif transportista and not rut_es_valido(transportista.vat):
            problemas.append((_(
                "El RUT del transportista %(nombre)s (%(rut)s) no es válido.",
                nombre=transportista.display_name, rut=transportista.vat,
            ), SIEMPRE))
        if not (self.l10n_cl_edi_transport_id or transportista):
            # La guía sale con «Sin Dato», que la norma admite cuando no se conoce el vehículo
            # (un tercero, el cliente que retira): se avisa, no se bloquea.
            problemas.append((_(
                "No se indicó el vehículo ni el transportista: la guía saldrá con «Sin Dato»."
            ), AVISO))
        return problemas

    def _l10n_cl_transport_blockers(self):
        """Los problemas que impiden emitir la guía, según lo que pidió la empresa."""
        self.ensure_one()
        estricto = self.company_id.l10n_cl_transport_check == "block"
        return [texto for texto, nivel in self._l10n_cl_transport_problems()
                if nivel == SIEMPRE or (nivel == ESTRICTO and estricto)]

    @api.depends(
        "state", "country_code", "picking_type_code", "l10n_cl_dte_status",
        "partner_id.street", "partner_id.street2", "partner_id.city",
        "l10n_cl_fleet_vehicle_id", "l10n_cl_edi_transport_id", "l10n_cl_edi_driver_id",
        "l10n_cl_edi_driver_id.vat", "l10n_cl_transport_partner_id",
        "l10n_cl_transport_partner_id.vat", "carrier_id",
    )
    def _compute_l10n_cl_transport_issues(self):
        for picking in self:
            # El aviso aparece cuando la entrega ya está lista para su guía, o cuando alguien
            # empezó a llenar el transporte: no en cada entrega que nunca llevará guía.
            avisar = picking._l10n_cl_needs_transport() and (
                picking.state == "done"
                or picking.l10n_cl_fleet_vehicle_id
                or picking.l10n_cl_edi_transport_id
                or picking.carrier_id
            )
            problemas = picking._l10n_cl_transport_problems() if avisar else []
            picking.l10n_cl_transport_issues = (
                Markup("<strong>%s</strong><ul class='mb-0'>%s</ul>") % (
                    _("Antes de emitir la guía de despacho:"),
                    Markup("").join(Markup("<li>%s</li>") % escape(texto) for texto, _b in problemas),
                )
                if problemas else False
            )

    # ------------------------------------------------------------------ lotes de entregas

    def _l10n_cl_sync_batch_vehicle(self):
        """El vehículo de la entrega pasa a su lote (lo hacía una automatización de Studio)."""
        for picking in self:
            lote = picking.batch_id
            if lote and picking.l10n_cl_fleet_vehicle_id and lote.vehicle_id != picking.l10n_cl_fleet_vehicle_id:
                lote.sudo().vehicle_id = picking.l10n_cl_fleet_vehicle_id

    @api.model_create_multi
    def create(self, vals_list):
        pickings = super().create(vals_list)
        pickings.filtered("l10n_cl_fleet_vehicle_id")._l10n_cl_sync_batch_vehicle()
        return pickings

    def write(self, vals):
        res = super().write(vals)
        if "l10n_cl_fleet_vehicle_id" in vals or "batch_id" in vals:
            self._l10n_cl_sync_batch_vehicle()
        return res

    # ------------------------------------------------------------------ emisión

    def _l10n_cl_prepare_transport_data(self):
        """Antes de crear la guía: revisa los datos de transporte y completa las fechas."""
        errores = []
        for picking in self.filtered(lambda p: p._l10n_cl_needs_transport()):
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
                "No se puede emitir la guía de despacho: faltan datos de transporte que exige "
                "la Res. Ex. SII N° 154.\n\n%s", "\n\n".join(errores)
            ))

    def create_delivery_guide(self):
        self._l10n_cl_prepare_transport_data()
        return super().create_delivery_guide()
