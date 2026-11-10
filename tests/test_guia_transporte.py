from odoo.exceptions import UserError
from odoo.tests import Form, TransactionCase, tagged

from ..models.rut import nombre_propio, normalizar_patente, rut_canonico, rut_con_puntos, rut_es_valido


@tagged("post_install", "-at_install")
class TestGuiaTransporte(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.empresa = cls.env.company
        chile = cls.env.ref("base.cl")
        cls.empresa.write({"country_id": chile.id, "account_fiscal_country_id": chile.id})
        cls.empresa.partner_id.vat = "76086428-5"
        cls.chofer = cls.env["hr.employee"].create({
            "name": "Juan Chofer", "identification_id": "11.111.111-1", "l10n_cl_is_driver": True})
        cls.peoneta = cls.env["hr.employee"].create({"name": "Pedro Peoneta"})
        marca = cls.env["fleet.vehicle.model.brand"].create({"name": "Chevrolet"})
        cls.modelo = cls.env["fleet.vehicle.model"].create({"name": "NPR 816", "brand_id": marca.id})
        cls.camion = cls.env["fleet.vehicle"].create({
            "model_id": cls.modelo.id,
            "license_plate": "tsrv-15",
            "company_id": cls.empresa.id,
            "l10n_cl_driver_employee_id": cls.chofer.id,
            "l10n_cl_crew_employee_ids": [(6, 0, cls.peoneta.ids)],
        })
        cls.cliente = cls.env["res.partner"].create({
            "name": "Cliente Destino", "street": "Av. Siempre Viva 742", "city": "Rancagua",
        })
        cls.tipo_salida = cls.env["stock.picking.type"].search(
            [("code", "=", "outgoing"), ("company_id", "=", cls.empresa.id)], limit=1)
        cls.tipo_interno = cls.env["stock.picking.type"].search(
            [("code", "=", "internal"), ("company_id", "=", cls.empresa.id)], limit=1)
        cls.etiqueta_transportista = cls.env.ref("simplefy_guia_transporte.partner_category_carrier")
        cls.etiqueta_chofer = cls.env.ref("simplefy_guia_transporte.partner_category_external_driver")

    def _entrega(self, tipo=None, **vals):
        tipo = tipo or self.tipo_salida
        return self.env["stock.picking"].create(dict({
            "picking_type_id": tipo.id,
            "partner_id": self.cliente.id,
            "location_id": tipo.default_location_src_id.id,
            "location_dest_id": (tipo.default_location_dest_id
                                 or self.env.ref("stock.stock_location_customers")).id,
        }, **vals))

    def _validada(self, tipo=None, **vals):
        """Una operación validada: la sección de transporte aparece recién entonces."""
        producto = self.env["product.product"].create({"name": "Saco 15 kg", "type": "consu"})
        entrega = self._entrega(tipo, **vals)
        self.env["stock.move"].create({
            "name": producto.name, "product_id": producto.id, "product_uom_qty": 2,
            "picking_id": entrega.id, "location_id": entrega.location_id.id,
            "location_dest_id": entrega.location_dest_id.id,
        })
        entrega.action_confirm()
        entrega.move_ids.write({"quantity": 2, "picked": True})
        entrega.button_validate()
        self.assertEqual(entrega.state, "done")
        return entrega

    def _externo(self, nombre="Transportes Sur SpA", rut="77806647-5"):
        return self.env["res.partner"].create({
            "name": nombre, "vat": rut, "is_company": True,
            "category_id": [(4, self.etiqueta_transportista.id)]})

    # ---------------------------------------------------------------- RUT, patente y nombres

    def test_rut(self):
        self.assertTrue(rut_es_valido("76.086.428-5"))
        self.assertTrue(rut_es_valido("CL760864285"))
        self.assertTrue(rut_es_valido("10.000.013-k"))
        self.assertFalse(rut_es_valido("76.086.428-4"))
        self.assertFalse(rut_es_valido("0-0"))
        self.assertFalse(rut_es_valido(False))
        self.assertEqual(rut_canonico("10.000.013-k"), "10000013-K")
        self.assertEqual(rut_con_puntos("76086428-5"), "76.086.428-5")

    def test_patente(self):
        self.assertEqual(normalizar_patente(" cyzx-40 "), "CYZX40")
        self.assertEqual(normalizar_patente("TX.26 18"), "TX2618")
        self.assertFalse(normalizar_patente(""))

    def test_nombre_propio(self):
        self.assertEqual(nombre_propio("JUAN carlos  DE la FUENTE"), "Juan Carlos de la Fuente")
        self.assertEqual(nombre_propio("josé o'higgins pérez-cotapos"), "José O'Higgins Pérez-Cotapos")
        self.assertEqual(nombre_propio("TRANSPORTES DEL SUR SPA", empresa=True), "Transportes del Sur SpA")
        self.assertEqual(nombre_propio("logística norte ltda", empresa=True), "Logística Norte Ltda.")

    # ---------------------------------------------------------------- flota propia

    def test_vehiculo_completa_sin_borrar(self):
        otro = self.env["hr.employee"].create({"name": "Otro Chofer", "l10n_cl_is_driver": True})
        entrega = self._entrega()
        entrega.write({"l10n_cl_driver_employee_id": otro.id, "l10n_cl_trailer_license_plate": "jj-11-22"})
        entrega.l10n_cl_fleet_vehicle_id = self.camion
        self.assertEqual(entrega.l10n_cl_license_plate, "TSRV15")
        self.assertEqual(entrega.l10n_cl_driver_employee_id, otro, "el chofer ya elegido no se cambia")
        self.assertEqual(entrega.l10n_cl_trailer_license_plate, "JJ1122", "el carro no se borra")
        self.assertEqual(entrega.l10n_cl_crew_employee_ids, self.peoneta)

    def test_vehiculo_en_formulario_no_borra(self):
        """Aldo: «si se selecciona un transporte con las celdas rellenas, estas se borran»."""
        sin_chofer = self.env["fleet.vehicle"].create({
            "model_id": self.modelo.id, "license_plate": "HLHB-31", "company_id": self.empresa.id})
        with Form(self._validada()) as form:
            form.l10n_cl_driver_employee_id = self.chofer
            form.l10n_cl_trailer_license_plate = "jj1122"
            form.l10n_cl_fleet_vehicle_id = sin_chofer
            self.assertEqual(form.l10n_cl_driver_employee_id, self.chofer)
            self.assertEqual(form.l10n_cl_trailer_license_plate, "JJ1122")
            self.assertEqual(form.l10n_cl_license_plate, "HLHB31")

    def test_flota_propia_transportista_y_chofer(self):
        entrega = self._entrega(l10n_cl_fleet_vehicle_id=self.camion.id)
        self.assertEqual(entrega.l10n_cl_transport_mode, "own")
        self.assertEqual(entrega._l10n_cl_transportista(), self.empresa.partner_id)
        self.assertEqual(entrega.l10n_cl_driver_employee_id, self.chofer)
        self.assertEqual(entrega._l10n_cl_chofer(), {"name": "Juan Chofer", "vat": "11.111.111-1"})
        self.assertEqual(entrega.l10n_cl_driver_vat, "11.111.111-1")
        self.assertEqual(entrega.l10n_cl_transport_vat, "76.086.428-5")

    def test_pasar_a_externo_quita_el_vehiculo_propio(self):
        with Form(self._validada()) as form:
            form.l10n_cl_fleet_vehicle_id = self.camion
            form.l10n_cl_trailer_license_plate = "JJ1122"
            form.l10n_cl_transport_mode = "external"
            self.assertFalse(form.l10n_cl_fleet_vehicle_id)
            self.assertFalse(form.l10n_cl_license_plate, "la patente del camión propio no sirve")
            self.assertEqual(form.l10n_cl_trailer_license_plate, "JJ1122", "lo escrito a mano queda")

    def test_copia_no_arrastra_transporte(self):
        entrega = self._entrega(l10n_cl_fleet_vehicle_id=self.camion.id)
        copia = entrega.copy()
        self.assertFalse(copia.l10n_cl_fleet_vehicle_id)
        self.assertFalse(copia.l10n_cl_license_plate)
        self.assertFalse(copia.l10n_cl_driver_employee_id)

    # ---------------------------------------------------------------- transporte externo

    def test_externo_no_crea_vehiculos(self):
        vehiculos = self.env["fleet.vehicle"].search_count([])
        transportista = self._externo()
        entrega = self._entrega(
            l10n_cl_transport_mode="external",
            l10n_cl_transport_partner_id=transportista.id,
            l10n_cl_license_plate="ab-cd-12",
        )
        self.assertEqual(entrega.l10n_cl_license_plate, "ABCD12")
        self.assertEqual(self.env["fleet.vehicle"].search_count([]), vehiculos)
        self.assertEqual(entrega._l10n_cl_transportista(), transportista)

    def test_metodo_de_envio_externo(self):
        courier = self._externo("Courier Express SpA", "96.919.050-8")
        metodo = self.env["delivery.carrier"].create({
            "name": "Courier", "product_id": self.env["product.product"].create(
                {"name": "Despacho", "type": "service"}).id,
            "l10n_cl_transport_partner_id": courier.id,
        })
        entrega = self._entrega(carrier_id=metodo.id)
        self.assertEqual(entrega.l10n_cl_transport_mode, "external")
        self.assertEqual(entrega.l10n_cl_transport_partner_id, courier)

    def test_alta_rapida_de_chofer(self):
        entrega = self._entrega()
        accion = entrega.action_l10n_cl_new_driver()
        asistente = self.env[accion["res_model"]].with_context(accion["context"]).create({
            "name": "  MARÍA josé DE LA cruz ", "vat": "22.444.777-9"})
        self.assertEqual(asistente.preview_name, "María José de la Cruz")
        asistente.action_confirm()
        chofer = entrega.l10n_cl_edi_driver_id
        self.assertEqual(chofer.name, "María José de la Cruz")
        self.assertEqual(chofer.vat, "22444777-9")
        self.assertFalse(chofer.is_company)
        self.assertIn(self.etiqueta_chofer, chofer.category_id)
        self.assertEqual(entrega.l10n_cl_transport_mode, "external")
        self.assertEqual(entrega._l10n_cl_chofer()["name"], "María José de la Cruz")

        # El mismo RUT, escrito de otra forma, no crea un contacto duplicado.
        otra = self._entrega()
        asistente = self.env["l10n_cl.transport.contact.wizard"].create({
            "picking_id": otra.id, "contact_type": "driver", "name": "maria cruz", "vat": "224447779"})
        self.assertEqual(asistente.existing_partner_id, chofer)
        asistente.action_confirm()
        self.assertEqual(otra.l10n_cl_edi_driver_id, chofer)

    def test_alta_rapida_rut_invalido(self):
        asistente = self.env["l10n_cl.transport.contact.wizard"].create({
            "contact_type": "carrier", "name": "transportes sur spa", "vat": "77.806.647-4"})
        with self.assertRaises(UserError):
            asistente.action_confirm()

    def test_alta_rapida_de_transportista(self):
        entrega = self._entrega()
        asistente = self.env["l10n_cl.transport.contact.wizard"].create({
            "picking_id": entrega.id, "contact_type": "carrier",
            "name": "TRANSPORTES SUR SPA", "vat": "78.444.555-0"})
        asistente.action_confirm()
        transportista = entrega.l10n_cl_transport_partner_id
        self.assertEqual(transportista.name, "Transportes Sur SpA")
        self.assertTrue(transportista.is_company)
        self.assertIn(self.etiqueta_transportista, transportista.category_id)

    def test_rut_del_chofer_externo_desde_la_entrega(self):
        chofer = self.env["res.partner"].create({"name": "Chofer Externo"})
        entrega = self._entrega(l10n_cl_transport_mode="external", l10n_cl_edi_driver_id=chofer.id)
        entrega.l10n_cl_driver_vat = "12.345.678-5"
        self.assertEqual(chofer.vat, "12345678-5")
        self.assertEqual(entrega.l10n_cl_driver_vat, "12.345.678-5")

    # ---------------------------------------------------------------- traslados internos

    def test_traslado_interno_lleva_transporte(self):
        traslado = self._entrega(tipo=self.tipo_interno, l10n_cl_fleet_vehicle_id=self.camion.id)
        self.assertTrue(traslado._l10n_cl_transport_applies())
        self.assertEqual(traslado.l10n_cl_license_plate, "TSRV15")

    # ---------------------------------------------------------------- revisión

    def test_problemas_flota_propia(self):
        sin_rut = self.env["hr.employee"].create({"name": "Sin Rut", "l10n_cl_is_driver": True})
        entrega = self._entrega(l10n_cl_license_plate="TSRV15", l10n_cl_driver_employee_id=sin_rut.id)
        textos = [t for t, _n in entrega._l10n_cl_transport_problems()]
        self.assertTrue(any("ficha de empleado" in t for t in textos))
        self.assertFalse(entrega._l10n_cl_transport_blockers(), "por defecto solo se informa")
        self.empresa.l10n_cl_transport_check = "block"
        self.assertTrue(entrega._l10n_cl_transport_blockers())

    def test_rut_invalido_siempre_bloquea(self):
        malo = self.env["res.partner"].create({"name": "Chofer Malo", "vat": "11111111-2"})
        entrega = self._entrega(
            l10n_cl_transport_mode="external", l10n_cl_transport_partner_id=self._externo().id,
            l10n_cl_license_plate="AB1234", l10n_cl_edi_driver_id=malo.id)
        self.assertTrue(any("no es válido" in t for t in entrega._l10n_cl_transport_blockers()))

    def test_patente_larga_siempre_bloquea(self):
        entrega = self._entrega(l10n_cl_license_plate="ABCDEFGHIJ")
        self.assertTrue(any("8 caracteres" in t for t in entrega._l10n_cl_transport_blockers()))

    def test_sin_datos_solo_avisa(self):
        entrega = self._entrega()
        problemas = entrega._l10n_cl_transport_problems()
        self.assertTrue(any("Sin Dato" in t for t, _n in problemas))
        self.empresa.l10n_cl_transport_check = "block"
        self.assertFalse(entrega._l10n_cl_transport_blockers())

    def test_aviso_solo_con_la_operacion_validada(self):
        pendiente = self._entrega(l10n_cl_license_plate="AB1234")
        self.assertFalse(pendiente.l10n_cl_transport_issues, "antes de validar no se muestra")
        validada = self._validada(l10n_cl_license_plate="AB1234")
        self.assertIn("Antes de emitir", validada.l10n_cl_transport_issues)

    def test_seccion_solo_con_la_operacion_validada(self):
        arch = self.env["stock.picking"].get_view(view_type="form")["arch"]
        self.assertIn("state != 'done' or country_code != 'CL'", arch)

    # ---------------------------------------------------------------- lotes

    def test_lote_pasa_vehiculo_solo_a_flota_propia(self):
        propia = self._entrega()
        externa = self._entrega(l10n_cl_transport_mode="external")
        lote = self.env["stock.picking.batch"].create({"picking_ids": [(6, 0, (propia | externa).ids)]})
        lote.vehicle_id = self.camion
        self.assertEqual(propia.l10n_cl_fleet_vehicle_id, self.camion)
        self.assertEqual(propia.l10n_cl_license_plate, "TSRV15")
        self.assertFalse(externa.l10n_cl_fleet_vehicle_id)
