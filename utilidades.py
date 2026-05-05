import os
import math
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

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
    
    logo_path = "eklogo.png" if os.path.exists("eklogo.png") else ("logo.png" if os.path.exists("logo.png") else None)
    if logo_path:
        elements.append(Image(logo_path, width=65, height=40, hAlign='CENTER'))
        elements.append(Spacer(1, 10))
        
    titulo_style = ParagraphStyle(name='TituloCentro', parent=styles['Heading1'], alignment=TA_CENTER)
    elements.append(Paragraph(f"ORDEN DE RETIRO - E.K. LOGISTICA", titulo_style)); elements.append(Spacer(1, 20))
    data = [['FECHA:', op.fecha_ingreso.strftime("%d/%m/%Y")], ['N° ORDEN/GUÍA:', op.guia_remito or f"RET-{op.id}"], ['CLIENTE:', op.destinatario], ['DOMICILIO:', f"{op.domicilio} ({op.localidad})"], ['BULTOS:', str(op.bultos)], ['OBSERVACIONES:', op.info_intercambio or "Sin observaciones"]]
    t = Table(data, colWidths=[150, 300]); t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('BACKGROUND', (0,0), (0,-1), colors.lightgrey), ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold')]))
    elements.append(t); elements.append(Spacer(1, 50)); elements.append(Paragraph("______________________________", TA_CENTER)); elements.append(Paragraph("Firma del Cliente / Remitente", TA_CENTER))
    doc.build(elements)

def crear_pdf_ruta(nombre_archivo, ops, sucursal, chofer, usuario, fecha_generacion):
    doc = SimpleDocTemplate(nombre_archivo, pagesize=landscape(A4), rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=25)
    elements = []; styles = getSampleStyleSheet()
    
    estilo_celda = ParagraphStyle(name='Celda', parent=styles['Normal'], fontSize=8, leading=9, wordWrap='CJK')
    estilo_celda_centro = ParagraphStyle(name='CeldaCentro', parent=styles['Normal'], fontSize=8, leading=9, alignment=TA_CENTER, wordWrap='CJK')
    estilo_titulo = ParagraphStyle(name='Titulo', parent=styles['Heading1'], alignment=1, fontSize=14, spaceAfter=5)
    
    logo_path = "eklogo.png" if os.path.exists("eklogo.png") else ("logo.png" if os.path.exists("logo.png") else None)
    if logo_path:
        elements.append(Image(logo_path, width=65, height=40, hAlign='CENTER'))
        elements.append(Spacer(1, 5))
    
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
                    if op.monto_recaudacion > 0: obs_str += f"<b>COBRAR: $ {op.monto_recaudacion:,.2f}</b>"
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
    
    logo_path = "eklogo.png" if os.path.exists("eklogo.png") else ("logo.png" if os.path.exists("logo.png") else None)
    if logo_path:
        elements.append(Image(logo_path, width=65, height=40, hAlign='CENTER'))
        elements.append(Spacer(1, 10))
        
    estilo_celda = ParagraphStyle(name='Celda', parent=styles['Normal'], fontSize=8, leading=9, wordWrap='CJK')
    estilo_celda_centro = ParagraphStyle(name='CeldaCentro', parent=styles['Normal'], fontSize=8, leading=9, alignment=TA_CENTER, wordWrap='CJK')
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
    doc = SimpleDocTemplate(nombre_archivo, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=25, bottomMargin=25)
    elements = []; styles = getSampleStyleSheet()
    
    logo_path = "eklogo.png" if os.path.exists("eklogo.png") else ("logo.png" if os.path.exists("logo.png") else None)
    if logo_path:
        elements.append(Image(logo_path, width=65, height=40, hAlign='CENTER'))
        elements.append(Spacer(1, 10))

    titulo_style = ParagraphStyle(name='TituloCentro', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=16)
    sub_style = ParagraphStyle(name='SubCentro', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10)
    estilo_filtro = ParagraphStyle(name='Filtro', parent=styles['Normal'], fontSize=9, leading=11, alignment=TA_CENTER, textColor=colors.darkblue)
    
    elements.append(Paragraph(f"REPORTE - {sucursal.upper()}", titulo_style))
    elements.append(Paragraph(f"Generado el: {fecha_generacion} por {usuario}", sub_style))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph(filtro_info, estilo_filtro))
    elements.append(Spacer(1, 15))
    
    estilo_celda = ParagraphStyle(name='CeldaTabla', parent=styles['Normal'], fontSize=8, leading=10, alignment=TA_CENTER)
    estilo_guia = ParagraphStyle(name='CeldaGuia', parent=styles['Normal'], fontSize=8, leading=10, alignment=TA_CENTER, wordWrap='CJK')
    estilo_monto = ParagraphStyle(name='CeldaMonto', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)
    estilo_subtotal = ParagraphStyle(name='CeldaSub', parent=styles['Normal'], fontSize=10, alignment=TA_RIGHT, fontName='Helvetica-Bold')
    estilo_head = ParagraphStyle(name='Encabezado', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER, fontName='Helvetica-Bold')

    data = [[
        Paragraph('FECHA', estilo_head),
        Paragraph('GUÍA', estilo_head),
        Paragraph('CLIENTE', estilo_head),
        Paragraph('DESTINO', estilo_head),
        Paragraph('ESTADO', estilo_head),
        Paragraph('MONTO', estilo_head)
    ]]
    
    for op in resultados: 
        data.append([
            Paragraph(op.fecha_ingreso.strftime("%d/%m/%Y"), estilo_celda), 
            Paragraph(op.guia_remito or "-", estilo_guia), 
            Paragraph(op.proveedor[:25], estilo_celda), 
            Paragraph(op.destinatario[:35], estilo_guia), 
            Paragraph(op.estado, estilo_celda), 
            Paragraph(f"$ {op.monto_servicio:,.2f}", estilo_monto)
        ])
        
    data.append([
        '', '', '', 
        Paragraph('TOTALES:', estilo_subtotal), 
        Paragraph(f"{len(resultados)} Guías", estilo_subtotal), 
        Paragraph(f"$ {total_dinero:,.2f}", estilo_subtotal)
    ])
    
    t = Table(data, colWidths=[65, 140, 140, 250, 100, 90], repeatRows=1)
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey), 
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey), 
        ('ALIGN', (0,0), (-1,-1), 'CENTER'), 
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BACKGROUND', (0,-1), (-1,-1), colors.whitesmoke),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(t)
    
    def add_footer(canvas, doc): 
        canvas.saveState(); canvas.setFont('Helvetica', 8); page_width, _ = landscape(A4)
        canvas.drawCentredString(page_width / 2.0, 20, f"Generado por: {usuario} | Pág. {doc.page}"); canvas.restoreState()
    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)

# 🔥 NUEVO GENERADOR DE FACTURACIÓN: HOJA APAISADA + CALCULO DE IVA 🔥
def crear_pdf_facturacion(nombre_archivo, data_filas, prov_nombre, periodo_str, usuario, fecha_generacion):
    # 1. Hoja Apaisada (landscape) para que entren todas las columnas sin cortar los bordes
    doc = SimpleDocTemplate(nombre_archivo, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=25, bottomMargin=25)
    elements = []
    styles = getSampleStyleSheet()
    
    logo_path = "eklogo.png" if os.path.exists("eklogo.png") else ("logo.png" if os.path.exists("logo.png") else None)
    if logo_path:
        elements.append(Image(logo_path, width=65, height=40, hAlign='CENTER'))
        elements.append(Spacer(1, 10))
        
    title_style = ParagraphStyle(name='TitleCenter', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=16)
    client_style = ParagraphStyle(name='Client', parent=styles['Normal'], alignment=TA_CENTER, fontSize=11, spaceAfter=15)
    
    elements.append(Paragraph(f"RENDICIÓN {prov_nombre.upper()}", title_style))
    elements.append(Paragraph(f"Período: {periodo_str}", client_style))
    
    # 2. Estilos específicos para la tabla
    estilo_centro = ParagraphStyle(name='Cent', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER)
    estilo_izq = ParagraphStyle(name='Izq', parent=styles['Normal'], fontSize=8, alignment=TA_LEFT, wordWrap='CJK')
    estilo_der = ParagraphStyle(name='Der', parent=styles['Normal'], fontSize=8, alignment=TA_RIGHT)
    estilo_head = ParagraphStyle(name='Head', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold', alignment=TA_CENTER)
    estilo_tot_der = ParagraphStyle(name='TotDer', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', alignment=TA_RIGHT)
    
    processed_data = []
    
    # Convertimos los textos sueltos en Párrafos procesables por ReportLab
    for i, row in enumerate(data_filas):
        new_row = []
        es_totales = (i >= len(data_filas) - 4) # Detecta las últimas 4 filas (Separador, Subtotal, IVA, Total Final)
        
        for j, cell in enumerate(row):
            cell_str = str(cell) if cell is not None else ""
            
            if i == 0: # Fila Título
                new_row.append(Paragraph(cell_str, estilo_head))
            elif es_totales: # Fila de IVA y Totales
                new_row.append(Paragraph(cell_str, estilo_tot_der))
            else: # Filas de datos normales
                if j in [1, 2]: # Guia, Zona -> Alineado a la izquierda
                    new_row.append(Paragraph(cell_str, estilo_izq))
                elif j >= 4: # Montos -> Alineado a la derecha
                    new_row.append(Paragraph(cell_str, estilo_der))
                else: # Fecha y Bultos -> Centrados
                    new_row.append(Paragraph(cell_str, estilo_centro))
                    
        processed_data.append(new_row)
        
    # 3. Anchos fijos y calculados matemáticamente para llenar exacto la hoja A4 Horizontal (Total = 795 pts)
    t = Table(processed_data, colWidths=[75, 190, 120, 60, 85, 85, 85, 95], repeatRows=1)
    
    # Estilo base de la grilla
    t_style = [
        ('GRID', (0,0), (-1,-1), 0.5, colors.black), 
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey), 
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]
    
    # 4. Estilos condicionales para la zona del IVA y totales al final de la página
    if len(data_filas) >= 5: 
        t_style.extend([
            # Borrar bordes de la fila vacía (-4) para que funcione como "Espacio en blanco"
            ('LINEABOVE', (0,-4), (-1,-4), 0, colors.white),
            ('LINEBELOW', (0,-4), (-1,-4), 0, colors.white),
            ('LINEBEFORE', (0,-4), (-1,-4), 0, colors.white),
            ('LINEAFTER', (0,-4), (-1,-4), 0, colors.white),
            ('BACKGROUND', (0,-4), (-1,-4), colors.white),
            
            # Pintar de gris y enmarcar la zona de resultados (-3 a -1)
            ('BACKGROUND', (0,-3), (-1,-1), colors.whitesmoke), 
            ('LINEABOVE', (0,-3), (-1,-3), 1.5, colors.black), 
            
            # Combinar las columnas vacías para que el texto encaje hermoso a la derecha
            ('SPAN', (0, -3), (3, -3)), # SUBTOTALES
            ('SPAN', (0, -2), (5, -2)), # IVA
            ('SPAN', (0, -1), (5, -1)), # TOTAL FACTURA
        ])
        
    t.setStyle(TableStyle(t_style))
    elements.append(t)
    
    def add_footer(canvas, doc): 
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        page_width, _ = landscape(A4)
        canvas.drawCentredString(page_width / 2.0, 20, f"Generado por: {usuario} | Fecha: {fecha_generacion} | Pág. {doc.page}")
        canvas.restoreState()
        
    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)

def crear_pdf_resumen_diario(nombre_archivo, chofer, fecha_str, entregados, no_entregados, sucursal, usuario):
    doc = SimpleDocTemplate(nombre_archivo, pagesize=portrait(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    logo_path = "eklogo.png" if os.path.exists("eklogo.png") else ("logo.png" if os.path.exists("logo.png") else None)
    if logo_path:
        elements.append(Image(logo_path, width=65, height=40, hAlign='CENTER'))
        elements.append(Spacer(1, 10))
        
    titulo = ParagraphStyle(name='Tit', parent=styles['Heading1'], alignment=TA_CENTER)
    
    estilo_celda = ParagraphStyle(name='CeldaTabla', parent=styles['Normal'], fontSize=8, leading=10, alignment=TA_CENTER, wordWrap='CJK')
    estilo_celda_izq = ParagraphStyle(name='CeldaIzq', parent=styles['Normal'], fontSize=8, leading=10, alignment=TA_LEFT, wordWrap='CJK')
    
    elements.append(Paragraph(f"RESUMEN DIARIO DE CHOFER - {sucursal.upper()}", titulo))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"<b>Chofer:</b> {chofer} &nbsp;&nbsp;&nbsp; <b>Fecha:</b> {fecha_str} &nbsp;&nbsp;&nbsp; <b>Generado por:</b> {usuario}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph(f"✅ ENTREGAS / RETIROS EXITOSOS ({len(entregados)})", styles['Heading2']))
    if entregados:
        data_e = [["GUÍA", "CLIENTE", "DESTINATARIO", "DOMICILIO", "BULTOS", "ENTREGADO"]]
        for row in entregados:
            g = row[1] or "-"
            if row[4] and "Retiro" in row[4]: g = f"🔄 [RET] {g}"
            elif row[4] and "Flete" in row[4]: g = f"⏱️ {g}"
            
            cliente = row[5] or "-"
            dest = row[2] or "-"
            dom = row[3] or "-"
            bultos = str(row[6]) if row[6] else "1"
            
            f_ent = "-"
            if len(row) > 7 and row[7]:
                f_ent = row[7].strftime("%d/%m %H:%M")
            
            data_e.append([
                Paragraph(g, estilo_celda), 
                Paragraph(cliente, estilo_celda_izq), 
                Paragraph(dest, estilo_celda_izq), 
                Paragraph(dom, estilo_celda_izq), 
                Paragraph(bultos, estilo_celda), 
                Paragraph(f_ent, estilo_celda)
            ])
            
        t_e = Table(data_e, colWidths=[75, 80, 90, 150, 45, 95])
        t_e.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('BACKGROUND', (0,0), (-1,0), colors.lightgreen),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 8),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(t_e)
    else:
        elements.append(Paragraph("No hay entregas registradas.", styles['Normal']))
        
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph(f"⚠️ NO ENTREGADOS / PENDIENTES / REPROGRAMADAS ({len(no_entregados)})", styles['Heading2']))
    if no_entregados:
        data_n = [["GUÍA", "CLIENTE", "DESTINATARIO", "MOTIVO"]]
        for row in no_entregados:
            g = row[0] or "-"
            if row[3] and "Retiro" in row[3]: g = f"🔄 [RET] {g}"
            elif row[3] and "Flete" in row[3]: g = f"⏱️ {g}"
            
            dest = row[1] or "-"
            mot = row[2] or "-"
            cliente = row[4] if len(row) > 4 and row[4] else "-"
            
            data_n.append([
                Paragraph(g, estilo_celda), 
                Paragraph(cliente, estilo_celda_izq),
                Paragraph(dest, estilo_celda_izq), 
                Paragraph(mot, estilo_celda_izq)
            ])
            
        t_n = Table(data_n, colWidths=[80, 90, 115, 250])
        t_n.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('BACKGROUND', (0,0), (-1,0), colors.lightcoral),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 8),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(t_n)
    else:
        elements.append(Paragraph("No hay fallos registrados.", styles['Normal']))
        
    doc.build(elements)

def crear_pdf_despacho_papeles(nombre_archivo, numero_lote, ops, proveedor_nombre, usuario, fecha_generacion):
    doc = SimpleDocTemplate(nombre_archivo, pagesize=portrait(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []; styles = getSampleStyleSheet()

    logo_path = "eklogo.png" if os.path.exists("eklogo.png") else ("logo.png" if os.path.exists("logo.png") else None)
    if logo_path:
        elements.append(Image(logo_path, width=65, height=40, hAlign='CENTER'))
        elements.append(Spacer(1, 10))

    titulo = ParagraphStyle(name='Tit', parent=styles['Heading1'], alignment=TA_CENTER)
    subtit = ParagraphStyle(name='Sub', parent=styles['Normal'], alignment=TA_CENTER, fontSize=11)

    elements.append(Paragraph(f"REMITO DE ENTREGA DE DOCUMENTACIÓN FÍSICA", titulo))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph(f"<b>LOTE N°:</b> {numero_lote}", subtit))
    elements.append(Paragraph(f"<b>PROVEEDOR/DESTINO:</b> {proveedor_nombre.upper()}", subtit))
    elements.append(Paragraph(f"<b>Generado por:</b> {usuario} &nbsp;&nbsp;&nbsp; <b>Fecha:</b> {fecha_generacion}", subtit))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph(f"Se hace entrega de los siguientes <b>{len(ops)} documentos originales (Remitos/Guías)</b> correspondientes a entregas finalizadas:", styles['Normal']))
    elements.append(Spacer(1, 10))

    data = [["#", "FECHA ENTREGA", "GUÍA / REMITO", "DESTINATARIO", "BULTOS"]]
    estilo_celda = ParagraphStyle(name='Celda', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)
    estilo_izq = ParagraphStyle(name='Izq', parent=styles['Normal'], fontSize=9, alignment=TA_LEFT)

    for i, op in enumerate(ops, 1):
        f_ent = op.fecha_entrega.strftime("%d/%m/%Y") if op.fecha_entrega else (op.fecha_ingreso.strftime("%d/%m/%Y") if op.fecha_ingreso else "-")
        data.append([
            str(i),
            Paragraph(f_ent, estilo_celda),
            Paragraph(op.guia_remito or "-", estilo_celda),
            Paragraph(op.destinatario or "-", estilo_izq),
            str(int(op.bultos) if op.bultos else 1)
        ])

    t = Table(data, colWidths=[30, 90, 140, 220, 50], repeatRows=1)
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(t)

    elements.append(Spacer(1, 60))
    firma_data = [["______________________________", "______________________________"],
                  ["Entregado por (E.K. Logística)", "Recibido por (Firma y Aclaración)"]]
    t_firma = Table(firma_data, colWidths=[250, 250])
    t_firma.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
    elements.append(t_firma)

    doc.build(elements)

def crear_pdf_general_tarifas(ruta_output, titulo_doc, data, usuario_nombre):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from datetime import datetime

    # Usamos formato apaisado (landscape) para que entren más columnas
    doc = SimpleDocTemplate(ruta_output, pagesize=landscape(A4))
    elements = []
    styles = getSampleStyleSheet()

    # Título
    elements.append(Paragraph(f"<b>{titulo_doc}</b>", styles['Title']))
    elements.append(Spacer(1, 12))
    
    # Info de impresión
    fecha_hoy = datetime.now().strftime("%d/%m/%Y %H:%M")
    elements.append(Paragraph(f"Impreso por: {usuario_nombre} | Fecha: {fecha_hoy}", styles['Normal']))
    elements.append(Spacer(1, 20))

    # Crear Tabla
    t = Table(data, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0d47a1")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements.append(t)
    doc.build(elements)
    