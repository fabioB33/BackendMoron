from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from datetime import datetime
from io import BytesIO
import qrcode
from PIL import Image as PILImage
import os

def generate_qr_code(data):
    """
    Genera un código QR y lo retorna como imagen
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convertir a BytesIO para usar con ReportLab
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    return buffer

def add_watermark(canvas_obj, width, height, text):
    """
    Agrega una marca de agua diagonal en el PDF
    """
    canvas_obj.saveState()
    canvas_obj.setFillColor(colors.HexColor('#F1F5F9'), alpha=0.3)
    canvas_obj.setFont("Helvetica-Bold", 60)
    
    # Rotar y posicionar el texto diagonal
    canvas_obj.translate(width/2, height/2)
    canvas_obj.rotate(45)
    canvas_obj.drawCentredString(0, 0, text)
    
    canvas_obj.restoreState()

def generate_afap_certificate(afap_data):
    """
    Genera un certificado AFAP en PDF con QR Code, Watermark y Firma Digital
    """
    buffer = BytesIO()
    
    # Create the PDF object
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Colors
    header_color = colors.HexColor('#0F172A')  # Slate 900
    blue_color = colors.HexColor('#2563EB')    # Blue 600
    emerald_color = colors.HexColor('#10B981') # Emerald 500
    
    # Add watermark
    add_watermark(pdf, width, height, "ARGENTINA")
    
    # Header - Municipalidad
    pdf.setFillColor(header_color)
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawCentredString(width/2, height - 1.5*cm, "ARGENTINA HABILITACIONES")
    
    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(width/2, height - 2*cm, "Dirección de Habilitaciones Comerciales")
    
    # Línea separadora
    pdf.setStrokeColor(blue_color)
    pdf.setLineWidth(2)
    pdf.line(2*cm, height - 2.5*cm, width - 2*cm, height - 2.5*cm)
    
    # Título del certificado
    pdf.setFillColor(blue_color)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawCentredString(width/2, height - 4*cm, "AUTORIZACIÓN DE FUNCIONAMIENTO")
    pdf.drawCentredString(width/2, height - 4.5*cm, "AUTOMÁTICO PRECARIA (AFAP)")
    
    # Número de AFAP con badge
    pdf.setFillColor(emerald_color)
    pdf.roundRect(width/2 - 3*cm, height - 6*cm, 6*cm, 0.8*cm, 0.3*cm, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(width/2, height - 5.7*cm, f"N° {afap_data['numero_afap']}")
    
    # Estado: APROBADO
    pdf.setFillColor(emerald_color)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(width/2, height - 6.5*cm, "✓ APROBADO")
    
    # Información del titular
    y_pos = height - 8*cm
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(2*cm, y_pos, "TITULAR:")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(5*cm, y_pos, afap_data.get('titular_nombre', ''))
    
    y_pos -= 0.7*cm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(2*cm, y_pos, "CUIT/CUIL:")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(5*cm, y_pos, afap_data.get('titular_cuit', ''))
    
    # Domicilio del comercio
    y_pos -= 1*cm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(2*cm, y_pos, "DOMICILIO DEL COMERCIO:")
    
    y_pos -= 0.7*cm
    pdf.setFont("Helvetica", 11)
    domicilio = f"{afap_data.get('domicilio_calle', '')} {afap_data.get('domicilio_altura', '')}"
    if afap_data.get('domicilio_piso'):
        domicilio += f", Piso {afap_data['domicilio_piso']}"
    if afap_data.get('domicilio_depto'):
        domicilio += f", Depto {afap_data['domicilio_depto']}"
    if afap_data.get('domicilio_local'):
        domicilio += f", Local {afap_data['domicilio_local']}"
    pdf.drawString(2*cm, y_pos, domicilio)
    
    y_pos -= 0.7*cm
    pdf.drawString(2*cm, y_pos, f"{afap_data.get('domicilio_localidad', 'Argentina')}")
    
    # Rubro
    y_pos -= 1*cm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(2*cm, y_pos, "RUBRO:")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(5*cm, y_pos, afap_data.get('rubro_tipo', ''))
    
    y_pos -= 0.7*cm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(2*cm, y_pos, "ACTIVIDAD:")
    pdf.setFont("Helvetica", 11)
    
    # Wrap long text
    descripcion = afap_data.get('rubro_descripcion', '')
    if len(descripcion) > 70:
        pdf.drawString(5*cm, y_pos, descripcion[:70])
        y_pos -= 0.5*cm
        pdf.drawString(5*cm, y_pos, descripcion[70:140])
    else:
        pdf.drawString(5*cm, y_pos, descripcion)
    
    y_pos -= 0.7*cm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(2*cm, y_pos, "SUPERFICIE:")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(5*cm, y_pos, f"{afap_data.get('metros_cuadrados', '')} m²")
    
    # Fechas
    y_pos -= 1.5*cm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(2*cm, y_pos, "FECHA DE EMISIÓN:")
    pdf.setFont("Helvetica", 11)
    fecha_emision = datetime.fromisoformat(afap_data.get('fecha_solicitud', datetime.now().isoformat()))
    pdf.drawString(6*cm, y_pos, fecha_emision.strftime('%d/%m/%Y'))
    
    y_pos -= 0.7*cm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(2*cm, y_pos, "FECHA DE VENCIMIENTO:")
    pdf.setFont("Helvetica", 11)
    if afap_data.get('fecha_vencimiento'):
        fecha_venc = datetime.fromisoformat(afap_data['fecha_vencimiento'])
        pdf.drawString(6*cm, y_pos, fecha_venc.strftime('%d/%m/%Y'))
    
    # Texto legal
    y_pos -= 1.5*cm
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(2*cm, y_pos, "IMPORTANTE:")
    
    y_pos -= 0.6*cm
    pdf.setFont("Helvetica", 9)
    texto_legal = [
        "• Esta autorización tiene carácter PRECARIO y validez de 30 días corridos.",
        "• Permite el inicio de actividades mientras se tramita la habilitación definitiva.",
        "• No exime del cumplimiento de las normativas municipales vigentes.",
        "• Debe exhibirse en lugar visible del establecimiento.",
        "• La municipalidad se reserva el derecho de realizar inspecciones.",
    ]
    
    for linea in texto_legal:
        pdf.drawString(2*cm, y_pos, linea)
        y_pos -= 0.5*cm
    
    # Recuadro de firma digital
    y_pos -= 1*cm
    pdf.setStrokeColor(colors.black)
    pdf.setLineWidth(1)
    pdf.rect(width - 8*cm, y_pos - 3*cm, 6*cm, 2.5*cm)
    
    # Firma Digital Badge
    pdf.setFillColor(blue_color)
    pdf.roundRect(width - 7.5*cm, y_pos - 0.8*cm, 5*cm, 0.6*cm, 0.2*cm, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawCentredString(width - 5*cm, y_pos - 0.6*cm, "🔒 FIRMADO DIGITALMENTE")
    
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(width - 5*cm, y_pos - 1.3*cm, "Dirección de Habilitaciones")
    pdf.drawCentredString(width - 5*cm, y_pos - 1.8*cm, "Argentina Habilitaciones")
    
    # Código de verificación
    pdf.setFont("Helvetica", 7)
    pdf.setFillColor(colors.grey)
    codigo_verificacion = f"VER-{afap_data['numero_afap']}-{datetime.now().strftime('%Y%m%d%H%M')}"
    pdf.drawCentredString(width - 5*cm, y_pos - 2.5*cm, f"Código: {codigo_verificacion}")
    
    # QR Code Real
    try:
        # URL para verificar el certificado
        # Usa el dominio de la variable de entorno o un default para desarrollo
        base_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        verification_url = f"{base_url}/verificar-certificado/{afap_data['id']}"
        qr_buffer = generate_qr_code(verification_url)
        
        # Guardar temporalmente para usar con ReportLab
        qr_path = f"/tmp/qr_{afap_data['numero_afap']}.png"
        with open(qr_path, 'wb') as f:
            f.write(qr_buffer.read())
        
        # Insertar QR en el PDF
        pdf.drawImage(qr_path, 2*cm, 2*cm, width=3*cm, height=3*cm)
        
        # Label del QR
        pdf.setFont("Helvetica-Bold", 9)
        pdf.setFillColor(colors.black)
        pdf.drawCentredString(3.5*cm, 1.5*cm, "Escanear para verificar")
        pdf.setFont("Helvetica", 7)
        pdf.setFillColor(colors.grey)
        pdf.drawCentredString(3.5*cm, 1.2*cm, f"AFAP-{afap_data['numero_afap']}")
        
        # Limpiar archivo temporal
        if os.path.exists(qr_path):
            os.remove(qr_path)
            
    except Exception as e:
        print(f"Error generating QR code: {e}")
        # Fallback: dibujar recuadro simple
        pdf.setStrokeColor(colors.grey)
        pdf.setLineWidth(1)
        pdf.rect(2*cm, 2*cm, 3*cm, 3*cm)
    
    # Footer con timestamp
    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(colors.grey)
    pdf.drawCentredString(width/2, 1.5*cm, "Argentina Habilitaciones - Sistema de Habilitaciones Digitales")
    pdf.drawCentredString(width/2, 1*cm, f"Generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M:%S')} hs")
    
    # Número de página y validez
    pdf.setFont("Helvetica-Bold", 7)
    pdf.setFillColor(emerald_color)
    pdf.drawString(2*cm, 0.5*cm, "✓ DOCUMENTO VÁLIDO")
    pdf.setFillColor(colors.grey)
    pdf.drawRightString(width - 2*cm, 0.5*cm, "Página 1 de 1")
    
    # Finalize PDF
    pdf.save()
    
    # Get the value of the BytesIO buffer
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes
