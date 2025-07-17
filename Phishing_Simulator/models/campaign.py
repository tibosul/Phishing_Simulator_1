from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship
from utils.database import db


class Campaign(db.Model):
    """
    Model pentru campaniile de phishing
    
    Attributes:
        id: ID unic al campaniei
        name: Numele campaniei
        description: Descrierea campaniei
        type: Tipul campaniei (email, sms, both)
        status: Statusul campaniei (draft, active, paused, completed)
        created_at: Data creării
        updated_at: Data ultimei modificări
        started_at: Data pornirii campaniei
        ended_at: Data încheierii campaniei
        created_by: Cine a creat campania (pentru viitor - multi-user)
        
        # Setări specifice
        auto_start: Pornire automată la crearea țintelor
        track_opens: Urmărire deschideri email-uri
        track_clicks: Urmărire click-uri pe linkuri
        
        # Relații cu alte modele
        targets: Lista țintelor asociate acestei campanii
        tracking_events: Lista evenimentelor de tracking
        captured_credentials: Lista credențialelor capturate
    """
    
    __tablename__ = 'campaigns'
    
    # === CÂMPURI PRINCIPALE ===
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    
    # === TIP ȘI STATUS ===
    type = Column(
        Enum('email', 'sms', 'both', name='campaign_type'),
        nullable=False,
        default='email'
    )
    
    status = Column(
        Enum('draft', 'active', 'paused', 'completed', name='campaign_status'),
        nullable=False,
        default='draft'
    )
    
    # === TIMESTAMPS ===
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    
    # === SETĂRI ===
    auto_start = Column(Boolean, default=False)
    track_opens = Column(Boolean, default=True)
    track_clicks = Column(Boolean, default=True)
    
    # === METADATA ===
    created_by = Column(String(50), default='admin')  # Pentru viitor - multi-user
    
    # === RELAȚII ===
    targets = relationship('Target', backref='campaign', lazy=True, cascade='all, delete-orphan')
    tracking_events = relationship('Tracking', backref='campaign', lazy=True, cascade='all, delete-orphan')
    captured_credentials = relationship('Credential', backref='campaign', lazy=True, cascade='all, delete-orphan')
    
    def __init__(self, name, type='email', description=None, **kwargs):
        """
        Inițializează o nouă campanie
        
        Args:
            name: Numele campaniei
            type: Tipul campaniei (email, sms, both)
            description: Descrierea campaniei
            **kwargs: Alte argumente opționale
        """
        self.name = name
        self.type = type
        self.description = description
        
        # Setează valorile opționale
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def __repr__(self):
        return f'<Campaign {self.name} ({self.status})>'
    
    def __str__(self):
        return f'{self.name} - {self.type.upper()} Campaign'
    
    # === PROPERTIES ===
    
    @property
    def is_active(self):
        """Verifică dacă campania este activă"""
        return self.status == 'active'
    
    @property
    def is_completed(self):
        """Verifică dacă campania este completată"""
        return self.status == 'completed'
    
    @property
    def duration(self):
        """Calculează durata campaniei"""
        if self.started_at and self.ended_at:
            return self.ended_at - self.started_at
        elif self.started_at:
            return datetime.utcnow() - self.started_at
        return None
    
    @property
    def total_targets(self):
        """Numărul total de ținte"""
        return len(self.targets)
    
    @property
    def total_clicks(self):
        """Numărul total de click-uri"""
        return len([event for event in self.tracking_events if event.event_type == 'link_clicked'])
    
    @property
    def total_credentials(self):
        """Numărul total de credențiale capturate"""
        return len(self.captured_credentials)
    
    @property
    def success_rate(self):
        """Rata de succes (credențiale / ținte)"""
        if self.total_targets == 0:
            return 0
        return (self.total_credentials / self.total_targets) * 100
    
    @property
    def click_rate(self):
        """Rata de click-uri (click-uri / ținte)"""
        if self.total_targets == 0:
            return 0
        return (self.total_clicks / self.total_targets) * 100
    
    # === METODE BUSINESS ===
    
    def start(self):
        """
        Pornește campania
        
        Returns:
            bool: True dacă campania a fost pornită cu succes
        """
        if self.status != 'draft':
            raise ValueError(f"Cannot start campaign with status: {self.status}")
        
        if self.total_targets == 0:
            raise ValueError("Cannot start campaign without targets")
        
        self.status = 'active'
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        
        db.session.commit()
        return True
    
    def pause(self):
        """
        Pune campania în pauză
        
        Returns:
            bool: True dacă campania a fost pusă în pauză
        """
        if self.status != 'active':
            raise ValueError(f"Cannot pause campaign with status: {self.status}")
        
        self.status = 'paused'
        self.updated_at = datetime.utcnow()
        
        db.session.commit()
        return True
    
    def resume(self):
        """
        Reia o campanie pusă în pauză
        
        Returns:
            bool: True dacă campania a fost reluată
        """
        if self.status != 'paused':
            raise ValueError(f"Cannot resume campaign with status: {self.status}")
        
        self.status = 'active'
        self.updated_at = datetime.utcnow()
        
        db.session.commit()
        return True
    
    def complete(self):
        """
        Marchează campania ca fiind completată
        
        Returns:
            bool: True dacă campania a fost completată
        """
        if self.status not in ['active', 'paused']:
            raise ValueError(f"Cannot complete campaign with status: {self.status}")
        
        self.status = 'completed'
        self.ended_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        
        db.session.commit()
        return True
    
    def get_statistics(self):
        """
        Returnează statistici detaliate despre campanie
        
        Returns:
            dict: Dicționar cu statistici
        """
        from models.tracking import Tracking
        
        # Calculează statistici pentru evenimente
        events_stats = {}
        for event in self.tracking_events:
            event_type = event.event_type
            if event_type not in events_stats:
                events_stats[event_type] = 0
            events_stats[event_type] += 1
        
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'status': self.status,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'ended_at': self.ended_at,
            'duration': str(self.duration) if self.duration else None,
            'targets': {
                'total': self.total_targets,
            },
            'performance': {
                'total_clicks': self.total_clicks,
                'click_rate': round(self.click_rate, 2),
                'total_credentials': self.total_credentials,
                'success_rate': round(self.success_rate, 2),
            },
            'events': events_stats
        }
    
    # === METODE STATICE ===
    
    @staticmethod
    def get_active_campaigns():
        """Returnează toate campaniile active"""
        return Campaign.query.filter_by(status='active').all()
    
    @staticmethod
    def get_recent_campaigns(limit=5):
        """Returnează cele mai recente campanii"""
        return Campaign.query.order_by(Campaign.created_at.desc()).limit(limit).all()
    
    @staticmethod
    def search_campaigns(query):
        """
        Caută campanii după nume sau descriere
        
        Args:
            query: Textul de căutat
            
        Returns:
            list: Lista campaniilor găsite
        """
        return Campaign.query.filter(
            db.or_(
                Campaign.name.contains(query),
                Campaign.description.contains(query)
            )
        ).all()
    
    # === VALIDĂRI ===
    
    def validate(self):
        """
        Validează datele campaniei
        
        Raises:
            ValueError: Dacă datele nu sunt valide
        """
        if not self.name or len(self.name.strip()) < 3:
            raise ValueError("Campaign name must be at least 3 characters")
        
        if self.type not in ['email', 'sms', 'both']:
            raise ValueError("Campaign type must be 'email', 'sms', or 'both'")
        
        # Set default status if not set
        if self.status is None:
            self.status = 'draft'
        
        if self.status not in ['draft', 'active', 'paused', 'completed']:
            raise ValueError("Invalid campaign status")
        
        return True
    
    def to_dict(self):
        """
        Convertește campania într-un dicționar pentru JSON
        
        Returns:
            dict: Reprezentarea campaniei ca dicționar
        """
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'type': self.type,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'auto_start': self.auto_start,
            'track_opens': self.track_opens,
            'track_clicks': self.track_clicks,
            'created_by': self.created_by,
            'statistics': {
                'total_targets': self.total_targets,
                'total_clicks': self.total_clicks,
                'total_credentials': self.total_credentials,
                'success_rate': self.success_rate,
                'click_rate': self.click_rate
            }
        }