from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from utils.database import db
import json
import hashlib


class Credential(db.Model):
    """
    Model pentru credențialele capturate în campaniile de phishing
    
    Attributes:
        id: ID unic al credențialei
        campaign_id: ID-ul campaniei asociate
        target_id: ID-ul țintei care a introdus credențialele
        
        # Credential data
        username: Username/email introdus
        password: Parola introdusă (în clar pentru analiză)
        password_hash: Hash-ul parolei pentru securitate
        
        # Capture context
        captured_at: Momentul capturării
        ip_address: IP-ul de unde au fost introduse
        user_agent: Browser-ul folosit
        referrer: De unde a venit utilizatorul
        session_id: ID-ul sesiunii
        
        # Form data
        form_data: Date suplimentare din formular (JSON)
        page_url: URL-ul paginii unde au fost introduse
        form_fields: Câmpurile din formular (JSON)
        
        # Analysis
        password_strength: Puterea parolei (weak/medium/strong)
        is_common_password: Dacă parola e în listele comune
        credential_type: Tipul credențialei (banking, email, social, etc.)
        
        # Security
        is_real_credential: Dacă pare o credențială reală
        risk_score: Scorul de risc (0-100)
        flagged_for_review: Marcat pentru review manual
        
        # Metadata
        processed: Dacă credențialele au fost procesate
        notified: Dacă target-ul a fost notificat
    """
    
    __tablename__ = 'credentials'
    
    # === CÂMPURI PRINCIPALE ===
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), nullable=False)
    target_id = Column(Integer, ForeignKey('targets.id'), nullable=False)
    
    # === CREDENTIAL DATA ===
    username = Column(String(255), nullable=False)
    password = Column(String(255), nullable=False)  # În clar pentru analiză educațională
    password_hash = Column(String(64))  # SHA-256 hash pentru securitate
    
    # === CAPTURE CONTEXT ===
    captured_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ip_address = Column(String(45))  # IPv6 compatible
    user_agent = Column(Text)
    referrer = Column(String(500))
    session_id = Column(String(64))
    
    # === FORM DATA ===
    form_data = Column(Text)  # JSON cu toate câmpurile din formular
    page_url = Column(String(500))
    form_fields = Column(Text)  # JSON cu metadata despre câmpuri
    
    # === ANALYSIS ===
    password_strength = Column(
        db.Enum('very_weak', 'weak', 'medium', 'strong', 'very_strong', name='password_strength'),
        default='weak'
    )
    is_common_password = Column(Boolean, default=False)
    credential_type = Column(String(50))  # banking, email, social, work, etc.
    
    # === SECURITY ===
    is_real_credential = Column(Boolean, default=True)
    risk_score = Column(Integer, default=0)  # 0-100
    flagged_for_review = Column(Boolean, default=False)
    
    # === METADATA ===
    processed = Column(Boolean, default=False)
    notified = Column(Boolean, default=False)
    
    def __init__(self, campaign_id, target_id, username, password, **kwargs):
        """
        Inițializează o nouă credențială capturată
        
        Args:
            campaign_id: ID-ul campaniei
            target_id: ID-ul țintei
            username: Username-ul introdus
            password: Parola introdusă
            **kwargs: Alte argumente opționale
        """
        self.campaign_id = campaign_id
        self.target_id = target_id
        self.username = username.strip() if username else ""
        self.password = password.strip() if password else ""
        
        # Generează hash-ul parolei
        self.password_hash = self._hash_password(self.password)
        
        # Setează valorile opționale
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        # Analizează parola automat
        self._analyze_password()
        self._detect_credential_type()
        self._calculate_risk_score()
    
    def __repr__(self):
        return f'<Credential {self.username} - Campaign {self.campaign_id}>'
    
    def __str__(self):
        masked_password = "*" * len(self.password) if self.password else ""
        return f'{self.username} / {masked_password} (captured at {self.captured_at.strftime("%Y-%m-%d %H:%M")})'
    
    # === PROPERTIES ===
    
    @property
    def form_data_dict(self):
        """Returnează datele din formular ca dicționar"""
        if self.form_data:
            try:
                return json.loads(self.form_data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    @form_data_dict.setter
    def form_data_dict(self, data):
        """Setează datele din formular"""
        if data:
            self.form_data = json.dumps(data)
        else:
            self.form_data = None
    
    @property
    def form_fields_dict(self):
        """Returnează metadata câmpurilor ca dicționar"""
        if self.form_fields:
            try:
                return json.loads(self.form_fields)
            except json.JSONDecodeError:
                return {}
        return {}
    
    @form_fields_dict.setter
    def form_fields_dict(self, data):
        """Setează metadata câmpurilor"""
        if data:
            self.form_fields = json.dumps(data)
        else:
            self.form_fields = None
    
    @property
    def masked_password(self):
        """Returnează parola mascată pentru afișare"""
        if not self.password:
            return ""
        return "*" * len(self.password)
    
    @property
    def password_length(self):
        """Lungimea parolei"""
        return len(self.password) if self.password else 0
    
    @property
    def time_since_capture(self):
        """Timpul trecut de la capturare"""
        return datetime.utcnow() - self.captured_at
    
    @property
    def is_suspicious(self):
        """Verifică dacă credențiala este suspectă"""
        return (
            self.risk_score > 70 or
            not self.is_real_credential or
            self.flagged_for_review
        )
    
    @property
    def strength_score(self):
        """Scorul numeric al puterii parolei"""
        strength_scores = {
            'very_weak': 1,
            'weak': 2,
            'medium': 3,
            'strong': 4,
            'very_strong': 5
        }
        return strength_scores.get(self.password_strength, 1)
    
    # === METODE BUSINESS ===
    
    def _hash_password(self, password):
        """Generează hash SHA-256 pentru parolă"""
        if not password:
            return ""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    def _analyze_password(self):
        """Analizează puterea parolei"""
        if not self.password:
            self.password_strength = 'very_weak'
            return
        
        password = self.password
        score = 0
        
        # Lungime
        if len(password) >= 8:
            score += 1
        if len(password) >= 12:
            score += 1
        
        # Complexitate
        if any(c.islower() for c in password):
            score += 1
        if any(c.isupper() for c in password):
            score += 1
        if any(c.isdigit() for c in password):
            score += 1
        if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            score += 1
        
        # Setează puterea bazată pe scor
        if score <= 2:
            self.password_strength = 'very_weak'
        elif score == 3:
            self.password_strength = 'weak'
        elif score == 4:
            self.password_strength = 'medium'
        elif score == 5:
            self.password_strength = 'strong'
        else:
            self.password_strength = 'very_strong'
        
        # Verifică parolele comune
        self._check_common_password()
    
    def _check_common_password(self):
        """Verifică dacă parola este în listele comune"""
        common_passwords = [
            'password', '123456', '123456789', 'qwerty', 'abc123',
            'password123', 'admin', 'letmein', 'welcome', 'monkey',
            'dragon', 'master', 'shadow', 'qwerty123', 'football'
        ]
        
        self.is_common_password = self.password.lower() in common_passwords
        
        if self.is_common_password:
            self.password_strength = 'very_weak'
    
    def _detect_credential_type(self):
        """Detectează tipul credențialei bazat pe username și context"""
        username_lower = self.username.lower()
        
        # Banking keywords
        banking_keywords = ['revolut', 'bank', 'credit', 'card', 'payment']
        if any(keyword in username_lower for keyword in banking_keywords):
            self.credential_type = 'banking'
        
        # Email patterns
        elif '@' in self.username:
            domain = self.username.split('@')[-1].lower()
            if domain in ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com']:
                self.credential_type = 'email'
            elif domain in ['company.com', 'corp.com'] or 'work' in domain:
                self.credential_type = 'work'
            else:
                self.credential_type = 'email'
        
        # Social media patterns
        elif any(social in username_lower for social in ['facebook', 'twitter', 'linkedin', 'instagram']):
            self.credential_type = 'social'
        
        # Default
        else:
            self.credential_type = 'general'
    
    def _calculate_risk_score(self):
        """Calculează scorul de risc (0-100)"""
        risk = 0
        
        # Username suspect
        if not self.username or len(self.username) < 3:
            risk += 30
        
        # Parolă suspectă
        if not self.password or len(self.password) < 4:
            risk += 40
        
        if self.is_common_password:
            risk += 20
        
        if self.password_strength in ['very_weak', 'weak']:
            risk += 15
        
        # Pattern suspect
        if self.username == self.password:
            risk += 25
        
        if 'test' in self.username.lower() or 'test' in self.password.lower():
            risk += 15
        
        # Credențiale foarte simple
        if self.password in ['123', '1234', 'pass', 'admin']:
            risk += 30
        
        self.risk_score = min(risk, 100)
        
        # Flag pentru review dacă risc mare
        if self.risk_score > 70:
            self.flagged_for_review = True
        
        # Detectează credențiale false
        if self.risk_score > 80:
            self.is_real_credential = False
    
    def mark_as_processed(self):
        """Marchează credențiala ca procesată"""
        self.processed = True
        db.session.commit()
    
    def mark_as_notified(self):
        """Marchează că target-ul a fost notificat"""
        self.notified = True
        db.session.commit()
    
    def flag_for_review(self, reason=None):
        """Marchează credențiala pentru review manual"""
        self.flagged_for_review = True
        
        if reason:
            form_data = self.form_data_dict
            form_data['flag_reason'] = reason
            self.form_data_dict = form_data
        
        db.session.commit()
    
    def get_security_analysis(self):
        """
        Returnează o analiză detaliată de securitate
        
        Returns:
            dict: Analiza de securitate
        """
        analysis = {
            'password_strength': {
                'level': self.password_strength,
                'score': self.strength_score,
                'length': self.password_length,
                'is_common': self.is_common_password
            },
            'risk_assessment': {
                'score': self.risk_score,
                'is_suspicious': self.is_suspicious,
                'is_real': self.is_real_credential,
                'flagged': self.flagged_for_review
            },
            'credential_info': {
                'type': self.credential_type,
                'username_length': len(self.username),
                'same_user_pass': self.username == self.password
            },
            'recommendations': self._get_security_recommendations()
        }
        
        return analysis
    
    def _get_security_recommendations(self):
        """Generează recomandări de securitate"""
        recommendations = []
        
        if self.password_strength in ['very_weak', 'weak']:
            recommendations.append("Use a stronger password with at least 8 characters")
        
        if self.is_common_password:
            recommendations.append("Avoid using common passwords")
        
        if len(self.password) < 8:
            recommendations.append("Use a password with at least 8 characters")
        
        if not any(c.isdigit() for c in self.password):
            recommendations.append("Include numbers in your password")
        
        if not any(c in "!@#$%^&*" for c in self.password):
            recommendations.append("Include special characters in your password")
        
        if self.username == self.password:
            recommendations.append("Never use the same value for username and password")
        
        return recommendations
    
    # === METODE STATICE ===
    
    @staticmethod
    def get_campaign_credentials(campaign_id):
        """Returnează toate credențialele unei campanii"""
        return Credential.query.filter_by(campaign_id=campaign_id).all()
    
    @staticmethod
    def get_weak_passwords(campaign_id=None):
        """Returnează credențialele cu parole slabe"""
        query = Credential.query.filter(
            Credential.password_strength.in_(['very_weak', 'weak'])
        )
        
        if campaign_id:
            query = query.filter_by(campaign_id=campaign_id)
        
        return query.all()
    
    @staticmethod
    def get_common_passwords_stats(campaign_id=None):
        """Returnează statistici despre parolele comune"""
        from sqlalchemy import func
        
        query = db.session.query(
            Credential.password,
            func.count(Credential.id).label('count')
        )
        
        if campaign_id:
            query = query.filter_by(campaign_id=campaign_id)
        
        return query.group_by(Credential.password)\
                   .order_by(func.count(Credential.id).desc())\
                   .limit(10).all()
    
    @staticmethod
    def get_strength_distribution(campaign_id=None):
        """Returnează distribuția puterii parolelor"""
        from sqlalchemy import func
        
        query = db.session.query(
            Credential.password_strength,
            func.count(Credential.id).label('count')
        )
        
        if campaign_id:
            query = query.filter_by(campaign_id=campaign_id)
        
        results = query.group_by(Credential.password_strength).all()
        
        distribution = {
            'very_weak': 0,
            'weak': 0,
            'medium': 0,
            'strong': 0,
            'very_strong': 0
        }
        
        for result in results:
            distribution[result.password_strength] = result.count
        
        return distribution
    
    @staticmethod
    def get_flagged_credentials(campaign_id=None):
        """Returnează credențialele marcate pentru review"""
        query = Credential.query.filter_by(flagged_for_review=True)
        
        if campaign_id:
            query = query.filter_by(campaign_id=campaign_id)
        
        return query.all()
    
    def to_dict(self, include_password=False):
        """
        Convertește credențiala într-un dicționar pentru JSON
        
        Args:
            include_password: Dacă să includă parola în clar
            
        Returns:
            dict: Reprezentarea credențialei ca dicționar
        """
        data = {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'target_id': self.target_id,
            'username': self.username,
            'password': self.password if include_password else self.masked_password,
            'password_hash': self.password_hash,
            'captured_at': self.captured_at.isoformat() if self.captured_at else None,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'referrer': self.referrer,
            'session_id': self.session_id,
            'form_data': self.form_data_dict,
            'page_url': self.page_url,
            'form_fields': self.form_fields_dict,
            'password_strength': self.password_strength,
            'password_length': self.password_length,
            'is_common_password': self.is_common_password,
            'credential_type': self.credential_type,
            'is_real_credential': self.is_real_credential,
            'risk_score': self.risk_score,
            'is_suspicious': self.is_suspicious,
            'flagged_for_review': self.flagged_for_review,
            'processed': self.processed,
            'notified': self.notified,
            'security_analysis': self.get_security_analysis()
        }
        
        return data