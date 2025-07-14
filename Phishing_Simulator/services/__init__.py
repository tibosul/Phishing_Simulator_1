# ===========================================
# services/__init__.py
# ===========================================

"""
Services package pentru Phishing Simulator

Conține logica business a aplicației:
- email_service: Trimiterea email-urilor de phishing
- sms_service: Trimiterea SMS-urilor de phishing
- ollama_service: Personalizarea cu AI
- tracking_service: Urmărirea evenimentelor
- credential_capture: Capturarea credențialelor
"""

from .email_service import EmailService
from .sms_service import SMSService
from .ollama_service import OllamaService
from .tracking_service import TrackingService
from .credential_capture import CredentialCaptureService
from .campaign_service import CampaignService

__all__ = [
    'EmailService',
    'SMSService',
    'OllamaService', 
    'TrackingService',
    'CredentialCaptureService',
    'CampaignService'
]