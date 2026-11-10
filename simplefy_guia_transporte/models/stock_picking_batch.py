from odoo import models


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    def write(self, vals):
        res = super().write(vals)
        if vals.get("vehicle_id"):
            # El vehículo elegido en el lote pasa a sus operaciones con flota propia que todavía
            # no tienen uno (las de transporte externo usan el vehículo del transportista).
            for lote in self:
                lote.picking_ids.filtered(
                    lambda p: not p.l10n_cl_fleet_vehicle_id
                    and p.l10n_cl_transport_mode == "own"
                    and not p._l10n_cl_transport_locked()
                ).l10n_cl_fleet_vehicle_id = lote.vehicle_id
        return res
