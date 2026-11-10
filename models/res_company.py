from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_cl_transport_check = fields.Selection(
        [("warn", "Informar y emitir"), ("block", "Bloquear la emisión")],
        string="Datos de transporte faltantes",
        default="warn",
        required=True,
        help="Tratamiento de una guía de despacho a la que le faltan datos de transporte de la "
             "Res. Ex. SII N° 154 (patente, chofer, RUT, calle o comuna de destino). «Informar y "
             "emitir» la emite y detalla lo pendiente en la operación; «Bloquear la emisión» no "
             "la emite hasta completarlos. Un RUT con dígito verificador incorrecto o una patente "
             "de más de 8 caracteres siempre bloquean la emisión.",
    )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_cl_transport_check = fields.Selection(
        related="company_id.l10n_cl_transport_check", readonly=False
    )
