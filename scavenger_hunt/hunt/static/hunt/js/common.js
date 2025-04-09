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

// WebSocket utility functions
const WebSocketUtils = {
    // Initialize a WebSocket connection with auto-reconnect
    createConnection: function(url, onMessageCallback, onOpenCallback, onCloseCallback, onErrorCallback) {
        let socket = null;
        let reconnectAttempts = 0;
        let reconnectTimer = null;
        const maxReconnectAttempts = 10;
        const baseReconnectDelay = 1000; // Start with 1 second
        
        function updateConnectionStatus(status) {
            const statusElement = document.getElementById('connection-status');
            if (!statusElement) return;
            
            statusElement.classList.remove('connected', 'disconnected', 'connecting');
            
            if (status === 'connected') {
                statusElement.classList.add('connected');
                statusElement.innerHTML = '<span>Connected ✓</span>';
            } else if (status === 'disconnected') {
                statusElement.classList.add('disconnected');
                statusElement.innerHTML = '<span>Disconnected ✗</span>';
            } else {
                statusElement.classList.add('connecting');
                statusElement.innerHTML = '<span>Connecting...</span>';
            }
        }
        
        function connect() {
            if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
                console.log('WebSocket already connected or connecting, skipping reconnect');
                return;
            }
            
            try {
                updateConnectionStatus('connecting');
                console.log(`Connecting to WebSocket: ${url} (Attempt ${reconnectAttempts + 1})`);
                
                socket = new WebSocket(url);
                
                socket.addEventListener('open', function(event) {
                    console.log('WebSocket connection established');
                    reconnectAttempts = 0;
                    updateConnectionStatus('connected');
                    
                    if (typeof onOpenCallback === 'function') {
                        onOpenCallback(event, socket);
                    }
                });
                
                socket.addEventListener('message', function(event) {
                    if (typeof onMessageCallback === 'function') {
                        onMessageCallback(event, socket);
                    }
                });
                
                socket.addEventListener('close', function(event) {
                    console.log(`WebSocket connection closed. Code: ${event.code}, Reason: ${event.reason}`);
                    updateConnectionStatus('disconnected');
                    
                    if (typeof onCloseCallback === 'function') {
                        onCloseCallback(event);
                    }
                    
                    // Don't reconnect if we closed it deliberately (code 1000)
                    if (event.code !== 1000 && reconnectAttempts < maxReconnectAttempts) {
                        const delay = Math.min(30000, baseReconnectDelay * Math.pow(1.5, reconnectAttempts));
                        console.log(`Reconnecting in ${delay/1000} seconds...`);
                        
                        clearTimeout(reconnectTimer);
                        reconnectTimer = setTimeout(function() {
                            reconnectAttempts++;
                            connect();
                        }, delay);
                    } else if (reconnectAttempts >= maxReconnectAttempts) {
                        console.log('Max reconnect attempts reached. Giving up.');
                        showNotification('Connection lost. Please refresh the page.', 'error', 0);
                    }
                });
                
                socket.addEventListener('error', function(event) {
                    console.error('WebSocket error:', event);
                    updateConnectionStatus('disconnected');
                    
                    if (typeof onErrorCallback === 'function') {
                        onErrorCallback(event);
                    }
                });
                
                return socket;
            } catch (error) {
                console.error('Error creating WebSocket:', error);
                updateConnectionStatus('disconnected');
                
                if (reconnectAttempts < maxReconnectAttempts) {
                    const delay = Math.min(30000, baseReconnectDelay * Math.pow(1.5, reconnectAttempts));
                    console.log(`Error connecting. Retrying in ${delay/1000} seconds...`);
                    
                    clearTimeout(reconnectTimer);
                    reconnectTimer = setTimeout(function() {
                        reconnectAttempts++;
                        connect();
                    }, delay);
                } else {
                    console.log('Max reconnect attempts reached. Giving up.');
                    showNotification('Connection failed. Please refresh the page.', 'error', 0);
                }
                
                return null;
            }
        }
        
        // Return the socket and methods to control it
        const connection = {
            socket: connect(),
            close: function() {
                if (socket && socket.readyState === WebSocket.OPEN) {
                    socket.close(1000, 'Closed by client');
                }
                clearTimeout(reconnectTimer);
            },
            reconnect: function() {
                this.close();
                reconnectAttempts = 0;
                this.socket = connect();
            },
            send: function(data) {
                if (socket && socket.readyState === WebSocket.OPEN) {
                    if (typeof data === 'object') {
                        socket.send(JSON.stringify(data));
                    } else {
                        socket.send(data);
                    }
                    return true;
                } else {
                    console.warn('Cannot send message, socket not connected');
                    return false;
                }
            }
        };
        
        return connection;
    },
    
    // Get WebSocket protocol based on page protocol
    getSocketProtocol: function() {
        return window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    },
    
    // Create a WebSocket URL
    createSocketUrl: function(path) {
        const protocol = this.getSocketProtocol();
        return `${protocol}//${window.location.host}/${path}`;
    }
};

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
        
        #connection-status {
            position: fixed;
            bottom: 10px;
            left: 10px;
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 12px;
            z-index: 9999;
        }
        
        #connection-status.connected {
            background-color: rgba(40, 167, 69, 0.8);
            color: white;
        }
        
        #connection-status.disconnected {
            background-color: rgba(220, 53, 69, 0.8);
            color: white;
        }
        
        #connection-status.connecting {
            background-color: rgba(255, 193, 7, 0.8);
            color: black;
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