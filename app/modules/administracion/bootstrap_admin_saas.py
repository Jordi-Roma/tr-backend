"""Provisionamiento interactivo unico del primer Administrador SaaS.

Uso supervisado: python -m app.modules.administracion.bootstrap_admin_saas
Nunca ejecutar automaticamente durante un despliegue ni guardar la clave en Git.
"""

from getpass import getpass

from app.core.security import hashear_password
from app.database.connection import get_connection


def main() -> None:
    print("Alta inicial de ADMIN_SAAS (solo entorno autorizado).")
    nombre = input("Nombre: ").strip()
    apellido = input("Apellido: ").strip()
    username = input("Username nuevo: ").strip().lower()
    correo = input("Correo nuevo: ").strip().lower()
    password = getpass("Contrasena nueva: ")
    if not nombre or not apellido or len(username) < 4 or "@" not in correo:
        raise ValueError("Datos de identidad invalidos.")
    password_hash = hashear_password(password)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext('bootstrap_admin_saas'))")
            cur.execute(
                """SELECT 1 FROM usuario_rol ur
                   JOIN rol r ON r.id=ur.rol_id
                   WHERE r.nombre='ADMIN_SAAS' AND ur.activo=TRUE LIMIT 1"""
            )
            if cur.fetchone() is not None:
                raise ValueError("Ya existe un ADMIN_SAAS activo; no se crea otro.")
            cur.execute(
                """INSERT INTO usuario (nombre,apellido,username,correo,password_hash,empresa_id)
                   VALUES (%s,%s,%s,%s,%s,NULL) RETURNING id""",
                (nombre, apellido, username, correo, password_hash),
            )
            usuario_id = int(cur.fetchone()[0])
            cur.execute(
                """INSERT INTO usuario_rol (usuario_id,rol_id)
                   SELECT %s,id FROM rol WHERE nombre='ADMIN_SAAS' AND activo=TRUE
                   RETURNING rol_id""",
                (usuario_id,),
            )
            if cur.fetchone() is None:
                raise ValueError("La migracion de ADMIN_SAAS no esta aplicada.")
        conn.commit()
        print(f"ADMIN_SAAS creado con id={usuario_id}. La clave no se muestra.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
