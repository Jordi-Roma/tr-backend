"""CU04/CU05 sobre PostgreSQL explícito y desechable."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from test_multitenant_integration import actor, empresas, cliente, consulta, mercaderia
from test_cuenta_integration import login, PASSWORD
from app.main import app
from app.modules.autenticacion.repositories import (
    administracion_acceso_repository as acceso,
)


@pytest.fixture
def api():
    return TestClient(app)


def rid(nombre):
    return consulta("SELECT id FROM rol WHERE nombre=%s", (nombre,), True)["id"]


def body(rol="CLIENTE"):
    nombre = "cu04" + uuid4().hex[:12]
    return dict(
        nombre="Cuenta",
        apellido="Prueba",
        username=nombre,
        correo=nombre + "@example.invalid",
        password=PASSWORD,
        rol_id=rid(rol),
    )


def datos(u):
    return {k: u[k] for k in ("nombre", "apellido", "username", "correo")}


def as_headers(api, actor):
    nombre = consulta("SELECT username FROM usuario WHERE id=%s", (actor,), True)[
        "username"
    ]
    return login(api, None, nombre, "Prueba-AS-local-123")


def test_listado_inactivos_busqueda_y_baja_logica(api, empresas):
    a, _, _, _ = empresas
    h = login(api, a, a["codigo"])
    b = body()
    r = api.post("/api/v1/usuarios", headers=h, json=b)
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    assert "password_hash" not in r.json()
    assert api.patch(f"/api/v1/usuarios/{uid}/desactivar", headers=h).status_code == 200
    r = api.get(
        "/api/v1/usuarios/paginados",
        headers=h,
        params={"estado": "INACTIVOS", "busqueda": b["username"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 1 and r.json()["registros"][0]["id"] == uid
    assert (
        consulta("SELECT activo FROM cliente WHERE usuario_id=%s", (uid,), True)[
            "activo"
        ]
        is True
    )
    assert api.patch(f"/api/v1/usuarios/{uid}/activar", headers=h).status_code == 200
    r = api.get(
        "/api/v1/usuarios/paginados",
        headers=h,
        params={"estado": "TODOS", "por_pagina": 1, "pagina": 2},
    )
    assert r.json()["total"] == 2 and len(r.json()["registros"]) == 1
    assert (
        api.get("/api/v1/usuarios/paginados?estado=MAL", headers=h).status_code == 422
    )


@pytest.mark.parametrize(
    "accion", ["ver", "editar", "baja", "alta", "asignar", "retirar"]
)
def test_ids_de_otra_empresa_no_se_administran(api, empresas, accion):
    a, b, _, _ = empresas
    _, _, nombre = cliente(b)
    uid = consulta("SELECT id FROM usuario WHERE username=%s", (nombre,), True)["id"]
    h = login(api, a, a["codigo"])
    url = f"/api/v1/usuarios/{uid}"
    if accion == "ver":
        r = api.get(url, headers=h)
    elif accion == "editar":
        r = api.put(url, headers=h, json=datos(body()))
    elif accion == "baja":
        r = api.patch(url + "/desactivar", headers=h)
    elif accion == "alta":
        r = api.patch(url + "/activar", headers=h)
    elif accion == "asignar":
        r = api.post(url + f'/roles/{rid("ADMINISTRADOR")}', headers=h)
    else:
        r = api.patch(url + f'/roles/{rid("CLIENTE")}/desactivar', headers=h)
    assert r.status_code == 404, r.text
    assert (
        consulta("SELECT activo FROM usuario WHERE id=%s", (uid,), True)["activo"]
        is True
    )


def test_as_gestiona_solo_cuentas_autorizadas(api, empresas):
    a, b, _, actor = empresas
    h = as_headers(api, actor)
    r = api.post("/api/v1/saas/usuarios", headers=h, json=body("ADMIN_SAAS"))
    assert r.status_code == 201, r.text
    nuevo = r.json()["id"]
    assert (
        api.patch(f"/api/v1/saas/usuarios/{nuevo}/desactivar", headers=h).status_code
        == 200
    )
    assert (
        api.patch(f"/api/v1/saas/usuarios/{nuevo}/activar", headers=h).status_code
        == 200
    )
    assert (
        api.patch(f"/api/v1/saas/usuarios/{actor}/desactivar", headers=h).status_code
        == 409
    )
    r = api.post(
        "/api/v1/saas/usuarios",
        headers=h,
        params={"empresa_id": a["id"]},
        json=body("ADMINISTRADOR"),
    )
    assert r.status_code == 201, r.text
    objetivo = r.json()["id"]
    registros = api.get(
        "/api/v1/saas/bitacora",
        headers=h,
        params={"usuario_id": actor, "accion": "CREAR_USUARIO"},
    ).json()["registros"]
    assert registros[0]["objetivo_usuario_id"] == objetivo
    detalle = api.get(f'/api/v1/saas/bitacora/{registros[0]["id"]}', headers=h).json()
    assert detalle["objetivo_usuario_id"] == objetivo
    assert detalle["empresa_afectada_id"] == a["id"]
    assert detalle["empresa_id"] is None
    assert api.get("/api/v1/usuarios", headers=h).status_code == 403
    assert (
        api.get(
            "/api/v1/saas/usuarios", headers=h, params={"empresa_id": 9999999}
        ).status_code
        == 404
    )
    uid, _, _ = cliente(a)
    assert (
        api.get(
            f"/api/v1/saas/usuarios/{uid}", headers=h, params={"empresa_id": a["id"]}
        ).status_code
        == 404
    )
    assert (
        api.post(
            "/api/v1/saas/usuarios",
            headers=h,
            params={"empresa_id": a["id"]},
            json=body("CLIENTE"),
        ).status_code
        == 403
    )
    ad = login(api, a, a["codigo"])
    assert api.get("/api/v1/saas/usuarios", headers=ad).status_code == 403
    assert (
        api.post("/api/v1/usuarios", headers=ad, json=body("ADMIN_SAAS")).status_code
        == 403
    )


def test_dos_bajas_no_dejan_empresa_sin_admin(api, empresas):
    a, _, _, actor = empresas
    h = as_headers(api, actor)
    r = api.post(
        "/api/v1/saas/usuarios",
        headers=h,
        params={"empresa_id": a["id"]},
        json=body("ADMINISTRADOR"),
    )
    assert r.status_code == 201, r.text
    ids = [a["admin_usuario_id"], r.json()["id"]]
    with ThreadPoolExecutor(max_workers=2) as pool:
        respuestas = list(
            pool.map(
                lambda uid: api.patch(
                    f"/api/v1/saas/usuarios/{uid}/desactivar",
                    headers=h,
                    params={"empresa_id": a["id"]},
                ),
                ids,
            )
        )
    assert sorted(r.status_code for r in respuestas) == [200, 409]
    assert (
        consulta(
            "SELECT count(*) n FROM usuario WHERE empresa_id=%s AND activo",
            (a["id"],),
            True,
        )["n"]
        == 1
    )


def test_protege_cuenta_propia_y_empresa_inmutable(api, empresas):
    a, b, _, _ = empresas
    h = login(api, a, a["codigo"])
    uid = a["admin_usuario_id"]
    assert api.patch(f"/api/v1/usuarios/{uid}/desactivar", headers=h).status_code == 409
    assert (
        api.patch(
            f'/api/v1/usuarios/{uid}/roles/{rid("ADMINISTRADOR")}/desactivar', headers=h
        ).status_code
        == 409
    )
    u = api.get(f"/api/v1/usuarios/{uid}", headers=h).json()
    assert (
        api.put(
            f"/api/v1/usuarios/{uid}",
            headers=h,
            json={**datos(u), "empresa_id": b["id"]},
        ).status_code
        == 422
    )
    assert (
        api.put(
            f"/api/v1/usuarios/{uid}",
            headers=h,
            json={**datos(u), "correo": "otra@example.invalid"},
        ).status_code
        == 409
    )


def test_editar_identidad_cierra_todas_sesiones_duplicado_hace_rollback(api, empresas):
    a, _, _, _ = empresas
    h = login(api, a, a["codigo"])
    uid, _, nombre = cliente(a)
    otro, _, nombre_otro = cliente(a)
    hc = login(api, a, nombre)
    hc2 = login(api, a, nombre)
    u = api.get(f"/api/v1/usuarios/{uid}", headers=h).json()
    assert (
        api.put(
            f"/api/v1/usuarios/{uid}",
            headers=h,
            json={**datos(u), "username": nombre_otro, "nombre": "No guardar"},
        ).status_code
        == 409
    )
    assert api.get(f"/api/v1/usuarios/{uid}", headers=h).json()["nombre"] == u["nombre"]
    r = api.put(
        f"/api/v1/usuarios/{uid}",
        headers=h,
        json={**datos(u), "username": nombre + "x"},
    )
    assert r.status_code == 200, r.text
    for headers in [hc, hc2]:
        assert api.get("/api/v1/perfil", headers=headers).status_code == 401
    eventos = consulta(
        "SELECT * FROM bitacora WHERE objetivo_usuario_id=%s AND accion='EDITAR_USUARIO'",
        (uid,),
    )
    assert len(eventos) == 1 and eventos[0]["empresa_id"] == a["id"]
    assert eventos[0]["direccion_ip"] is None
    assert (
        api.get("/api/v1/perfil", headers=login(api, a, nombre + "x")).status_code
        == 200
    )


def test_vinculos_requeridos_y_revocacion_al_asignar_rol(api, empresas):
    a, _, _, _ = empresas
    h = login(api, a, a["codigo"])
    uid, _, nombre = cliente(a)
    hc = login(api, a, nombre)
    assert (
        api.post(f'/api/v1/usuarios/{uid}/roles/{rid("CAJERO")}', headers=h).status_code
        == 409
    )
    suc, _, _ = mercaderia(a)
    consulta(
        "INSERT INTO empleado(usuario_id,sucursal_id,codigo_empleado,cargo,empresa_id) VALUES(%s,%s,%s,'Prueba',%s)",
        (uid, suc, uuid4().hex, a["id"]),
    )
    assert (
        api.post(f'/api/v1/usuarios/{uid}/roles/{rid("CAJERO")}', headers=h).status_code
        == 200
    )
    assert api.get("/api/v1/perfil", headers=hc).status_code == 401
    assert (
        api.post("/api/v1/usuarios", headers=h, json=body("CAJERO")).status_code == 409
    )


def test_permisos_editables_aplicados_y_sesiones_revocadas(api, empresas):
    a, _, _, actor = empresas
    ha = as_headers(api, actor)
    h = login(api, a, a["codigo"])
    rol = rid("ADMINISTRADOR")
    original = api.get(f"/api/v1/roles/{rol}/permisos", headers=ha).json()[
        "permiso_ids"
    ]
    permiso = consulta("SELECT id FROM permiso WHERE accion='usuarios:ver'", una=True)[
        "id"
    ]
    try:
        payload = {
            "permiso_ids": [i for i in original if i != permiso],
            "confirmar_global": True,
        }
        assert (
            api.put(
                f"/api/v1/roles/{rol}/permisos",
                headers=ha,
                json={**payload, "confirmar_global": False},
            ).status_code
            == 400
        )
        r = api.put(f"/api/v1/roles/{rol}/permisos", headers=ha, json=payload)
        assert r.status_code == 200, r.text
        assert api.get("/api/v1/usuarios", headers=h).status_code == 401
        h = login(api, a, a["codigo"])
        assert api.get("/api/v1/usuarios/paginados", headers=h).status_code == 403
        assert (
            "usuarios:ver"
            not in api.get("/api/v1/autenticacion/capacidades", headers=h).json()[
                "permisos"
            ]
        )
        assert api.get("/api/v1/perfil", headers=h).status_code == 200
    finally:
        r = api.put(
            f"/api/v1/roles/{rol}/permisos",
            headers=ha,
            json={"permiso_ids": original, "confirmar_global": True},
        )
        assert r.status_code == 200, r.text
    assert (
        api.get("/api/v1/usuarios", headers=login(api, a, a["codigo"])).status_code
        == 200
    )


@pytest.mark.parametrize(
    "rol",
    [
        "ADMINISTRADOR",
        "ADMIN_SAAS",
        "CLIENTE",
        "CAJERO",
        "ENCARGADO_SUCURSAL",
        "PROVEEDOR",
    ],
)
def test_roles_base_no_se_renombran_ni_desactivan(api, empresas, rol):
    _, _, _, actor = empresas
    h = as_headers(api, actor)
    id_rol = rid(rol)
    assert (
        api.put(
            f"/api/v1/roles/{id_rol}", headers=h, json={"nombre": "OTRO"}
        ).status_code
        == 409
    )
    assert api.patch(f"/api/v1/roles/{id_rol}/desactivar", headers=h).status_code == 409


def test_permisos_protegidos_y_claves_libres_se_rechazan(api, empresas):
    a, _, _, actor = empresas
    h = as_headers(api, actor)
    rol = rid("ADMINISTRADOR")
    original = api.get(f"/api/v1/roles/{rol}/permisos", headers=h).json()["permiso_ids"]
    p = consulta("SELECT id FROM permiso WHERE accion='productos:crear'", una=True)[
        "id"
    ]
    assert p in original
    assert (
        api.put(
            f"/api/v1/roles/{rol}/permisos",
            headers=h,
            json={
                "permiso_ids": [i for i in original if i != p],
                "confirmar_global": True,
            },
        ).status_code
        == 409
    )
    assert (
        api.post(
            "/api/v1/permisos",
            headers=h,
            json={"nombre": "Falso", "modulo": "AUTENTICACION", "accion": "inventado"},
        ).status_code
        == 409
    )
    assert (
        api.put(
            f"/api/v1/roles/{rol}",
            headers=login(api, a, a["codigo"]),
            json={"descripcion": "No autorizado"},
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    "query",
    [
        {"fecha_desde": "mal"},
        {"fecha_hasta": "2026-02-31"},
        {"fecha_desde": "2026-10-24", "fecha_hasta": "2026-10-23"},
        {"pagina": 0},
        {"por_pagina": 201},
        {"usuario_id": -1},
    ],
)
def test_filtros_invalidos_de_bitacora_no_producen_500(api, empresas, query):
    a, _, _, _ = empresas
    h = login(api, a, a["codigo"])
    assert api.get("/api/v1/bitacora", headers=h, params=query).status_code == 422


def test_bitacora_aislamiento_detalle_orden_y_contexto_heredado(api, empresas):
    a, b, _, actor = empresas
    ha = as_headers(api, actor)
    h = login(api, a, a["codigo"])
    hb = login(api, b, b["codigo"])

    def evento(empresa, uid, accion):
        return consulta(
            """INSERT INTO bitacora(empresa_id,usuario_id,accion,modulo,resultado,fecha)
            VALUES(%s,%s,%s,'PRUEBA','EXITOSO','2026-10-23 12:00:00-04') RETURNING id""",
            (empresa, uid, accion),
            True,
        )["id"]

    ids = [evento(a["id"], a["admin_usuario_id"], "MISMA_FECHA") for _ in range(4)]
    ajeno = evento(b["id"], b["admin_usuario_id"], "OTRA_EMPRESA")
    legado = evento(None, a["admin_usuario_id"], "CONTEXTO_DESCONOCIDO")
    plataforma = evento(None, actor, "EVENTO_AS")
    filtro = {
        "accion": "MISMA_FECHA",
        "por_pagina": 2,
        "fecha_desde": "2026-10-23",
        "fecha_hasta": "2026-10-23",
    }
    r = api.get("/api/v1/bitacora", headers=h, params=filtro)
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 4 and [x["id"] for x in r.json()["registros"]] == list(
        reversed(ids[-2:])
    )
    assert api.get(f"/api/v1/bitacora/{ajeno}", headers=h).status_code == 404
    assert api.get(f"/api/v1/bitacora/{ids[0]}", headers=hb).status_code == 404
    assert api.get(f"/api/v1/saas/bitacora/{legado}", headers=ha).status_code == 404
    assert api.get(f"/api/v1/saas/bitacora/{ids[0]}", headers=ha).status_code == 404
    assert api.get(f"/api/v1/saas/bitacora/{plataforma}", headers=ha).status_code == 200
    assert api.get("/api/v1/saas/bitacora", headers=h).status_code == 403
    assert "PRUEBA" in api.get("/api/v1/bitacora/opciones", headers=h).json()["modulos"]
    assert (
        len(
            api.get(
                "/api/v1/saas/bitacora",
                headers=ha,
                params={"accion": "EVENTO_AS", "usuario_id": actor},
            ).json()["registros"]
        )
        == 1
    )


def test_suspension_permite_revocar_no_otorgar_accesos(api, empresas):
    a, _, _, _ = empresas
    h = login(api, a, a["codigo"])
    uid, _, nombre = cliente(a)
    consulta("UPDATE empresa SET estado='SUSPENDIDA' WHERE id=%s", (a["id"],))
    assert api.get("/api/v1/usuarios/paginados", headers=h).status_code == 200
    assert api.patch(f"/api/v1/usuarios/{uid}/desactivar", headers=h).status_code == 200
    assert api.patch(f"/api/v1/usuarios/{uid}/activar", headers=h).status_code == 403
    assert api.post("/api/v1/usuarios", headers=h, json=body()).status_code == 403


def test_login_en_curso_rechaza_version_anterior_de_roles(api, empresas, monkeypatch):
    from app.modules.autenticacion.services import sesion_service
    from app.modules.autenticacion.repositories.usuario_repository import (
        obtener_usuario_por_id,
    )

    a, _, _, _ = empresas
    uid, _, nombre = cliente(a)
    admin = obtener_usuario_por_id(a["admin_usuario_id"])
    crear = sesion_service.crear_sesion

    def cambiar(*args, **kwargs):
        acceso.rol_usuario(admin, a["id"], uid, rid("ADMINISTRADOR"), True)
        return crear(*args, **kwargs)

    monkeypatch.setattr(sesion_service, "crear_sesion", cambiar)
    r = api.post(
        "/api/v1/autenticacion/login",
        json={
            "identificador": nombre,
            "password": PASSWORD,
            "empresa_codigo": a["codigo"],
        },
    )
    assert r.status_code == 401, r.text
    assert (
        consulta(
            "SELECT count(*) n FROM sesion WHERE usuario_id=%s AND activa", (uid,), True
        )["n"]
        == 0
    )


def test_cuenta_admin_revocada_no_ejecuta_peticion_previa(empresas):
    from app.modules.autenticacion.repositories.usuario_repository import (
        obtener_usuario_por_id,
    )

    a, _, _, _ = empresas
    viejo = obtener_usuario_por_id(a["admin_usuario_id"])
    uid, _, _ = cliente(a)
    consulta(
        "UPDATE usuario SET version_acceso=version_acceso+1 WHERE id=%s", (viejo["id"],)
    )
    with pytest.raises(Exception) as e:
        acceso.estado_usuario(viejo, a["id"], uid, False)
    assert getattr(e.value, "status_code", None) == 401
    assert (
        consulta("SELECT activo FROM usuario WHERE id=%s", (uid,), True)["activo"]
        is True
    )


@pytest.mark.parametrize("permiso", list(acceso.CONFIGURABLES))
def test_todas_las_capacidades_editables_bloquean_su_api(api, empresas, permiso):
    a, _, _, actor = empresas
    ha = as_headers(api, actor)
    uid, _, _ = cliente(a)
    rol = rid("ADMINISTRADOR")
    original = api.get(f"/api/v1/roles/{rol}/permisos", headers=ha).json()[
        "permiso_ids"
    ]
    pid = consulta("SELECT id FROM permiso WHERE accion=%s", (permiso,), True)["id"]
    try:
        assert (
            api.put(
                f"/api/v1/roles/{rol}/permisos",
                headers=ha,
                json={
                    "permiso_ids": [i for i in original if i != pid],
                    "confirmar_global": True,
                },
            ).status_code
            == 200
        )
        h = login(api, a, a["codigo"])
        url = f"/api/v1/usuarios/{uid}"
        if permiso == "usuarios:ver":
            r = api.get("/api/v1/usuarios/paginados", headers=h)
        elif permiso == "usuarios:crear":
            r = api.post("/api/v1/usuarios", headers=h, json=body())
        elif permiso == "usuarios:editar":
            r = api.put(url, headers=h, json=datos(body()))
        elif permiso == "usuarios:desactivar":
            r = api.patch(url + "/desactivar", headers=h)
        elif permiso == "usuarios:activar":
            r = api.patch(url + "/activar", headers=h)
        elif permiso == "roles:ver":
            r = api.get("/api/v1/acceso/catalogos", headers=h)
        elif permiso == "roles:asignar":
            r = api.post(url + f"/roles/{rol}", headers=h)
        elif permiso == "roles:retirar":
            r = api.patch(url + f"/roles/{rol}/desactivar", headers=h)
        else:
            r = api.get("/api/v1/bitacora", headers=h)
        assert r.status_code == 403, r.text
        rechazo = consulta(
            "SELECT * FROM bitacora WHERE usuario_id=%s AND accion='PERMISO_DENEGADO' ORDER BY id DESC LIMIT 1",
            (a["admin_usuario_id"],),
            True,
        )
        assert rechazo["empresa_id"] == a["id"] and rechazo["resultado"] == "BLOQUEADO"
    finally:
        assert (
            api.put(
                f"/api/v1/roles/{rol}/permisos",
                headers=ha,
                json={"permiso_ids": original, "confirmar_global": True},
            ).status_code
            == 200
        )


def test_rol_invalida_recuperacion_emitida_y_en_curso(api, empresas):
    from app.modules.autenticacion.repositories import (
        password_reset_repository as reset,
    )

    a, _, _, _ = empresas
    h = login(api, a, a["codigo"])
    uid, _, nombre = cliente(a)
    identidad = reset.obtener_usuario_por_identificador(nombre, a["id"])
    assert reset.guardar_token_reset(uid, "hash-sintetico", 15, a["id"], identidad)
    assert (
        api.post(
            f'/api/v1/usuarios/{uid}/roles/{rid("ADMINISTRADOR")}', headers=h
        ).status_code
        == 200
    )
    assert (
        reset.consumir_token_reset(uid, "hash-sintetico", "no-guardar", a["id"])
        is False
    )
    # Sin la espera de 60 s: la prueba debe fallar por versión, no por frecuencia.
    consulta(
        "UPDATE password_reset_token SET fecha_creacion=CURRENT_TIMESTAMP-INTERVAL '2 minutes' WHERE usuario_id=%s",
        (uid,),
    )
    assert (
        reset.guardar_token_reset(uid, "hash-en-curso", 15, a["id"], identidad) is False
    )


def test_repetir_operacion_no_revoca_de_nuevo_ni_duplica_eventos(api, empresas):
    a, _, _, _ = empresas
    h = login(api, a, a["codigo"])
    uid, _, nombre = cliente(a)
    assert api.patch(f"/api/v1/usuarios/{uid}/desactivar", headers=h).status_code == 200
    assert api.patch(f"/api/v1/usuarios/{uid}/activar", headers=h).status_code == 200
    hc = login(api, a, nombre)
    version = consulta("SELECT version_acceso FROM usuario WHERE id=%s", (uid,), True)[
        "version_acceso"
    ]
    consulta("UPDATE empresa SET estado='SUSPENDIDA' WHERE id=%s", (a["id"],))
    assert api.patch(f"/api/v1/usuarios/{uid}/activar", headers=h).status_code == 200
    assert api.get("/api/v1/perfil", headers=hc).status_code == 200
    assert (
        consulta("SELECT version_acceso FROM usuario WHERE id=%s", (uid,), True)[
            "version_acceso"
        ]
        == version
    )
    for accion in ("ACTIVAR_USUARIO", "DESACTIVAR_USUARIO"):
        assert (
            consulta(
                "SELECT count(*) n FROM bitacora WHERE objetivo_usuario_id=%s AND accion=%s",
                (uid, accion),
                True,
            )["n"]
            == 1
        )


def test_restauracion_empresa_conserva_auditoria_as_de_cuentas(
    api, empresas, tmp_path, monkeypatch
):
    from uuid import UUID
    from cryptography.fernet import Fernet
    from app.modules.administracion.services import respaldo_service as respaldos

    a, b, _, actor = empresas
    h = as_headers(api, actor)
    monkeypatch.setenv("STYLEAR_BACKUP_DIR", str(tmp_path / "privado"))
    monkeypatch.setenv("STYLEAR_BACKUP_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("STYLEAR_BACKUP_RETENTION_DAYS", "7")
    monkeypatch.setattr(respaldos, "STATIC", tmp_path / "static")
    # La cuenta y su evento AS se crean antes de la copia de empresa.
    r = api.post(
        "/api/v1/saas/usuarios",
        headers=h,
        params={"empresa_id": a["id"]},
        json=body("ADMINISTRADOR"),
    )
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    copia = respaldos.crear_respaldo(actor, a["id"])
    identificador = UUID(str(copia["id"]))
    previa = respaldos.previsualizar_restauracion(identificador, actor)
    posterior = api.post(
        "/api/v1/saas/usuarios",
        headers=h,
        params={"empresa_id": a["id"]},
        json=body("ADMINISTRADOR"),
    ).json()["id"]
    objetivos = [uid, posterior]
    eventos = consulta(
        "SELECT to_jsonb(b) fila FROM bitacora b WHERE empresa_id IS NULL AND objetivo_usuario_id=ANY(%s) ORDER BY id",
        (objetivos,),
    )
    usuarios_b = consulta(
        "SELECT to_jsonb(u) fila FROM usuario u WHERE empresa_id=%s ORDER BY id",
        (b["id"],),
    )
    consulta("UPDATE empresa SET estado='SUSPENDIDA' WHERE id=%s", (a["id"],))
    assert (
        respaldos.restaurar_respaldo(identificador, actor, previa["confirmacion"])[
            "estado"
        ]
        == "RESTAURADO"
    )
    assert (
        consulta(
            "SELECT to_jsonb(b) fila FROM bitacora b WHERE empresa_id IS NULL AND objetivo_usuario_id=ANY(%s) ORDER BY id",
            (objetivos,),
        )
        == eventos
    )
    assert (
        consulta(
            "SELECT to_jsonb(u) fila FROM usuario u WHERE empresa_id=%s ORDER BY id",
            (b["id"],),
        )
        == usuarios_b
    )
    assert consulta("SELECT id FROM usuario WHERE id=%s", (uid,), True)["id"] == uid
    assert consulta("SELECT id FROM usuario WHERE id=%s", (posterior,), True) is None


def test_rol_adicional_conservado_exige_confirmacion_y_revoca_sesiones(api, empresas):
    a, _, _, actor = empresas
    h = as_headers(api, actor)
    uid, _, nombre = cliente(a)
    rol = consulta(
        "INSERT INTO rol(nombre,descripcion) VALUES(%s,'Heredado') RETURNING id",
        ("HEREDADO_" + uuid4().hex[:8],),
        True,
    )["id"]
    consulta("INSERT INTO usuario_rol(usuario_id,rol_id) VALUES(%s,%s)", (uid, rol))
    hc = login(api, a, nombre)
    assert api.patch(f"/api/v1/roles/{rol}/desactivar", headers=h).status_code == 400
    assert (
        api.patch(
            f"/api/v1/roles/{rol}/desactivar?confirmar_global=true", headers=h
        ).status_code
        == 200
    )
    assert api.get("/api/v1/perfil", headers=hc).status_code == 401
    r = api.get("/api/v1/roles?estado=INACTIVOS", headers=h)
    assert any(x["id"] == rol and not x["configurable"] for x in r.json())
    assert (
        api.patch(
            f"/api/v1/roles/{rol}/activar?confirmar_global=true", headers=h
        ).status_code
        == 200
    )
    assert api.get("/api/v1/perfil", headers=login(api, a, nombre)).status_code == 200
    eventos = consulta(
        "SELECT descripcion FROM bitacora WHERE usuario_id=%s AND accion='EDITAR_PLANTILLA' AND descripcion LIKE %s",
        (actor, f"%ID {rol}%"),
    )
    assert len(eventos) == 2


def test_token_cu02_sin_version_sigue_valido_hasta_cambio_sensible(api, empresas):
    from app.core.security import crear_token_acceso, verificar_token_acceso

    a, _, _, _ = empresas
    uid, _, nombre = cliente(a)
    h = login(api, a, nombre)
    payload = verificar_token_acceso(h["Authorization"].split(" ", 1)[1])
    payload.pop("version_acceso")
    antiguo = {"Authorization": "Bearer " + crear_token_acceso(payload)}
    assert api.get("/api/v1/perfil", headers=antiguo).status_code == 200
    admin = login(api, a, a["codigo"])
    r = api.post(f'/api/v1/usuarios/{uid}/roles/{rid("ADMINISTRADOR")}', headers=admin)
    assert r.status_code == 200, r.text
    assert api.get("/api/v1/perfil", headers=antiguo).status_code == 401


def test_arranque_exige_migracion_cu04_y_no_solo_multitenant():
    from app.main import verificar_migracion_multitenant

    version = "2026_10_23_cu04_cu05_01"
    verificar_migracion_multitenant()
    try:
        consulta("DELETE FROM schema_migrations WHERE version=%s", (version,))
        with pytest.raises(RuntimeError, match="CU04/CU05"):
            verificar_migracion_multitenant()
    finally:
        consulta(
            "INSERT INTO schema_migrations(version,archivo) VALUES(%s,%s)",
            (version, "database/migracion_cu04_cu05_01.sql"),
        )
    verificar_migracion_multitenant()
