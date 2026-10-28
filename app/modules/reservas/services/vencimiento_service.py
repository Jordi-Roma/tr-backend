"""Liberación idempotente de reservas, también cuando no hay clientes conectados."""
import asyncio
import logging
from psycopg2.extras import RealDictCursor
from app.database.connection import get_connection

log=logging.getLogger(__name__)


def vencer_reservas(empresa_id=None):
    from app.modules.reservas.repositories.reserva_repository import _vencer_reservas_expiradas_cursor
    conn=get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if empresa_id is None:
                cur.execute('''SELECT DISTINCT empresa_id FROM reserva WHERE activo
                    AND estado NOT IN ('COMPLETADA','CANCELADA','VENCIDA')
                    AND fecha_expiracion<CURRENT_TIMESTAMP ORDER BY empresa_id''')
                empresas=[r['empresa_id'] for r in cur.fetchall()]
            else:
                empresas=[empresa_id]
            for empresa in empresas:
                _vencer_reservas_expiradas_cursor(cur,empresa)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


async def ejecutar_vencimientos():
    while True:
        await asyncio.sleep(60)
        try:
            await asyncio.to_thread(vencer_reservas)
        except Exception:
            log.exception('No se pudieron liberar las reservas vencidas; se reintentará.')
