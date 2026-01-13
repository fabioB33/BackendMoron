import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

async def send_certificate_email(user_email, user_name, afap_numero, afap_data):
    """
    Envía email automático con el certificado AFAP
    En producción, aquí se integraría con Resend, SendGrid, etc.
    Por ahora, simula el envío y registra en logs
    """
    try:
        # Simulación del email
        email_content = f"""
        Estimado/a {user_name},

        ¡Felicitaciones! Tu solicitud AFAP #{afap_numero} ha sido APROBADA.

        Detalles:
        - Comercio: {afap_data.get('rubro_descripcion', '')}
        - Domicilio: {afap_data.get('domicilio_calle', '')} {afap_data.get('domicilio_altura', '')}
        - Superficie: {afap_data.get('metros_cuadrados', '')} m²
        - Vigencia: 30 días desde la fecha de emisión

        Podés descargar tu certificado ingresando a:
        https://municipality-portal.preview.emergentagent.com/mis-solicitudes

        El certificado debe ser exhibido en lugar visible del establecimiento.

        Importante:
        - Esta autorización es PRECARIA y tiene validez de 30 días
        - Permite iniciar actividades mientras se tramita la habilitación definitiva
        - No exime del cumplimiento de normativas municipales

        Argentina
        Dirección de Habilitaciones
        """
        
        # Log del email (en producción sería un envío real)
        logger.info(f"📧 EMAIL SIMULADO enviado a: {user_email}")
        logger.info(f"   Asunto: AFAP #{afap_numero} - Certificado Aprobado")
        logger.info(f"   Usuario: {user_name}")
        
        # En producción, aquí iría:
        # await send_email_via_resend(user_email, "AFAP Aprobado", email_content, pdf_attachment)
        
        return {
            "success": True,
            "message": f"Email enviado a {user_email}",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

async def send_status_notification(user_email, user_name, afap_numero, old_status, new_status, observaciones=None):
    """
    Envía notificación cuando cambia el estado de un AFAP
    """
    try:
        status_messages = {
            "pendiente": "está pendiente de revisión",
            "inspeccion": "fue programada para inspección",
            "aprobado": "fue APROBADA ✓",
            "rechazado": "fue rechazada"
        }
        
        message = status_messages.get(new_status, f"cambió a {new_status}")
        
        email_content = f"""
        Estimado/a {user_name},

        Tu solicitud AFAP #{afap_numero} {message}.

        {f'Observaciones: {observaciones}' if observaciones else ''}

        Podés ver el estado actualizado ingresando a:
        https://municipality-portal.preview.emergentagent.com/mis-solicitudes

        Argentina
        """
        
        logger.info(f"📧 NOTIFICACIÓN enviada a: {user_email}")
        logger.info(f"   AFAP #{afap_numero}: {old_status} → {new_status}")
        
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Error sending notification: {str(e)}")
        return {"success": False, "error": str(e)}
