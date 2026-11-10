from odoo import api, models

from .rut import rut_canonico

ETIQUETAS = {
    "driver": "simplefy_guia_transporte.partner_category_external_driver",
    "carrier": "simplefy_guia_transporte.partner_category_carrier",
}


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _l10n_cl_add_transport_tag(self, tipo):
        """Marca los contactos como chofer externo o transportista (`tipo`: driver, carrier)."""
        etiqueta = self.env.ref(ETIQUETAS[tipo], raise_if_not_found=False)
        if etiqueta:
            self.filtered(lambda c: etiqueta not in c.category_id).sudo().write(
                {"category_id": [(4, etiqueta.id)]})

    @api.model
    def _l10n_cl_find_by_rut(self, rut):
        """Contacto con ese RUT, escrito con o sin puntos y con o sin el prefijo «CL»."""
        canonico = rut_canonico(rut)
        if not canonico:
            return self.browse()
        cuerpo, dv = canonico.split("-")
        variantes = {canonico, "%s%s" % (cuerpo, dv), "CL%s%s" % (cuerpo, dv),
                     "%s-%s" % ("{:,}".format(int(cuerpo)).replace(",", "."), dv)}
        variantes |= {v.lower() for v in variantes}
        return self.with_context(active_test=False).search(
            [("vat", "in", list(variantes)), ("parent_id", "=", False)], order="active desc, id", limit=1)
