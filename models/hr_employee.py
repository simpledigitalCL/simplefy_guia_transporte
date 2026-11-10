from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    l10n_cl_is_driver = fields.Boolean(
        string="Chofer de la empresa",
        help="Conduce los vehículos de la Flota. Solo estos empleados se ofrecen como chofer en "
             "las guías de despacho; el RUT que va en la guía es su número de identificación.",
    )


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    # Los usuarios sin acceso a Empleados buscan a los choferes por aquí.
    l10n_cl_is_driver = fields.Boolean(readonly=True)
