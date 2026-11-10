from odoo import _, api, fields, models

ZONA = "America/Santiago"

# Estados de la carga de un vehículo en un día.
SOBRECARGA, ENTREGADA, LISTA, CARGANDO = "overload", "delivered", "ready", "loading"
ESTADOS_CARGA = [(CARGANDO, "En carga"), (LISTA, "Carga lista"), (ENTREGADA, "Carga entregada"),
                 (SOBRECARGA, "Sobrecarga")]


def dia_chile(env, momento):
    """Fecha en Chile de un instante guardado en UTC."""
    if not momento:
        return False
    return fields.Datetime.context_timestamp(env["res.users"].with_context(tz=ZONA), momento).date()


def formato_kg(valor):
    return "{:,.0f}".format(valor or 0.0).replace(",", ".")


class StockPicking(models.Model):
    _inherit = "stock.picking"

    l10n_cl_load_date = fields.Date(
        string="Día de carga",
        compute="_compute_l10n_cl_load_dates",
        store=True,
        index=True,
        help="Día en que la operación sale en el vehículo: la fecha de salida de la guía o, si no "
             "la tiene, la fecha programada.",
    )
    l10n_cl_load_until = fields.Date(
        string="Ocupa el vehículo hasta",
        compute="_compute_l10n_cl_load_dates",
        store=True,
        index=True,
        help="Último día en que la carga ocupa el vehículo: la fecha de llegada o, si no la tiene, "
             "el día de salida. Desde el día siguiente el espacio queda disponible.",
    )
    l10n_cl_day_load_weight = fields.Float(
        string="Carga del día",
        compute="_compute_l10n_cl_day_load",
        digits="Stock Weight",
        help="Peso de todas las operaciones del vehículo que lo ocupan el día de carga de esta.",
    )
    l10n_cl_day_load_count = fields.Integer(
        string="Operaciones del día", compute="_compute_l10n_cl_day_load"
    )
    l10n_cl_day_load_status = fields.Selection(
        ESTADOS_CARGA,
        string="Estado de la carga",
        compute="_compute_l10n_cl_day_load",
    )
    l10n_cl_day_load_message = fields.Char(
        string="Aviso de la carga", compute="_compute_l10n_cl_day_load"
    )

    @api.depends("l10n_cl_edi_departure_date", "l10n_cl_edi_arrival_date", "scheduled_date")
    def _compute_l10n_cl_load_dates(self):
        for picking in self:
            salida = (dia_chile(self.env, picking.l10n_cl_edi_departure_date)
                      or dia_chile(self.env, picking.scheduled_date))
            llegada = picking.l10n_cl_edi_arrival_date
            picking.l10n_cl_load_date = salida
            picking.l10n_cl_load_until = max(llegada, salida) if (llegada and salida) else salida

    # ------------------------------------------------------------------ carga del día

    @api.model
    def _l10n_cl_vehicle_loads(self, vehiculos, desde, hasta):
        """Operaciones de esos vehículos que los ocupan algún día entre `desde` y `hasta`."""
        if not vehiculos or not desde:
            return self.browse()
        return self.sudo().search([
            ("l10n_cl_fleet_vehicle_id", "in", vehiculos.ids),
            ("l10n_cl_transport_mode", "=", "own"),
            ("state", "not in", ("draft", "cancel")),
            ("l10n_cl_load_date", "<=", hasta),
            ("l10n_cl_load_until", ">=", desde),
        ])

    @api.model
    def _l10n_cl_load_summary(self, vehiculo, dia, cargas, hoy):
        """Peso, cantidad y estado de la carga de un vehículo en un día."""
        del_dia = cargas.filtered(lambda p: p.l10n_cl_fleet_vehicle_id == vehiculo
                                  and p.l10n_cl_load_date and p.l10n_cl_load_until
                                  and p.l10n_cl_load_date <= dia <= p.l10n_cl_load_until)
        peso = sum(del_dia.mapped("weight"))
        capacidad = vehiculo.l10n_cl_weight_capacity
        if capacidad and peso > capacidad:
            estado = SOBRECARGA
        elif del_dia and all(p.state == "done" and p.l10n_cl_load_until < hoy for p in del_dia):
            estado = ENTREGADA
        elif del_dia and all(p.state == "done" for p in del_dia):
            estado = LISTA
        else:
            estado = CARGANDO
        return {"weight": peso, "count": len(del_dia), "status": estado, "capacity": capacidad}

    @api.model
    def _l10n_cl_load_message(self, resumen, dia):
        fecha = dia.strftime("%d-%m-%Y")
        if resumen["status"] == SOBRECARGA:
            return _("Sobrecarga: el vehículo lleva %(peso)s kg el %(fecha)s y su capacidad es de "
                     "%(cap)s kg.", peso=formato_kg(resumen["weight"]), fecha=fecha,
                     cap=formato_kg(resumen["capacity"]))
        if resumen["status"] == ENTREGADA:
            return _("Carga entregada: las operaciones del %s ya llegaron a destino y el vehículo "
                     "tiene su capacidad disponible.", fecha)
        if resumen["status"] == LISTA:
            return _("Carga lista: las %(n)s operaciones del vehículo para el %(fecha)s están "
                     "validadas.", n=resumen["count"], fecha=fecha)
        return False

    @api.depends("l10n_cl_fleet_vehicle_id", "l10n_cl_transport_mode", "l10n_cl_load_date",
                 "l10n_cl_load_until", "weight", "state")
    def _compute_l10n_cl_day_load(self):
        hoy = dia_chile(self.env, fields.Datetime.now())
        propias = self.filtered(lambda p: p.l10n_cl_fleet_vehicle_id and p.l10n_cl_load_date
                                and p.l10n_cl_transport_mode == "own")
        dias = [d for d in propias.mapped("l10n_cl_load_date") if d]
        cargas = (self._l10n_cl_vehicle_loads(propias.l10n_cl_fleet_vehicle_id, min(dias), max(dias))
                  if dias else self.browse())
        for picking in self:
            if picking not in propias:
                picking.l10n_cl_day_load_weight = 0.0
                picking.l10n_cl_day_load_count = 0
                picking.l10n_cl_day_load_status = False
                picking.l10n_cl_day_load_message = False
                continue
            # La operación en pantalla cuenta con sus datos actuales, aunque no esté guardada.
            otras = cargas.filtered(lambda p: p.id != picking._origin.id)
            if picking.state not in ("draft", "cancel"):
                otras |= picking
            resumen = self._l10n_cl_load_summary(
                picking.l10n_cl_fleet_vehicle_id, picking.l10n_cl_load_date, otras, hoy)
            picking.l10n_cl_day_load_weight = resumen["weight"]
            picking.l10n_cl_day_load_count = resumen["count"]
            picking.l10n_cl_day_load_status = resumen["status"]
            picking.l10n_cl_day_load_message = self._l10n_cl_load_message(
                resumen, picking.l10n_cl_load_date)

    def action_l10n_cl_view_day_loads(self):
        """Las operaciones que ocupan el vehículo el día de carga de esta."""
        self.ensure_one()
        return self.l10n_cl_fleet_vehicle_id._l10n_cl_action_loads(self.l10n_cl_load_date)
