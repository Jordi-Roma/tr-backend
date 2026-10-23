"""Pruebas aisladas de identidad, alcance y plan; no necesitan DATABASE_URL."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.core.contexto_empresa import exigir_empresa_id, normalizar_codigo_empresa
from app.core.plan_empresa import bloquear_empresa_y_obtener_limite, exigir_funcion_empresa
from app.modules.autenticacion.dependencies.admin_required import requerir_admin, requerir_admin_saas
from app.modules.autenticacion.dependencies.usuario_actual import obtener_usuario_actual
from app.modules.autenticacion.schemas.sesion.sesion_request import LoginRequest
from app.modules.autenticacion.services.sesion_service import iniciar_sesion
from app.modules.administracion.router.empresa_publica_router import obtener_empresa_publica


class TestContextoEmpresa(unittest.TestCase):
    def test_codigo_normalizado_sin_empresa_predeterminada(self):
        self.assertEqual(normalizar_codigo_empresa("  StyleAR "), "stylear")
        with self.assertRaises(ValueError):
            normalizar_codigo_empresa("otra/empresa")
        with self.assertRaises(HTTPException) as raised:
            exigir_empresa_id({"id": 1, "empresa_id": None})
        self.assertEqual(raised.exception.status_code, 403)

    def test_login_rechaza_codigo_ajeno_aunque_clave_sea_correcta(self):
        usuario = {
            "id": 5, "activo": True, "bloqueado_hasta": None,
            "password_hash": "fake", "roles": ["CLIENTE"],
            "empresa_id": 10, "empresa_codigo": "stylear", "empresa_estado": "ACTIVA",
        }
        with patch("app.modules.autenticacion.services.sesion_service.obtener_usuario_para_login", return_value=usuario), \
             patch("app.modules.autenticacion.services.sesion_service.verificar_password", return_value=True), \
             patch("app.modules.autenticacion.services.sesion_service.registrar_bitacora_login"), \
             patch("app.modules.autenticacion.services.sesion_service.crear_sesion") as crear:
            with self.assertRaises(HTTPException) as raised:
                iniciar_sesion(LoginRequest(identificador="cliente", password="secreto", empresa_codigo="otra"))
            self.assertEqual(raised.exception.status_code, 401)
            crear.assert_not_called()

    def test_login_exitoso_liga_token_y_sesion_a_empresa(self):
        usuario = {
            "id": 5, "nombre": "Ana", "apellido": "Lopez", "username": "ana",
            "correo": "ana@example.com", "activo": True, "bloqueado_hasta": None,
            "password_hash": "fake", "roles": ["CLIENTE"],
            "empresa_id": 10, "empresa_codigo": "stylear", "empresa_estado": "ACTIVA",
        }
        with patch("app.modules.autenticacion.services.sesion_service.obtener_usuario_para_login", return_value=usuario), \
             patch("app.modules.autenticacion.services.sesion_service.verificar_password", return_value=True), \
             patch("app.modules.autenticacion.services.sesion_service.registrar_bitacora_login"), \
             patch("app.modules.autenticacion.services.sesion_service.reiniciar_intentos_login"), \
             patch("app.modules.autenticacion.services.sesion_service.crear_sesion", return_value={"id": 7}) as crear, \
             patch("app.modules.autenticacion.services.sesion_service.crear_token_acceso", return_value="jwt") as token:
            respuesta = iniciar_sesion(LoginRequest(identificador="ana", password="secreto", empresa_codigo="stylear"))
            crear.assert_called_once_with(5, 10, identidad_verificada=usuario)
            self.assertEqual(token.call_args.args[0]["empresa_id"], 10)
            self.assertEqual(respuesta.empresa_codigo, "stylear")

    def test_empresa_publica_inactiva_no_se_expone(self):
        with patch("app.modules.administracion.router.empresa_publica_router.resolver_empresa_por_codigo",
                   return_value={"id": 11, "codigo": "otra", "nombre": "Otra", "estado": "CANCELADA"}):
            with self.assertRaises(HTTPException) as raised:
                obtener_empresa_publica("otra")
            self.assertEqual(raised.exception.status_code, 404)

    def test_token_cruzado_rechazado_antes_de_usar_sesion(self):
        payload = {"sub": "5", "sid": "7", "empresa_id": 99}
        usuario = {"id": 5, "activo": True, "empresa_id": 10,
                   "empresa_estado": "ACTIVA", "roles": ["CLIENTE"]}
        with patch("app.modules.autenticacion.dependencies.usuario_actual.verificar_token_acceso", return_value=payload), \
             patch("app.modules.autenticacion.dependencies.usuario_actual.obtener_usuario_por_id", return_value=usuario), \
             patch("app.modules.autenticacion.dependencies.usuario_actual.sesion_esta_activa", return_value=True) as sesion:
            with self.assertRaises(HTTPException) as raised:
                obtener_usuario_actual(SimpleNamespace(credentials="token"))
            self.assertEqual(raised.exception.status_code, 401)
            sesion.assert_called_once_with(7, 5, 99)

    def test_empresa_suspendida_conserva_identidad_para_consultas(self):
        payload = {"sub": "5", "sid": "7", "empresa_id": 10}
        usuario = {"id": 5, "activo": True, "empresa_id": 10,
                   "empresa_estado": "SUSPENDIDA", "roles": ["CLIENTE"]}
        with patch("app.modules.autenticacion.dependencies.usuario_actual.verificar_token_acceso", return_value=payload), \
             patch("app.modules.autenticacion.dependencies.usuario_actual.obtener_usuario_por_id", return_value=usuario), \
             patch("app.modules.autenticacion.dependencies.usuario_actual.sesion_esta_activa", return_value=True):
            self.assertIs(obtener_usuario_actual(SimpleNamespace(credentials="token")), usuario)

    def test_admin_saas_no_es_admin_comercial(self):
        plataforma = {"id": 1, "empresa_id": None, "roles": ["ADMIN_SAAS"]}
        empresa = {"id": 2, "empresa_id": 10, "roles": ["ADMINISTRADOR"]}
        self.assertIs(requerir_admin_saas(plataforma), plataforma)
        self.assertIs(requerir_admin(empresa), empresa)
        with self.assertRaises(HTTPException):
            requerir_admin(plataforma)
        with self.assertRaises(HTTPException):
            requerir_admin_saas(empresa)


class _CursorFalso:
    def __init__(self, row):
        self.row = row
        self.consultas = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def execute(self, query, params):
        self.consultas.append((query, params))

    def fetchone(self):
        if "FOR UPDATE" in self.consultas[-1][0]:
            return {"id": 10}
        return self.row

    def fetchall(self):
        return []

    def close(self):
        pass


class _ConexionFalsa:
    def __init__(self, cursor):
        self.cursor_falso = cursor

    def cursor(self, **_):
        return self.cursor_falso

    def close(self):
        pass


class TestPlanEmpresa(unittest.TestCase):
    @staticmethod
    def _plan(codigo="BASICO", funciones=None, limites=None):
        from datetime import date
        return {"empresa_estado": "ACTIVA", "suscripcion_estado": "ACTIVA",
                "plan_activo": True, "fecha_inicio": date(2020, 1, 1),
                "fecha_vencimiento": None, "plan_codigo": codigo,
                "funciones": funciones or {}, "limites": limites or {}}

    def test_funcion_inhabilitada_rechazada(self):
        cursor = _CursorFalso(self._plan(funciones={"vestidor": False}))
        with patch("app.core.plan_empresa.get_connection", return_value=_ConexionFalsa(cursor)):
            with self.assertRaises(HTTPException) as raised:
                exigir_funcion_empresa(10, "vestidor")
            self.assertEqual(raised.exception.status_code, 403)

    def test_plan_legacy_mantiene_funciones(self):
        cursor = _CursorFalso(self._plan(codigo="STYLEAR_LEGADO"))
        with patch("app.core.plan_empresa.get_connection", return_value=_ConexionFalsa(cursor)):
            exigir_funcion_empresa(10, "vestidor")

    def test_cupo_bloquea_empresa_antes_de_contar(self):
        cursor = _CursorFalso(self._plan(limites={"sucursales": 2}))
        self.assertEqual(bloquear_empresa_y_obtener_limite(cursor, 10, "sucursales"), 2)
        self.assertIn("FOR UPDATE", cursor.consultas[0][0])

    def test_suscripcion_vencida_bloquea_funcion(self):
        from datetime import date
        plan = self._plan(funciones={"vestidor": True})
        plan["fecha_vencimiento"] = date(2020, 1, 2)
        cursor = _CursorFalso(plan)
        with patch("app.core.plan_empresa.get_connection", return_value=_ConexionFalsa(cursor)):
            with self.assertRaises(HTTPException) as raised:
                exigir_funcion_empresa(10, "vestidor")
            self.assertEqual(raised.exception.status_code, 403)

    def test_listado_usuarios_filtra_empresa(self):
        from app.modules.autenticacion.repositories.usuario_admin_repository import listar_usuarios
        cursor = _CursorFalso(None)
        with patch("app.modules.autenticacion.repositories.usuario_admin_repository.get_connection",
                   return_value=_ConexionFalsa(cursor)):
            self.assertEqual(listar_usuarios(10), [])
            self.assertIn("u.empresa_id = %s", cursor.consultas[0][0])
            self.assertEqual(cursor.consultas[0][1], (10,))


if __name__ == "__main__":
    unittest.main()
