from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    l10n_cl_transport_partner_id = fields.Many2one(
        "res.partner",
        string="Transportista para la guía",
        help="Empresa que hace el traslado con este método de envío (un courier, por ejemplo). "
             "Su nombre y RUT van en la guía de despacho. Vacío si el traslado lo hace la "
             "propia empresa con un vehículo de la Flota.",
    )
