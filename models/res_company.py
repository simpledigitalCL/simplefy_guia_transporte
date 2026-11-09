from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_cl_transport_check = fields.Selection(
        [("warn", "Solo avisar"), ("block", "Bloquear la emisión")],
        string="Datos de transporte faltantes",
        default="warn",
        required=True,
        help="Al emitir una guía de despacho a la que le faltan datos de transporte de la "
             "Res. 154 (chofer, su RUT, la calle o comuna de destino): «Solo avisar» la emite y "
             "muestra lo que falta en la entrega; «Bloquear la emisión» no la emite hasta "
             "completarlos. Un RUT con dígito verificador malo o una patente de más de 8 "
             "caracteres siempre bloquean: la guía saldría con datos errados.",
    )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_cl_transport_check = fields.Selection(
        related="company_id.l10n_cl_transport_check", readonly=False
    )
