import os
import math
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

def parsear_txt_dhl_logic(filepath):
    with open(filepath, 'r', encoding='latin-1', errors='replace') as f: lines = f.readlines()
    records = []; current_record = None
    for line in lines:
        line_str = line.replace('\n', '').replace('\r', '')
        if len(line_str) > 20 and line_str[0:4].strip().isdigit() and line_str[6:16].strip().isalnum():
            if current_record: records.append(current_record)
            guia = line_str[6:18].strip(); bloque_datos = line_str[18:50].strip().split(); bultos = 1; peso_val = 1.0
            if len(bloque_datos) >= 1:
                bultos_str = bloque_datos[0].split('/')[0]
                if bultos_str.isdigit(): bultos = int(bultos_str)
            if len(bloque_datos) >= 2:
                peso_str = bloque_datos[1].replace(',', '.')
                try: peso_val = float(peso_str)
                except: peso_val = 1.0 
            consignee = line_str[94:119].strip() if len(line_str) >= 94 else ""
            current_record = {'guia': guia, 'bultos': bultos, 'peso': peso_val, 'consignee_lines': [consignee] if consignee else []}
        elif current_record:
            if "***** END OF REPORT" in line_str: break
            consignee = line_str[94:119].strip() if len(line_str) >= 94 else ""
            if consignee: current_record['consignee_lines'].append(consignee)
    if current_record: records.append(current_record)
    
    ops_a_guardar = []
    for r in records:
        lines = r['consignee_lines']; nombre = lines[0] if lines else "SIN NOMBRE"; telefono = ""; domicilio_parts = []
        for l in lines[1:]:
            if "TEL.:" in l: telefono = l.split("TEL.:")[1].strip()
            elif "TAX NO.:" in l: continue
            else: domicilio_parts.append(l)
        domicilio = " ".join(domicilio_parts).strip()
        if not domicilio: domicilio = "SIN DOMICILIO"
        ops_a_guardar.append({'guia': r['guia'], 'bultos': r['bultos'], 'peso': r.get('peso', 1.0), 'destinatario': nombre, 'domicilio': domicilio, 'celular': telefono})
    return ops_a_guardar

def crear_pdf_retiro(nombre_archivo, op):
    doc = SimpleDocTemplate(nombre_archivo, pagesize=portrait(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []; styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle(name='TituloCentro', parent=styles['Heading1'], alignment=TA_CENTER)
    elements.append(Paragraph(f"ORDEN DE RETIRO - E.K. LOGISTICA", titulo_style)); elements.append(Spacer(1, 20))
    data = [['FECHA:', op.fecha_ingreso.strftime("%d/%m/%Y")], ['N° ORDEN/GUÍA:', op.guia_remito or f"RET-{op.id}"], ['CLIENTE:', op.destinatario], ['DOMICILIO:', f"{op.domicilio} ({op.localidad})"], ['BULTOS:', str(op.bultos)], ['OBSERVACIONES:', op.info_intercambio or "Sin observaciones"]]
    t = Table(data, colWidths=[150, 300]); t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('BACKGROUND', (0,0), (0,-1), colors.lightgrey), ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold')]))
    elements.append(t); elements.append(Spacer(1, 50)); elements.append(Paragraph("______________________________", TA_CENTER)); elements.append(Paragraph("Firma del Cliente / Remitente", TA_CENTER))
    doc.build(elements)

def crear_pdf_ruta(nombre_archivo, ops, sucursal, chofer, usuario, fecha_generacion):
    doc = SimpleDocTemplate(nombre_archivo, pagesize=landscape(A4), rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=25)
    elements = []; styles = getSampleStyleSheet()
    estilo_celda = ParagraphStyle(name='Celda', parent=styles['Normal'], fontSize=8, leading=9)
    estilo_celda_centro = ParagraphStyle(name='CeldaCentro', parent=styles['Normal'], fontSize=8, leading=9, alignment=TA_CENTER)
    estilo_titulo = ParagraphStyle(name='Titulo', parent=styles['Heading1'], alignment=1, fontSize=14, spaceAfter=5)
    
    if os.path.exists("logo.png"): elements.append(Image("logo.png", width=100, height=40))
    
    titulo_combinado = f"HOJA DE RUTA - {sucursal.upper()} <font size=11>(Chofer: {chofer.upper()})</font>"
    elements.append(Paragraph(titulo_combinado, estilo_titulo)); elements.append(Spacer(1, 5))
    
    entregas = [op for op in ops if "Retiro" not in (op.tipo_servicio or "")]
    retiros = [op for op in ops if "Retiro" in (op.tipo_servicio or "")]
    
    entregas.sort(key=lambda x: (x.proveedor.lower(), x.destinatario.lower()))
    retiros.sort(key=lambda x: (x.proveedor.lower(), x.destinatario.lower()))
    
    tiene_obs = any(op.es_contra_reembolso or (op.info_intercambio and op.info_intercambio.strip() != "") for op in ops)
    
    encabezados = ['OK', 'GUÍA / REMITO', 'PROVEEDOR', 'DESTINATARIO', 'TELÉFONO', 'DOMICILIO', 'BULTOS']
    if tiene_obs: encabezados.append('OBS / COBRO')
        
    data = [encabezados]
    
    estilos_tabla = [
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (3,1), (3,-1), 'LEFT'), 
        ('ALIGN', (5,1), (5,-1), 'LEFT'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]
    
    current_row = 1
    
    def agregar_filas(lista_ops, es_retiro=False):
        nonlocal current_row
        for op in lista_ops:
            prefijo = "<b>[RET]</b> " if es_retiro else ""
            guia_txt = Paragraph(f"{prefijo}{op.guia_remito or '-'}", estilo_celda_centro)
            
            prov_txt = Paragraph(f"{op.proveedor}", estilo_celda_centro)
            dest_txt = Paragraph(f"<b>{op.destinatario}</b>", estilo_celda)
            tel_txt = Paragraph(f"{op.celular or '-'}", estilo_celda_centro)
            dom_txt = Paragraph(f"{op.domicilio} - <b>{op.localidad}</b>", estilo_celda)
            
            det_b = str(op.bultos)
            if op.bultos_frio and op.bultos_frio > 0 and op.bultos_frio < op.bultos: det_b += f" <br/>({op.bultos-op.bultos_frio}C/{op.bultos_frio}R)"
            elif op.bultos_frio == op.bultos: det_b += " <br/>(FRIO)"
            bultos_p = Paragraph(f"<b>{det_b}</b>", estilo_celda_centro)
            
            checkbox = Paragraph("<font size=12>O</font>", estilo_celda_centro)
            fila = [checkbox, guia_txt, prov_txt, dest_txt, tel_txt, dom_txt, bultos_p]
            
            if tiene_obs:
                obs_str = ""
                if op.es_contra_reembolso:
                    if op.monto_recaudacion > 0: obs_str += f"<b>COBRAR: $ {op.monto_recaudacion:,.0f}</b>"
                    if op.info_intercambio:
                        if obs_str: obs_str += " | "
                        obs_str += f"{op.info_intercambio}"
                fila.append(Paragraph(obs_str, estilo_celda_centro))
                
            data.append(fila)
            if current_row % 2 == 0:
                estilos_tabla.append(('BACKGROUND', (0, current_row), (-1, current_row), colors.whitesmoke))
            current_row += 1

    agregar_filas(entregas, False)
    
    if retiros:
        separador = [''] * len(encabezados)
        separador[0] = Paragraph("<font size=10><b>⬇️ ZONA DE RETIROS (RECOLECCIÓN) ⬇️</b></font>", estilo_celda_centro)
        data.append(separador)
        estilos_tabla.append(('SPAN', (0, current_row), (-1, current_row)))
        estilos_tabla.append(('BACKGROUND', (0, current_row), (-1, current_row), colors.silver))
        current_row += 1
        
        agregar_filas(retiros, True)

    if tiene_obs: anchos = [25, 100, 80, 130, 75, 195, 50, 147]
    else: anchos = [25, 110, 95, 170, 80, 252, 70]

    t = Table(data, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle(estilos_tabla))
    elements.append(t)
    
    def add_footer(canvas, doc): 
        canvas.saveState()
        canvas.setFont('Helvetica-Bold', 9)
        page_width, _ = landscape(A4)
        footer_text = f"TOTAL ENTREGAS: {len(entregas)}   |   TOTAL RETIROS: {len(retiros)}   |   Generado por: {usuario}   |   Fecha: {fecha_generacion}   |   Pág. {doc.page}"
        canvas.drawCentredString(page_width / 2.0, 15, footer_text)
        canvas.restoreState()
        
    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)

def crear_pdf_tercerizados(nombre_archivo, ops, sucursal, transporte, usuario, fecha_generacion):
    doc = SimpleDocTemplate(nombre_archivo, pagesize=landscape(A4), rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=25)
    elements = []; styles = getSampleStyleSheet()
    estilo_celda = ParagraphStyle(name='Celda', parent=styles['Normal'], fontSize=8, leading=9)
    estilo_celda_centro = ParagraphStyle(name='CeldaCentro', parent=styles['Normal'], fontSize=8, leading=9, alignment=TA_CENTER)
    estilo_titulo = ParagraphStyle(name='Titulo', parent=styles['Heading1'], alignment=1, fontSize=14, spaceAfter=5)
    
    titulo_combinado = f"REMITO DE CARGA TERCERIZADA - {sucursal.upper()} <font size=11>(Empresa: {transporte.upper()})</font>"
    elements.append(Paragraph(titulo_combinado, estilo_titulo)); elements.append(Spacer(1, 10))
    
    entregas = [op for op in ops if "Retiro" not in (op.tipo_servicio or "")]
    retiros = [op for op in ops if "Retiro" in (op.tipo_servicio or "")]
    entregas.sort(key=lambda x: (x.proveedor.lower(), x.destinatario.lower()))
    retiros.sort(key=lambda x: (x.proveedor.lower(), x.destinatario.lower()))
    
    encabezados = ['OK', 'GUÍA / REMITO', 'DESTINATARIO', 'TELÉFONO', 'DOMICILIO', 'BULTOS']
    data = [encabezados]
    
    estilos_tabla_t = [
        ('GRID', (0,0), (-1,-1), 0.5, colors.black), 
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey), 
        ('TEXTCOLOR', (0,0), (-1,0), colors.black), 
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9), 
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), 
        ('ALIGN', (0,0), (-1,-1), 'CENTER'), 
        ('ALIGN', (2,1), (2,-1), 'LEFT'),
        ('ALIGN', (4,1), (4,-1), 'LEFT'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]
    
    current_row = 1
    def agregar_filas_t(lista_ops, es_retiro=False):
        nonlocal current_row
        for op in lista_ops:
            det_b = str(op.bultos)
            if op.bultos_frio and op.bultos_frio > 0: det_b += f" ({op.bultos-op.bultos_frio}C/{op.bultos_frio}R)"
            
            prefijo = "<b>[RET]</b> " if es_retiro else ""
            guia_txt = Paragraph(f"{prefijo}{op.guia_remito or '-'}", estilo_celda_centro)
            dest_txt = Paragraph(f"<b>{op.destinatario}</b>", estilo_celda)
            tel_txt = Paragraph(f"{op.celular or '-'}", estilo_celda_centro)
            dom_txt = Paragraph(f"{op.domicilio} - <b>{op.localidad}</b>", estilo_celda)
            bultos_p = Paragraph(f"<b>{det_b}</b>", estilo_celda_centro)
            
            data.append([Paragraph("<font size=12>O</font>", estilo_celda_centro), guia_txt, dest_txt, tel_txt, dom_txt, bultos_p])
            if current_row % 2 == 0: estilos_tabla_t.append(('BACKGROUND', (0, current_row), (-1, current_row), colors.whitesmoke))
            current_row += 1

    agregar_filas_t(entregas, False)
    
    if retiros:
        separador = [''] * len(encabezados)
        separador[0] = Paragraph("<font size=10><b>⬇️ ZONA DE RETIROS (RECOLECCIÓN) ⬇️</b></font>", estilo_celda_centro)
        data.append(separador)
        estilos_tabla_t.append(('SPAN', (0, current_row), (-1, current_row)))
        estilos_tabla_t.append(('BACKGROUND', (0, current_row), (-1, current_row), colors.silver))
        current_row += 1
        agregar_filas_t(retiros, True)
    
    t = Table(data, colWidths=[30, 110, 180, 100, 312, 80], repeatRows=1)
    t.setStyle(TableStyle(estilos_tabla_t)); elements.append(t)
    
    def add_footer(canvas, doc): 
        canvas.saveState(); canvas.setFont('Helvetica-Bold', 9); page_width, _ = landscape(A4)
        footer_text = f"TOTAL ENTREGAS: {len(entregas)}   |   TOTAL RETIROS: {len(retiros)}   |   Generado por: {usuario}   |   Pág. {doc.page}"
        canvas.drawCentredString(page_width / 2.0, 15, footer_text); canvas.restoreState()
        
    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)

def crear_pdf_reporte(nombre_archivo, resultados, sucursal, usuario, fecha_generacion, filtro_info, total_dinero):
    doc = SimpleDocTemplate(nombre_archivo, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []; styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle(name='TituloCentro', parent=styles['Heading1'], alignment=TA_CENTER)
    sub_style = ParagraphStyle(name='SubCentro', parent=styles['Normal'], alignment=TA_CENTER)
    elements.append(Paragraph(f"REPORTE - {sucursal.upper()}", titulo_style))
    elements.append(Paragraph(f"Generado el: {fecha_generacion} por {usuario}", sub_style))
    elements.append(Paragraph(filtro_info, styles['Normal'])); elements.append(Spacer(1, 20))
    data = [['FECHA', 'GUÍA', 'CLIENTE', 'DESTINO', 'ESTADO', 'MONTO']]; 
    for op in resultados: data.append([op.fecha_ingreso.strftime("%d/%m/%Y"), op.guia_remito or "-", op.proveedor[:15], op.destinatario[:20], op.estado, f"$ {op.monto_servicio:,.0f}"])
    data.append(['', '', '', 'TOTALES:', f"{len(resultados)} Guías", f"$ {total_dinero:,.2f}"])
    t = Table(data, colWidths=[60, 100, 100, 200, 100, 80])
    t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,0), (-1,0), colors.lightgrey), ('TEXTCOLOR', (0,0), (-1,0), colors.black), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTSIZE', (0,0), (-1,-1), 9), ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'), ('BACKGROUND', (0,-1), (-1,-1), colors.lightgrey)]))
    elements.append(t)
    def add_footer(canvas, doc): 
        canvas.saveState(); canvas.setFont('Helvetica', 8); page_width, _ = landscape(A4)
        canvas.drawCentredString(page_width / 2.0, 20, f"Generado por: {usuario} | Pág. {doc.page}"); canvas.restoreState()
    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)


# 🔥 FACTURACIÓN NUEVA CON LOGO, 2 DECIMALES Y AUTO-AJUSTE 🔥
def crear_pdf_facturacion(nombre_archivo, data_filas, prov_nombre, periodo_str, usuario, fecha_generacion):
    doc = SimpleDocTemplate(nombre_archivo, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=25, bottomMargin=25)
    elements = []
    styles = getSampleStyleSheet()
    
    # 1. Buscamos el Logo
    logo_path = "eklogo.png" if os.path.exists("eklogo.png") else ("logo.png" if os.path.exists("logo.png") else None)
    if logo_path:
        elements.append(Image(logo_path, width=150, height=60, hAlign='CENTER'))
        elements.append(Spacer(1, 10))
        
    title_style = ParagraphStyle(name='TitleCenter', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=18)
    client_style = ParagraphStyle(name='Client', parent=styles['Normal'], alignment=TA_CENTER, fontSize=12, spaceAfter=15)
    
    elements.append(Paragraph(f"RENDICIÓN {prov_nombre.upper()}", title_style))
    elements.append(Paragraph(f"Período: {periodo_str}", client_style))
    
    # Estilos específicos para celdas
    estilo_celda = ParagraphStyle(name='CeldaTabla', parent=styles['Normal'], fontSize=8, leading=10, alignment=TA_CENTER)
    # Permite saltos de línea (wordWrap) para números de guía largos
    estilo_guia = ParagraphStyle(name='CeldaGuia', parent=styles['Normal'], fontSize=8, leading=10, alignment=TA_CENTER, wordWrap='CJK')
    estilo_monto = ParagraphStyle(name='CeldaMonto', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)
    estilo_subtotal = ParagraphStyle(name='CeldaSub', parent=styles['Normal'], fontSize=10, alignment=TA_RIGHT, fontName='Helvetica-Bold')
    
    processed_data = []
    
    for i, row in enumerate(data_filas):
        # La fila 0 es el encabezado, lo dejamos tal cual
        if i == 0:
            processed_data.append(row) 
            continue
            
        new_row = []
        es_totales = (i >= len(data_filas) - 3) # Detecta si son las últimas 3 filas (Subtotales, IVA, Total)
        
        for j, cell in enumerate(row):
            cell_str = str(cell) if cell is not None else ""
            
            # Columna GUÍA (Índice 1): Le aplicamos Paragraph para que no desborde
            if j == 1 and not es_totales and cell_str:
                new_row.append(Paragraph(cell_str, estilo_guia))
                
            # Columnas de Montos (Índices 4, 5, 6): Pasamos a formato .2f y alineamos a la derecha
            elif j in [4, 5, 6] and cell_str:
                if "$" in cell_str:
                    num_str = cell_str.replace("$", "").replace(",", "").strip()
                    try:
                        num = float(num_str)
                        val_formatted = f"$ {num:,.2f}"
                    except:
                        val_formatted = cell_str
                else:
                    val_formatted = cell_str
                    
                if es_totales:
                    new_row.append(Paragraph(val_formatted, estilo_subtotal))
                else:
                    new_row.append(Paragraph(val_formatted, estilo_monto))
                    
            # Columna 0 en los totales (Los textos de la izquierda)
            elif j == 0 and es_totales:
                new_row.append(Paragraph(cell_str, estilo_subtotal))
                
            # Resto de celdas normales
            else:
                if cell_str:
                    new_row.append(Paragraph(cell_str, estilo_celda))
                else:
                    new_row.append("")
                    
        processed_data.append(new_row)
        
    # Anchos ajustados exactamente para el tamaño de la hoja A4 (Total ~555 puntos)
    t = Table(processed_data, colWidths=[55, 130, 90, 55, 75, 70, 80], repeatRows=1)
    
    t_style = [
        ('GRID', (0,0), (-1,-1), 0.5, colors.black), 
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey), 
        ('TEXTCOLOR', (0,0), (-1,0), colors.black), 
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), 
        ('ALIGN', (0,0), (-1,0), 'CENTER'), 
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        
        # Bloque final (Totales)
        ('BACKGROUND', (0,-3), (-1,-1), colors.whitesmoke), 
        ('SPAN', (0, -3), (3, -3)), ('ALIGN', (0,-3), (3,-3), 'RIGHT'),
        ('SPAN', (0, -2), (5, -2)), ('ALIGN', (0,-2), (5,-2), 'RIGHT'),
        ('SPAN', (0, -1), (5, -1)), ('ALIGN', (0,-1), (5,-1), 'RIGHT')
    ]
    t.setStyle(TableStyle(t_style))
    elements.append(t)
    
    def add_footer(canvas, doc): 
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        page_width, _ = A4
        canvas.drawCentredString(page_width / 2.0, 20, f"Generado por: {usuario} | Fecha: {fecha_generacion} | Pág. {doc.page}")
        canvas.restoreState()
        
    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)

def crear_pdf_resumen_diario(nombre_archivo, chofer, fecha_str, entregados, no_entregados, sucursal, usuario):
    doc = SimpleDocTemplate(nombre_archivo, pagesize=portrait(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    titulo = ParagraphStyle(name='Tit', parent=styles['Heading1'], alignment=TA_CENTER)
    
    elements.append(Paragraph(f"RESUMEN DIARIO DE CHOFER - {sucursal.upper()}", titulo))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"<b>Chofer:</b> {chofer} &nbsp;&nbsp;&nbsp; <b>Fecha:</b> {fecha_str} &nbsp;&nbsp;&nbsp; <b>Generado por:</b> {usuario}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph(f"✅ ENTREGAS / RETIROS EXITOSOS ({len(entregados)})", styles['Heading2']))
    if entregados:
        data_e = [["GUÍA", "DESTINATARIO", "DOMICILIO"]]
        for row in entregados:
            g = row[1]
            dest = row[2]
            dom = row[3]
            data_e.append([Paragraph(g or "-", styles['Normal']), Paragraph(dest, styles['Normal']), Paragraph(dom, styles['Normal'])])
        t_e = Table(data_e, colWidths=[120, 180, 235])
        t_e.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('BACKGROUND', (0,0), (-1,0), colors.lightgreen),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(t_e)
    else:
        elements.append(Paragraph("No hay entregas registradas.", styles['Normal']))
        
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph(f"⚠️ NO ENTREGADOS / PENDIENTES ({len(no_entregados)})", styles['Heading2']))
    if no_entregados:
        data_n = [["GUÍA", "DESTINATARIO", "MOTIVO"]]
        for row in no_entregados:
            g = row[0]
            dest = row[1]
            mot = row[2]
            data_n.append([Paragraph(g or "-", styles['Normal']), Paragraph(dest, styles['Normal']), Paragraph(mot, styles['Normal'])])
        t_n = Table(data_n, colWidths=[120, 180, 235])
        t_n.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('BACKGROUND', (0,0), (-1,0), colors.lightcoral),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(t_n)
    else:
        elements.append(Paragraph("No hay fallos registrados.", styles['Normal']))
        
    doc.build(elements)