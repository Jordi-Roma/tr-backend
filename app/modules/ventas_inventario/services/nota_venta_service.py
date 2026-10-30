from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

from app.core.contexto_empresa import exigir_empresa_id
from app.modules.ventas_inventario.repositories.nota_venta_repository import obtener_nota
from app.modules.ventas_inventario.services.inventario_service import obtener_venta_service

DIRECTORIO_LOGOS = Path(__file__).resolve().parents[4]/'static'/'empresas'


def preparar_nota(usuario, venta_id):
    obtener_venta_service(usuario,venta_id)  # Empresa + sucursal antes de emitir/leer.
    try:
        return obtener_nota(venta_id,exigir_empresa_id(usuario))
    except ValueError as error:
        raise HTTPException(409,str(error)) from error


def generar_pdf(nota):
    datos = nota['datos']
    salida = BytesIO()
    styles = getSampleStyleSheet()
    p = lambda texto, estilo='Normal': Paragraph(escape(str(texto or '')),styles[estilo])
    empresa = datos['empresa']
    doc = SimpleDocTemplate(salida,pagesize=(21*cm,29.7*cm),
        leftMargin=1.7*cm,rightMargin=1.7*cm,topMargin=1.5*cm,bottomMargin=1.5*cm,
        title=f'Nota de venta {nota["numero"]} - {empresa}',author=empresa)
    contenido=[]
    config=datos.get('comprobante_config') or {}
    logo=config.get('logo_archivo')
    if logo and Path(logo).name == logo:
        ruta=DIRECTORIO_LOGOS/logo
        if ruta.is_file():
            imagen=Image(str(ruta),width=3*cm,height=2*cm,kind='proportional')
            contenido.append(imagen)
    contenido += [p(empresa,'Title'),p(f'NOTA DE VENTA N.º {nota["numero"]:08d}','Heading2'),
        p(f'Sucursal: {datos["sucursal"]}'),p(datos['direccion']),p(datos.get('telefono'))]
    fecha=datetime.fromisoformat(datos['fecha_venta'])
    if fecha.tzinfo:
        fecha=fecha.astimezone(ZoneInfo('America/La_Paz'))
    contenido += [p(f'Fecha: {fecha:%d/%m/%Y %H:%M}'),p(f'Venta: {datos["codigo"]}'),
        p(f'Cliente: {datos.get("cliente") or "Consumidor final"}'),p(f'Atendido por: {datos.get("vendedor") or "—"}'),Spacer(1,.5*cm)]
    filas=[[p(t) for t in ['Prenda / variante','Cant.','P. unitario','Descuento','Subtotal']]]
    for item in datos['detalles']:
        filas.append([p(f'{item["producto"]} · {item["talla"]} / {item["color"]}'),
            p(item['cantidad']),p(f'Bs {Decimal(item["precio_unitario"]):.2f}'),
            p(f'Bs {Decimal(item["descuento"]):.2f}'),p(f'Bs {Decimal(item["subtotal"]):.2f}')])
    tabla=Table(filas,colWidths=[7.1*cm,1.5*cm,3*cm,3*cm,3*cm],repeatRows=1,hAlign='LEFT')
    tabla.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8ecf0')),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),9),
        ('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#334155'))]))
    contenido += [tabla,Spacer(1,.5*cm),p(f'Subtotal: Bs {Decimal(datos["subtotal"]):.2f}'),
        p(f'Descuento / anticipo aplicado: Bs {Decimal(datos["descuento"]):.2f}'),
        p(f'Total de esta venta: Bs {Decimal(datos["total"]):.2f}','Heading2'),p(f'Método de pago: {datos.get("metodo_pago") or "—"}'),
        Spacer(1,.5*cm),p(config.get('condiciones') or 'Conserve esta nota para consultar las condiciones de cambios de la empresa.'),
        Spacer(1,.3*cm),p('Comprobante comercial. No es una factura fiscal.')]
    doc.build(contenido)
    return salida.getvalue()


def enviar_nota(usuario, venta_id):
    from app.core.email import enviar_correo_con_adjunto, usa_destino_fijo
    nota=preparar_nota(usuario,venta_id)
    datos=nota['datos']
    if not datos.get('correo') and not usa_destino_fijo():
        raise HTTPException(409,'La venta no tiene un cliente con correo registrado.')
    try:
        enviar_correo_con_adjunto(datos.get('correo'),f'Nota de venta {nota["numero"]} — {datos["empresa"]}',
            f'Adjuntamos su nota de venta de {datos["empresa"]}, sucursal {datos["sucursal"]}.',
            generar_pdf(nota),f'nota-venta-{nota["numero"]:08d}.pdf',datos['empresa'])
    except (ValueError,OSError) as error:
        raise HTTPException(503,'No se pudo enviar el correo. La venta sigue registrada y el PDF está disponible.') from error
    return {'mensaje':('Nota de venta enviada al correo de recepción configurado.'
                      if usa_destino_fijo() else 'Nota de venta enviada al correo registrado del cliente.')}
