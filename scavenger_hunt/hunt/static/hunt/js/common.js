/**
 * Common JavaScript functions used across the Scavenger Hunt application
 */

// Document ready function (jQuery alternative)
function docReady(fn) {
    if (document.readyState === "complete" || document.readyState === "interactive") {
        setTimeout(fn, 1);
    } else {
        document.addEventListener("DOMContentLoaded", fn);
    }
}

// Show a notification message
function showNotification(message, type = 'info', duration = 5000) {
    const container = document.createElement('div');
    container.className = `notification notification-${type}`;
    container.textContent = message;
    
    document.body.appendChild(container);
    
    // Trigger animation
    setTimeout(() => container.classList.add('show'), 10);
    
    // Auto dismiss
    setTimeout(() => {
        container.classList.remove('show');
        setTimeout(() => container.remove(), 300);
    }, duration);
}

// Format date/time
function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

// Debug logger that only logs in development mode
function debugLog(...args) {
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        console.log('[DEBUG]', ...args);
    }
}

// Simple form validation
function validateForm(formElement) {
    let isValid = true;
    const inputs = formElement.querySelectorAll('input[required], select[required], textarea[required]');
    
    inputs.forEach(input => {
        if (!input.value.trim()) {
            isValid = false;
            input.classList.add('error');
        } else {
            input.classList.remove('error');
        }
    });
    
    return isValid;
}

// Add some CSS for notifications
document.addEventListener('DOMContentLoaded', () => {
    const style = document.createElement('style');
    style.textContent = `
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 4px;
            color: white;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            z-index: 9999;
            opacity: 0;
            transform: translateY(-10px);
            transition: all 0.3s ease;
        }
        
        .notification.show {
            opacity: 1;
            transform: translateY(0);
        }
        
        .notification-info {
            background-color: #2196F3;
        }
        
        .notification-success {
            background-color: #4CAF50;
        }
        
        .notification-warning {
            background-color: #FFC107;
            color: #333;
        }
        
        .notification-error {
            background-color: #F44336;
        }
    `;
    document.head.appendChild(style);
});

// Common utility functions for hunt app

// Document ready handler
$(document).ready(function() {
    // Initialize tooltips if Bootstrap is available
    if (typeof bootstrap !== 'undefined') {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    // Generic error handler for AJAX requests
    $(document).ajaxError(function(event, jqxhr, settings, thrownError) {
        console.error("AJAX Error:", thrownError);
    });
});

// Helper function for CSRF token handling
function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
} 