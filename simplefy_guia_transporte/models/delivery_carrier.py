from odoo import api, fields, models


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    l10n_cl_transport_partner_id = fields.Many2one(
        "res.partner",
        string="Transportista para la guía",
        help="Empresa externa que realiza el traslado con este método de envío (un courier, por "
             "ejemplo). Las guías de despacho con este método se emiten como transporte externo, "
             "con el nombre y el RUT de esta empresa. Vacío si el traslado se realiza con la "
             "flota propia.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        metodos = super().create(vals_list)
        metodos.l10n_cl_transport_partner_id._l10n_cl_add_transport_tag("carrier")
        return metodos

    def write(self, vals):
        res = super().write(vals)
        if vals.get("l10n_cl_transport_partner_id"):
            self.l10n_cl_transport_partner_id._l10n_cl_add_transport_tag("carrier")
        return res
