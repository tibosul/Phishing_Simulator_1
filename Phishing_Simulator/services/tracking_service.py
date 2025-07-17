import logging
from datetime import datetime, timedelta
from flask import request, current_app
from sqlalchemy import func, desc
from user_agents import parse

from models.campaign import Campaign
from models.target import Target
from models.tracking import Tracking
from models.credential import Credential
from utils.database import db
from utils.helpers import get_client_ip, get_user_agent, generate_tracking_token, log_security_event
from utils.validators import ValidationError


class TrackingService:
    """
    Service pentru urmărirea și analiza evenimentelor în campaniile de phishing
    
    Features:
    - Email opens (tracking pixel)
    - Link clicks 
    - Page visits (fake site)
    - Form submissions
    - Device fingerprinting
    - Analytics și conversion funnels
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def track_email_open(self, campaign_id, target_id, tracking_token=None):
        """
        Trackează deschiderea unui email prin tracking pixel
        
        Args:
            campaign_id: ID-ul campaniei
            target_id: ID-ul țintei
            tracking_token: Token de tracking (opțional)
            
        Returns:
            Tracking: Evenimentul creat
        """
        try:
            # Verifică validitatea
            campaign = db.session.get(Campaign, campaign_id)
            target = db.session.get(Target, target_id)
            
            if not campaign or not target:
                raise ValidationError("Invalid campaign or target ID")
            
            # Verifică dacă e prima deschidere (pentru unicitate)
            existing_open = Tracking.query.filter_by(
                campaign_id=campaign_id,
                target_id=target_id,
                event_type='email_opened'
            ).first()
            
            is_unique = existing_open is None
            
            # Parsează informații despre client
            user_agent_string = get_user_agent()
            user_agent = parse(user_agent_string)
            
            # Date despre eveniment
            event_data = {
                'tracking_token': tracking_token,
                'referrer': request.headers.get('Referer', '') if request else '',
                'is_first_open': is_unique,
                'open_count': 1 if is_unique else existing_open.extra_data.get('open_count', 1) + 1
            }
            
            # Informații browser
            browser_data = {
                'browser': user_agent.browser.family,
                'browser_version': user_agent.browser.version_string,
                'os': user_agent.os.family,
                'os_version': user_agent.os.version_string,
                'device_family': user_agent.device.family
            }
            
            # Informații device
            device_data = {
                'is_mobile': user_agent.is_mobile,
                'is_tablet': user_agent.is_tablet,
                'is_pc': user_agent.is_pc,
                'is_bot': user_agent.is_bot
            }
            
            # Creează evenimentul
            tracking_event = Tracking(
                campaign_id=campaign_id,
                event_type='email_opened',
                target_id=target_id,
                ip_address=get_client_ip(),
                user_agent=user_agent_string,
                tracking_token=tracking_token,
                is_unique=is_unique
            )
            
            tracking_event.browser_data = browser_data
            tracking_event.device_data = device_data
            tracking_event.extra_data = event_data
            
            db.session.add(tracking_event)
            db.session.commit()
            
            self.logger.info(f"Email open tracked: Campaign {campaign_id}, Target {target_id} ({'first time' if is_unique else 'repeat'})")
            
            if is_unique:
                log_security_event('email_opened', f"Email opened by {target.email}")
            
            return tracking_event
            
        except Exception as e:
            self.logger.error(f"Error tracking email open: {str(e)}")
            raise
    
    def track_link_click(self, campaign_id, target_id, destination_url=None, tracking_token=None):
        """
        Trackează click pe link din email
        
        Args:
            campaign_id: ID-ul campaniei
            target_id: ID-ul țintei
            destination_url: URL destinație
            tracking_token: Token de tracking
            
        Returns:
            tuple: (tracking_event, redirect_url)
        """
        try:
            campaign = db.session.get(Campaign, campaign_id)
            target = db.session.get(Target, target_id)
            
            if not campaign or not target:
                raise ValidationError("Invalid campaign or target ID")
            
            # Verifică dacă e primul click
            existing_click = Tracking.query.filter_by(
                campaign_id=campaign_id,
                target_id=target_id,
                event_type='link_clicked'
            ).first()
            
            is_unique = existing_click is None
            
            # Construiește URL-ul de destinație (site fake)
            if not destination_url:
                base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
                destination_url = f"{base_url}/revolut/login?c={campaign_id}&t={target_id}&token={tracking_token}"
            
            # Parsează client info
            user_agent_string = get_user_agent()
            user_agent = parse(user_agent_string)
            
            event_data = {
                'destination_url': destination_url,
                'tracking_token': tracking_token,
                'referrer': request.headers.get('Referer', '') if request else '',
                'is_first_click': is_unique,
                'click_count': 1 if is_unique else existing_click.extra_data.get('click_count', 1) + 1
            }
            
            browser_data = {
                'browser': user_agent.browser.family,
                'browser_version': user_agent.browser.version_string,
                'os': user_agent.os.family,
                'device_family': user_agent.device.family
            }
            
            device_data = {
                'is_mobile': user_agent.is_mobile,
                'is_tablet': user_agent.is_tablet,
                'is_pc': user_agent.is_pc
            }
            
            # Creează evenimentul
            tracking_event = Tracking(
                campaign_id=campaign_id,
                event_type='link_clicked',
                target_id=target_id,
                ip_address=get_client_ip(),
                user_agent=user_agent_string,
                tracking_token=tracking_token,
                is_unique=is_unique
            )
            
            tracking_event.browser_data = browser_data
            tracking_event.device_data = device_data
            tracking_event.extra_data = event_data
            
            db.session.add(tracking_event)
            db.session.commit()
            
            # Actualizează statusul target-ului
            if is_unique:
                target.mark_link_clicked()
            
            self.logger.info(f"Link click tracked: Campaign {campaign_id}, Target {target_id}")
            log_security_event('link_clicked', f"Link clicked by {target.email}")
            
            return tracking_event, destination_url
            
        except Exception as e:
            self.logger.error(f"Error tracking link click: {str(e)}")
            raise
    
    def track_page_visit(self, campaign_id, target_id, page_url, tracking_token=None):
        """
        Trackează vizitarea unei pagini din site-ul fake
        
        Args:
            campaign_id: ID-ul campaniei
            target_id: ID-ul țintei  
            page_url: URL-ul paginii
            tracking_token: Token de tracking
            
        Returns:
            Tracking: Evenimentul creat
        """
        try:
            user_agent_string = get_user_agent()
            user_agent = parse(user_agent_string)
            
            event_data = {
                'page_url': page_url,
                'tracking_token': tracking_token,
                'referrer': request.headers.get('Referer', '') if request else '',
                'session_duration': 0  # Va fi actualizat de JS
            }
            
            tracking_event = Tracking(
                campaign_id=campaign_id,
                event_type='page_visited',
                target_id=target_id,
                ip_address=get_client_ip(),
                user_agent=user_agent_string,
                tracking_token=tracking_token
            )
            
            tracking_event.extra_data = event_data
            
            db.session.add(tracking_event)
            db.session.commit()
            
            self.logger.debug(f"Page visit tracked: {page_url} for target {target_id}")
            
            return tracking_event
            
        except Exception as e:
            self.logger.error(f"Error tracking page visit: {str(e)}")
            raise
    
    def track_form_view(self, campaign_id, target_id, form_type='login', tracking_token=None):
        """
        Trackează vizualizarea unui formular
        
        Args:
            campaign_id: ID-ul campaniei
            target_id: ID-ul țintei
            form_type: Tipul formularului (login, register, verify)
            tracking_token: Token de tracking
            
        Returns:
            Tracking: Evenimentul creat
        """
        try:
            event_data = {
                'form_type': form_type,
                'tracking_token': tracking_token,
                'page_url': request.url if request else None,
                'time_to_view': 0  # Timpul de la click la vizualizare
            }
            
            tracking_event = Tracking(
                campaign_id=campaign_id,
                event_type='form_viewed',
                target_id=target_id,
                ip_address=get_client_ip(),
                user_agent=get_user_agent(),
                tracking_token=tracking_token
            )
            
            tracking_event.extra_data = event_data
            
            db.session.add(tracking_event)
            db.session.commit()
            
            self.logger.debug(f"Form view tracked: {form_type} for target {target_id}")
            
            return tracking_event
            
        except Exception as e:
            self.logger.error(f"Error tracking form view: {str(e)}")
            raise
    
    def track_form_submission(self, campaign_id, target_id, form_data, tracking_token=None):
        """
        Trackează submisia unui formular (înainte de capturarea credențialelor)
        
        Args:
            campaign_id: ID-ul campaniei
            target_id: ID-ul țintei
            form_data: Datele din formular (fără parole în clar)
            tracking_token: Token de tracking
            
        Returns:
            Tracking: Evenimentul creat
        """
        try:
            # Sanitizează datele (nu stocăm parole în tracking)
            safe_form_data = {
                'username_length': len(form_data.get('username', '')),
                'password_length': len(form_data.get('password', '')),
                'form_fields': list(form_data.keys()),
                'submission_time': datetime.utcnow().isoformat()
            }
            
            event_data = {
                'form_type': 'login_submission',
                'tracking_token': tracking_token,
                'form_data': safe_form_data,
                'page_url': request.url if request else None
            }
            
            tracking_event = Tracking(
                campaign_id=campaign_id,
                event_type='form_submitted',
                target_id=target_id,
                ip_address=get_client_ip(),
                user_agent=get_user_agent(),
                tracking_token=tracking_token
            )
            
            tracking_event.extra_data = event_data
            
            db.session.add(tracking_event)
            db.session.commit()
            
            self.logger.info(f"Form submission tracked for target {target_id}")
            
            return tracking_event
            
        except Exception as e:
            self.logger.error(f"Error tracking form submission: {str(e)}")
            raise
    
    def get_conversion_funnel(self, campaign_id):
        """
        Calculează funnel-ul de conversie pentru o campanie
        
        Args:
            campaign_id: ID-ul campaniei
            
        Returns:
            dict: Datele funnel-ului
        """
        try:
            funnel_steps = [
                'email_sent',
                'email_opened',
                'link_clicked', 
                'page_visited',
                'form_viewed',
                'form_submitted',
                'credentials_entered'
            ]
            
            funnel_data = {}
            
            for step in funnel_steps:
                if step == 'credentials_entered':
                    # Pentru credențiale, numără din tabla credentials
                    count = Credential.query.filter_by(campaign_id=campaign_id).count()
                else:
                    # Pentru restul, numără target-uri unice cu acest eveniment
                    count = db.session.query(func.count(Tracking.target_id.distinct()))\
                                   .filter_by(campaign_id=campaign_id, event_type=step)\
                                   .scalar() or 0
                
                funnel_data[step] = count
            
            # Calculează ratele de conversie
            total_sent = funnel_data.get('email_sent', 0)
            if total_sent > 0:
                # Create a copy of the items to avoid modifying dict during iteration
                for step, count in list(funnel_data.items()):
                    funnel_data[f'{step}_rate'] = round((count / total_sent) * 100, 2)
            
            return funnel_data
            
        except Exception as e:
            self.logger.error(f"Error calculating conversion funnel: {str(e)}")
            return {}
    
    def get_campaign_timeline(self, campaign_id, limit=50):
        """
        Returnează timeline-ul evenimentelor pentru o campanie
        
        Args:
            campaign_id: ID-ul campaniei
            limit: Numărul maxim de evenimente
            
        Returns:
            list: Lista evenimentelor ordonate cronologic
        """
        try:
            events = Tracking.query.filter_by(campaign_id=campaign_id)\
                           .order_by(desc(Tracking.timestamp))\
                           .limit(limit).all()
            
            timeline = []
            for event in events:
                timeline.append({
                    'timestamp': event.timestamp,
                    'event_type': event.event_type,
                    'target_id': event.target_id,
                    'target_email': event.target.email if event.target else 'Unknown',
                    'ip_address': event.ip_address,
                    'browser': event.browser_data.get('browser', 'Unknown') if event.browser_data else 'Unknown',
                    'device': 'Mobile' if event.device_data and event.device_data.get('is_mobile') else 'Desktop',
                    'details': event.extra_data
                })
            
            return timeline
            
        except Exception as e:
            self.logger.error(f"Error getting campaign timeline: {str(e)}")
            return []
    
    def get_hourly_activity(self, campaign_id, days=7):
        """
        Returnează activitatea pe ore pentru ultimele zile
        
        Args:
            campaign_id: ID-ul campaniei
            days: Numărul de zile înapoi
            
        Returns:
            dict: Activitatea pe fiecare oră (0-23)
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            results = db.session.query(
                func.extract('hour', Tracking.timestamp).label('hour'),
                func.count(Tracking.id).label('count')
            ).filter(
                Tracking.campaign_id == campaign_id,
                Tracking.timestamp >= start_date
            ).group_by('hour').all()
            
            # Inițializează toate orele cu 0
            hourly_data = {hour: 0 for hour in range(24)}
            
            # Populează cu datele reale
            for result in results:
                hourly_data[int(result.hour)] = result.count
            
            return hourly_data
            
        except Exception as e:
            self.logger.error(f"Error getting hourly activity: {str(e)}")
            return {}
    
    def get_device_statistics(self, campaign_id):
        """
        Returnează statistici despre device-urile utilizatorilor
        
        Args:
            campaign_id: ID-ul campaniei
            
        Returns:
            dict: Statistici device-uri, browsere, OS
        """
        try:
            # Device types
            mobile_count = db.session.query(func.count(Tracking.id))\
                                   .filter_by(campaign_id=campaign_id)\
                                   .filter(Tracking.device_info.like('%"is_mobile": true%'))\
                                   .scalar() or 0
            
            desktop_count = db.session.query(func.count(Tracking.id))\
                                    .filter_by(campaign_id=campaign_id)\
                                    .filter(Tracking.device_info.like('%"is_mobile": false%'))\
                                    .scalar() or 0
            
            # Top browsers (simplified - ar trebui să parseze JSON-ul)
            top_browsers = db.session.query(
                Tracking.browser_info,
                func.count(Tracking.id).label('count')
            ).filter_by(campaign_id=campaign_id)\
             .group_by(Tracking.browser_info)\
             .order_by(desc('count'))\
             .limit(5).all()
            
            return {
                'device_types': {
                    'mobile': mobile_count,
                    'desktop': desktop_count,
                    'total': mobile_count + desktop_count
                },
                'top_browsers': [
                    {'browser': b.browser_info, 'count': b.count} 
                    for b in top_browsers if b.browser_info
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting device statistics: {str(e)}")
            return {}
    
    def get_target_journey(self, campaign_id, target_id):
        """
        Returnează călătoria completă a unui target prin campanie
        
        Args:
            campaign_id: ID-ul campaniei
            target_id: ID-ul țintei
            
        Returns:
            dict: Journey complet cu timeline și metrici
        """
        try:
            target = db.session.get(Target, target_id)
            if not target:
                raise ValidationError(f"Target {target_id} not found")
            
            # Toate evenimentele pentru acest target
            events = Tracking.query.filter_by(
                campaign_id=campaign_id,
                target_id=target_id
            ).order_by(Tracking.timestamp.asc()).all()
            
            # Credențialele capturate
            credentials = Credential.query.filter_by(
                campaign_id=campaign_id,
                target_id=target_id
            ).all()
            
            journey = {
                'target': {
                    'id': target.id,
                    'email': target.email,
                    'name': target.display_name,
                    'status': target.status
                },
                'timeline': [
                    {
                        'timestamp': event.timestamp,
                        'event_type': event.event_type,
                        'details': event.extra_data,
                        'ip_address': event.ip_address,
                        'user_agent': event.user_agent
                    }
                    for event in events
                ],
                'credentials': [
                    {
                        'captured_at': cred.captured_at,
                        'username': cred.username,
                        'password_strength': cred.password_strength,
                        'risk_score': cred.risk_score
                    }
                    for cred in credentials
                ],
                'summary': {
                    'total_events': len(events),
                    'engagement_score': target.engagement_score,
                    'time_to_click': self._calculate_time_to_click(events),
                    'time_to_submit': self._calculate_time_to_submit(events)
                }
            }
            
            return journey
            
        except Exception as e:
            self.logger.error(f"Error getting target journey: {str(e)}")
            return {}
    
    def _calculate_time_to_click(self, events):
        """Calculează timpul de la email trimis la primul click"""
        email_sent = next((e for e in events if e.event_type == 'email_sent'), None)
        link_clicked = next((e for e in events if e.event_type == 'link_clicked'), None)
        
        if email_sent and link_clicked:
            delta = link_clicked.timestamp - email_sent.timestamp
            return delta.total_seconds()
        return None
    
    def _calculate_time_to_submit(self, events):
        """Calculează timpul de la click la submisia formularului"""
        link_clicked = next((e for e in events if e.event_type == 'link_clicked'), None)
        form_submitted = next((e for e in events if e.event_type == 'form_submitted'), None)
        
        if link_clicked and form_submitted:
            delta = form_submitted.timestamp - link_clicked.timestamp
            return delta.total_seconds()
        return None