"""Alta rápida de un chofer externo o de un transportista desde la guía de despacho: se piden solo
el nombre y el RUT; el módulo ordena los datos y completa el resto del contacto."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.rut import nombre_propio, rut_canonico, rut_con_puntos, rut_es_valido


class TransportContactWizard(models.TransientModel):
    _name = "l10n_cl.transport.contact.wizard"
    _description = "Nuevo chofer externo o transportista"

    picking_id = fields.Many2one("stock.picking", string="Operación", ondelete="cascade")
    contact_type = fields.Selection(
        [("driver", "Chofer externo"), ("carrier", "Transportista")],
        string="Tipo de contacto", required=True, default="driver",
    )
    name = fields.Char(string="Nombre completo", required=True)
    vat = fields.Char(string="RUT", required=True)
    preview_name = fields.Char(string="Se registrará como", compute="_compute_preview")
    preview_vat = fields.Char(string="RUT registrado", compute="_compute_preview")
    existing_partner_id = fields.Many2one(
        "res.partner", string="Contacto existente", compute="_compute_preview",
        help="Ya hay un contacto con este RUT: se utiliza ese y no se crea otro.",
    )

    @api.depends("name", "vat", "contact_type")
    def _compute_preview(self):
        Partner = self.env["res.partner"]
        for wizard in self:
            wizard.preview_name = nombre_propio(wizard.name, empresa=wizard.contact_type == "carrier")
            valido = rut_es_valido(wizard.vat)
            wizard.preview_vat = rut_con_puntos(wizard.vat) if valido else False
            wizard.existing_partner_id = Partner._l10n_cl_find_by_rut(wizard.vat) if valido else False

    def _partner_values(self):
        self.ensure_one()
        empresa = self.contact_type == "carrier"
        vals = {
            "name": self.preview_name,
            "vat": rut_canonico(self.vat),
            "is_company": empresa,
            "company_type": "company" if empresa else "person",
            "country_id": self.env.ref("base.cl").id,
            "function": False if empresa else _("Chofer"),
        }
        Partner = self.env["res.partner"]
        tipo_rut = self.env.ref("l10n_cl.it_RUT", raise_if_not_found=False)
        if tipo_rut and "l10n_latam_identification_type_id" in Partner._fields:
            vals["l10n_latam_identification_type_id"] = tipo_rut.id
        if "l10n_cl_sii_taxpayer_type" in Partner._fields:
            # 1: contribuyente de primera categoría (empresa); 3: persona natural.
            vals["l10n_cl_sii_taxpayer_type"] = "1" if empresa else "3"
        return vals

    def action_confirm(self):
        self.ensure_one()
        if not rut_es_valido(self.vat):
            raise UserError(_(
                "El RUT %s no es válido. Revise el número y el dígito verificador.", self.vat))
        if not self.preview_name:
            raise UserError(_("Ingrese el nombre completo."))
        contacto = self.existing_partner_id
        if contacto:
            if not contacto.active:
                contacto.active = True
        else:
            contacto = self.env["res.partner"].create(self._partner_values())
        contacto._l10n_cl_add_transport_tag(self.contact_type)

        picking = self.picking_id
        if picking and not picking._l10n_cl_transport_locked():
            campo = "l10n_cl_edi_driver_id" if self.contact_type == "driver" else "l10n_cl_transport_partner_id"
            picking.write({"l10n_cl_transport_mode": "external", campo: contacto.id})
        return {"type": "ir.actions.act_window_close"}
