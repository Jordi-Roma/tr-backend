from html import escape
from io import BytesIO
import math

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak

METRICAS = {'muestras': 'Muestras evaluadas', 'mae': 'Error absoluto medio (MAE)',
            'rmse': 'Raíz del error cuadrático medio (RMSE)', 'mae_referencia': 'MAE de referencia',
            'unidad': 'Unidad del error', 'silhouette': 'Separación interna (silhouette)',
            'ari_medio': 'Comparación entre semillas (ARI)', 'grupos': 'Grupos encontrados',
            'clientes_analizados': 'Clientes analizados', 'evaluacion': 'Tipo de evaluación'}


def _valor_metrica(v):
    return {'UNIDADES_POR_PRODUCTO_SUCURSAL_SEMANA': 'Unidades por producto, sucursal y semana',
            'INTERNA_SOBRE_LA_MISMA_INSTANTANEA': 'Interna sobre la misma instantánea'}.get(v, v) if isinstance(v, str) else v


def _columnas(tipo):
    return ([('fecha_corte', 'Corte'), ('objetivo_hasta', 'Objetivo hasta'), ('sucursal', 'Sucursal'),
             ('producto_id', 'Producto'), ('unidades_reales', 'Observadas'), ('unidades_predichas', 'Predichas'),
             ('referencia_semana_anterior', 'Referencia')]
            if tipo == 'PREDICCIONES' else
            [('cliente_id', 'Cliente'), ('grupo', 'Grupo'), ('recencia_dias', 'Recencia días'),
             ('frecuencia_compras', 'Compras'), ('gasto_bs', 'Gasto Bs')])


def _filas(reporte):
    return [{**r, **({'gasto_bs': r['gasto_centavos'] / 100} if 'gasto_centavos' in r else {})}
            for r in reporte['datos']['filas']]


def _metadatos(r):
    d = r['datos']
    nota = ('Evaluación histórica de semanas de prueba; no es pronóstico oficial vigente.'
            if r['tipo'] == 'PREDICCIONES' else
            'Evaluación interna de la instantánea. Silhouette no es exactitud; ARI compara semillas, no estabilidad futura.')
    filas = [('Empresa', r['empresa']), ('Origen', 'DEMOSTRACIÓN SINTÉTICA' if d['origen'] == 'DEMOSTRACION' else 'OFICIAL'),
            ('Estado', d['estado']), ('Generado', r['generado_en']), ('Alcance', 'Filtro completo, no solo página visible'),
            ('Fuente', d.get('fuente_datos') or 'Artefactos de modelos del servidor'),
            ('Auditoría de fuente', d.get('evaluado_en') or 'No corresponde'),
            ('Modelo entrenado', d.get('entrenado_en') or 'Sin modelo disponible'),
            ('Sucursales autorizadas', r.get('alcance_sucursales', 'Según sesión')),
            ('Nota', nota), ('Advertencia', d['advertencia']), ('Dataset', d.get('dataset_id', 'Sin modelo disponible')),
            ('Corte de segmentación', d.get('fecha_corte', 'No corresponde')),
            ('Ventana días', d.get('ventana_dias', 'No corresponde')),
            ('Sin compras en ventana', d.get('clientes_sin_compras_ventana', 'No corresponde')),
            *[(f'Filtro: {k}', str(v)) for k, v in r['filtros'].items()]]
    return [f for f in filas if (r['tipo'] == 'SEGMENTOS' or f[0] not in
            {'Corte de segmentación', 'Ventana días', 'Sin compras en ventana'}) and
            (f[0] != 'Auditoría de fuente' or d.get('evaluado_en'))]


def _seguro(v):
    if isinstance(v, str):
        v = ''.join(c for c in v if ord(c) >= 32 or c in '\n\t')
        if v.lstrip().startswith(('=', '+', '-', '@')):
            return "'" + v
    return v


def crear_excel_ml(reporte):
    wb = Workbook()
    resumen = wb.active
    resumen.title = 'Resumen'
    resumen.append(['StyleAR', reporte['titulo']])
    for k, v in _metadatos(reporte): resumen.append([k, _seguro(v)])
    metricas = wb.create_sheet('Métricas')
    metricas.append(['Indicador', 'Valor'])
    for k, v in (reporte['datos'].get('metricas') or {}).items(): metricas.append([METRICAS.get(k, k), _seguro(_valor_metrica(v))])
    if not reporte['datos'].get('metricas'): metricas.append(['Disponibilidad', 'Sin modelo o resultados para el filtro'])
    datos = wb.create_sheet('Datos')
    columnas = _columnas(reporte['tipo'])
    datos.append([titulo for _, titulo in columnas])
    for fila in _filas(reporte): datos.append([_seguro(fila.get(k, '')) for k, _ in columnas])
    datos.freeze_panes = 'A2'
    datos.auto_filter.ref = datos.dimensions
    grafico = wb.create_sheet('Gráfico')
    if reporte['tipo'] == 'PREDICCIONES':
        grafico.append(['Fecha de corte', 'Observadas', 'Predichas', 'Referencia'])
        for p in reporte['datos']['serie']:
            grafico.append([p['fecha_corte'], p['unidades_reales'], p['unidades_predichas'], p['referencia_semana_anterior']])
        chart = LineChart()
        chart.title = 'Evaluación histórica: unidades semanales'
        chart.y_axis.title = 'Unidades'
        chart.x_axis.title = 'Fecha de corte'
    else:
        grafico.append(['Grupo', 'Clientes', 'Recencia media días', 'Compras medias', 'Gasto medio Bs', 'Descripción'])
        for p in reporte['datos']['perfiles']:
            grafico.append([_seguro(p['nombre']), p['clientes'], p['recencia_media_dias'], p['frecuencia_media_compras'],
                            p['gasto_medio_centavos'] / 100, _seguro(p['descripcion'])])
        chart = BarChart()
        chart.title = 'Clientes por grupo (empresa completa)'
        chart.y_axis.title = 'Clientes'
    if grafico.max_row > 1:
        columnas_grafico = 4 if reporte['tipo'] == 'PREDICCIONES' else 2
        chart.add_data(Reference(grafico, min_col=2, max_col=columnas_grafico, min_row=1, max_row=grafico.max_row), titles_from_data=True)
        chart.set_categories(Reference(grafico, min_col=1, min_row=2, max_row=grafico.max_row))
        chart.width, chart.height = 22, 11
        grafico.add_chart(chart, 'H2')
    for sheet in wb:
        sheet.freeze_panes = 'A2'
        for cell in sheet[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='344C2B')
        for columna in sheet.columns:
            sheet.column_dimensions[columna[0].column_letter].width = min(70, max(16, max(len(str(c.value or '')) for c in columna) + 2))
        for fila in sheet:
            for cell in fila:
                if isinstance(cell.value, str): cell.value = _seguro(cell.value)
    salida = BytesIO(); wb.save(salida)
    return salida.getvalue()


def crear_pdf_ml(reporte):
    salida = BytesIO()
    ancho, alto = landscape(A4)
    doc = SimpleDocTemplate(salida, pagesize=(ancho, alto), leftMargin=32, rightMargin=32, topMargin=40, bottomMargin=36)
    estilos = getSampleStyleSheet()
    compacto = ParagraphStyle('MLCompacto', parent=estilos['Normal'], fontSize=8, leading=10)
    celda = ParagraphStyle('MLCelda', parent=compacto, fontSize=7.5, leading=9)
    cabecera = ParagraphStyle('MLCabecera', parent=celda, textColor=colors.white)
    story = [Paragraph('StyleAR · ' + escape(reporte['titulo']), estilos['Title']), Spacer(1, 8)]
    for k, v in _metadatos(reporte):
        story.append(Paragraph(escape(f'{k}: {v}'), compacto))
    story.append(Spacer(1, 8))
    for k, v in (reporte['datos'].get('metricas') or {}).items():
        valor = f'{v:.3f}' if isinstance(v, float) else _valor_metrica(v)
        story.append(Paragraph(escape(f'{METRICAS.get(k, k)}: {valor}'), compacto))
    d = reporte['datos']
    if d.get('serie'):
        serie = d['serie']; dibujo = Drawing(750, 180); chart = LinePlot()
        chart.x, chart.y, chart.width, chart.height = 35, 35, 700, 125
        campos = ('unidades_reales', 'unidades_predichas', 'referencia_semana_anterior')
        chart.data = [[(i, float(p[c])) for i, p in enumerate(serie)] for c in campos]
        chart.xValueAxis.valueMin = 0; chart.xValueAxis.valueMax = max(1, len(serie) - 1)
        chart.xValueAxis.valueSteps = list(range(0, len(serie), max(1, math.ceil(len(serie) / 8))))
        chart.xValueAxis.labelTextFormat = lambda x: serie[min(len(serie)-1, int(x))]['fecha_corte']
        chart.xValueAxis.labels.fontSize = 7
        chart.yValueAxis.valueMin = 0
        chart.yValueAxis.valueMax = max(1, max(float(p[c]) for p in serie for c in campos))
        for i, color in enumerate(('#344c2b', '#245a81', '#754565')): chart.lines[i].strokeColor = colors.HexColor(color)
        chart.lines[1].strokeDashArray = [6, 3]; chart.lines[2].strokeDashArray = [2, 3]
        dibujo.add(chart); story.extend([Spacer(1, 8), dibujo,
            Paragraph('Observadas: verde continuo · Predichas: azul con guiones · Referencia: violeta con puntos. Totales semanales del filtro completo.', compacto)])
    if d.get('perfiles'):
        story.append(Paragraph('Perfiles y gráfico de la empresa completa; la tabla respeta el filtro de grupo.', compacto))
        dibujo = Drawing(750, 150); chart = HorizontalBarChart()
        chart.x, chart.y, chart.width, chart.height = 70, 25, 640, 110
        chart.data = [[p['clientes'] for p in d['perfiles']]]
        chart.categoryAxis.categoryNames = [p['nombre'] for p in d['perfiles']]
        chart.valueAxis.valueMin = 0; chart.bars[0].fillColor = colors.HexColor('#344c2b')
        dibujo.add(chart); story.extend([Spacer(1, 8), dibujo])
        for p in d['perfiles']:
            story.append(Paragraph(escape(f"{p['nombre']}: {p['clientes']} clientes. {p['descripcion']}"), compacto))
    if d['filas']: story.append(PageBreak())
    story.extend([Spacer(1, 12), Paragraph(f"Detalle completo del filtro: {d['total_filas']} filas", estilos['Heading2'])])
    columnas = _columnas(reporte['tipo'])
    filas = [[Paragraph(escape(titulo), cabecera) for _, titulo in columnas]]
    for fila in _filas(reporte):
        valores = []
        for k, _ in columnas:
            valor = fila.get(k, '')
            if isinstance(valor, float): valor = f'{valor:.2f}'
            valores.append(Paragraph(escape(str(valor)), celda))
        filas.append(valores)
    if len(filas) == 1:
        story.append(Paragraph('Sin modelo o resultados para el origen y filtros solicitados. No se sustituyeron por datos de demostración.', compacto))
    else:
        tabla = Table(filas, colWidths=[(ancho - 64) / len(columnas)] * len(columnas), repeatRows=1)
        tabla.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#344c2b')),
                                  ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f4ef')]),
                                  ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 6),
                                  ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
        story.append(tabla)
    def pagina(canvas, documento):
        canvas.saveState(); canvas.setFont('Helvetica', 8)
        origen = 'DEMOSTRACION SINTETICA' if d['origen'] == 'DEMOSTRACION' else 'OFICIAL'
        canvas.drawString(32, alto - 22, f"StyleAR | {origen} | {reporte['empresa']}")
        canvas.drawRightString(ancho - 32, 20, f'Página {documento.page}')
        canvas.restoreState()
    doc.build(story, onFirstPage=pagina, onLaterPages=pagina)
    return salida.getvalue()
