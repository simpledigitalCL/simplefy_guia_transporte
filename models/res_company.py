from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_cl_transport_check = fields.Selection(
        [("warn", "Informar y emitir"), ("block", "Bloquear la emisión")],
        string="Datos de transporte faltantes",
        default="warn",
        required=True,
        help="Tratamiento de una guía de despacho a la que le faltan datos de transporte de la "
             "Res. Ex. SII N° 154 (patente, chofer, RUT del chofer o del transportista, calle de "
             "destino). «Informar y emitir» la emite y detalla lo pendiente en la operación; "
             "«Bloquear la emisión» no la emite hasta completarlos. Lo que el SII rechaza siempre "
             "bloquea la emisión: un RUT con dígito verificador incorrecto, una patente de más de "
             "8 caracteres, un destinatario sin RUT o sin comuna.",
    )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_cl_transport_check = fields.Selection(
        related="company_id.l10n_cl_transport_check", readonly=False
    )
