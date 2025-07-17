/**
 * Admin Interface JavaScript - Phishing Simulator
 * Handles all admin dashboard functionality and API interactions
 */

class AdminInterface {
    constructor() {
        this.apiBase = '/admin/api';  // Centralized API base URL
        this.realTimeEnabled = false;
        this.realTimeInterval = null;
        this.charts = {};
        this.lastUpdate = null;
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
    }

    /**
     * Load quick stats for navbar
     */
    async loadQuickStats() {
        try {
            const response = await fetch(`${this.apiBase}/stats`);
            const data = await response.json();

            if (data.error) {
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
            const response = await fetch(`${this.apiBase}/realtime`);
            const data = await response.json();

            if (data.events && data.events.length > 0) {
                this.updateNotifications(data.events.slice(0, 5)); // Last 5 events
            }
        } catch (error) {
            console.error('Error loading notifications:', error);
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
     * Setup real-time updates
     */
    setupRealTime() {
        this.realTimeInterval = setInterval(() => {
            if (this.realTimeEnabled) {
                this.updateRealTimePanel();
            }
            this.loadQuickStats(); // Refresh stats every 30 seconds
        }, 30000);
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
            const response = await fetch(`${this.apiBase}/realtime`);
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
     * Toggle sidebar for mobile
     */
    toggleSidebar() {
        const sidebar = document.getElementById('sidebar-nav');
        if (sidebar) {
            sidebar.classList.toggle('show');
        }
    }

    /**
     * Export data functionality
     */
    async exportData() {
        this.showLoading();

        try {
            const response = await fetch(`${this.apiBase}/export`);
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
            this.showToast('Export failed', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Submit AJAX forms
     */
    async submitAjaxForm(form) {
        const formData = new FormData(form);
        const method = form.method || 'POST';
        const url = form.action;

        this.showLoading();

        try {
            const response = await fetch(url, {
                method: method,
                body: formData
            });

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
            this.showToast('Network error occurred', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Check system health
     */
    async checkSystemHealth() {
        try {
            // Use consistent API endpoint
            const response = await fetch(`${this.apiBase}/health`);
            const data = await response.json();

            const healthStatus = document.getElementById('health-status');
            if (healthStatus) {
                if (data.status === 'healthy') {
                    healthStatus.className = 'badge bg-success ms-auto';
                    healthStatus.textContent = '●';
                } else {
                    healthStatus.className = 'badge bg-danger ms-auto';
                    healthStatus.textContent = '●';
                }
            }
        } catch (error) {
            console.error('Health check error:', error);
            const healthStatus = document.getElementById('health-status');
            if (healthStatus) {
                healthStatus.className = 'badge bg-warning ms-auto';
                healthStatus.textContent = '●';
            }
        }
    }

    /**
     * Setup auto-refresh for elements
     */
    setupAutoRefresh() {
        const autoRefreshElements = document.querySelectorAll('[data-auto-refresh]');

        autoRefreshElements.forEach(element => {
            const interval = parseInt(element.dataset.autoRefresh) || 30000;
            const url = element.dataset.refreshUrl;

            if (url) {
                setInterval(async () => {
                    try {
                        const response = await fetch(url);
                        const data = await response.json();

                        if (element.dataset.refreshType === 'text') {
                            element.textContent = data.value || data;
                        } else if (element.dataset.refreshType === 'html') {
                            element.innerHTML = data.html || data;
                        }
                    } catch (error) {
                        console.error('Auto-refresh error:', error);
                    }
                }, interval);
            }
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
        }
    }

    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.remove('show');
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
        const toastId = 'toast-' + Date.now();
        const bgClass = type === 'success' ? 'bg-success' : type === 'error' ? 'bg-danger' : 'bg-info';

        const toastHtml = `
            <div class="toast ${bgClass} text-white" id="${toastId}" role="alert">
                <div class="toast-header ${bgClass} text-white border-0">
                    <i class="bi bi-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-triangle' : 'info-circle'} me-2"></i>
                    <strong class="me-auto">Notification</strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        `;

        container.insertAdjacentHTML('beforeend', toastHtml);

        // Initialize and show toast
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, { autohide: true, delay: 5000 });
        toast.show();

        // Remove from DOM after hide
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }

    refreshPageData() {
        // Refresh page-specific data without full reload
        if (typeof window.refreshData === 'function') {
            window.refreshData();
        } else {
            this.loadQuickStats();
        }
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
    document.addEventListener('DOMContentLoaded', () => AdminInterface.init());
} else {
    AdminInterface.init();
}

// Global reference for external use
window.AdminInterface = AdminInterface;