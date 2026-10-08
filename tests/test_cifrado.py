"""Cifrado de los vectores faciales. No necesita Mongo ni cámara.

    python -m unittest discover -s tests -t .
"""
import unittest
from unittest import mock

import numpy as np
from cryptography.fernet import Fernet

from app.core import cifrado
from app.services.face_service import find_best_match


class CifradoEmbeddingTest(unittest.TestCase):
    def setUp(self):
        self.embedding = list(np.random.default_rng(1).normal(size=128))

    def test_lo_cifrado_no_contiene_el_vector_y_se_recupera_exacto(self):
        cifrado_ = cifrado.cifrar_embedding(self.embedding)

        self.assertIsInstance(cifrado_, str)
        self.assertNotIn(str(self.embedding[0]), cifrado_)
        np.testing.assert_array_equal(cifrado.descifrar_embedding(cifrado_), np.array(self.embedding))

    def test_cifrar_dos_veces_da_textos_distintos(self):
        self.assertNotEqual(cifrado.cifrar_embedding(self.embedding), cifrado.cifrar_embedding(self.embedding))

    def test_acepta_el_vector_en_claro_de_alumnos_anteriores(self):
        np.testing.assert_array_equal(cifrado.descifrar_embedding(self.embedding), np.array(self.embedding))

    def test_con_otra_clave_no_se_puede_descifrar(self):
        cifrado_ = cifrado.cifrar_embedding(self.embedding)
        with mock.patch.object(cifrado, "_fernet", Fernet(Fernet.generate_key())):
            with self.assertRaises(RuntimeError):
                cifrado.descifrar_embedding(cifrado_)

    def test_un_dato_alterado_se_rechaza(self):
        cifrado_ = cifrado.cifrar_embedding(self.embedding)
        alterado = cifrado_[:-4] + ("AAAA" if not cifrado_.endswith("AAAA") else "BBBB")
        with self.assertRaises(RuntimeError):
            cifrado.descifrar_embedding(alterado)

    def test_el_reconocimiento_funciona_con_el_vector_descifrado(self):
        candidato = {"_id": "a", "face_embedding": cifrado.descifrar_embedding(cifrado.cifrar_embedding(self.embedding))}
        match = find_best_match(self.embedding, [candidato])

        self.assertIsNotNone(match)
        self.assertAlmostEqual(match["similarity"], 1.0)


if __name__ == "__main__":
    unittest.main()
