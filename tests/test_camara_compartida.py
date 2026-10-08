"""Uso compartido de la cámara, sin cámara real: cv2.VideoCapture se reemplaza por un doble.

    python -m unittest discover -s tests -t .
"""
import asyncio
import threading
import unittest
from unittest import mock

import numpy as np

from app.services import camera_service as modulo_camara
from app.services import vista_previa
from app.services.camera_service import CameraService, capture_single_frame


class CapturaFalsa:
    """Doble de cv2.VideoCapture que cuenta cuántas veces se abre y se libera."""

    abiertas = 0
    liberadas = 0
    disponible = True

    def __init__(self, indice):
        self._abierta = type(self).disponible
        if self._abierta:
            type(self).abiertas += 1

    def isOpened(self):
        return self._abierta

    def read(self):
        return True, np.zeros((48, 64, 3), dtype=np.uint8)

    def release(self):
        if self._abierta:
            self._abierta = False
            type(self).liberadas += 1


class CamaraFalsaTestCase(unittest.TestCase):
    def setUp(self):
        CapturaFalsa.abiertas = 0
        CapturaFalsa.liberadas = 0
        CapturaFalsa.disponible = True
        parche = mock.patch.object(modulo_camara.cv2, "VideoCapture", CapturaFalsa)
        parche.start()
        self.addCleanup(parche.stop)

        self.camara = CameraService(target_fps=200)
        self.addCleanup(self.camara.liberar_todos)


class ConsumidoresTest(CamaraFalsaTestCase):
    def test_se_abre_con_el_primero_y_se_libera_con_el_ultimo(self):
        self.camara.adquirir("practica:1")
        self.camara.adquirir("vista_previa:a")
        self.assertEqual(CapturaFalsa.abiertas, 1)

        self.camara.liberar("vista_previa:a")
        self.assertTrue(self.camara.encendida)  # la práctica la sigue usando
        self.assertEqual(CapturaFalsa.liberadas, 0)

        self.camara.liberar("practica:1")
        self.assertFalse(self.camara.encendida)
        self.assertEqual(CapturaFalsa.liberadas, 1)
        self.assertIsNone(self.camara.get_latest_frame())

    def test_terminar_la_practica_no_apaga_la_vista_previa(self):
        self.camara.adquirir("vista_previa:a")
        self.camara.adquirir("practica:1")
        self.camara.liberar("practica:1")

        self.assertTrue(self.camara.encendida)
        self.assertEqual(self.camara.consumidores(), {"vista_previa:a"})
        self.assertEqual((CapturaFalsa.abiertas, CapturaFalsa.liberadas), (1, 0))

    def test_adquirir_dos_veces_no_cuenta_doble(self):
        self.camara.adquirir("vista_previa:a")
        self.camara.adquirir("vista_previa:a")
        self.assertEqual(CapturaFalsa.abiertas, 1)

        self.camara.liberar("vista_previa:a")
        self.assertFalse(self.camara.encendida)

    def test_liberar_sin_haber_adquirido_no_rompe_el_conteo(self):
        self.camara.liberar("nadie")
        self.camara.adquirir("practica:1")
        self.camara.liberar("nadie")
        self.camara.liberar("vista_previa:a")

        self.assertTrue(self.camara.encendida)
        self.assertEqual(self.camara.consumidores(), {"practica:1"})

    def test_si_la_camara_no_abre_el_consumidor_no_queda_registrado(self):
        CapturaFalsa.disponible = False
        with self.assertRaises(RuntimeError):
            self.camara.adquirir("vista_previa:a")

        self.assertEqual(self.camara.consumidores(), set())
        self.assertFalse(self.camara.encendida)

        # Y se puede volver a intentar cuando la cámara ya esté
        CapturaFalsa.disponible = True
        self.camara.adquirir("vista_previa:a")
        self.assertTrue(self.camara.encendida)

    def test_hay_frame_en_cuanto_se_adquiere(self):
        self.camara.adquirir("vista_previa:a")
        self.assertIsNotNone(self.camara.get_latest_frame())

    def test_se_puede_volver_a_encender_despues_de_apagar(self):
        self.camara.adquirir("practica:1")
        self.camara.liberar("practica:1")
        self.camara.adquirir("practica:2")

        self.assertTrue(self.camara.encendida)
        self.assertEqual((CapturaFalsa.abiertas, CapturaFalsa.liberadas), (2, 1))

    def test_liberar_todos_apaga_aunque_queden_consumidores(self):
        self.camara.adquirir("practica:1")
        self.camara.adquirir("vista_previa:a")
        self.camara.liberar_todos()

        self.assertFalse(self.camara.encendida)
        self.assertEqual(self.camara.consumidores(), set())
        self.assertEqual(CapturaFalsa.liberadas, 1)

    def test_adquirir_y_liberar_desde_varios_hilos(self):
        def trabajar(nombre):
            for _ in range(50):
                self.camara.adquirir(nombre)
                self.camara.liberar(nombre)

        hilos = [threading.Thread(target=trabajar, args=(f"hilo:{i}",)) for i in range(8)]
        self.camara.adquirir("practica:1")  # mantiene la cámara abierta todo el rato
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join()

        self.assertEqual(self.camara.consumidores(), {"practica:1"})
        self.assertEqual((CapturaFalsa.abiertas, CapturaFalsa.liberadas), (1, 0))

        self.camara.liberar("practica:1")
        self.assertEqual(CapturaFalsa.liberadas, 1)


class CapturaUnicaTest(CamaraFalsaTestCase):
    def setUp(self):
        super().setUp()
        parche = mock.patch.object(modulo_camara, "camera_service", self.camara)
        parche.start()
        self.addCleanup(parche.stop)

    def test_con_la_camara_encendida_no_abre_el_dispositivo_otra_vez(self):
        self.camara.adquirir("vista_previa:a")
        frame = capture_single_frame()

        self.assertIsNotNone(frame)
        self.assertEqual(CapturaFalsa.abiertas, 1)

    def test_con_la_camara_apagada_abre_captura_y_libera(self):
        frame = capture_single_frame()

        self.assertIsNotNone(frame)
        self.assertEqual((CapturaFalsa.abiertas, CapturaFalsa.liberadas), (1, 1))
        self.assertFalse(self.camara.encendida)


class VistaPreviaTest(CamaraFalsaTestCase, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        super().setUp()
        for nombre, valor in (
            ("camera_service", self.camara),
            ("_lock", asyncio.Lock()),
            ("_ultima_lectura", {}),
            ("_vigilante", None),
            ("GRACIA_SIN_LECTURA_SEGUNDOS", 0.2),
            ("VIGILANCIA_INTERVALO_SEGUNDOS", 0.02),
        ):
            parche = mock.patch.object(vista_previa, nombre, valor)
            parche.start()
            self.addCleanup(parche.stop)

    async def test_encender_dos_veces_y_apagar_una_la_apaga(self):
        await vista_previa.encender("a")
        await vista_previa.encender("a")
        await vista_previa.apagar("a")

        self.assertFalse(vista_previa.activa("a"))
        self.assertFalse(self.camara.encendida)

    async def test_apagar_sin_encender_no_falla(self):
        await vista_previa.apagar("a")
        self.assertFalse(self.camara.encendida)

    async def test_cada_usuario_tiene_la_suya(self):
        await vista_previa.encender("a")
        await vista_previa.encender("b")
        await vista_previa.apagar("a")

        self.assertTrue(vista_previa.activa("b"))
        self.assertTrue(self.camara.encendida)

    async def test_sin_lecturas_se_apaga_sola(self):
        await vista_previa.encender("a")
        await asyncio.sleep(0.5)

        self.assertFalse(vista_previa.activa("a"))
        self.assertFalse(self.camara.encendida)

    async def test_mientras_se_lee_el_stream_sigue_encendida(self):
        await vista_previa.encender("a")
        for _ in range(10):
            await asyncio.sleep(0.05)
            vista_previa.marcar_lectura("a")

        self.assertTrue(vista_previa.activa("a"))
        self.assertTrue(self.camara.encendida)

    async def test_al_caducar_no_apaga_la_camara_de_una_practica(self):
        self.camara.adquirir("practica:1")
        await vista_previa.encender("a")
        await asyncio.sleep(0.5)

        self.assertFalse(vista_previa.activa("a"))
        self.assertEqual(self.camara.consumidores(), {"practica:1"})
        self.assertTrue(self.camara.encendida)

    async def test_si_la_camara_no_abre_no_queda_encendida(self):
        CapturaFalsa.disponible = False
        with self.assertRaises(RuntimeError):
            await vista_previa.encender("a")

        self.assertFalse(vista_previa.activa("a"))
        self.assertEqual(self.camara.consumidores(), set())


if __name__ == "__main__":
    unittest.main()
