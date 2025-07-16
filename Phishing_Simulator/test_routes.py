# TEST SCRIPT pentru verificarea routes-urilor
# Pune acest fișier în root: test_routes.py

from app import app
import requests

def test_all_routes():
    """Testează toate route-urile să vadă dacă răspund corect"""
    
    test_urls = [
        # Dashboard routes
        ('GET', '/admin/', 'dashboard.index'),
        ('GET', '/admin/dashboard', 'dashboard.index'), 
        ('GET', '/admin/analytics', 'dashboard.analytics'),
        ('GET', '/admin/health', 'dashboard.health_check'),
        
        # Campaign routes  
        ('GET', '/admin/campaigns/', 'campaigns.list_campaigns'),
        ('GET', '/admin/campaigns/create', 'campaigns.create_campaign'),
        # ('GET', '/admin/campaigns/1', 'campaigns.view_campaign'),  # Test cu ID real
        # ('GET', '/admin/campaigns/1/edit', 'campaigns.edit_campaign'),
        
        # Template routes
        ('GET', '/admin/templates/', 'templates.list_templates'),
        ('GET', '/admin/templates/create', 'templates.create_template'),
        # ('GET', '/admin/templates/1', 'templates.view_template'),
        
        # Target routes  
        ('GET', '/admin/targets/', 'targets.list_targets'),
        ('GET', '/admin/targets/create', 'targets.create_target'),
    ]
    
    with app.test_client() as client:
        print("=== TESTING ROUTES ===\n")
        
        for method, url, endpoint in test_urls:
            try:
                if method == 'GET':
                    response = client.get(url)
                    
                status_icon = "✅" if response.status_code == 200 else "❌"
                content_type = response.headers.get('Content-Type', 'unknown')
                
                print(f"{status_icon} {method} {url}")
                print(f"   Status: {response.status_code}")
                print(f"   Content-Type: {content_type}")
                print(f"   Endpoint: {endpoint}")
                
                if response.status_code != 200:
                    print(f"   ERROR: {response.data.decode('utf-8')[:100]}...")
                
                print()
                
            except Exception as e:
                print(f"❌ {method} {url}")
                print(f"   EXCEPTION: {str(e)}")
                print()

if __name__ == '__main__':
    test_all_routes()