from io import BytesIO
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File
from pydantic import BaseModel, Field
from psycopg2.extras import Json

from app.core.contexto_empresa import exigir_empresa_id
from app.modules.administracion.dependencies.empleado_access import requerir_admin_o_encargado_o_cajero
from app.modules.autenticacion.repositories.perfil_repository import _transaccion
from app.modules.ventas_inventario.services.inventario_service import _sucursal_permitida
from app.modules.ventas_inventario.services.nota_venta_service import preparar_nota, generar_pdf, enviar_nota

router=APIRouter(prefix='/api/v1/ventas-presenciales',tags=['Notas de venta'])


def administrador(actor=Depends(requerir_admin_o_encargado_o_cajero)):
    if 'ADMINISTRADOR' not in actor.get('roles',[]):
        raise HTTPException(403,'Solo el administrador de la empresa configura sus comprobantes.')
    return actor


class ConfiguracionComprobante(BaseModel):
    condiciones: str = Field(default='',max_length=1500)


@router.get('/opciones')
def opciones(sucursal_id:int|None=None,q:str='',actor=Depends(requerir_admin_o_encargado_o_cajero)):
    from app.modules.reservas.repositories.carrito_repository import _obtener_precio_final_variante_cursor
    empresa=exigir_empresa_id(actor)
    sucursal=_sucursal_permitida(actor,sucursal_id)
    with _transaccion() as cur:
        cur.execute('''SELECT id,nombre FROM sucursal WHERE empresa_id=%s AND activo
            AND (%s::bigint IS NULL OR id=%s) ORDER BY nombre,id''',(empresa,sucursal,sucursal))
        sucursales=[dict(r) for r in cur.fetchall()]
        cur.execute('''SELECT pv.id,p.nombre AS producto_nombre,t.nombre AS talla_nombre,
            c.nombre AS color_nombre,pv.sku,
            COALESCE(sum(CASE WHEN s.id IS NOT NULL THEN greatest(i.stock_disponible-i.stock_reservado,0) ELSE 0 END),0)::int AS stock
            FROM producto_variante pv JOIN producto p ON p.id=pv.producto_id AND p.empresa_id=pv.empresa_id
            JOIN talla t ON t.id=pv.talla_id AND t.empresa_id=pv.empresa_id
            JOIN color c ON c.id=pv.color_id AND c.empresa_id=pv.empresa_id
            LEFT JOIN inventario_sucursal i ON i.producto_variante_id=pv.id AND i.empresa_id=pv.empresa_id
                AND i.activo AND (%s::bigint IS NULL OR i.sucursal_id=%s)
            LEFT JOIN sucursal s ON s.id=i.sucursal_id AND s.empresa_id=pv.empresa_id AND s.activo
            WHERE pv.empresa_id=%s AND pv.activo AND p.activo
                AND (p.nombre ILIKE %s OR pv.sku ILIKE %s)
            GROUP BY pv.id,p.nombre,t.nombre,c.nombre ORDER BY p.nombre,pv.id LIMIT 100''',
            (sucursal,sucursal,empresa,'%'+q[:100]+'%','%'+q[:100]+'%'))
        variantes=[dict(r) for r in cur.fetchall()]
        for variante in variantes:
            variante['precio']=_obtener_precio_final_variante_cursor(cur,variante['id'],sucursal)
    return {'sucursales':sucursales,'variantes':variantes,
            'puede_descontar':bool(set(actor['roles']).intersection({'ADMINISTRADOR','ENCARGADO_SUCURSAL'})),
            'sucursal_asignada':sucursal}


@router.get('/clientes-opciones')
def clientes(q:str='',actor=Depends(requerir_admin_o_encargado_o_cajero)):
    empresa=exigir_empresa_id(actor)
    with _transaccion() as cur:
        cur.execute('''SELECT c.id,concat_ws(' ',u.nombre,u.apellido) AS nombre,u.correo
            FROM cliente c JOIN usuario u ON u.id=c.usuario_id AND u.empresa_id=c.empresa_id
            WHERE c.empresa_id=%s AND c.activo AND u.activo
                AND (u.nombre ILIKE %s OR u.apellido ILIKE %s OR u.correo ILIKE %s)
            ORDER BY u.nombre,c.id LIMIT 30''', (empresa,*(['%'+q[:100]+'%']*3)))
        return [dict(r) for r in cur.fetchall()]


@router.get('/configuracion-comprobante')
def configuracion(actor=Depends(administrador)):
    with _transaccion() as cur:
        cur.execute('SELECT nombre,comprobante_config FROM empresa WHERE id=%s',(exigir_empresa_id(actor),))
        return dict(cur.fetchone())


@router.patch('/configuracion-comprobante')
def guardar_configuracion(datos:ConfiguracionComprobante,actor=Depends(administrador)):
    with _transaccion() as cur:
        cur.execute("UPDATE empresa SET comprobante_config=comprobante_config || %s WHERE id=%s",
                    (Json(datos.model_dump()),exigir_empresa_id(actor)))
    return {'mensaje':'Condiciones de la empresa guardadas para futuras notas.'}


@router.post('/configuracion-comprobante/logo')
async def subir_logo(archivo:UploadFile=File(...),actor=Depends(administrador)):
    from PIL import Image, UnidentifiedImageError
    contenido=await archivo.read(2*1024*1024+1)
    if len(contenido)>2*1024*1024:
        raise HTTPException(413,'El logo debe pesar hasta 2 MB.')
    try:
        imagen=Image.open(BytesIO(contenido))
        if imagen.format not in {'PNG','JPEG'} or imagen.width*imagen.height>10_000_000:
            raise ValueError()
        imagen.load()
        imagen=imagen.convert('RGBA')
        imagen.thumbnail((1000,1000))
    except (UnidentifiedImageError,ValueError,OSError,Image.DecompressionBombError) as error:
        raise HTTPException(422,'Selecciona una imagen PNG o JPG válida.') from error
    empresa=exigir_empresa_id(actor)
    nombre=f'{empresa}-{uuid4().hex}.png'
    from app.modules.ventas_inventario.services import nota_venta_service
    carpeta=nota_venta_service.DIRECTORIO_LOGOS
    carpeta.mkdir(parents=True,exist_ok=True)
    imagen.save(carpeta/nombre,format='PNG')
    with _transaccion() as cur:
        cur.execute('UPDATE empresa SET comprobante_config=comprobante_config || %s WHERE id=%s',
                    (Json({'logo_archivo':nombre,'logo_url':f'/static/empresas/{nombre}'}),empresa))
    return {'mensaje':'Logo de la empresa guardado para futuras notas.'}


@router.get('/{venta_id}/nota.pdf')
def descargar(venta_id:int,actor=Depends(requerir_admin_o_encargado_o_cajero)):
    nota=preparar_nota(actor,venta_id)
    return Response(generar_pdf(nota),media_type='application/pdf',
        headers={'Content-Disposition':f'attachment; filename="nota-venta-{nota["numero"]:08d}.pdf"'})


@router.post('/{venta_id}/nota/correo')
def correo(venta_id:int,actor=Depends(requerir_admin_o_encargado_o_cajero)):
    return enviar_nota(actor,venta_id)
