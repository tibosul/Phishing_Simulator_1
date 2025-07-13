from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from utils.database import db
from utils.validators import validate_email, validate_phone_number, ValidationError


class Target(db.Model):
    """
    Model pentru țintele/victimele campaniilor de phishing
    
    Attributes:
        id: ID unic al țintei
        campaign_id: ID-ul campaniei asociate
        email: Adresa de email a țintei
        phone: Numărul de telefon
        first_name: Prenumele
        last_name: Numele de familie
        company: Compania unde lucrează
        position: Poziția în companie
        notes: Notițe despre țintă
        
        # Metadata
        created_at: Data adăugării în sistem
        updated_at: Data ultimei modificări
        
        # Status tracking
        email_sent: A fost trimis email-ul
        sms_sent: A fost trimis SMS-ul
        clicked_link: A făcut click pe link
        entered_credentials: A introdus credențiale
        
        # Relații
        tracking_events: Evenimentele de tracking pentru această țintă
        captured_credentials: Credențialele capturate de la această țintă
    """
    
    __tablename__ = 'targets'
    
    # === CÂMPURI PRINCIPALE ===
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), nullable=False)
    
    # === INFORMAȚII CONTACT ===
    email = Column(String(254), nullable=False)  # RFC 5321 limit
    phone = Column(String(20))
    
    # === INFORMAȚII PERSONALE ===
    first_name = Column(String(50))
    last_name = Column(String(50))
    company = Column(String(100))
    position = Column(String(100))
    notes = Column(Text)
    
    # === TIMESTAMPS ===
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # === STATUS TRACKING ===
    email_sent = Column(Boolean, default=False)
    sms_sent = Column(Boolean, default=False)
    clicked_link = Column(Boolean, default=False)
    entered_credentials = Column(Boolean, default=False)
    
    # === RELAȚII ===
    tracking_events = relationship('Tracking', backref='target', lazy=True, cascade='all, delete-orphan')
    captured_credentials = relationship('Credential', backref='target', lazy=True, cascade='all, delete-orphan')
    
    def __init__(self, campaign_id, email, **kwargs):
        """
        Inițializează o nouă țintă
        
        Args:
            campaign_id: ID-ul campaniei
            email: Adresa de email (obligatorie)
            **kwargs: Alte informații opționale
        """
        self.campaign_id = campaign_id
        self.email = email.lower().strip()  # Normalizează email-ul
        
        # Setează valorile opționale
        for key, value in kwargs.items():
            if hasattr(self, key) and value:
                if isinstance(value, str):
                    setattr(self, key, value.strip())
                else:
                    setattr(self, key, value)
    
    def __repr__(self):
        return f'<Target {self.email} (Campaign {self.campaign_id})>'
    
    def __str__(self):
        if self.first_name and self.last_name:
            return f'{self.first_name} {self.last_name} ({self.email})'
        return self.email
    
    # === PROPERTIES ===
    
    @property
    def full_name(self):
        """Numele complet al țintei"""
        if self.first_name and self.last_name:
            return f'{self.first_name} {self.last_name}'
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return None
    
    @property
    def display_name(self):
        """Numele pentru afișare (full_name sau email)"""
        return self.full_name or self.email
    
    @property
    def engagement_score(self):
        """
        Scorul de engagement (0-100) bazat pe acțiunile țintei
        
        Returns:
            int: Scor între 0 și 100
        """
        score = 0
        
        if self.email_sent:
            score += 10
        if self.sms_sent:
            score += 10
        if self.clicked_link:
            score += 40
        if self.entered_credentials:
            score += 40
        
        return min(score, 100)
    
    @property
    def status(self):
        """
        Statusul țintei bazat pe acțiuni
        
        Returns:
            str: Status descriptiv
        """
        if self.entered_credentials:
            return 'credentials_entered'
        elif self.clicked_link:
            return 'clicked_link'
        elif self.email_sent or self.sms_sent:
            return 'contacted'
        else:
            return 'pending'
    
    @property
    def status_display(self):
        """Statusul pentru afișare user-friendly"""
        status_map = {
            'credentials_entered': 'Credentials Captured',
            'clicked_link': 'Clicked Link',
            'contacted': 'Contacted',
            'pending': 'Pending'
        }
        return status_map.get(self.status, 'Unknown')
    
    @property
    def last_activity(self):
        """Ultima activitate a țintei"""
        if not self.tracking_events:
            return None
        
        return max(self.tracking_events, key=lambda x: x.timestamp).timestamp
    
    # === METODE BUSINESS ===
    
    def mark_email_sent(self):
        """Marchează că email-ul a fost trimis"""
        self.email_sent = True
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def mark_sms_sent(self):
        """Marchează că SMS-ul a fost trimis"""
        self.sms_sent = True
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def mark_link_clicked(self):
        """Marchează că linkul a fost accesat"""
        self.clicked_link = True
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def mark_credentials_entered(self):
        """Marchează că credențialele au fost introduse"""
        self.entered_credentials = True
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def update_profile(self, **kwargs):
        """
        Actualizează profilul țintei cu informații noi
        
        Args:
            **kwargs: Câmpurile de actualizat
        """
        allowed_fields = [
            'first_name', 'last_name', 'company', 'position', 
            'phone', 'notes'
        ]
        
        updated = False
        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(self, field):
                if isinstance(value, str):
                    value = value.strip()
                if value != getattr(self, field):
                    setattr(self, field, value)
                    updated = True
        
        if updated:
            self.updated_at = datetime.utcnow()
            db.session.commit()
        
        return updated
    
    def get_personalization_data(self):
        """
        Returnează datele pentru personalizarea email-urilor/SMS-urilor
        
        Returns:
            dict: Dicționar cu datele de personalizare
        """
        return {
            'first_name': self.first_name or 'User',
            'last_name': self.last_name or '',
            'full_name': self.full_name or 'User',
            'email': self.email,
            'company': self.company or 'Your Company',
            'position': self.position or 'Employee',
            'display_name': self.display_name
        }
    
    def get_tracking_summary(self):
        """
        Returnează un sumar al activităților de tracking
        
        Returns:
            dict: Sumar cu evenimente și timeline
        """
        from collections import defaultdict
        
        events_by_type = defaultdict(list)
        
        for event in self.tracking_events:
            events_by_type[event.event_type].append({
                'timestamp': event.timestamp,
                'ip_address': event.ip_address,
                'user_agent': event.user_agent
            })
        
        return {
            'target_id': self.id,
            'email': self.email,
            'status': self.status,
            'engagement_score': self.engagement_score,
            'last_activity': self.last_activity,
            'events': dict(events_by_type),
            'timeline': sorted([
                {
                    'type': event.event_type,
                    'timestamp': event.timestamp,
                    'details': {
                        'ip': event.ip_address,
                        'user_agent': event.user_agent[:50] + '...' if event.user_agent and len(event.user_agent) > 50 else event.user_agent
                    }
                }
                for event in self.tracking_events
            ], key=lambda x: x['timestamp'], reverse=True)
        }
    
    # === VALIDĂRI ===
    
    def validate(self):
        """
        Validează datele țintei
        
        Raises:
            ValidationError: Dacă datele nu sunt valide
        """
        # Validează email-ul (obligatoriu)
        if not self.email:
            raise ValidationError("Email address is required")
        
        try:
            validate_email(self.email)
        except ValidationError as e:
            raise ValidationError(f"Invalid email: {str(e)}")
        
        # Validează telefonul (opțional)
        if self.phone:
            try:
                validate_phone_number(self.phone)
            except ValidationError as e:
                raise ValidationError(f"Invalid phone: {str(e)}")
        
        # Validează lungimile câmpurilor
        if self.first_name and len(self.first_name) > 50:
            raise ValidationError("First name too long")
        
        if self.last_name and len(self.last_name) > 50:
            raise ValidationError("Last name too long")
        
        if self.company and len(self.company) > 100:
            raise ValidationError("Company name too long")
        
        return True
    
    # === METODE STATICE ===
    
    @staticmethod
    def create_from_csv_row(campaign_id, row):
        """
        Creează o țintă din rândul unui CSV
        
        Args:
            campaign_id: ID-ul campaniei
            row: Dicționarul cu datele din CSV
            
        Returns:
            Target: Noua țintă creată
        """
        # Mapare flexibilă pentru header-urile CSV
        email_fields = ['email', 'Email', 'EMAIL', 'e-mail', 'mail']
        phone_fields = ['phone', 'Phone', 'PHONE', 'telephone', 'mobile']
        first_name_fields = ['first_name', 'First Name', 'firstname', 'fname']
        last_name_fields = ['last_name', 'Last Name', 'lastname', 'lname']
        company_fields = ['company', 'Company', 'COMPANY', 'organization']
        
        def get_field_value(possible_fields):
            for field in possible_fields:
                if field in row and row[field]:
                    return row[field].strip()
            return None
        
        email = get_field_value(email_fields)
        if not email:
            raise ValidationError("Email field not found in CSV row")
        
        target = Target(
            campaign_id=campaign_id,
            email=email,
            phone=get_field_value(phone_fields),
            first_name=get_field_value(first_name_fields),
            last_name=get_field_value(last_name_fields),
            company=get_field_value(company_fields),
            position=row.get('position') or row.get('Position'),
            notes=row.get('notes') or row.get('Notes')
        )
        
        target.validate()
        return target
    
    @staticmethod
    def get_by_email_and_campaign(email, campaign_id):
        """
        Găsește o țintă după email și campanie
        
        Args:
            email: Adresa de email
            campaign_id: ID-ul campaniei
            
        Returns:
            Target or None: Ținta găsită sau None
        """
        return Target.query.filter_by(
            email=email.lower().strip(),
            campaign_id=campaign_id
        ).first()
    
    @staticmethod
    def get_targets_by_status(campaign_id, status):
        """
        Returnează țintele dintr-o campanie cu un anumit status
        
        Args:
            campaign_id: ID-ul campaniei
            status: Statusul căutat
            
        Returns:
            list: Lista țintelor
        """
        targets = Target.query.filter_by(campaign_id=campaign_id).all()
        return [target for target in targets if target.status == status]
    
    def to_dict(self):
        """
        Convertește ținta într-un dicționar pentru JSON
        
        Returns:
            dict: Reprezentarea țintei ca dicționar
        """
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'email': self.email,
            'phone': self.phone,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'display_name': self.display_name,
            'company': self.company,
            'position': self.position,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'status': self.status,
            'status_display': self.status_display,
            'engagement_score': self.engagement_score,
            'email_sent': self.email_sent,
            'sms_sent': self.sms_sent,
            'clicked_link': self.clicked_link,
            'entered_credentials': self.entered_credentials,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None
        }