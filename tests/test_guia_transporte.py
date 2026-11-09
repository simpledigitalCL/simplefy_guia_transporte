from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..models.rut import normalizar_patente, rut_es_valido


@tagged("post_install", "-at_install")
class TestGuiaTransporte(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.empresa = cls.env.company
        cls.empresa.partner_id.vat = "76086428-5"
        cls.chofer = cls.env["res.partner"].create({"name": "Juan Chofer", "vat": "11111111-1"})
        marca = cls.env["fleet.vehicle.model.brand"].create({"name": "Chevrolet"})
        cls.modelo = cls.env["fleet.vehicle.model"].create({"name": "NPR 816", "brand_id": marca.id})
        cls.camion = cls.env["fleet.vehicle"].create({
            "model_id": cls.modelo.id,
            "license_plate": "tsrv-15",
            "driver_id": cls.chofer.id,
            "company_id": cls.empresa.id,
        })
        cls.cliente = cls.env["res.partner"].create({
            "name": "Cliente Destino", "street": "Av. Siempre Viva 742", "city": "Rancagua",
        })
        cls.tipo_salida = cls.env["stock.picking.type"].search(
            [("code", "=", "outgoing"), ("company_id", "=", cls.empresa.id)], limit=1)

    def _entrega(self, **vals):
        return self.env["stock.picking"].create(dict({
            "picking_type_id": self.tipo_salida.id,
            "partner_id": self.cliente.id,
            "location_id": self.tipo_salida.default_location_src_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
        }, **vals))

    # ---------------------------------------------------------------- RUT y patente

    def test_rut(self):
        self.assertTrue(rut_es_valido("76.086.428-5"))
        self.assertTrue(rut_es_valido("CL760864285"))
        self.assertTrue(rut_es_valido("11111111-1"))
        self.assertTrue(rut_es_valido("10.000.013-k"))
        self.assertFalse(rut_es_valido("76.086.428-4"))
        self.assertFalse(rut_es_valido("0-0"))
        self.assertFalse(rut_es_valido(False))

    def test_patente(self):
        self.assertEqual(normalizar_patente(" cyzx-40 "), "CYZX40")
        self.assertEqual(normalizar_patente("TX.26 18"), "TX2618")
        self.assertFalse(normalizar_patente(""))

    # ---------------------------------------------------------------- Flota → transporte

    def test_flota_crea_transporte(self):
        transporte = self.camion._l10n_cl_get_transport()
        self.assertEqual(transporte.license_plate, "TSRV15")
        self.assertEqual(transporte.operator_id, self.chofer)
        self.assertEqual(transporte.transport_company_id, self.empresa.partner_id)
        self.assertIn("TSRV15", transporte.display_name)

    def test_flota_actualiza_transporte(self):
        otro = self.env["res.partner"].create({"name": "Pedro Chofer", "vat": "22222222-2"})
        self.camion.write({"license_plate": "TSRV-16", "driver_id": otro.id})
        transporte = self.camion._l10n_cl_get_transport()
        self.assertEqual(transporte.license_plate, "TSRV16")
        self.assertEqual(transporte.operator_id, otro)
        self.camion.active = False
        self.assertFalse(transporte.active)

    def test_vehiculo_sin_patente(self):
        sin_patente = self.env["fleet.vehicle"].create({"model_id": self.modelo.id})
        self.assertFalse(sin_patente._l10n_cl_get_transport())

    def test_creacion_rapida_de_patente(self):
        transporte = self.env["l10n_cl_edi.vehicle"].create({"name": "ab-12-34"})
        self.assertEqual(transporte.license_plate, "AB1234")
        self.assertEqual(transporte.name, "AB1234")
        self.assertEqual(transporte.transport_company_id, self.env.company.partner_id)

    # ---------------------------------------------------------------- la entrega

    def test_entrega_desde_la_flota(self):
        entrega = self._entrega(l10n_cl_fleet_vehicle_id=self.camion.id)
        self.assertEqual(entrega.l10n_cl_edi_transport_id, self.camion._l10n_cl_get_transport())
        self.assertEqual(entrega.l10n_cl_edi_driver_id, self.chofer)
        self.assertEqual(entrega.l10n_cl_transport_partner_id, self.empresa.partner_id)
        bloqueos = [t for t, bloquea in entrega._l10n_cl_transport_problems() if bloquea]
        self.assertFalse(bloqueos, bloqueos)

    def test_courier_del_metodo_de_envio(self):
        courier = self.env["res.partner"].create({"name": "Courier SpA", "vat": "77806647-5"})
        producto = self.env["product.product"].create({"name": "Despacho", "type": "service"})
        metodo = self.env["delivery.carrier"].create({
            "name": "Courier", "product_id": producto.id,
            "l10n_cl_transport_partner_id": courier.id,
        })
        entrega = self._entrega(carrier_id=metodo.id)
        self.assertEqual(entrega.l10n_cl_transport_partner_id, courier)
        self.assertFalse(entrega.l10n_cl_edi_transport_id)
        # Sin patente no se bloquea: la guía sale con «Sin Dato».
        bloqueos = [t for t, bloquea in entrega._l10n_cl_transport_problems() if bloquea]
        self.assertFalse(bloqueos, bloqueos)

    def test_chofer_con_rut_malo_bloquea(self):
        self.chofer.vat = "11111111-2"
        entrega = self._entrega(l10n_cl_fleet_vehicle_id=self.camion.id)
        bloqueos = [t for t, bloquea in entrega._l10n_cl_transport_problems() if bloquea]
        self.assertEqual(len(bloqueos), 1)
        self.assertIn("no es válido", bloqueos[0])

    def test_vehiculo_propio_sin_chofer_bloquea(self):
        camion = self.env["fleet.vehicle"].create({
            "model_id": self.modelo.id, "license_plate": "HLHB31", "company_id": self.empresa.id,
        })
        entrega = self._entrega(l10n_cl_fleet_vehicle_id=camion.id)
        bloqueos = [t for t, bloquea in entrega._l10n_cl_transport_problems() if bloquea]
        self.assertIn("Indique el chofer del vehículo.", bloqueos)

    def test_sin_transporte_solo_avisa(self):
        entrega = self._entrega()
        problemas = entrega._l10n_cl_transport_problems()
        self.assertEqual([b for _t, b in problemas], [False])

    def test_direccion_sin_calle_bloquea(self):
        self.cliente.street = False
        entrega = self._entrega(l10n_cl_fleet_vehicle_id=self.camion.id)
        bloqueos = [t for t, bloquea in entrega._l10n_cl_transport_problems() if bloquea]
        self.assertTrue(any("no tiene calle" in t for t in bloqueos), bloqueos)

    def test_guia_emitida_no_cambia(self):
        entrega = self._entrega(l10n_cl_fleet_vehicle_id=self.camion.id)
        transporte = entrega.l10n_cl_edi_transport_id
        entrega.l10n_cl_dte_status = "accepted"
        otro = self.env["fleet.vehicle"].create({
            "model_id": self.modelo.id, "license_plate": "SRKW74", "company_id": self.empresa.id,
        })
        entrega.l10n_cl_fleet_vehicle_id = otro
        self.assertEqual(entrega.l10n_cl_edi_transport_id, transporte)

    def test_copia_no_arrastra_transporte(self):
        entrega = self._entrega(
            l10n_cl_fleet_vehicle_id=self.camion.id,
            l10n_cl_edi_departure_date="2026-11-09 12:00:00",
        )
        copia = entrega.copy()
        self.assertFalse(copia.l10n_cl_fleet_vehicle_id)
        self.assertFalse(copia.l10n_cl_edi_transport_id)
        self.assertFalse(copia.l10n_cl_edi_departure_date)

    def test_acompanantes_habituales(self):
        peoneta = self.env["hr.employee"].create({"name": "Peoneta Uno"})
        self.camion.l10n_cl_crew_employee_ids = peoneta
        entrega = self._entrega(l10n_cl_fleet_vehicle_id=self.camion.id)
        self.assertEqual(entrega.l10n_cl_crew_employee_ids, peoneta)

    def test_carga_asignada(self):
        categoria = self.env["fleet.vehicle.model.category"].create(
            {"name": "Categoría de prueba de la guía", "weight_capacity": 4900})
        self.camion.category_id = categoria
        producto = self.env["product.product"].create(
            {"name": "Saco 15 kg", "is_storable": True, "weight": 15})
        self.env["stock.quant"]._update_available_quantity(
            producto, self.tipo_salida.default_location_src_id, 100)
        entrega = self._entrega(
            l10n_cl_fleet_vehicle_id=self.camion.id,
            move_ids=[(0, 0, {
                "name": producto.name, "product_id": producto.id, "product_uom_qty": 10,
                "location_id": self.tipo_salida.default_location_src_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            })],
        )
        entrega.action_confirm()
        entrega.action_assign()
        self.assertEqual(entrega.state, "assigned")
        self.assertEqual(entrega.l10n_cl_vehicle_weight_capacity, 4900)
        self.assertAlmostEqual(entrega.l10n_cl_vehicle_load_weight, 150)
        self.assertEqual(self.camion.l10n_cl_picking_count, 1)

    def test_lote_toma_el_vehiculo_y_lo_reparte(self):
        entrega = self._entrega(l10n_cl_fleet_vehicle_id=self.camion.id)
        otra = self._entrega()
        lote = self.env["stock.picking.batch"].create({"picking_ids": [(6, 0, (entrega | otra).ids)]})
        entrega.l10n_cl_fleet_vehicle_id = self.camion
        self.assertEqual(lote.vehicle_id, self.camion)
        self.assertEqual(otra.l10n_cl_fleet_vehicle_id, self.camion)
        self.assertEqual(otra.l10n_cl_edi_driver_id, self.chofer)

    def test_preparar_completa_fechas(self):
        entrega = self._entrega(l10n_cl_fleet_vehicle_id=self.camion.id)
        if entrega.country_code != "CL":
            self.skipTest("La empresa de prueba no es chilena.")
        entrega._l10n_cl_prepare_transport_data()
        self.assertTrue(entrega.l10n_cl_edi_departure_date)
        self.assertEqual(
            entrega.l10n_cl_edi_arrival_date,
            entrega._l10n_cl_edi_get_departure_datetime().date(),
        )

    def test_preparar_bloquea_con_mensaje(self):
        self.chofer.vat = False
        entrega = self._entrega(l10n_cl_fleet_vehicle_id=self.camion.id)
        if entrega.country_code != "CL":
            self.skipTest("La empresa de prueba no es chilena.")
        with self.assertRaisesRegex(UserError, "Ingrese el RUT del chofer"):
            entrega._l10n_cl_prepare_transport_data()
