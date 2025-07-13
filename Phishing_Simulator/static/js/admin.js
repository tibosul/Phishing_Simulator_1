/**
 * Admin Panel JavaScript pentru Phishing Simulator
 */

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Phishing Simulator Admin Panel - JavaScript Loaded');
    
    // Initialize all components
    initializeComponents();
    initializeAnimations();
    initializeFormHandlers();
    initializeTooltips();
});

/**
 * Initialize main components
 */
function initializeComponents() {
    // Set active navigation link
    setActiveNavLink();
    
    // Initialize auto-dismissing alerts
    initializeAlerts();
    
    // Initialize loading states
    initializeLoadingStates();
    
    // Initialize table sorting
    initializeTableSorting();
}

/**
 * Set active navigation link based on current page
 */
function setActiveNavLink() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    
    navLinks.forEach(link => {
        link.classList.remove('active');
        
        const href = link.getAttribute('href');
        if (href && currentPath.includes(href.split('/').pop())) {
            link.classList.add('active');
        }
    });
}

/**
 * Initialize auto-dismissing alerts
 */
function initializeAlerts() {
    const alerts = document.querySelectorAll('.alert');
    
    alerts.forEach(alert => {
        // Add fade-in animation
        alert.classList.add('fade-in');
        
        // Auto-dismiss success and info alerts after 5 seconds
        if (alert.classList.contains('alert-success') || alert.classList.contains('alert-info')) {
            setTimeout(() => {
                dismissAlert(alert);
            }, 5000);
        }
    });
}

/**
 * Dismiss alert with animation
 */
function dismissAlert(alert) {
    alert.style.opacity = '0';
    alert.style.transform = 'translateX(100%)';
    
    setTimeout(() => {
        if (alert.parentNode) {
            alert.parentNode.removeChild(alert);
        }
    }, 300);
}

/**
 * Initialize loading states for buttons and forms
 */
function initializeLoadingStates() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                setLoadingState(submitBtn, true);
            }
        });
    });
}

/**
 * Set loading state for button
 */
function setLoadingState(button, isLoading) {
    if (isLoading) {
        button.disabled = true;
        button.classList.add('loading');
        
        const originalText = button.innerHTML;
        button.setAttribute('data-original-text', originalText);
        
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
    } else {
        button.disabled = false;
        button.classList.remove('loading');
        
        const originalText = button.getAttribute('data-original-text');
        if (originalText) {
            button.innerHTML = originalText;
        }
    }
}

/**
 * Initialize table sorting functionality
 */
function initializeTableSorting() {
    const tables = document.querySelectorAll('.table');
    
    tables.forEach(table => {
        const headers = table.querySelectorAll('thead th');
        
        headers.forEach((header, index) => {
            if (header.textContent.trim() && !header.classList.contains('no-sort')) {
                header.style.cursor = 'pointer';
                header.setAttribute('title', 'Click to sort');
                
                header.addEventListener('click', () => {
                    sortTable(table, index);
                });
            }
        });
    });
}

/**
 * Sort table by column
 */
function sortTable(table, columnIndex) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    // Determine sort direction
    const header = table.querySelectorAll('thead th')[columnIndex];
    const isAscending = !header.classList.contains('sort-desc');
    
    // Remove sort classes from all headers
    table.querySelectorAll('thead th').forEach(th => {
        th.classList.remove('sort-asc', 'sort-desc');
    });
    
    // Add sort class to current header
    header.classList.add(isAscending ? 'sort-asc' : 'sort-desc');
    
    // Sort rows
    rows.sort((a, b) => {
        const aText = a.cells[columnIndex].textContent.trim();
        const bText = b.cells[columnIndex].textContent.trim();
        
        // Try to parse as numbers
        const aNum = parseFloat(aText);
        const bNum = parseFloat(bText);
        
        if (!isNaN(aNum) && !isNaN(bNum)) {
            return isAscending ? aNum - bNum : bNum - aNum;
        }
        
        // Sort as strings
        return isAscending ? aText.localeCompare(bText) : bText.localeCompare(aText);
    });
    
    // Re-append sorted rows
    rows.forEach(row => tbody.appendChild(row));
}

/**
 * Initialize animations
 */
function initializeAnimations() {
    // Animate cards on page load
    const cards = document.querySelectorAll('.card');
    cards.forEach((card, index) => {
        setTimeout(() => {
            card.classList.add('fade-in');
        }, index * 100);
    });
    
    // Animate statistics cards
    const statsCards = document.querySelectorAll('.stats-card');
    statsCards.forEach((card, index) => {
        setTimeout(() => {
            animateNumber(card);
        }, index * 200);
    });
}

/**
 * Animate numbers in statistics cards
 */
function animateNumber(card) {
    const numberElement = card.querySelector('h4');
    if (!numberElement) return;
    
    const finalNumber = parseInt(numberElement.textContent) || 0;
    let currentNumber = 0;
    const increment = Math.ceil(finalNumber / 30);
    
    const animation = setInterval(() => {
        currentNumber += increment;
        if (currentNumber >= finalNumber) {
            currentNumber = finalNumber;
            clearInterval(animation);
        }
        numberElement.textContent = currentNumber.toLocaleString();
    }, 50);
}

/**
 * Initialize form handlers
 */
function initializeFormHandlers() {
    // Search form auto-submit
    const searchInputs = document.querySelectorAll('input[name="q"]');
    searchInputs.forEach(input => {
        let timeoutId;
        input.addEventListener('input', function() {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => {
                if (this.value.length > 2 || this.value.length === 0) {
                    this.form.submit();
                }
            }, 500);
        });
    });
    
    // Filter dropdowns auto-submit
    const filterSelects = document.querySelectorAll('select[name="status"], select[name="type"]');
    filterSelects.forEach(select => {
        select.addEventListener('change', function() {
            this.form.submit();
        });
    });
    
    // Form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(form)) {
                e.preventDefault();
            }
        });
    });
}

/**
 * Basic form validation
 */
function validateForm(form) {
    let isValid = true;
    const requiredFields = form.querySelectorAll('[required]');
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            showFieldError(field, 'This field is required');
            isValid = false;
        } else {
            clearFieldError(field);
        }
    });
    
    // Email validation
    const emailFields = form.querySelectorAll('input[type="email"]');
    emailFields.forEach(field => {
        if (field.value && !isValidEmail(field.value)) {
            showFieldError(field, 'Please enter a valid email address');
            isValid = false;
        }
    });
    
    return isValid;
}

/**
 * Show field error
 */
function showFieldError(field, message) {
    field.classList.add('is-invalid');
    
    let feedback = field.parentNode.querySelector('.invalid-feedback');
    if (!feedback) {
        feedback = document.createElement('div');
        feedback.className = 'invalid-feedback';
        field.parentNode.appendChild(feedback);
    }
    feedback.textContent = message;
}

/**
 * Clear field error
 */
function clearFieldError(field) {
    field.classList.remove('is-invalid');
    const feedback = field.parentNode.querySelector('.invalid-feedback');
    if (feedback) {
        feedback.remove();
    }
}

/**
 * Validate email format
 */
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * Initialize tooltips
 */
function initializeTooltips() {
    // Initialize Bootstrap tooltips if available
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
}

/**
 * Utility functions
 */
const AdminUtils = {
    /**
     * Show notification
     */
    showNotification: function(message, type = 'info') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        const container = document.querySelector('.container');
        if (container) {
            container.insertBefore(alertDiv, container.firstChild);
            
            // Auto-dismiss after 5 seconds
            setTimeout(() => {
                dismissAlert(alertDiv);
            }, 5000);
        }
    },
    
    /**
     * Confirm action
     */
    confirmAction: function(message, callback) {
        if (confirm(message)) {
            callback();
        }
    },
    
    /**
     * Format number with thousand separators
     */
    formatNumber: function(num) {
        return num.toLocaleString();
    },
    
    /**
     * Format date
     */
    formatDate: function(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    }
};

// Make AdminUtils globally available
window.AdminUtils = AdminUtils;