from odoo import fields, models


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    l10n_cl_driver_employee_id = fields.Many2one(
        "hr.employee",
        string="Chofer habitual",
        domain="[('l10n_cl_is_driver', '=', True)]",
        help="Empleado que suele conducir este vehículo. Se propone como chofer en las guías de "
             "despacho que se hagan con él, si todavía no tienen uno.",
    )
    l10n_cl_crew_employee_ids = fields.Many2many(
        "hr.employee",
        "fleet_vehicle_l10n_cl_crew_rel",
        "vehicle_id",
        "employee_id",
        string="Acompañantes habituales",
        help="Peonetas u otros empleados que suelen ir en este vehículo. Se proponen en cada "
             "operación que se haga con él, si todavía no tiene acompañantes.",
    )
    l10n_cl_weight_capacity = fields.Float(
        string="Capacidad de carga",
        related="category_id.weight_capacity",
        help="Peso máximo de la categoría del vehículo.",
    )
    l10n_cl_picking_ids = fields.One2many(
        "stock.picking", "l10n_cl_fleet_vehicle_id", string="Operaciones"
    )
    l10n_cl_pending_picking_ids = fields.Many2many(
        "stock.picking",
        string="Operaciones pendientes",
        compute="_compute_l10n_cl_pending_picking_ids",
        help="Entregas y traslados por despachar que tienen asignado este vehículo.",
    )
    l10n_cl_picking_count = fields.Integer(
        string="Cantidad de operaciones pendientes", compute="_compute_l10n_cl_pending_picking_ids"
    )

    def _compute_l10n_cl_pending_picking_ids(self):
        pendientes = self.env["stock.picking"].search([
            ("l10n_cl_fleet_vehicle_id", "in", self.ids),
            ("state", "not in", ("draft", "done", "cancel")),
        ])
        for vehiculo in self:
            propias = pendientes.filtered(lambda p: p.l10n_cl_fleet_vehicle_id == vehiculo)
            vehiculo.l10n_cl_pending_picking_ids = propias
            vehiculo.l10n_cl_picking_count = len(propias)

    def action_l10n_cl_view_pickings(self):
        self.ensure_one()
        accion = self.env["ir.actions.act_window"]._for_xml_id("stock.action_picking_tree_all")
        accion.update({
            "domain": [("l10n_cl_fleet_vehicle_id", "=", self.id)],
            "context": {"search_default_available": 1, "default_l10n_cl_fleet_vehicle_id": self.id},
            "display_name": self.display_name,
        })
        return accion
