"""Asistente para pasar a este módulo los datos de transporte que una empresa tenía en campos
personalizados (hechos con Studio o a mano): copia los datos, cambia vistas, filtros y la guía
impresa, archiva las automatizaciones de esos campos y, si se pide, elimina los campos viejos.

No conoce ningún campo de ninguna empresa: propone, por tipo, los campos personalizados que
calzan con cada campo del módulo, y la persona revisa la propuesta antes de migrar."""
import logging
import re

from markupsafe import Markup, escape
from psycopg2.extras import Json

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

_logger = logging.getLogger(__name__)

# Campos del módulo que pueden tomar el lugar de un campo personalizado.
DESTINOS = [
    ("stock.picking", "l10n_cl_fleet_vehicle_id"),
    ("stock.picking", "l10n_cl_crew_employee_ids"),
    ("stock.picking", "l10n_cl_vehicle_weight_capacity"),
    ("stock.picking", "l10n_cl_vehicle_load_weight"),
    ("fleet.vehicle", "l10n_cl_crew_employee_ids"),
    ("fleet.vehicle", "l10n_cl_weight_capacity"),
    ("fleet.vehicle", "l10n_cl_pending_picking_ids"),
]
# En el formulario de la entrega estos se ven en la sección de transporte. Donde una vista
# personalizada los ponía arriba se esconden para las entregas que muestran la sección (no se
# quitan: las personalizaciones de Studio ubican otros cambios por la posición de los campos).
EN_LA_SECCION = {
    "l10n_cl_fleet_vehicle_id", "l10n_cl_crew_employee_ids",
    "l10n_cl_vehicle_weight_capacity", "l10n_cl_vehicle_load_weight",
}
SOLO_FUERA_DE_LA_SECCION = "country_code == 'CL' and (picking_type_code in ('outgoing', 'internal') or l10n_cl_dte_status)"


def _renombrar(texto, renombres):
    for viejo, nuevo in renombres.items():
        texto = re.sub(r"\b%s\b" % re.escape(viejo), nuevo, texto)
    return texto


class TransportFieldMigration(models.TransientModel):
    _name = "l10n_cl.transport.field.migration"
    _description = "Traer datos de campos personalizados al transporte de la guía"

    line_ids = fields.One2many(
        "l10n_cl.transport.field.migration.line", "wizard_id", string="Campos"
    )
    copy_data = fields.Boolean(string="Copiar los datos", default=True)
    update_views = fields.Boolean(
        string="Cambiar vistas y filtros guardados", default=True,
        help="Donde una vista, un filtro guardado o la guía impresa usa el campo personalizado, "
             "pasa a usar el campo del módulo.",
    )
    remove_guide_lines = fields.Boolean(
        string="Quitar estas líneas de la guía impresa", default=True,
        help="Si la guía impresa mostraba estos campos en un bloque propio, se quita: los datos "
             "de transporte ya salen en el bloque de la Res. 154.",
    )
    archive_automations = fields.Boolean(
        string="Archivar las automatizaciones de estos campos", default=True,
        help="Las automatizaciones que se disparan con estos campos o los usan en su código se "
             "archivan: el módulo hace lo mismo (por ejemplo, pasar el vehículo al lote).",
    )
    delete_fields = fields.Boolean(
        string="Eliminar los campos personalizados al terminar",
        help="Solo se eliminan los que ya no usa ninguna vista, filtro ni acción. No se puede "
             "deshacer: conviene hacerlo después de revisar el resultado.",
    )
    state = fields.Selection([("draft", "Por revisar"), ("done", "Terminado")], default="draft")
    result = fields.Html(string="Resultado", readonly=True, sanitize=False)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "line_ids" in fields_list:
            res["line_ids"] = [(0, 0, vals) for vals in self._propuestas()]
        return res

    @api.model
    def _candidatos(self, modelo, destino):
        campo = self.env[modelo]._fields[destino]
        dominio = [("model", "=", modelo), ("state", "=", "manual"), ("ttype", "=", campo.type)]
        if campo.relational:
            dominio.append(("relation", "=", campo.comodel_name))
        candidatos = self.env["ir.model.fields"].search(dominio)
        if campo.type == "float":
            # Un decimal se propone solo si se reconoce de dónde sale.
            if destino.endswith("weight_capacity"):
                candidatos = candidatos.filtered(lambda f: (f.related or "").endswith("weight_capacity"))
            else:
                candidatos = candidatos.filtered(lambda f: f.compute and "weight" in f.compute)
        return candidatos

    @api.model
    def _propuestas(self):
        lineas = []
        for modelo, destino in DESTINOS:
            campo = self.env[modelo]._fields[destino]
            candidatos = self._candidatos(modelo, destino)
            lineas.append({
                "model": modelo,
                "target_field": destino,
                "target_type": campo.type,
                "target_relation": campo.comodel_name if campo.relational else False,
                "source_field_id": candidatos.id if len(candidatos) == 1 else False,
            })
        return lineas

    # ------------------------------------------------------------------ migración

    def _renombres(self, lineas):
        renombres = {}
        for linea in lineas:
            renombres.setdefault(linea.model, {})[linea.source_field_id.name] = linea.target_field
        return renombres

    def _copiar_datos(self, lineas):
        informe = []
        cr = self.env.cr
        for linea in lineas:
            origen = linea.source_field_id
            if origen.related or origen.compute or not origen.store:
                continue  # sin datos propios: basta con cambiar las vistas
            tabla = self.env[linea.model]._table
            destino = self.env[linea.model]._fields[linea.target_field]
            if linea.target_field == "l10n_cl_pending_picking_ids":
                # Entregas enlazadas a mano a un vehículo: toman ese vehículo si no tienen uno y
                # están enlazadas a uno solo.
                cr.execute(SQL(
                    """UPDATE stock_picking p SET l10n_cl_fleet_vehicle_id = r.vehiculo
                         FROM (SELECT %(col_p)s AS picking, MIN(%(col_v)s) AS vehiculo FROM %(rel)s
                                GROUP BY %(col_p)s HAVING COUNT(*) = 1) r
                        WHERE p.id = r.picking AND p.l10n_cl_fleet_vehicle_id IS NULL""",
                    rel=SQL.identifier(origen.relation_table),
                    col_v=SQL.identifier(origen.column1),
                    col_p=SQL.identifier(origen.column2),
                ))
            elif destino.type == "many2one":
                cr.execute(SQL(
                    "UPDATE %(t)s SET %(d)s = %(o)s WHERE %(o)s IS NOT NULL AND %(d)s IS NULL",
                    t=SQL.identifier(tabla), d=SQL.identifier(destino.name), o=SQL.identifier(origen.name),
                ))
            elif destino.type == "many2many":
                cr.execute(SQL(
                    """INSERT INTO %(rel_d)s (%(c1_d)s, %(c2_d)s)
                       SELECT %(c1_o)s, %(c2_o)s FROM %(rel_o)s ON CONFLICT DO NOTHING""",
                    rel_d=SQL.identifier(destino.relation), c1_d=SQL.identifier(destino.column1),
                    c2_d=SQL.identifier(destino.column2), rel_o=SQL.identifier(origen.relation_table),
                    c1_o=SQL.identifier(origen.column1), c2_o=SQL.identifier(origen.column2),
                ))
            else:
                continue
            informe.append(_("%(origen)s → %(destino)s: %(n)s registros.",
                             origen=origen.field_description, destino=destino.string, n=cr.rowcount))
        self.env.invalidate_all()

        # Las operaciones abiertas que recibieron vehículo toman su patente y, si están vacíos,
        # el chofer y los acompañantes habituales. Si entre los acompañantes hay un solo chofer de
        # la empresa, ese es el chofer. Las ya despachadas no se tocan: su guía se emitió sin
        # esos datos.
        abiertas = self.env["stock.picking"].search([
            ("state", "not in", ("done", "cancel")),
            ("l10n_cl_dte_status", "in", (False, "cancelled")),
            "|", ("l10n_cl_fleet_vehicle_id", "!=", False), ("l10n_cl_crew_employee_ids", "!=", False),
        ])
        abiertas._l10n_cl_fill_from_vehicle()
        for picking in abiertas.filtered(lambda p: not p.l10n_cl_driver_employee_id):
            choferes = picking.l10n_cl_crew_employee_ids.filtered("l10n_cl_is_driver")
            if len(choferes) == 1:
                picking.write({
                    "l10n_cl_driver_employee_id": choferes.id,
                    "l10n_cl_crew_employee_ids": [(3, choferes.id)],
                })
        self.env.flush_all()
        if abiertas:
            informe.append(_("Patente y chofer completados en %s operaciones abiertas.", len(abiertas)))
        return informe

    def _reescribir_arch(self, vistas, transformar):
        """Aplica `transformar` al arch de cada vista, en todos los idiomas guardados."""
        cambiadas = self.env["ir.ui.view"]
        self.env.cr.execute("SELECT id, arch_db FROM ir_ui_view WHERE id = ANY(%s)", [vistas.ids])
        for vista_id, arch in self.env.cr.fetchall():
            nuevo = {idioma: transformar(texto) for idioma, texto in (arch or {}).items()}
            if nuevo != arch:
                self.env.cr.execute(
                    "UPDATE ir_ui_view SET arch_db = %s WHERE id = %s", [Json(nuevo), vista_id])
                cambiadas |= vistas.browse(vista_id)
        self.env.invalidate_all()
        self.env.registry.clear_cache("templates")
        return cambiadas

    def _cambiar_vistas(self, lineas):
        informe = []
        View = self.env["ir.ui.view"].with_context(active_test=False)
        for modelo, renombres in self._renombres(lineas).items():
            esconder = [o for o, d in renombres.items() if modelo == "stock.picking" and d in EN_LA_SECCION]
            vistas = View.search([("model", "=", modelo), ("type", "!=", "qweb")]).filtered(
                lambda v: any(re.search(r"\b%s\b" % re.escape(o), v.arch_db or "") for o in renombres))

            def transformar(texto, renombres=renombres, esconder=esconder):
                for origen in esconder:
                    texto = re.sub(
                        r'<field name="%s"((?:(?!invisible=)[^>])*?)(/?)>' % re.escape(origen),
                        r'<field name="%s"\1 invisible="%s"\2>' % (origen, SOLO_FUERA_DE_LA_SECCION),
                        texto)
                return _renombrar(texto, renombres)

            cambiadas = self._reescribir_arch(vistas.filtered(lambda v: v.type == "form"), transformar)
            cambiadas |= self._reescribir_arch(
                vistas.filtered(lambda v: v.type != "form"), lambda t, r=renombres: _renombrar(t, r))
            informe += [_("Vista cambiada: %s.", v.name) for v in cambiadas]

        # Plantillas de la guía impresa que usan los campos en `o.<campo>`.
        renombres = self._renombres(lineas).get("stock.picking", {})
        if renombres:
            plantillas = View.search([("type", "=", "qweb")]).filtered(
                lambda v: any("o.%s" % o in (v.arch_db or "") for o in renombres))

            def guia(texto):
                if self.remove_guide_lines:
                    for origen in renombres:
                        texto = re.sub(
                            r"\s*<t t-if=\"o\.%s\">.*?</t>" % re.escape(origen), "", texto, flags=re.S)
                return _renombrar(texto, renombres)

            informe += [_("Guía impresa cambiada: %s.", v.name)
                        for v in self._reescribir_arch(plantillas, guia)]
        return informe

    def _cambiar_filtros(self, lineas):
        informe = []
        for modelo, renombres in self._renombres(lineas).items():
            filtros = self.env["ir.filters"].with_context(active_test=False).search([("model_id", "=", modelo)])
            for filtro in filtros:
                vals = {}
                for campo in ("domain", "context", "sort"):
                    valor = filtro[campo] or ""
                    nuevo = _renombrar(valor, renombres)
                    if nuevo != valor:
                        vals[campo] = nuevo
                if vals:
                    filtro.write(vals)
                    informe.append(_("Filtro guardado cambiado: %s.", filtro.name))
        return informe

    def _automatizaciones(self, lineas):
        if "base.automation" not in self.env:
            return self.env["ir.actions.server"].browse()
        nombres = lineas.source_field_id.mapped("name")
        automatizaciones = self.env["base.automation"].search([
            ("model_id.model", "in", list(set(lineas.mapped("model")))),
        ])
        return automatizaciones.filtered(lambda a: (
            a.trigger_field_ids & lineas.source_field_id
            or any(n in (accion.code or "") for accion in a.action_server_ids for n in nombres)
        ))

    def _referencias(self, campo):
        """Lo que todavía nombra a un campo personalizado: vistas, filtros, acciones."""
        patron = re.compile(r"\b%s\b" % re.escape(campo.name))
        View = self.env["ir.ui.view"].with_context(active_test=False)
        quedan = [_("vista %s", v.name) for v in View.search([("arch_db", "ilike", campo.name)])
                  if patron.search(v.arch_db or "")]
        quedan += [_("filtro %s", f.name) for f in self.env["ir.filters"].with_context(active_test=False).search(
            ["|", "|", ("domain", "ilike", campo.name), ("context", "ilike", campo.name), ("sort", "ilike", campo.name)])]
        def archivada(accion):
            automatizacion = accion["base_automation_id"] if "base_automation_id" in accion._fields else None
            return bool(automatizacion) and not automatizacion.active

        quedan += [_("acción %s", a.name) for a in self.env["ir.actions.server"].with_context(active_test=False).search(
            [("code", "ilike", campo.name)]) if not archivada(a)]
        quedan += [_("campo %s", f.field_description) for f in self.env["ir.model.fields"].search([
            ("state", "=", "manual"), ("id", "!=", campo.id),
            "|", ("related", "ilike", campo.name), ("depends", "ilike", campo.name)])]
        return quedan

    def _eliminar_campos(self, lineas):
        informe = []
        # Primero los que dependen de otros (relacionados y calculados), después los que guardan datos.
        orden = lineas.source_field_id.sorted(lambda f: 0 if (f.related or f.compute) else 1)
        for campo in orden:
            quedan = self._referencias(campo)
            if quedan:
                informe.append(_("No se eliminó %(campo)s: todavía lo usa %(quien)s.",
                                 campo=campo.field_description, quien=", ".join(quedan)))
                continue
            nombre = campo.field_description
            try:
                # unlink normal: Odoo mismo se niega si una vista u otro campo todavía lo usa.
                with self.env.cr.savepoint():
                    campo.unlink()
            except UserError as error:
                informe.append(_("No se eliminó %(campo)s: %(motivo)s",
                                 campo=nombre, motivo=str(error)))
                continue
            informe.append(_("Campo eliminado: %s.", nombre))
        return informe

    def _verificar(self, lineas):
        """Cada vista de los modelos tocados se tiene que seguir armando."""
        for modelo in set(lineas.mapped("model")):
            for tipo in ("form", "list", "kanban", "calendar", "map", "search"):
                if self.env["ir.ui.view"].search_count([("model", "=", modelo), ("type", "=", tipo)]):
                    self.env[modelo].get_view(view_type=tipo)

    def action_migrar(self):
        self.ensure_one()
        lineas = self.line_ids.filtered("source_field_id")
        if not lineas:
            raise UserError(_("Elija al menos un campo personalizado para traer."))
        for linea in lineas:
            linea._check_compatible()
        informe = []
        if self.copy_data:
            informe += self._copiar_datos(lineas)
        if self.update_views:
            informe += self._cambiar_vistas(lineas)
            informe += self._cambiar_filtros(lineas)
        if self.archive_automations:
            automatizaciones = self._automatizaciones(lineas)
            automatizaciones.active = False
            informe += [_("Automatización archivada: %s.", a.name) for a in automatizaciones]
        self._verificar(lineas)
        if self.delete_fields:
            informe += self._eliminar_campos(lineas)
        _logger.info("Migración de campos de transporte: %s", informe)
        self.write({
            "state": "done",
            "result": Markup("<ul>%s</ul>") % Markup("").join(
                Markup("<li>%s</li>") % escape(texto) for texto in informe or [_("No había nada que cambiar.")]),
        })
        return {
            "type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id,
            "view_mode": "form", "target": "new", "name": _("Migración terminada"),
        }


class TransportFieldMigrationLine(models.TransientModel):
    _name = "l10n_cl.transport.field.migration.line"
    _description = "Campo personalizado a traer al transporte de la guía"

    wizard_id = fields.Many2one("l10n_cl.transport.field.migration", required=True, ondelete="cascade")
    model = fields.Char(required=True)
    target_field = fields.Char(required=True)
    target_type = fields.Char()
    target_relation = fields.Char()
    model_label = fields.Char(string="En", compute="_compute_labels")
    target_label = fields.Char(string="Campo del módulo", compute="_compute_labels")
    source_field_id = fields.Many2one(
        "ir.model.fields",
        string="Campo personalizado",
        domain="[('model', '=', model), ('state', '=', 'manual'), ('ttype', '=', target_type),"
               " ('relation', '=', target_relation)]",
        ondelete="cascade",
    )

    @api.depends("model", "target_field")
    def _compute_labels(self):
        for linea in self:
            linea.model_label = self.env["ir.model"]._get(linea.model).name
            linea.target_label = self.env[linea.model]._fields[linea.target_field].string

    def _check_compatible(self):
        self.ensure_one()
        origen = self.source_field_id
        if origen.model != self.model or origen.ttype != self.target_type or (
                (origen.relation or False) != (self.target_relation or False)):
            raise UserError(_(
                "%(origen)s no es del mismo tipo que %(destino)s.",
                origen=origen.field_description, destino=self.target_label))
