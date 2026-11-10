from odoo import fields, models

from .stock_picking import ESTADOS_CARGA, dia_chile


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    l10n_cl_today_load_weight = fields.Float(
        string="Carga de hoy", compute="_compute_l10n_cl_today_load", digits="Stock Weight",
        help="Peso de las operaciones que ocupan el vehículo hoy (desde su salida hasta su llegada).",
    )
    l10n_cl_today_load_count = fields.Integer(
        string="Operaciones de hoy", compute="_compute_l10n_cl_today_load"
    )
    l10n_cl_today_load_status = fields.Selection(
        ESTADOS_CARGA, string="Estado de la carga de hoy", compute="_compute_l10n_cl_today_load",
    )
    l10n_cl_today_load_message = fields.Char(
        string="Aviso de la carga de hoy", compute="_compute_l10n_cl_today_load"
    )

    def _compute_l10n_cl_today_load(self):
        Picking = self.env["stock.picking"]
        hoy = dia_chile(self.env, fields.Datetime.now())
        cargas = Picking._l10n_cl_vehicle_loads(self.filtered("id"), hoy, hoy)
        for vehiculo in self:
            resumen = Picking._l10n_cl_load_summary(vehiculo, hoy, cargas, hoy)
            vehiculo.l10n_cl_today_load_weight = resumen["weight"]
            vehiculo.l10n_cl_today_load_count = resumen["count"]
            vehiculo.l10n_cl_today_load_status = resumen["status"] if resumen["count"] else False
            vehiculo.l10n_cl_today_load_message = (
                Picking._l10n_cl_load_message(resumen, hoy) if resumen["count"] else False)

    def _l10n_cl_action_loads(self, dia):
        self.ensure_one()
        accion = self.env["ir.actions.act_window"]._for_xml_id("stock.action_picking_tree_all")
        accion.update({
            "domain": [
                ("l10n_cl_fleet_vehicle_id", "=", self.id),
                ("l10n_cl_transport_mode", "=", "own"),
                ("state", "not in", ("draft", "cancel")),
                ("l10n_cl_load_date", "<=", dia),
                ("l10n_cl_load_until", ">=", dia),
            ],
            "context": {"default_l10n_cl_fleet_vehicle_id": self.id},
            "display_name": "%s · %s" % (self.display_name, dia.strftime("%d-%m-%Y")),
        })
        return accion

    def action_l10n_cl_view_today_loads(self):
        return self._l10n_cl_action_loads(dia_chile(self.env, fields.Datetime.now()))
