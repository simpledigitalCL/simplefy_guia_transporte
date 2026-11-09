from odoo import api, fields, models

from .rut import normalizar_patente


class L10nClEdiVehicle(models.Model):
    """El transporte de la Res. 154, con nombres en español y ligado a la Flota."""

    _inherit = "l10n_cl_edi.vehicle"
    _description = "Transporte para la guía de despacho"
    _rec_names_search = ["name", "license_plate"]
    _order = "license_plate, id"

    name = fields.Char(string="Descripción")
    license_plate = fields.Char(string="Patente")
    trailer_license_plate = fields.Char(string="Patente del carro")
    transport_company_id = fields.Many2one(
        string="Transportista",
        help="Empresa que hace el traslado. Su nombre y RUT van en la guía de despacho.",
    )
    operator_id = fields.Many2one(
        string="Chofer habitual",
        help="Se propone como chofer al elegir este vehículo en una entrega.",
    )
    company_id = fields.Many2one(string="Empresa")
    fleet_vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Vehículo de la Flota",
        ondelete="set null",
        copy=False,
        index="btree_not_null",
        help="Vehículo de la Flota del que se toman la patente y el chofer designado.",
    )

    _sql_constraints = [
        (
            "l10n_cl_fleet_vehicle_uniq",
            "unique (fleet_vehicle_id)",
            "Un vehículo de la Flota tiene un solo transporte para la guía de despacho.",
        ),
    ]

    @api.depends("name", "license_plate")
    def _compute_display_name(self):
        for transporte in self:
            partes = [transporte.license_plate]
            if transporte.name and transporte.name != transporte.license_plate:
                partes.append(transporte.name)
            transporte.display_name = " · ".join(p for p in partes if p)

    @api.model
    def _l10n_cl_completar_valores(self, vals):
        """Una patente escrita a mano queda en su forma canónica; la descripción, si falta, es la
        patente. Así sirve la creación rápida desde la entrega, que solo manda `name`."""
        if vals.get("license_plate"):
            vals["license_plate"] = normalizar_patente(vals["license_plate"])
        if vals.get("trailer_license_plate"):
            vals["trailer_license_plate"] = normalizar_patente(vals["trailer_license_plate"])
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("license_plate") and vals.get("name"):
                vals["license_plate"] = vals["name"]
            self._l10n_cl_completar_valores(vals)
            if vals.get("license_plate") and (
                not vals.get("name") or normalizar_patente(vals["name"]) == vals["license_plate"]
            ):
                vals["name"] = vals["license_plate"]
            if not vals.get("transport_company_id"):
                empresa = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
                vals["transport_company_id"] = empresa.partner_id.id
        return super().create(vals_list)

    def write(self, vals):
        return super().write(self._l10n_cl_completar_valores(dict(vals)))

    @api.model
    def action_l10n_cl_sync_fleet(self):
        """Botón «Traer desde la Flota» de la lista."""
        self.env["fleet.vehicle"].sudo().with_context(active_test=False).search(
            [("company_id", "in", self.env.companies.ids + [False])]
        )._l10n_cl_sync_transport()
        return {"type": "ir.actions.client", "tag": "soft_reload"}
