from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from utils.database import db
import json


class Tracking(db.Model):
    """
    Model pentru evenimentele de tracking în campaniile de phishing
    
    Attributes:
        id: ID unic al evenimentului
        campaign_id: ID-ul campaniei asociate
        target_id: ID-ul țintei asociate (opțional pentru unele evenimente)
        event_type: Tipul evenimentului
        timestamp: Momentul când s-a întâmplat evenimentul
        
        # Client info
        ip_address: Adresa IP a clientului
        user_agent: User agent string
        browser_info: Informații despre browser (JSON)
        device_info: Informații despre device (JSON)
        location_info: Informații despre locație (JSON)
        
        # Event details
        event_data: Date suplimentare specifice evenimentului (JSON)
        referrer: De unde a venit utilizatorul
        session_id: ID-ul sesiunii pentru gruparea evenimentelor
        
        # Metadata
        tracking_token: Token unic pentru acest eveniment
        is_unique: Dacă evenimentul este unic pentru target
        processed: Dacă evenimentul a fost procesat
    """
    
    __tablename__ = 'tracking'
    
    # === CÂMPURI PRINCIPALE ===
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), nullable=False)
    target_id = Column(Integer, ForeignKey('targets.id'))  # Opțional pentru unele evenimente
    
    # === TIP EVENIMENT ===
    event_type = Column(
        Enum(
            'email_sent',           # Email trimis
            'sms_sent',            # SMS trimis
            'email_opened',        # Email deschis (tracking pixel)
            'link_clicked',        # Link accesat
            'page_visited',        # Pagină vizitată (fake site)
            'form_viewed',         # Formularul de login vizualizat
            'credentials_entered', # Credențiale introduse
            'form_submitted',      # Formularul submis
            'download_clicked',    # Click pe download (dacă aplicabil)
            'attachment_opened',   # Attachment deschis
            'redirect_followed',   # Redirect urmărit către site real
            name='tracking_event_type'
        ),
        nullable=False
    )
    
    # === TIMING ===
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # === CLIENT INFO ===
    ip_address = Column(String(45))  # IPv6 compatible
    user_agent = Column(Text)
    browser_info = Column(Text)  # JSON string
    device_info = Column(Text)   # JSON string
    location_info = Column(Text) # JSON string (dacă avem GeoIP)
    
    # === EVENT DETAILS ===
    event_data = Column(Text)    # JSON string cu date specifice
    referrer = Column(String(500))
    session_id = Column(String(64))
    
    # === METADATA ===
    tracking_token = Column(String(64), unique=True)
    is_unique = Column(Boolean, default=True)
    processed = Column(Boolean, default=False)
    
    def __init__(self, campaign_id, event_type, **kwargs):
        """
        Inițializează un nou eveniment de tracking
        
        Args:
            campaign_id: ID-ul campaniei
            event_type: Tipul evenimentului
            **kwargs: Alte argumente opționale
        """
        self.campaign_id = campaign_id
        self.event_type = event_type
        
        # Setează valorile opționale
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        # Generează tracking token dacă nu e furnizat
        if not self.tracking_token:
            self.tracking_token = self._generate_tracking_token()
    
    def __repr__(self):
        return f'<Tracking {self.event_type} - Campaign {self.campaign_id}>'
    
    def __str__(self):
        target_info = f" (Target {self.target_id})" if self.target_id else ""
        return f'{self.event_type} - {self.timestamp.strftime("%Y-%m-%d %H:%M")}{target_info}'
    
    # === PROPERTIES ===
    
    @property
    def browser_data(self):
        """Returnează informațiile despre browser ca dicționar"""
        if self.browser_info:
            try:
                return json.loads(self.browser_info)
            except json.JSONDecodeError:
                return {}
        return {}
    
    @browser_data.setter
    def browser_data(self, data):
        """Setează informațiile despre browser"""
        if data:
            self.browser_info = json.dumps(data)
        else:
            self.browser_info = None
    
    @property
    def device_data(self):
        """Returnează informațiile despre device ca dicționar"""
        if self.device_info:
            try:
                return json.loads(self.device_info)
            except json.JSONDecodeError:
                return {}
        return {}
    
    @device_data.setter
    def device_data(self, data):
        """Setează informațiile despre device"""
        if data:
            self.device_info = json.dumps(data)
        else:
            self.device_info = None
    
    @property
    def location_data(self):
        """Returnează informațiile despre locație ca dicționar"""
        if self.location_info:
            try:
                return json.loads(self.location_info)
            except json.JSONDecodeError:
                return {}
        return {}
    
    @location_data.setter
    def location_data(self, data):
        """Setează informațiile despre locație"""
        if data:
            self.location_info = json.dumps(data)
        else:
            self.location_info = None
    
    @property
    def extra_data(self):
        """Returnează datele suplimentare ca dicționar"""
        if self.event_data:
            try:
                return json.loads(self.event_data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    @extra_data.setter
    def extra_data(self, data):
        """Setează datele suplimentare"""
        if data:
            self.event_data = json.dumps(data)
        else:
            self.event_data = None
    
    @property
    def time_since_campaign_start(self):
        """Timpul trecut de la începutul campaniei"""
        if hasattr(self, 'campaign') and self.campaign.started_at:
            return self.timestamp - self.campaign.started_at
        return None
    
    @property
    def is_conversion_event(self):
        """Verifică dacă evenimentul este o conversie (credential capture)"""
        return self.event_type == 'credentials_entered'
    
    @property
    def is_engagement_event(self):
        """Verifică dacă evenimentul indică engagement"""
        engagement_events = [
            'email_opened', 'link_clicked', 'page_visited', 
            'form_viewed', 'credentials_entered'
        ]
        return self.event_type in engagement_events
    
    # === METODE BUSINESS ===
    
    def mark_as_processed(self):
        """Marchează evenimentul ca procesat"""
        self.processed = True
        db.session.commit()
    
    def update_location_from_ip(self):
        """
        Actualizează informațiile de locație pe baza IP-ului
        (placeholder pentru integrarea cu servicii GeoIP)
        """
        if self.ip_address and not self.location_data:
            # Aici s-ar integra cu un serviciu GeoIP
            # Pentru demo, setăm date fictive
            location_data = {
                'country': 'Romania',
                'city': 'Bucharest',
                'region': 'Bucharest',
                'timezone': 'Europe/Bucharest',
                'coordinates': {
                    'lat': 44.4268,
                    'lon': 26.1025
                }
            }
            self.location_data = location_data
    
    def parse_user_agent(self):
        """
        Parsează user agent string pentru a extrage informații despre browser și device
        """
        if not self.user_agent:
            return
        
        # Implementare simplificată - în practică s-ar folosi o librărie specializată
        user_agent = self.user_agent.lower()
        
        # Browser detection
        browser_data = {
            'name': 'Unknown',
            'version': 'Unknown',
            'engine': 'Unknown'
        }
        
        if 'chrome' in user_agent:
            browser_data['name'] = 'Chrome'
            browser_data['engine'] = 'Blink'
        elif 'firefox' in user_agent:
            browser_data['name'] = 'Firefox'
            browser_data['engine'] = 'Gecko'
        elif 'safari' in user_agent:
            browser_data['name'] = 'Safari'
            browser_data['engine'] = 'WebKit'
        elif 'edge' in user_agent:
            browser_data['name'] = 'Edge'
            browser_data['engine'] = 'Blink'
        
        # Device detection
        device_data = {
            'type': 'Desktop',
            'os': 'Unknown',
            'is_mobile': False,
            'is_tablet': False
        }
        
        if any(mobile in user_agent for mobile in ['mobile', 'android', 'iphone']):
            device_data['type'] = 'Mobile'
            device_data['is_mobile'] = True
        elif 'tablet' in user_agent or 'ipad' in user_agent:
            device_data['type'] = 'Tablet'
            device_data['is_tablet'] = True
        
        if 'windows' in user_agent:
            device_data['os'] = 'Windows'
        elif 'mac' in user_agent:
            device_data['os'] = 'macOS'
        elif 'linux' in user_agent:
            device_data['os'] = 'Linux'
        elif 'android' in user_agent:
            device_data['os'] = 'Android'
        elif 'ios' in user_agent:
            device_data['os'] = 'iOS'
        
        self.browser_data = browser_data
        self.device_data = device_data
    
    def calculate_time_to_action(self, reference_event_type='email_sent'):
        """
        Calculează timpul până la această acțiune de la un eveniment de referință
        
        Args:
            reference_event_type: Tipul evenimentului de referință
            
        Returns:
            timedelta or None: Timpul trecut
        """
        if not self.target_id:
            return None
        
        reference_event = Tracking.query.filter_by(
            campaign_id=self.campaign_id,
            target_id=self.target_id,
            event_type=reference_event_type
        ).order_by(Tracking.timestamp.asc()).first()
        
        if reference_event:
            return self.timestamp - reference_event.timestamp
        
        return None
    
    def _generate_tracking_token(self):
        """Generează un token unic pentru tracking"""
        import secrets
        return secrets.token_urlsafe(32)
    
    # === METODE STATICE ===
    
    @staticmethod
    def create_event(campaign_id, event_type, target_id=None, **kwargs):
        """
        Creează un nou eveniment de tracking
        
        Args:
            campaign_id: ID-ul campaniei
            event_type: Tipul evenimentului
            target_id: ID-ul țintei (opțional)
            **kwargs: Date suplimentare
            
        Returns:
            Tracking: Evenimentul creat
        """
        tracking = Tracking(
            campaign_id=campaign_id,
            event_type=event_type,
            target_id=target_id,
            **kwargs
        )
        
        # Parse user agent dacă e disponibil
        if tracking.user_agent:
            tracking.parse_user_agent()
        
        # Update location dacă e disponibil IP
        if tracking.ip_address:
            tracking.update_location_from_ip()
        
        db.session.add(tracking)
        db.session.commit()
        
        return tracking
    
    @staticmethod
    def get_campaign_timeline(campaign_id, limit=50):
        """Returnează timeline-ul evenimentelor pentru o campanie"""
        return Tracking.query.filter_by(campaign_id=campaign_id)\
                           .order_by(Tracking.timestamp.desc())\
                           .limit(limit).all()
    
    @staticmethod
    def get_target_journey(campaign_id, target_id):
        """Returnează călătoria unui target prin campanie"""
        return Tracking.query.filter_by(
            campaign_id=campaign_id,
            target_id=target_id
        ).order_by(Tracking.timestamp.asc()).all()
    
    @staticmethod
    def get_conversion_funnel(campaign_id):
        """
        Returnează datele pentru funnel-ul de conversie
        
        Returns:
            dict: Numărul de utilizatori pentru fiecare pas
        """
        from sqlalchemy import func
        
        funnel_steps = [
            'email_sent',
            'email_opened', 
            'link_clicked',
            'page_visited',
            'form_viewed',
            'credentials_entered'
        ]
        
        funnel_data = {}
        
        for step in funnel_steps:
            count = db.session.query(func.count(Tracking.target_id.distinct()))\
                             .filter_by(campaign_id=campaign_id, event_type=step)\
                             .scalar()
            funnel_data[step] = count or 0
        
        return funnel_data
    
    @staticmethod
    def get_hourly_activity(campaign_id, days=7):
        """Returnează activitatea pe ore pentru ultimele zile"""
        from sqlalchemy import func
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        results = db.session.query(
            func.extract('hour', Tracking.timestamp).label('hour'),
            func.count(Tracking.id).label('count')
        ).filter(
            Tracking.campaign_id == campaign_id,
            Tracking.timestamp >= start_date
        ).group_by('hour').all()
        
        # Convert to dict with all 24 hours
        hourly_data = {hour: 0 for hour in range(24)}
        for result in results:
            hourly_data[int(result.hour)] = result.count
        
        return hourly_data
    
    @staticmethod
    def get_top_user_agents(campaign_id, limit=10):
        """Returnează cele mai comune user agents"""
        from sqlalchemy import func
        
        return db.session.query(
            Tracking.user_agent,
            func.count(Tracking.id).label('count')
        ).filter_by(campaign_id=campaign_id)\
         .group_by(Tracking.user_agent)\
         .order_by(func.count(Tracking.id).desc())\
         .limit(limit).all()
    
    def to_dict(self):
        """
        Convertește evenimentul într-un dicționar pentru JSON
        
        Returns:
            dict: Reprezentarea evenimentului ca dicționar
        """
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'target_id': self.target_id,
            'event_type': self.event_type,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'browser_data': self.browser_data,
            'device_data': self.device_data,
            'location_data': self.location_data,
            'extra_data': self.extra_data,
            'referrer': self.referrer,
            'session_id': self.session_id,
            'tracking_token': self.tracking_token,
            'is_unique': self.is_unique,
            'processed': self.processed,
            'is_conversion_event': self.is_conversion_event,
            'is_engagement_event': self.is_engagement_event
        }