from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship
from utils.database import db
from utils.validators import validate_template_content, ValidationError


class Template(db.Model):
    """
    Model pentru template-urile de email și SMS folosite în campanii
    
    Attributes:
        id: ID unic al template-ului
        name: Numele template-ului (pentru identificare în admin)
        type: Tipul template-ului (email, sms)
        subject: Subiectul (doar pentru email-uri)
        content: Conținutul template-ului cu placeholder-uri
        description: Descrierea template-ului
        
        # Metadata
        created_at: Data creării
        updated_at: Data ultimei modificări
        created_by: Cine a creat template-ul
        is_active: Template-ul este activ/disponibil
        
        # Template settings
        language: Limba template-ului (ro, en, etc.)
        category: Categoria template-ului (banking, social, work, etc.)
        difficulty_level: Nivelul de dificultate (easy, medium, hard)
        
        # Usage stats
        usage_count: De câte ori a fost folosit template-ul
        success_rate: Rata de succes medie
    """
    
    __tablename__ = 'templates'
    
    # === CÂMPURI PRINCIPALE ===
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    type = Column(
        Enum('email', 'sms', name='template_type'),
        nullable=False,
        default='email'
    )
    
    # === CONȚINUT ===
    subject = Column(String(200))  # Doar pentru email-uri
    content = Column(Text, nullable=False)
    description = Column(Text)
    
    # === METADATA ===
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(50), default='admin')
    is_active = Column(Boolean, default=True)
    
    # === SETTINGS ===
    language = Column(String(5), default='en')  # ISO language code
    category = Column(String(50))  # banking, social, work, government, etc.
    difficulty_level = Column(
        Enum('easy', 'medium', 'hard', name='difficulty_level'),
        default='medium'
    )
    
    # === USAGE STATS ===
    usage_count = Column(Integer, default=0)
    success_rate = Column(db.Float, default=0.0)  # Percentage
    
    def __init__(self, name, type, content, **kwargs):
        """
        Inițializează un nou template
        
        Args:
            name: Numele template-ului
            type: Tipul (email/sms)
            content: Conținutul template-ului
            **kwargs: Alte argumente opționale
        """
        self.name = name
        self.type = type
        self.content = content
        
        # Setează valorile opționale
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def __repr__(self):
        return f'<Template {self.name} ({self.type})>'
    
    def __str__(self):
        return f'{self.name} - {self.type.upper()} Template'
    
    # === PROPERTIES ===
    
    @property
    def is_email(self):
        """Verifică dacă template-ul este pentru email"""
        return self.type == 'email'
    
    @property
    def is_sms(self):
        """Verifică dacă template-ul este pentru SMS"""
        return self.type == 'sms'
    
    @property
    def content_length(self):
        """Lungimea conținutului template-ului"""
        return len(self.content) if self.content else 0
    
    @property
    def placeholder_count(self):
        """Numărul de placeholder-uri din template"""
        import re
        if not self.content:
            return 0
        placeholders = re.findall(r'{{[^}]+}}', self.content)
        return len(placeholders)
    
    @property
    def available_placeholders(self):
        """Lista placeholder-urilor disponibile în template"""
        import re
        if not self.content:
            return []
        placeholders = re.findall(r'{{([^}]+)}}', self.content)
        return list(set(placeholders))  # Remove duplicates
    
    @property
    def estimated_success_rate(self):
        """Rata de succes estimată bazată pe dificultate și categoria"""
        base_rates = {
            'easy': 0.45,
            'medium': 0.30,
            'hard': 0.15
        }
        
        category_multipliers = {
            'banking': 1.2,
            'social': 1.0,
            'work': 1.1,
            'government': 1.3,
            'shopping': 0.9
        }
        
        base_rate = base_rates.get(self.difficulty_level, 0.30)
        multiplier = category_multipliers.get(self.category, 1.0)
        
        return min(base_rate * multiplier, 0.60)  # Cap at 60%
    
    # === METODE BUSINESS ===
    
    def render_content(self, target_data=None, campaign_data=None):
        """
        Renderizează conținutul template-ului cu datele target-ului
        
        Args:
            target_data: Dicționar cu datele target-ului
            campaign_data: Dicționar cu datele campaniei
            
        Returns:
            str: Conținutul renderizat
        """
        if not self.content:
            return ""
        
        rendered_content = self.content
        
        # Default data
        default_data = {
            'target_name': 'User',
            'target_first_name': 'User',
            'target_last_name': '',
            'target_email': 'user@example.com',
            'target_company': 'Your Company',
            'target_position': 'Employee',
            'tracking_link': '#',
            'unsubscribe_link': '#',
            'current_date': datetime.now().strftime('%Y-%m-%d'),
            'current_year': datetime.now().year
        }
        
        # Merge cu datele target-ului
        if target_data:
            default_data.update(target_data)
        
        # Merge cu datele campaniei
        if campaign_data:
            default_data.update(campaign_data)
        
        # Înlocuiește placeholder-urile
        for key, value in default_data.items():
            placeholder = f'{{{{{key}}}}}'
            rendered_content = rendered_content.replace(placeholder, str(value))
        
        return rendered_content
    
    def render_subject(self, target_data=None, campaign_data=None):
        """
        Renderizează subiectul template-ului (doar pentru email-uri)
        
        Args:
            target_data: Dicționar cu datele target-ului
            campaign_data: Dicționar cu datele campaniei
            
        Returns:
            str: Subiectul renderizat
        """
        if not self.is_email or not self.subject:
            return ""
        
        rendered_subject = self.subject
        
        # Default data
        default_data = {
            'target_name': 'User',
            'target_first_name': 'User',
            'target_company': 'Your Company',
            'current_date': datetime.now().strftime('%Y-%m-%d')
        }
        
        # Merge cu datele furnizate
        if target_data:
            default_data.update(target_data)
        if campaign_data:
            default_data.update(campaign_data)
        
        # Înlocuiește placeholder-urile
        for key, value in default_data.items():
            placeholder = f'{{{{{key}}}}}'
            rendered_subject = rendered_subject.replace(placeholder, str(value))
        
        return rendered_subject
    
    def increment_usage(self):
        """Incrementează contorul de utilizare"""
        self.usage_count += 1
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def update_success_rate(self, new_rate):
        """
        Actualizează rata de succes cu o nouă valoare
        
        Args:
            new_rate: Noua rată de succes (0-100)
        """
        if 0 <= new_rate <= 100:
            # Calculează media ponderată
            if self.usage_count > 0:
                self.success_rate = ((self.success_rate * (self.usage_count - 1)) + new_rate) / self.usage_count
            else:
                self.success_rate = new_rate
            
            self.updated_at = datetime.utcnow()
            db.session.commit()
    
    def clone(self, new_name=None):
        """
        Clonează template-ul cu un nume nou
        
        Args:
            new_name: Numele noului template (dacă nu e specificat, se adaugă "Copy")
            
        Returns:
            Template: Noul template clonat
        """
        if not new_name:
            new_name = f"{self.name} - Copy"
        
        cloned = Template(
            name=new_name,
            type=self.type,
            content=self.content,
            subject=self.subject,
            description=self.description,
            language=self.language,
            category=self.category,
            difficulty_level=self.difficulty_level
        )
        
        return cloned
    
    # === VALIDĂRI ===
    
    def validate(self):
        """
        Validează datele template-ului
        
        Raises:
            ValidationError: Dacă datele nu sunt valide
        """
        if not self.name or len(self.name.strip()) < 3:
            raise ValidationError("Template name must be at least 3 characters")
        
        if self.type not in ['email', 'sms']:
            raise ValidationError("Template type must be 'email' or 'sms'")
        
        if not self.content:
            raise ValidationError("Template content is required")
        
        # Validează conținutul specific pentru tip
        validate_template_content(self.content, self.type)
        
        # Pentru email-uri, subiectul este obligatoriu
        if self.is_email and not self.subject:
            raise ValidationError("Subject is required for email templates")
        
        # Verifică dacă conține placeholder pentru tracking link
        if '{{tracking_link}}' not in self.content:
            raise ValidationError("Template must contain {{tracking_link}} placeholder")
        
        return True
    
    # === METODE STATICE ===
    
    @staticmethod
    def get_by_category(category):
        """Returnează template-urile dintr-o anumită categorie"""
        return Template.query.filter_by(category=category, is_active=True).all()
    
    @staticmethod
    def get_by_type(template_type):
        """Returnează template-urile de un anumit tip"""
        return Template.query.filter_by(type=template_type, is_active=True).all()
    
    @staticmethod
    def get_popular_templates(limit=5):
        """Returnează template-urile cele mai populare"""
        return Template.query.filter_by(is_active=True)\
                           .order_by(Template.usage_count.desc())\
                           .limit(limit).all()
    
    @staticmethod
    def get_high_success_templates(limit=5):
        """Returnează template-urile cu rata de succes mare"""
        return Template.query.filter_by(is_active=True)\
                           .filter(Template.success_rate > 20)\
                           .order_by(Template.success_rate.desc())\
                           .limit(limit).all()
    
    @staticmethod
    def search_templates(query):
        """
        Caută template-uri după nume, descriere sau conținut
        
        Args:
            query: Textul de căutat
            
        Returns:
            list: Lista template-urilor găsite
        """
        return Template.query.filter(
            db.or_(
                Template.name.contains(query),
                Template.description.contains(query),
                Template.content.contains(query)
            )
        ).filter_by(is_active=True).all()
    
    def to_dict(self):
        """
        Convertește template-ul într-un dicționar pentru JSON
        
        Returns:
            dict: Reprezentarea template-ului ca dicționar
        """
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'subject': self.subject,
            'content': self.content,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'is_active': self.is_active,
            'language': self.language,
            'category': self.category,
            'difficulty_level': self.difficulty_level,
            'usage_count': self.usage_count,
            'success_rate': self.success_rate,
            'content_length': self.content_length,
            'placeholder_count': self.placeholder_count,
            'available_placeholders': self.available_placeholders,
            'estimated_success_rate': self.estimated_success_rate
        }