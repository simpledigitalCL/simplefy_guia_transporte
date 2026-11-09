from odoo import api, fields, models

from .rut import normalizar_patente

# Cambios en la ficha del vehículo que se reflejan en su transporte para la guía.
CAMPOS_SINCRONIZADOS = {"license_plate", "model_id", "driver_id", "active", "company_id"}


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    l10n_cl_transport_ids = fields.One2many(
        "l10n_cl_edi.vehicle", "fleet_vehicle_id", string="Transporte para la guía de despacho"
    )
    l10n_cl_crew_employee_ids = fields.Many2many(
        "hr.employee",
        "fleet_vehicle_l10n_cl_crew_rel",
        "vehicle_id",
        "employee_id",
        string="Acompañantes habituales",
        help="Peonetas u otros empleados que suelen ir en este vehículo. Se proponen en cada "
             "entrega que se haga con él.",
    )
    l10n_cl_weight_capacity = fields.Float(
        string="Capacidad de carga",
        related="category_id.weight_capacity",
        help="Peso máximo de la categoría del vehículo.",
    )
    l10n_cl_picking_ids = fields.One2many(
        "stock.picking", "l10n_cl_fleet_vehicle_id", string="Entregas"
    )
    l10n_cl_pending_picking_ids = fields.Many2many(
        "stock.picking",
        string="Entregas pendientes",
        compute="_compute_l10n_cl_pending_picking_ids",
        help="Entregas por despachar que tienen asignado este vehículo.",
    )
    l10n_cl_picking_count = fields.Integer(
        string="Entregas pendientes", compute="_compute_l10n_cl_pending_picking_ids"
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

    def _l10n_cl_get_transport(self):
        """El transporte para la guía de este vehículo (vacío si no tiene patente)."""
        self.ensure_one()
        return self.env["l10n_cl_edi.vehicle"].search([("fleet_vehicle_id", "=", self.id)], limit=1)

    def _l10n_cl_transport_values(self):
        self.ensure_one()
        vals = {
            "name": self.model_id.display_name or normalizar_patente(self.license_plate),
            "license_plate": normalizar_patente(self.license_plate),
            "company_id": self.company_id.id,
            "active": self.active,
        }
        # El chofer designado en la Flota manda; si no hay, se conserva el que tenga el transporte.
        if self.driver_id:
            vals["operator_id"] = self.driver_id.id
        return vals

    def _l10n_cl_sync_transport(self):
        """Crea o pone al día el transporte para la guía de cada vehículo con patente. El
        transportista de un transporte que ya existe no se toca: puede haberse cambiado a mano."""
        Transporte = self.env["l10n_cl_edi.vehicle"].sudo().with_context(active_test=False)
        for vehiculo in self.sudo():
            if not normalizar_patente(vehiculo.license_plate):
                continue
            vals = vehiculo._l10n_cl_transport_values()
            transporte = Transporte.search([("fleet_vehicle_id", "=", vehiculo.id)], limit=1)
            if transporte:
                transporte.write(vals)
            else:
                empresa = vehiculo.company_id or self.env.company
                Transporte.create(dict(
                    vals,
                    fleet_vehicle_id=vehiculo.id,
                    transport_company_id=empresa.partner_id.id,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        vehiculos = super().create(vals_list)
        vehiculos._l10n_cl_sync_transport()
        return vehiculos

    def write(self, vals):
        res = super().write(vals)
        if CAMPOS_SINCRONIZADOS & set(vals):
            self._l10n_cl_sync_transport()
        return res
