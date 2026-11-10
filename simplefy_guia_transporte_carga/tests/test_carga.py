from datetime import timedelta

from odoo import fields
from odoo.tests import Form, TransactionCase, tagged

from ..models.stock_picking import dia_chile


@tagged("post_install", "-at_install")
class TestCargaVehiculo(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.empresa = cls.env.company
        chile = cls.env.ref("base.cl")
        cls.empresa.write({"country_id": chile.id, "account_fiscal_country_id": chile.id})
        categoria = cls.env["fleet.vehicle.model.category"].create({"name": "Camión 1 TON (prueba)", "weight_capacity": 1000})
        marca = cls.env["fleet.vehicle.model.brand"].create({"name": "Marca prueba"})
        modelo = cls.env["fleet.vehicle.model"].create({"name": "Modelo prueba", "brand_id": marca.id})
        cls.camion = cls.env["fleet.vehicle"].create({
            "model_id": modelo.id, "license_plate": "PRUE-12", "category_id": categoria.id,
            "company_id": cls.empresa.id})
        cls.saco = cls.env["product.product"].create({"name": "Saco 100 kg (prueba)", "type": "consu", "weight": 100})
        cls.cliente = cls.env["res.partner"].create({
            "name": "Cliente Prueba SpA", "vat": "76543210-3", "street": "Calle 1", "city": "Rancagua"})
        cls.tipo = cls.env["stock.picking.type"].search(
            [("code", "=", "outgoing"), ("company_id", "=", cls.empresa.id)], limit=1)
        cls.hoy = dia_chile(cls.env, fields.Datetime.now())

    def _operacion(self, sacos, dias_salida=0, dias_llegada=None, **vals):
        ahora = fields.Datetime.now()
        entrega = self.env["stock.picking"].create(dict({
            "picking_type_id": self.tipo.id,
            "partner_id": self.cliente.id,
            "location_id": self.tipo.default_location_src_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            "scheduled_date": ahora + timedelta(days=dias_salida),
            "l10n_cl_fleet_vehicle_id": self.camion.id,
            "move_ids": [(0, 0, {
                "product_id": self.saco.id, "product_uom_qty": sacos,
                "location_id": self.tipo.default_location_src_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id})],
        }, **vals))
        entrega.action_confirm()
        if dias_llegada is not None:
            entrega.l10n_cl_edi_arrival_date = self.hoy + timedelta(days=dias_llegada)
        return entrega

    def _validar(self, entrega):
        for move in entrega.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        entrega.button_validate()
        self.assertEqual(entrega.state, "done")

    def test_carga_del_dia_y_sobrecarga(self):
        a = self._operacion(6)
        self.assertEqual(a.l10n_cl_load_date, self.hoy)
        self.assertEqual(a.l10n_cl_day_load_weight, 600)
        self.assertEqual(a.l10n_cl_day_load_status, "loading")
        b = self._operacion(5)
        self.assertEqual(b.l10n_cl_day_load_weight, 1100)
        self.assertEqual(b.l10n_cl_day_load_status, "overload")
        self.assertIn("Sobrecarga", b.l10n_cl_day_load_message)
        self.assertIn("1.100", b.l10n_cl_day_load_message)
        self.assertEqual(self.camion.l10n_cl_today_load_weight, 1100)
        self.assertEqual(self.camion.l10n_cl_today_load_status, "overload")

    def test_la_llegada_libera_el_espacio(self):
        # Salió ayer y llegó ayer: hoy ya no ocupa el vehículo.
        ayer = self._operacion(8, dias_salida=-1, dias_llegada=-1)
        # Salió ayer y llega mañana: hoy sigue ocupando el vehículo.
        en_ruta = self._operacion(3, dias_salida=-1, dias_llegada=1)
        hoy = self._operacion(2)
        self.assertEqual(ayer.l10n_cl_load_until, self.hoy - timedelta(days=1))
        self.assertEqual(hoy.l10n_cl_day_load_weight, 500, "200 de hoy + 300 en ruta")
        self.assertEqual(hoy.l10n_cl_day_load_count, 2)
        self.assertEqual(ayer.l10n_cl_day_load_weight, 1100, "ayer: 800 + 300")

    def test_carga_lista_y_entregada(self):
        a = self._operacion(2)
        b = self._operacion(3)
        self._validar(a)
        self.assertEqual(b.l10n_cl_day_load_status, "loading", "falta validar b")
        self._validar(b)
        self.assertEqual(a.l10n_cl_day_load_status, "ready")
        self.assertIn("Carga lista", a.l10n_cl_day_load_message)
        anterior = self._operacion(4, dias_salida=-2, dias_llegada=-1)
        self._validar(anterior)
        anterior.l10n_cl_edi_departure_date = fields.Datetime.now() - timedelta(days=2)
        self.assertEqual(anterior.l10n_cl_day_load_status, "delivered")
        self.assertIn("Carga entregada", anterior.l10n_cl_day_load_message)

    def test_transporte_externo_no_carga_el_vehiculo(self):
        externa = self._operacion(9)
        externa.l10n_cl_transport_mode = "external"
        propia = self._operacion(1)
        self.assertFalse(externa.l10n_cl_day_load_status)
        self.assertEqual(propia.l10n_cl_day_load_weight, 100)

    def test_mismo_vehiculo_antes_y_despues_de_validar(self):
        otro = self.env["fleet.vehicle"].create({
            "model_id": self.camion.model_id.id, "license_plate": "OTRO-34", "company_id": self.empresa.id})
        entrega = self._operacion(1)
        with Form(entrega) as form:
            form.l10n_cl_fleet_vehicle_id = otro
        self.assertEqual(entrega.l10n_cl_fleet_vehicle_id, otro)
        self.assertEqual(entrega.l10n_cl_license_plate, "OTRO34", "la guía toma el vehículo elegido al preparar")
        self._validar(entrega)
        self.assertEqual(entrega.l10n_cl_fleet_vehicle_id, otro)

    def test_bloque_visible_antes_de_validar(self):
        arch = self.env["stock.picking"].get_view(view_type="form")["arch"]
        self.assertIn('name="l10n_cl_carga"', arch)
