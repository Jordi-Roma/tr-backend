from io import BytesIO
from html import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def crear_pdf(reporte: dict[str, object]) -> bytes:
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), leftMargin=28, rightMargin=28, topMargin=28, bottomMargin=28)
    styles = getSampleStyleSheet()
    story = [Paragraph("StyleAR · " + escape(str(reporte["titulo"])), styles["Title"]), Spacer(1, 10)]
    filtros = reporte["filtros_efectivos"]
    story.append(Paragraph(escape(f"Periodo: {filtros['fecha_desde']} al {filtros['fecha_hasta']} · Sucursal: {filtros['sucursal']} · Generado: {reporte['generado_en']}"), styles["Normal"]))
    if reporte.get("nota"):
        story.append(Spacer(1, 6))
        story.append(Paragraph(escape(str(reporte["nota"])), styles["Normal"]))
    story.append(Spacer(1, 14))
    for indicador in reporte["indicadores"]:
        story.append(Paragraph(escape(f"{indicador['label']}: {indicador['valor']}"), styles["Normal"]))
    story.append(Spacer(1, 12))
    serie = reporte["serie_grafico"][:12]
    if serie:
        drawing = Drawing(720, 185)
        chart = VerticalBarChart()
        chart.x, chart.y, chart.width, chart.height = 35, 45, 650, 115
        chart.data = [[float(item["valor"]) for item in serie]]
        chart.categoryAxis.categoryNames = [str(item["label"])[:12] for item in serie]
        chart.categoryAxis.labels.fontSize = 7
        chart.valueAxis.valueMin = 0
        chart.bars[0].fillColor = colors.HexColor("#829165")
        drawing.add(chart)
        story.append(drawing)
        story.append(Spacer(1, 10))
    columnas = reporte["columnas"]
    if not columnas:
        story.append(Paragraph("Sin datos para los filtros seleccionados.", styles["Normal"]))
    else:
        headers = [str(c["label"]) for c in columnas]
        rows = [headers]
        for fila in reporte["filas"]:
            rows.append([Paragraph(escape(str(fila.get(c["key"], "") or "")), styles["BodyText"]) for c in columnas])
        width = (landscape(A4)[0] - 56) / len(columnas)
        table = Table(rows, colWidths=[width] * len(columnas), repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#263043")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f5f1")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.append(table)
    doc.build(story)
    return output.getvalue()
