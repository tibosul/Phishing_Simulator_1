/**
 * Admin Interface JavaScript - Phishing Simulator
 * FIXED: Updated API endpoints to match new routes
 */

class AdminInterface {
    constructor() {
        this.apiBase = '/admin';  // FIXED: Align with Flask blueprint structure
        this.realTimeEnabled = false;
        this.realTimeInterval = null;
        this.charts = {};
        this.lastUpdate = null;
        this.debounceTimers = new Map();  // For debouncing operations
    }

    /**
     * Initialize the admin interface
     */
    static init() {
        const admin = new AdminInterface();
        admin.initEventListeners();
        admin.loadQuickStats();
        admin.initNotifications();
        admin.setupRealTime();
        admin.checkSystemHealth();
        return admin;
    }

    /**
     * Set up event listeners
     */
    initEventListeners() {
        // Sidebar toggle for mobile
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-bs-toggle="collapse"][data-bs-target="#sidebar-nav"]')) {
                this.toggleSidebar();
            }
        });

        // Close mobile sidebar when clicking on nav links
        document.addEventListener('click', (e) => {
            if (e.target.closest('.sidebar .nav-link') && window.innerWidth < 992) {
                // Add small delay to allow navigation to complete
                setTimeout(() => {
                    AdminInterface.closeMobileSidebar();
                }, 100);
            }
        });

        // Real-time panel toggle
        window.toggleRealTimePanel = () => this.toggleRealTimePanel();

        // Export data function
        window.exportData = () => this.exportData();

        // AJAX form submissions
        document.addEventListener('submit', (e) => {
            if (e.target.matches('.ajax-form')) {
                e.preventDefault();
                this.submitAjaxForm(e.target);
            }
        });

        // Auto-refresh elements
        this.setupAutoRefresh();
        
        // Escape key handling
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                // Close mobile sidebar
                AdminInterface.closeMobileSidebar();
                // Close real-time panel
                const realtimePanel = document.getElementById('realtime-panel');
                if (realtimePanel && realtimePanel.classList.contains('open')) {
                    this.toggleRealTimePanel();
                }
            }
        });
    }

    /**
     * Load quick stats for navbar
     */
    async loadQuickStats() {
        try {
            // FIXED: Use correct API endpoint structure
            const response = await fetch(`${this.apiBase}/api/stats`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            const data = await response.json();

            if (data.error) {
                console.error('Stats API error:', data.error);
                document.getElementById('quick-stats').textContent = 'Error loading stats';
                return;
            }

            const stats = data.activity_today || {};
            const totalEvents = stats.events || 0;
            const emailsSent = stats.emails_sent || 0;
            const clicks = stats.clicks || 0;

            const quickStatsElement = document.getElementById('quick-stats');
            if (quickStatsElement) {
                quickStatsElement.innerHTML =
                    `${totalEvents} events, ${emailsSent} emails, ${clicks} clicks today`;
            }

            // Update sidebar counters
            this.updateSidebarCounters(data);

        } catch (error) {
            console.error('Error loading quick stats:', error);
            const quickStatsElement = document.getElementById('quick-stats');
            if (quickStatsElement) {
                quickStatsElement.textContent = 'Stats unavailable';
            }
            // Don't show toast for stats errors as they happen in background
        }
    }

    /**
     * Update sidebar counters
     */
    updateSidebarCounters(data) {
        const campaignsCount = document.getElementById('campaigns-count');
        const targetsCount = document.getElementById('targets-count');

        if (campaignsCount && data.campaigns) {
            campaignsCount.textContent = data.campaigns.total || 0;
        }

        if (targetsCount && data.targets) {
            targetsCount.textContent = data.targets.total || 0;
        }
    }

    /**
     * Initialize notifications system
     */
    async initNotifications() {
        try {
            // FIXED: Use correct API endpoint structure
            const response = await fetch(`${this.apiBase}/api/realtime`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            const data = await response.json();

            if (data.events && data.events.length > 0) {
                this.updateNotifications(data.events.slice(0, 5)); // Last 5 events
            }
        } catch (error) {
            console.error('Error loading notifications:', error);
            // Silently fail for notifications as they're not critical
        }
    }

    /**
     * Update notifications dropdown
     */
    updateNotifications(events) {
        const dropdown = document.getElementById('notifications-dropdown');
        const counter = document.getElementById('notification-count');

        if (!dropdown) return;

        // Update counter
        if (counter) {
            counter.textContent = events.length;
            counter.style.display = events.length > 0 ? 'inline' : 'none';
        }

        // Clear existing notifications
        dropdown.innerHTML = '<li><h6 class="dropdown-header">Recent Activity</h6></li>';

        if (events.length === 0) {
            dropdown.innerHTML += '<li><div class="dropdown-item-text text-muted">No recent activity</div></li>';
            return;
        }

        // Add notifications
        events.forEach(event => {
            const timeAgo = this.formatTimeAgo(new Date(event.timestamp));
            const icon = this.getEventIcon(event.event_type);

            dropdown.innerHTML += `
                <li>
                    <a class="dropdown-item" href="#" onclick="AdminInterface.viewEvent('${event.id}')">
                        <i class="bi bi-${icon} me-2 text-primary"></i>
                        <div class="d-flex justify-content-between">
                            <span class="small">${this.formatEventDescription(event)}</span>
                            <span class="text-muted small">${timeAgo}</span>
                        </div>
                    </a>
                </li>
            `;
        });

        dropdown.innerHTML += '<li><hr class="dropdown-divider"></li>';
        dropdown.innerHTML += '<li><a class="dropdown-item text-center" href="/admin/realtime">View All Activity</a></li>';
    }

    /**
     * Setup real-time updates with optimized frequency
     */
    setupRealTime() {
        // FIXED: Reduced frequency from 30s to 60s for better performance
        this.realTimeInterval = setInterval(() => {
            if (this.realTimeEnabled) {
                this.updateRealTimePanel();
            }
            this.loadQuickStats(); // Refresh stats every 60 seconds
        }, 60000);
        
        // Cleanup interval on page unload
        window.addEventListener('beforeunload', () => {
            if (this.realTimeInterval) {
                clearInterval(this.realTimeInterval);
            }
        });
    }

    /**
     * Toggle real-time panel
     */
    toggleRealTimePanel() {
        const panel = document.getElementById('realtime-panel');
        if (!panel) return;

        const isOpen = panel.classList.contains('open');

        if (isOpen) {
            panel.classList.remove('open');
            this.realTimeEnabled = false;
        } else {
            panel.classList.add('open');
            this.realTimeEnabled = true;
            this.updateRealTimePanel();
        }
    }

    /**
     * Update real-time panel content
     */
    async updateRealTimePanel() {
        const content = document.getElementById('realtime-content');
        if (!content) return;

        try {
            // FIXED: Use correct API endpoint structure
            const response = await fetch(`${this.apiBase}/api/realtime`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            const data = await response.json();

            if (data.events && data.events.length > 0) {
                content.innerHTML = '';
                data.events.slice(0, 20).forEach(event => {
                    const eventDiv = document.createElement('div');
                    eventDiv.className = 'realtime-event';
                    eventDiv.innerHTML = `
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <i class="bi bi-${this.getEventIcon(event.event_type)} me-2"></i>
                                <strong>${event.event_type.replace('_', ' ')}</strong>
                            </div>
                            <span class="text-muted small">${this.formatTimeAgo(new Date(event.timestamp))}</span>
                        </div>
                        <div class="small text-muted mt-1">
                            ${event.target_email || 'Unknown'} • ${event.campaign_name || 'Unknown Campaign'}
                        </div>
                    `;
                    content.appendChild(eventDiv);
                });
            } else {
                content.innerHTML = '<div class="text-center text-muted">No recent activity</div>';
            }
        } catch (error) {
            console.error('Error updating real-time panel:', error);
            content.innerHTML = '<div class="text-center text-danger">Error loading activity</div>';
        }
    }

    /**
     * Toggle sidebar for mobile with backdrop
     */
    toggleSidebar() {
        const sidebar = document.getElementById('sidebar-nav');
        const backdrop = document.getElementById('sidebar-backdrop');
        
        if (sidebar) {
            const isOpen = sidebar.classList.contains('show');
            
            if (isOpen) {
                sidebar.classList.remove('show');
                if (backdrop) {
                    backdrop.classList.remove('show');
                }
            } else {
                sidebar.classList.add('show');
                if (backdrop) {
                    backdrop.classList.add('show');
                }
            }
        }
    }
    
    /**
     * Close mobile sidebar (static method for onclick)
     */
    static closeMobileSidebar() {
        const sidebar = document.getElementById('sidebar-nav');
        const backdrop = document.getElementById('sidebar-backdrop');
        
        if (sidebar) {
            sidebar.classList.remove('show');
        }
        if (backdrop) {
            backdrop.classList.remove('show');
        }
    }

    /**
     * Export data functionality with improved error handling
     */
    async exportData() {
        this.showLoading();

        try {
            // FIXED: Use correct API endpoint structure
            const response = await fetch(`${this.apiBase}/api/export`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            const data = await response.json();

            if (data.error) {
                this.showToast('Export failed: ' + data.error, 'error');
                return;
            }

            // Create and download file
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `phishing_simulator_export_${new Date().toISOString().split('T')[0]}.json`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            this.showToast('Data exported successfully!', 'success');
        } catch (error) {
            console.error('Export error:', error);
            this.showToast('Export failed: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Submit AJAX forms with improved error handling and validation
     */
    async submitAjaxForm(form) {
        // Validate form before submission
        const validationErrors = this.validateForm(form);
        if (validationErrors.length > 0) {
            this.showToast('Please fix the following errors:<br>' + validationErrors.join('<br>'), 'error');
            return;
        }
        
        const formData = new FormData(form);
        const method = form.method || 'POST';
        const url = form.action;

        this.showLoading();

        try {
            const response = await fetch(url, {
                method: method,
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();

            if (data.success) {
                this.showToast(data.message || 'Operation successful!', 'success');

                // Redirect if specified
                if (data.redirect) {
                    window.location.href = data.redirect;
                } else {
                    // Refresh current page data
                    this.refreshPageData();
                }
            } else {
                this.showToast(data.error || 'Operation failed', 'error');
            }
        } catch (error) {
            console.error('Form submission error:', error);
            this.showToast('Network error: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Check system health
     */
    async checkSystemHealth() {
        try {
            // FIXED: Health check endpoint is correct as is
            const response = await fetch('/admin/health', {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            const data = await response.json();

            const healthStatus = document.getElementById('health-status');
            if (healthStatus) {
                if (data.status === 'healthy') {
                    healthStatus.className = 'badge bg-success ms-auto';
                    healthStatus.textContent = '●';
                    healthStatus.title = 'System healthy';
                } else {
                    healthStatus.className = 'badge bg-danger ms-auto';
                    healthStatus.textContent = '●';
                    healthStatus.title = 'System unhealthy';
                }
            }
        } catch (error) {
            console.error('Health check error:', error);
            const healthStatus = document.getElementById('health-status');
            if (healthStatus) {
                healthStatus.className = 'badge bg-warning ms-auto';
                healthStatus.textContent = '●';
                healthStatus.title = 'Health check failed';
            }
        }
    }

    /**
     * Setup auto-refresh for elements with cleanup
     */
    setupAutoRefresh() {
        const autoRefreshElements = document.querySelectorAll('[data-auto-refresh]');

        autoRefreshElements.forEach(element => {
            const interval = parseInt(element.dataset.autoRefresh) || 60000; // Default 60s
            const url = element.dataset.refreshUrl;

            if (url) {
                const intervalId = setInterval(async () => {
                    try {
                        const response = await fetch(url, {
                            headers: {
                                'X-Requested-With': 'XMLHttpRequest'
                            }
                        });
                        if (!response.ok) {
                            throw new Error(`HTTP ${response.status}`);
                        }
                        const data = await response.json();

                        if (element.dataset.refreshType === 'text') {
                            element.textContent = data.value || data;
                        } else if (element.dataset.refreshType === 'html') {
                            element.innerHTML = data.html || data;
                        }
                    } catch (error) {
                        console.error('Auto-refresh error for element:', element, error);
                    }
                }, interval);
                
                // Store interval ID for cleanup
                element.dataset.intervalId = intervalId;
            }
        });
        
        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            autoRefreshElements.forEach(element => {
                if (element.dataset.intervalId) {
                    clearInterval(parseInt(element.dataset.intervalId));
                }
            });
        });
    }

    /**
     * Utility functions
     */

    formatTimeAgo(date) {
        const now = new Date();
        const diff = now - date;
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (days > 0) return `${days}d ago`;
        if (hours > 0) return `${hours}h ago`;
        if (minutes > 0) return `${minutes}m ago`;
        return 'Just now';
    }

    getEventIcon(eventType) {
        const icons = {
            'email_sent': 'envelope',
            'email_opened': 'envelope-open',
            'link_clicked': 'cursor',
            'page_visited': 'eye',
            'form_viewed': 'file-text',
            'form_submitted': 'check-square',
            'credentials_entered': 'shield-exclamation',
            'sms_sent': 'phone'
        };
        return icons[eventType] || 'activity';
    }

    formatEventDescription(event) {
        const descriptions = {
            'email_sent': 'Email sent',
            'email_opened': 'Email opened',
            'link_clicked': 'Link clicked',
            'page_visited': 'Page visited',
            'form_viewed': 'Form viewed',
            'form_submitted': 'Form submitted',
            'credentials_entered': 'Credentials captured',
            'sms_sent': 'SMS sent'
        };
        return descriptions[event.event_type] || event.event_type;
    }

    showLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.add('show');
            overlay.style.display = 'flex'; // Ensure it's visible
        }
    }

    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.remove('show');
            // Use timeout to allow CSS transition to complete
            setTimeout(() => {
                if (!overlay.classList.contains('show')) {
                    overlay.style.display = 'none';
                }
            }, 300);
        }
    }

    showToast(message, type = 'info') {
        // Create toast container if it doesn't exist
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            container.style.zIndex = '9999';
            document.body.appendChild(container);
        }

        // Create toast element
        const toastId = 'toast-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
        const bgClass = type === 'success' ? 'bg-success' : type === 'error' ? 'bg-danger' : 'bg-info';
        const iconClass = type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-triangle' : 'info-circle';

        const toastHtml = `
            <div class="toast ${bgClass} text-white" id="${toastId}" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header ${bgClass} text-white border-0">
                    <i class="bi bi-${iconClass} me-2"></i>
                    <strong class="me-auto">Notification</strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        `;

        container.insertAdjacentHTML('beforeend', toastHtml);

        // Initialize and show toast
        const toastElement = document.getElementById(toastId);
        if (toastElement && window.bootstrap) {
            const toast = new bootstrap.Toast(toastElement, { 
                autohide: true, 
                delay: type === 'error' ? 8000 : 5000 // Error messages stay longer
            });
            toast.show();

            // Remove from DOM after hide
            toastElement.addEventListener('hidden.bs.toast', () => {
                toastElement.remove();
            });
        }
    }

    /**
     * Input validation helpers
     */
    validateEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }
    
    validateRequired(value) {
        return value && value.trim().length > 0;
    }
    
    validateForm(form) {
        const errors = [];
        const requiredFields = form.querySelectorAll('[required]');
        
        requiredFields.forEach(field => {
            if (!this.validateRequired(field.value)) {
                errors.push(`${field.name || field.id || 'Field'} is required`);
                field.classList.add('is-invalid');
            } else {
                field.classList.remove('is-invalid');
            }
            
            // Email validation
            if (field.type === 'email' && field.value && !this.validateEmail(field.value)) {
                errors.push(`${field.name || field.id || 'Email field'} must be a valid email`);
                field.classList.add('is-invalid');
            }
        });
        
        return errors;
    }

    /**
     * API helper methods
     */

    async apiCall(endpoint, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        };

        const response = await fetch(endpoint, { ...defaultOptions, ...options });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }

    async get(endpoint) {
        return this.apiCall(endpoint);
    }

    async post(endpoint, data) {
        return this.apiCall(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async put(endpoint, data) {
        return this.apiCall(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async delete(endpoint) {
        return this.apiCall(endpoint, {
            method: 'DELETE'
        });
    }

    /**
     * Chart utilities
     */

    createChart(canvasId, config) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return null;

        // Destroy existing chart if exists
        if (this.charts[canvasId]) {
            this.charts[canvasId].destroy();
        }

        this.charts[canvasId] = new Chart(canvas, config);
        return this.charts[canvasId];
    }

    updateChart(canvasId, newData) {
        const chart = this.charts[canvasId];
        if (chart) {
            chart.data = newData;
            chart.update();
        }
    }

    /**
     * Delete campaign functionality
     */
    async deleteCampaign(campaignId, campaignName) {
        try {
            // Show confirmation modal if not already shown
            const confirmed = await this.showDeleteConfirmation(campaignName);
            if (!confirmed) return false;

            this.showLoading();

            // Get CSRF token from meta tag or form
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
                             document.querySelector('input[name="csrf_token"]')?.value ||
                             '';

            const formData = new FormData();
            formData.append('confirm', 'DELETE');
            if (csrfToken) {
                formData.append('csrf_token', csrfToken);
            }

            const response = await fetch(`/admin/campaigns/${campaignId}/delete`, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            const contentType = response.headers.get('content-type');
            
            if (!response.ok) {
                // Handle different response types
                if (contentType && contentType.includes('application/json')) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
                } else {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
            }

            // Check if response is JSON or HTML (redirect)
            if (contentType && contentType.includes('application/json')) {
                const data = await response.json();
                if (data.success) {
                    this.showToast(`Campaign "${campaignName}" deleted successfully!`, 'success');
                    // Redirect to campaigns list
                    window.location.href = '/admin/campaigns/';
                } else {
                    this.showToast(data.error || 'Failed to delete campaign', 'error');
                }
            } else {
                // If not JSON, assume successful redirect
                this.showToast(`Campaign "${campaignName}" deleted successfully!`, 'success');
                window.location.href = '/admin/campaigns/';
            }

        } catch (error) {
            console.error('Delete campaign error:', error);
            this.showToast('Error deleting campaign: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Show delete confirmation dialog
     */
    showDeleteConfirmation(campaignName) {
        return new Promise((resolve) => {
            const confirmed = confirm(
                `Are you sure you want to delete the campaign "${campaignName}"?\n\n` +
                'This will permanently delete:\n' +
                '• All campaign data\n' +
                '• All target information\n' +
                '• All tracking data\n' +
                '• All captured credentials\n\n' +
                'This action cannot be undone!'
            );
            resolve(confirmed);
        });
    }

    /**
     * Static utility methods
     */

    static viewEvent(eventId) {
        // Handle event viewing
        console.log('Viewing event:', eventId);
    }

    static formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    /**
     * Debounced wrapper for any function
     */
    debounce(key, func, wait = 300) {
        if (this.debounceTimers.has(key)) {
            clearTimeout(this.debounceTimers.get(key));
        }
        
        const timeout = setTimeout(() => {
            this.debounceTimers.delete(key);
            func();
        }, wait);
        
        this.debounceTimers.set(key, timeout);
    }

    static formatNumber(num) {
        return new Intl.NumberFormat().format(num);
    }

    static formatPercentage(value, total) {
        if (total === 0) return '0%';
        return ((value / total) * 100).toFixed(1) + '%';
    }
}

// Initialize when DOM is loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.adminInterface = AdminInterface.init();
    });
} else {
    window.adminInterface = AdminInterface.init();
}

// Global reference for external use
window.AdminInterface = AdminInterface;

// Global helper functions
window.deleteCampaign = function(campaignId, campaignName) {
    if (window.adminInterface) {
        return window.adminInterface.deleteCampaign(campaignId, campaignName);
    } else {
        console.error('Admin interface not initialized');
        return false;
    }
};