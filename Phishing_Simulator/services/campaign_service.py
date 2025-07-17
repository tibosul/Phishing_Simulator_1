import csv
import io
from datetime import datetime, timedelta
from flask import current_app
from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError

from models.campaign import Campaign
from models.target import Target
from models.tracking import Tracking
from models.credential import Credential
from utils.database import db
from utils.validators import validate_campaign_name, validate_csv_format, ValidationError
from utils.helpers import sanitize_input, log_security_event
from utils.security import sanitize_input as secure_sanitize_input
import logging


class CampaignService:
    """
    Service pentru gestionarea campaniilor de phishing
    
    Oferă funcționalități pentru:
    - Crearea și gestionarea campaniilor
    - Import/export ținte din CSV
    - Statistici și rapoarte
    - Operații batch pe campanii
    """
    
    @staticmethod
    def create_campaign(name, campaign_type, description=None, **options):
        """
        Creează o nouă campanie
        
        Args:
            name: Numele campaniei
            campaign_type: Tipul campaniei (email, sms, both)
            description: Descrierea campaniei
            **options: Opțiuni suplimentare (auto_start, track_opens, etc.)
            
        Returns:
            Campaign: Campania creată
            
        Raises:
            ValidationError: Dacă datele nu sunt valide
        """
        try:
            # Validează numele campaniei
            validate_campaign_name(name)
            
            # Sanitizează input-urile cu funcția securizată
            name = secure_sanitize_input(name, allow_html=False, strict=True)
            description = secure_sanitize_input(description, allow_html=True, strict=False) if description else None
            
            # Verifică dacă numele este unic
            existing = Campaign.query.filter_by(name=name).first()
            if existing:
                raise ValidationError(f"Campaign with name '{name}' already exists")
            
            # Validează tipul campaniei
            if campaign_type not in ['email', 'sms', 'both']:
                raise ValidationError("Campaign type must be 'email', 'sms', or 'both'")
            
            # Creează campania
            campaign = Campaign(
                name=name,
                type=campaign_type,
                description=description,
                **options
            )
            
            # Validează și salvează
            campaign.validate()
            db.session.add(campaign)
            db.session.commit()
            
            logging.info(f"Campaign created: {campaign.name} (ID: {campaign.id})")
            log_security_event('campaign_created', f"Campaign '{campaign.name}' created")
            
            return campaign
            
        except IntegrityError as e:
            db.session.rollback()
            raise ValidationError("Database error: Campaign name might already exist")
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating campaign: {str(e)}")
            raise
    
    @staticmethod
    def update_campaign(campaign_id, **updates):
        """
        Actualizează o campanie existentă
        
        Args:
            campaign_id: ID-ul campaniei
            **updates: Câmpurile de actualizat
            
        Returns:
            Campaign: Campania actualizată
            
        Raises:
            ValidationError: Dacă campania nu există sau datele nu sunt valide
        """
        try:
            campaign = db.session.get(Campaign, campaign_id)
            if not campaign:
                raise ValidationError(f"Campaign with ID {campaign_id} not found")
            
            # Nu permite modificarea campaniilor active pentru anumite câmpuri
            restricted_fields = ['type'] if campaign.is_active else []
            
            updated = False
            for field, value in updates.items():
                if field in restricted_fields:
                    raise ValidationError(f"Cannot modify '{field}' of active campaign")
                
                if hasattr(campaign, field):
                    # Validări speciale
                    if field == 'name':
                        validate_campaign_name(value)
                        value = sanitize_input(value)
                        
                        # Verifică unicitatea numelui (exclude campania curentă)
                        existing = Campaign.query.filter(
                            Campaign.name == value,
                            Campaign.id != campaign_id
                        ).first()
                        if existing:
                            raise ValidationError(f"Campaign name '{value}' already exists")
                    
                    elif field == 'type' and value not in ['email', 'sms', 'both']:
                        raise ValidationError("Invalid campaign type")
                    
                    elif field == 'description':
                        value = sanitize_input(value) if value else None
                    
                    # Actualizează doar dacă valoarea e diferită
                    if getattr(campaign, field) != value:
                        setattr(campaign, field, value)
                        updated = True
            
            if updated:
                campaign.updated_at = datetime.utcnow()
                campaign.validate()
                db.session.commit()
                
                logging.info(f"Campaign updated: {campaign.name} (ID: {campaign.id})")
                log_security_event('campaign_updated', f"Campaign '{campaign.name}' updated")
            
            return campaign
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating campaign {campaign_id}: {str(e)}")
            raise
    
    @staticmethod
    def delete_campaign(campaign_id, force=False):
        """
        Șterge o campanie
        
        Args:
            campaign_id: ID-ul campaniei
            force: Forțează ștergerea chiar dacă campania e activă
            
        Returns:
            bool: True dacă campania a fost ștearsă
            
        Raises:
            ValidationError: Dacă campania nu poate fi ștearsă
        """
        try:
            campaign = db.session.get(Campaign, campaign_id)
            if not campaign:
                raise ValidationError(f"Campaign with ID {campaign_id} not found")
            
            # Verifică dacă campania poate fi ștearsă
            if campaign.is_active and not force:
                raise ValidationError("Cannot delete active campaign. Stop it first or use force=True")
            
            campaign_name = campaign.name
            
            # Șterge campania (cascade va șterge automat targets, tracking, credentials)
            db.session.delete(campaign)
            db.session.commit()
            
            logging.info(f"Campaign deleted: {campaign_name} (ID: {campaign_id})")
            log_security_event('campaign_deleted', f"Campaign '{campaign_name}' deleted")
            
            return True
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error deleting campaign {campaign_id}: {str(e)}")
            raise
    
    @staticmethod
    def add_targets_from_csv(campaign_id, csv_content, skip_duplicates=True):
        """
        Adaugă ținte dintr-un fișier CSV
        
        Args:
            campaign_id: ID-ul campaniei
            csv_content: Conținutul fișierului CSV
            skip_duplicates: Sare peste duplicatele de email
            
        Returns:
            dict: Statistici despre import (added, skipped, errors)
        """
        try:
            campaign = db.session.get(Campaign, campaign_id)
            if not campaign:
                raise ValidationError(f"Campaign with ID {campaign_id} not found")
            
            # Validează CSV-ul
            required_columns = ['email']
            validate_csv_format(csv_content, required_columns)
            
            # Parsează CSV-ul
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file)
            
            stats = {
                'added': 0,
                'skipped': 0,
                'errors': []
            }
            
            for row_num, row in enumerate(reader, start=2):  # Start from 2 (after header)
                try:
                    # Verifică duplicatele
                    email = row.get('email', '').strip().lower()
                    if not email:
                        stats['errors'].append(f"Row {row_num}: Email is required")
                        continue
                    
                    if skip_duplicates:
                        existing = Target.get_by_email_and_campaign(email, campaign_id)
                        if existing:
                            stats['skipped'] += 1
                            continue
                    
                    # Creează ținta
                    target = Target.create_from_csv_row(campaign_id, row)
                    db.session.add(target)
                    stats['added'] += 1
                    
                except ValidationError as e:
                    stats['errors'].append(f"Row {row_num}: {str(e)}")
                except Exception as e:
                    stats['errors'].append(f"Row {row_num}: Unexpected error - {str(e)}")
            
            # Salvează modificările
            if stats['added'] > 0:
                db.session.commit()
                logging.info(f"Added {stats['added']} targets to campaign {campaign.name}")
            else:
                db.session.rollback()
            
            return stats
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error importing CSV for campaign {campaign_id}: {str(e)}")
            raise
    
    @staticmethod
    def add_single_target(campaign_id, email, **target_data):
        """
        Adaugă o singură țintă la campanie
        
        Args:
            campaign_id: ID-ul campaniei
            email: Adresa de email
            **target_data: Date suplimentare despre țintă
            
        Returns:
            Target: Ținta creată
        """
        try:
            campaign = db.session.get(Campaign, campaign_id)
            if not campaign:
                raise ValidationError(f"Campaign with ID {campaign_id} not found")
            
            # Verifică duplicatele
            existing = Target.get_by_email_and_campaign(email, campaign_id)
            if existing:
                raise ValidationError(f"Target with email '{email}' already exists in this campaign")
            
            # Creează ținta
            target = Target(campaign_id=campaign_id, email=email, **target_data)
            target.validate()
            
            db.session.add(target)
            db.session.commit()
            
            logging.info(f"Target added: {email} to campaign {campaign.name}")
            
            return target
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding target to campaign {campaign_id}: {str(e)}")
            raise
    
    @staticmethod
    def get_campaign_statistics(campaign_id):
        """
        Returnează statistici detaliate pentru o campanie
        
        Args:
            campaign_id: ID-ul campaniei
            
        Returns:
            dict: Statistici detaliate
        """
        try:
            campaign = db.session.get(Campaign, campaign_id)
            if not campaign:
                raise ValidationError(f"Campaign with ID {campaign_id} not found")
            
            # Statistici de bază
            base_stats = campaign.get_statistics()
            
            # Statistici suplimentare
            targets_by_status = {}
            for status in ['pending', 'contacted', 'clicked_link', 'credentials_entered']:
                targets_by_status[status] = len(Target.get_targets_by_status(campaign_id, status))
            
            # Activitate pe zile (ultimele 30 de zile)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            daily_activity = db.session.query(
                func.date(Tracking.timestamp).label('date'),
                func.count(Tracking.id).label('events')
            ).filter(
                Tracking.campaign_id == campaign_id,
                Tracking.timestamp >= thirty_days_ago
            ).group_by(func.date(Tracking.timestamp)).all()
            
            # Top IP-uri
            top_ips = db.session.query(
                Tracking.ip_address,
                func.count(Tracking.id).label('count')
            ).filter(
                Tracking.campaign_id == campaign_id
            ).group_by(Tracking.ip_address).order_by(desc('count')).limit(10).all()
            
            # Îmbunătățește statisticile de bază
            base_stats.update({
                'targets_by_status': targets_by_status,
                'daily_activity': [
                    {'date': str(day.date), 'events': day.events}
                    for day in daily_activity
                ],
                'top_ips': [
                    {'ip': ip.ip_address, 'count': ip.count}
                    for ip in top_ips if ip.ip_address
                ]
            })
            
            return base_stats
            
        except Exception as e:
            logging.error(f"Error getting statistics for campaign {campaign_id}: {str(e)}")
            raise
    
    @staticmethod
    def export_campaign_data(campaign_id, include_credentials=False):
        """
        Exportă datele unei campanii în format CSV
        
        Args:
            campaign_id: ID-ul campaniei
            include_credentials: Include credențialele capturate
            
        Returns:
            str: Conținutul CSV
        """
        try:
            campaign = db.session.get(Campaign, campaign_id)
            if not campaign:
                raise ValidationError(f"Campaign with ID {campaign_id} not found")
            
            output = io.StringIO()
            
            if include_credentials:
                # Export cu credențiale
                fieldnames = [
                    'email', 'first_name', 'last_name', 'company', 'position',
                    'status', 'engagement_score', 'captured_username', 'captured_password',
                    'credential_capture_time', 'last_activity'
                ]
                
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                
                for target in campaign.targets:
                    # Găsește credențialele capturate pentru această țintă
                    credential = None
                    if target.captured_credentials:
                        credential = target.captured_credentials[0]  # Prima credențială
                    
                    writer.writerow({
                        'email': target.email,
                        'first_name': target.first_name or '',
                        'last_name': target.last_name or '',
                        'company': target.company or '',
                        'position': target.position or '',
                        'status': target.status_display,
                        'engagement_score': target.engagement_score,
                        'captured_username': credential.username if credential else '',
                        'captured_password': credential.password if credential else '',
                        'credential_capture_time': credential.captured_at.isoformat() if credential else '',
                        'last_activity': target.last_activity.isoformat() if target.last_activity else ''
                    })
            else:
                # Export simplu
                fieldnames = [
                    'email', 'first_name', 'last_name', 'company', 'position',
                    'phone', 'status', 'engagement_score', 'email_sent', 'sms_sent',
                    'clicked_link', 'entered_credentials', 'last_activity'
                ]
                
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                
                for target in campaign.targets:
                    writer.writerow({
                        'email': target.email,
                        'first_name': target.first_name or '',
                        'last_name': target.last_name or '',
                        'company': target.company or '',
                        'position': target.position or '',
                        'phone': target.phone or '',
                        'status': target.status_display,
                        'engagement_score': target.engagement_score,
                        'email_sent': target.email_sent,
                        'sms_sent': target.sms_sent,
                        'clicked_link': target.clicked_link,
                        'entered_credentials': target.entered_credentials,
                        'last_activity': target.last_activity.isoformat() if target.last_activity else ''
                    })
            
            content = output.getvalue()
            output.close()
            
            logging.info(f"Campaign data exported: {campaign.name}")
            
            return content
            
        except Exception as e:
            logging.error(f"Error exporting campaign {campaign_id}: {str(e)}")
            raise
    
    @staticmethod
    def get_dashboard_stats():
        """
        Returnează statistici pentru dashboard-ul principal
        
        Returns:
            dict: Statistici generale
        """
        try:
            total_campaigns = Campaign.query.count()
            active_campaigns = Campaign.query.filter_by(status='active').count()
            total_targets = Target.query.count()
            total_credentials = Credential.query.count()
            
            # Campanii recente
            recent_campaigns = Campaign.get_recent_campaigns(5)
            
            # Activitate recentă (ultimele 24 ore)
            yesterday = datetime.utcnow() - timedelta(days=1)
            recent_activity = Tracking.query.filter(
                Tracking.timestamp >= yesterday
            ).count()
            
            return {
                'totals': {
                    'campaigns': total_campaigns,
                    'active_campaigns': active_campaigns,
                    'targets': total_targets,
                    'credentials': total_credentials
                },
                'recent_activity': recent_activity,
                'recent_campaigns': [
                    {
                        'id': c.id,
                        'name': c.name,
                        'type': c.type,
                        'status': c.status,
                        'targets': c.total_targets,
                        'success_rate': c.success_rate
                    }
                    for c in recent_campaigns
                ]
            }
            
        except Exception as e:
            logging.error(f"Error getting dashboard stats: {str(e)}")
            raise
    
    @staticmethod
    def search_campaigns(query, filters=None):
        """
        Caută campanii cu filtre
        
        Args:
            query: Textul de căutat
            filters: Filtre suplimentare (status, type, etc.)
            
        Returns:
            list: Lista campaniilor găsite
        """
        try:
            campaigns_query = Campaign.query
            
            # Aplică textul de căutare
            if query:
                query = f"%{query}%"
                campaigns_query = campaigns_query.filter(
                    db.or_(
                        Campaign.name.like(query),
                        Campaign.description.like(query)
                    )
                )
            
            # Aplică filtrele
            if filters:
                if 'status' in filters and filters['status']:
                    campaigns_query = campaigns_query.filter_by(status=filters['status'])
                
                if 'type' in filters and filters['type']:
                    campaigns_query = campaigns_query.filter_by(type=filters['type'])
                
                if 'created_after' in filters and filters['created_after']:
                    campaigns_query = campaigns_query.filter(
                        Campaign.created_at >= filters['created_after']
                    )
            
            # Ordonează după data creării (cele mai noi primul)
            campaigns = campaigns_query.order_by(desc(Campaign.created_at)).all()
            
            return campaigns
            
        except Exception as e:
            logging.error(f"Error searching campaigns: {str(e)}")
            raise