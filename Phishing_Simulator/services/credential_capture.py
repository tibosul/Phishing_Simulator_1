import logging
import hashlib
import re
from datetime import datetime, timedelta
from flask import request, current_app
from sqlalchemy import func

from models.campaign import Campaign
from models.target import Target
from models.credential import Credential
from models.tracking import Tracking
from utils.database import db
from utils.helpers import get_client_ip, get_user_agent, log_security_event, sanitize_input
from utils.validators import ValidationError
from services.tracking_service import TrackingService


class CredentialCaptureService:
    """
    Service pentru capturarea și analiza credențialelor în campaniile de phishing
    
    Features:
    - Capturarea sigură a credențialelor
    - Analiza puterii parolelor
    - Detectarea parolelor comune
    - Risk scoring automată
    - Detectarea credențialelor false/test
    - Notificări și alerting
    - Integrare completă cu TrackingService
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.tracking_service = TrackingService()
        
        # Lista parolelor comune pentru detectare
        self.common_passwords = {
            'password', 'password123', '123456', '123456789', 'qwerty', 
            'abc123', 'password1', 'admin', 'letmein', 'welcome',
            'monkey', 'dragon', 'master', 'shadow', 'qwerty123',
            'football', 'baseball', 'superman', 'michael', 'jordan',
            'parola', 'parola123', 'administrator', 'test', 'test123'
        }
        
        # Pattern-uri suspicioase pentru detectarea credențialelor false
        self.suspicious_patterns = [
            r'^test.*test$', r'^fake.*fake$', r'^admin.*admin$',
            r'^demo.*demo$', r'^example.*example$', r'^sample.*sample$'
        ]
    
    def capture_credentials(self, campaign_id, target_id, username, password, 
                          additional_data=None, tracking_token=None, session_data=None):
        """
        Capturează și analizează credențialele introduse de o țintă
        
        Args:
            campaign_id: ID-ul campaniei
            target_id: ID-ul țintei
            username: Username-ul introdus
            password: Parola introdusă
            additional_data: Date suplimentare din formular
            tracking_token: Token de tracking
            session_data: Date despre sesiune
            
        Returns:
            dict: Rezultatul capturării cu analiză completă
        """
        try:
            # Validări inițiale
            campaign = Campaign.query.get(campaign_id)
            target = Target.query.get(target_id)
            
            if not campaign or not target:
                raise ValidationError("Invalid campaign or target ID")
            
            # Sanitizează input-urile
            username = sanitize_input(username) if username else ""
            password = sanitize_input(password) if password else ""
            
            if not username or not password:
                raise ValidationError("Username and password are required")
            
            # Verifică duplicatele (același target, aceeași campanie)
            existing_credential = Credential.query.filter_by(
                campaign_id=campaign_id,
                target_id=target_id
            ).first()
            
            is_duplicate = existing_credential is not None
            
            # Creează înregistrarea credențialei
            credential = Credential(
                campaign_id=campaign_id,
                target_id=target_id,
                username=username,
                password=password,
                captured_at=datetime.utcnow(),
                ip_address=get_client_ip(),
                user_agent=get_user_agent(),
                session_id=tracking_token,
                page_url=request.url if request else None
            )
            
            # Adaugă date suplimentare din formular
            if additional_data:
                credential.form_data_dict = additional_data
            
            # Adaugă metadata despre sesiune
            if session_data:
                credential.form_fields_dict = session_data
            
            # Analizează credențiala
            analysis = self._analyze_credential(credential)
            
            # Aplică rezultatele analizei
            credential.password_strength = analysis['password_strength']
            credential.is_common_password = analysis['is_common_password']
            credential.credential_type = analysis['credential_type']
            credential.is_real_credential = analysis['is_real_credential']
            credential.risk_score = analysis['risk_score']
            credential.flagged_for_review = analysis['flagged_for_review']
            
            # Salvează în baza de date
            db.session.add(credential)
            db.session.commit()
            
            # Actualizează statusul țintei
            if not is_duplicate:
                target.mark_credentials_entered()
            
            # Creează eveniment de tracking
            self.tracking_service.track_form_submission(
                campaign_id=campaign_id,
                target_id=target_id,
                form_data={
                    'username': username,
                    'password': password,
                    **(additional_data if additional_data else {})
                },
                tracking_token=tracking_token
            )
            
            # Creează eveniment specific pentru credențiale
            credentials_event = Tracking(
                campaign_id=campaign_id,
                event_type='credentials_entered',
                target_id=target_id,
                ip_address=get_client_ip(),
                user_agent=get_user_agent(),
                tracking_token=tracking_token
            )
            
            credentials_event.extra_data = {
                'credential_id': credential.id,
                'password_strength': analysis['password_strength'],
                'risk_score': analysis['risk_score'],
                'is_duplicate': is_duplicate,
                'analysis_summary': analysis['summary']
            }
            
            db.session.add(credentials_event)
            db.session.commit()
            
            # Logging și alerting
            log_level = 'WARNING' if analysis['risk_score'] > 70 else 'INFO'
            self.logger.log(
                getattr(logging, log_level),
                f"Credentials captured: Target {target.email}, Risk: {analysis['risk_score']}, "
                f"Strength: {analysis['password_strength']}"
            )
            
            log_security_event(
                'credentials_captured',
                f"Credentials captured from {target.email} (Risk: {analysis['risk_score']})"
            )
            
            # Verifică dacă trebuie alertă pentru activitate suspectă
            if analysis['risk_score'] > 80:
                self._trigger_suspicious_activity_alert(credential, analysis)
            
            # Pregătește rezultatul
            result = {
                'success': True,
                'credential_id': credential.id,
                'is_duplicate': is_duplicate,
                'analysis': analysis,
                'target_info': {
                    'id': target.id,
                    'email': target.email,
                    'name': target.display_name
                },
                'recommendations': self._generate_security_recommendations(analysis)
            }
            
            self.logger.info(f"Credential capture successful: ID {credential.id}")
            
            return result
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error capturing credentials: {str(e)}")
            raise
    
    def _analyze_credential(self, credential):
        """
        Analizează credențiala capturată pentru securitate și autenticitate
        
        Args:
            credential: Obiectul Credential
            
        Returns:
            dict: Analiza completă
        """
        analysis = {
            'password_strength': 'weak',
            'is_common_password': False,
            'credential_type': 'general',
            'is_real_credential': True,
            'risk_score': 0,
            'flagged_for_review': False,
            'summary': '',
            'details': {}
        }
        
        # Analizează puterea parolei
        strength_analysis = self._analyze_password_strength(credential.password)
        analysis['password_strength'] = strength_analysis['strength']
        analysis['details']['password_analysis'] = strength_analysis
        
        # Verifică parolele comune
        analysis['is_common_password'] = credential.password.lower() in self.common_passwords
        
        # Detectează tipul credențialei
        analysis['credential_type'] = self._detect_credential_type(credential.username)
        
        # Detectează credențiale false/test
        authenticity_check = self._check_credential_authenticity(credential)
        analysis['is_real_credential'] = authenticity_check['is_real']
        analysis['details']['authenticity_check'] = authenticity_check
        
        # Calculează risk score
        analysis['risk_score'] = self._calculate_risk_score(credential, analysis)
        
        # Determină dacă necesită review manual
        analysis['flagged_for_review'] = (
            analysis['risk_score'] > 70 or
            not analysis['is_real_credential'] or
            analysis['is_common_password']
        )
        
        # Generează sumar
        analysis['summary'] = self._generate_analysis_summary(analysis)
        
        return analysis
    
    def _analyze_password_strength(self, password):
        """
        Analizează puterea unei parole
        
        Args:
            password: Parola de analizat
            
        Returns:
            dict: Analiza puterii parolei
        """
        if not password:
            return {'strength': 'very_weak', 'score': 0, 'feedback': ['Password is empty']}
        
        score = 0
        feedback = []
        
        # Lungime
        if len(password) >= 8:
            score += 1
            feedback.append("Good length (8+ characters)")
        else:
            feedback.append("Too short (less than 8 characters)")
        
        if len(password) >= 12:
            score += 1
            feedback.append("Excellent length (12+ characters)")
        
        # Complexitate
        if re.search(r'[a-z]', password):
            score += 1
            feedback.append("Contains lowercase letters")
        else:
            feedback.append("Missing lowercase letters")
        
        if re.search(r'[A-Z]', password):
            score += 1
            feedback.append("Contains uppercase letters")
        else:
            feedback.append("Missing uppercase letters")
        
        if re.search(r'\d', password):
            score += 1
            feedback.append("Contains numbers")
        else:
            feedback.append("Missing numbers")
        
        if re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
            score += 1
            feedback.append("Contains special characters")
        else:
            feedback.append("Missing special characters")
        
        # Determină puterea finală
        if score <= 2:
            strength = 'very_weak'
        elif score == 3:
            strength = 'weak'
        elif score == 4:
            strength = 'medium'
        elif score == 5:
            strength = 'strong'
        else:
            strength = 'very_strong'
        
        return {
            'strength': strength,
            'score': score,
            'max_score': 6,
            'feedback': feedback
        }
    
    def _detect_credential_type(self, username):
        """
        Detectează tipul credențialei pe baza username-ului
        
        Args:
            username: Username-ul de analizat
            
        Returns:
            str: Tipul credențialei
        """
        username_lower = username.lower()
        
        # Banking patterns
        banking_keywords = ['revolut', 'bank', 'card', 'payment', 'finance']
        if any(keyword in username_lower for keyword in banking_keywords):
            return 'banking'
        
        # Email patterns
        if '@' in username:
            domain = username.split('@')[-1].lower()
            if domain in ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com']:
                return 'personal_email'
            elif any(work_domain in domain for work_domain in ['.com', '.org', '.net']):
                return 'work_email'
            return 'email'
        
        # Social media patterns
        social_keywords = ['facebook', 'twitter', 'linkedin', 'instagram', 'social']
        if any(social in username_lower for social in social_keywords):
            return 'social_media'
        
        # Work patterns
        work_keywords = ['admin', 'user', 'employee', 'staff']
        if any(work in username_lower for work in work_keywords):
            return 'work'
        
        return 'general'
    
    def _check_credential_authenticity(self, credential):
        """
        Verifică dacă credențiala pare autentică sau e de test
        
        Args:
            credential: Obiectul Credential
            
        Returns:
            dict: Rezultatul verificării autenticității
        """
        issues = []
        is_real = True
        confidence = 100
        
        username = credential.username.lower()
        password = credential.password.lower()
        
        # Verifică pattern-uri suspicioase
        for pattern in self.suspicious_patterns:
            if re.search(pattern, username) or re.search(pattern, password):
                issues.append(f"Suspicious pattern detected: {pattern}")
                is_real = False
                confidence -= 30
        
        # Username și parola identice
        if username == password:
            issues.append("Username and password are identical")
            is_real = False
            confidence -= 25
        
        # Credențiale foarte simple
        simple_patterns = ['123', '1234', 'pass', 'admin', 'test', 'demo']
        if any(simple in password for simple in simple_patterns):
            issues.append("Password is too simple/generic")
            confidence -= 20
        
        # Username foarte generic
        generic_usernames = ['test', 'admin', 'user', 'demo', 'example', 'sample']
        if username in generic_usernames:
            issues.append("Username is too generic")
            confidence -= 15
        
        # Parola foarte scurtă
        if len(credential.password) < 4:
            issues.append("Password is extremely short")
            confidence -= 20
        
        # Verifică dacă conține cuvinte de test
        test_words = ['test', 'fake', 'demo', 'example', 'sample']
        if any(word in username for word in test_words) or any(word in password for word in test_words):
            issues.append("Contains test/demo words")
            confidence -= 25
        
        confidence = max(0, confidence)
        
        return {
            'is_real': is_real,
            'confidence': confidence,
            'issues': issues,
            'analysis': 'Likely real credential' if is_real else 'Likely test/fake credential'
        }
    
    def _calculate_risk_score(self, credential, analysis):
        """
        Calculează scorul de risc (0-100)
        
        Args:
            credential: Obiectul Credential
            analysis: Analiza existentă
            
        Returns:
            int: Scorul de risc
        """
        risk = 0
        
        # Risc bazat pe autenticitate
        if not analysis['is_real_credential']:
            risk += 40
        
        # Risc bazat pe puterea parolei
        strength_risk = {
            'very_weak': 30,
            'weak': 20,
            'medium': 10,
            'strong': 5,
            'very_strong': 0
        }
        risk += strength_risk.get(analysis['password_strength'], 20)
        
        # Risc parole comune
        if analysis['is_common_password']:
            risk += 25
        
        # Risc credențiale identice
        if credential.username.lower() == credential.password.lower():
            risk += 30
        
        # Risc lungime foarte mică
        if len(credential.password) < 4:
            risk += 20
        
        # Risc pattern-uri suspicioase din IP
        # (aici ai putea adăuga verificări pentru IP-uri cunoscute ca fiind de test)
        
        return min(100, risk)
    
    def _generate_analysis_summary(self, analysis):
        """
        Generează un sumar al analizei
        
        Args:
            analysis: Dicționarul cu analiza
            
        Returns:
            str: Sumarul analizei
        """
        strength = analysis['password_strength']
        risk = analysis['risk_score']
        
        if risk > 80:
            return f"HIGH RISK: {strength} password, likely test credential"
        elif risk > 50:
            return f"MEDIUM RISK: {strength} password, some concerns"
        elif risk > 20:
            return f"LOW RISK: {strength} password, appears genuine"
        else:
            return f"MINIMAL RISK: {strength} password, high confidence"
    
    def _generate_security_recommendations(self, analysis):
        """
        Generează recomandări de securitate bazate pe analiză
        
        Args:
            analysis: Analiza credențialei
            
        Returns:
            list: Lista recomandărilor
        """
        recommendations = []
        
        if analysis['password_strength'] in ['very_weak', 'weak']:
            recommendations.append("Use a stronger password with at least 8 characters")
        
        if analysis['is_common_password']:
            recommendations.append("Avoid using common passwords")
        
        if not analysis['is_real_credential']:
            recommendations.append("This appears to be a test credential - verify authenticity")
        
        if analysis['risk_score'] > 70:
            recommendations.append("Manual review recommended due to high risk score")
        
        # Recomandări generale
        recommendations.extend([
            "Use unique passwords for each account",
            "Enable two-factor authentication when available",
            "Consider using a password manager"
        ])
        
        return recommendations
    
    def _trigger_suspicious_activity_alert(self, credential, analysis):
        """
        Declanșează alertă pentru activitate suspectă
        
        Args:
            credential: Obiectul Credential
            analysis: Analiza credențialei
        """
        try:
            alert_data = {
                'timestamp': datetime.utcnow(),
                'credential_id': credential.id,
                'target_email': credential.target.email if credential.target else 'Unknown',
                'risk_score': analysis['risk_score'],
                'issues': analysis['details'].get('authenticity_check', {}).get('issues', []),
                'ip_address': credential.ip_address
            }
            
            self.logger.warning(f"SUSPICIOUS ACTIVITY ALERT: {alert_data}")
            
            # Aici ai putea adăuga integrări cu sisteme de alerting
            # (email notifications, Slack, etc.)
            
        except Exception as e:
            self.logger.error(f"Error triggering suspicious activity alert: {str(e)}")
    
    def get_campaign_credential_analysis(self, campaign_id):
        """
        Returnează analiza credențialelor pentru o campanie
        
        Args:
            campaign_id: ID-ul campaniei
            
        Returns:
            dict: Analiza completă a credențialelor
        """
        try:
            credentials = Credential.query.filter_by(campaign_id=campaign_id).all()
            
            if not credentials:
                return {'total': 0, 'analysis': 'No credentials captured yet'}
            
            # Statistici generale
            total_credentials = len(credentials)
            unique_targets = len(set(c.target_id for c in credentials))
            
            # Distribuția puterii parolelor
            strength_distribution = {}
            for strength in ['very_weak', 'weak', 'medium', 'strong', 'very_strong']:
                count = sum(1 for c in credentials if c.password_strength == strength)
                strength_distribution[strength] = count
            
            # Credențiale comune
            common_password_count = sum(1 for c in credentials if c.is_common_password)
            
            # Credențiale suspicioase
            high_risk_count = sum(1 for c in credentials if c.risk_score > 70)
            flagged_count = sum(1 for c in credentials if c.flagged_for_review)
            
            # Top 10 parole cele mai comune
            password_frequency = {}
            for credential in credentials:
                pwd = credential.password.lower()
                password_frequency[pwd] = password_frequency.get(pwd, 0) + 1
            
            top_passwords = sorted(
                password_frequency.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10]
            
            return {
                'total_credentials': total_credentials,
                'unique_targets': unique_targets,
                'strength_distribution': strength_distribution,
                'common_passwords': {
                    'count': common_password_count,
                    'percentage': round((common_password_count / total_credentials) * 100, 2)
                },
                'security_risks': {
                    'high_risk_count': high_risk_count,
                    'flagged_for_review': flagged_count,
                    'risk_percentage': round((high_risk_count / total_credentials) * 100, 2)
                },
                'top_passwords': [
                    {'password': pwd, 'count': count, 'masked': '*' * len(pwd)}
                    for pwd, count in top_passwords
                ],
                'recommendations': self._generate_campaign_recommendations(credentials)
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing campaign credentials: {str(e)}")
            return {'error': str(e)}
    
    def _generate_campaign_recommendations(self, credentials):
        """
        Generează recomandări pentru întreaga campanie
        
        Args:
            credentials: Lista credențialelor
            
        Returns:
            list: Recomandările pentru campanie
        """
        recommendations = []
        
        total = len(credentials)
        weak_passwords = sum(1 for c in credentials if c.password_strength in ['very_weak', 'weak'])
        common_passwords = sum(1 for c in credentials if c.is_common_password)
        
        if weak_passwords / total > 0.7:
            recommendations.append("70%+ of captured passwords are weak - focus on password strength training")
        
        if common_passwords / total > 0.3:
            recommendations.append("30%+ use common passwords - educate about password uniqueness")
        
        high_risk = sum(1 for c in credentials if c.risk_score > 70)
        if high_risk / total > 0.2:
            recommendations.append("20%+ are high-risk credentials - manual review recommended")
        
        return recommendations