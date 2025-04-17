/**
 * Common utility functions for the scavenger hunt application
 */

// Global variables for WebSocket connectivity
let lastWebSocketActivity = Date.now();
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY = 3000; // 3 seconds

/**
 * Setup auto-refresh mechanism if WebSocket activity stops
 * @param {number} checkInterval - Interval in ms to check for activity
 * @param {number} maxInactiveTime - Max time in ms without activity before refresh
 * @param {Function} reconnectFunction - Optional function to call for reconnection attempt before refresh
 */
function setupAutoRefresh(checkInterval = 10000, maxInactiveTime = 30000, reconnectFunction = null) {
    console.log("Setting up auto-refresh mechanism");
    
    // Check periodically if we need to refresh
    setInterval(function() {
        const now = Date.now();
        const timeSinceLastActivity = now - lastWebSocketActivity;
        
        console.log(`Time since last WebSocket activity: ${Math.round(timeSinceLastActivity/1000)}s`);
        
        // If no WebSocket activity for the specified time, try reconnect or refresh
        if (timeSinceLastActivity > maxInactiveTime) {
            console.log("No WebSocket updates detected for too long");
            
            // Try reconnection function if provided
            if (reconnectFunction && typeof reconnectFunction === 'function' && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                console.log(`Attempting reconnection (${reconnectAttempts + 1}/${MAX_RECONNECT_ATTEMPTS})`);
                reconnectAttempts++;
                showConnectionStatus('reconnecting', `Reconnecting (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`);
                reconnectFunction();
                
                // Update activity timestamp to prevent immediate refresh
                lastWebSocketActivity = Date.now();
            } else {
                // Fall back to page refresh
                showConnectionStatus('updating', 'No updates received. Refreshing page...');
                
                // Wait a moment for the notification to be visible
                setTimeout(function() {
                    location.reload();
                }, 1000);
            }
        }
    }, checkInterval);
}

/**
 * Show connection status to the user
 * @param {string} status - Status type (error, closed, reconnecting, connected, updating, failed)
 * @param {string} message - Message to display
 */
function showConnectionStatus(status, message) {
    console.log(`Connection status: ${status} - ${message}`);
    
    // Only show status for errors or important messages to avoid UI clutter
    if (['error', 'closed', 'failed', 'updating', 'reconnecting'].includes(status)) {
        const statusEl = document.createElement('div');
        statusEl.id = 'connection-status';
        statusEl.style.position = 'fixed';
        statusEl.style.bottom = '20px';
        statusEl.style.right = '20px';
        statusEl.style.padding = '10px 15px';
        statusEl.style.borderRadius = '5px';
        statusEl.style.zIndex = '1000';
        statusEl.style.maxWidth = '300px';
        
        // Style based on status
        if (status === 'error' || status === 'closed' || status === 'failed') {
            statusEl.style.backgroundColor = 'rgba(220, 53, 69, 0.9)';
        } else if (status === 'reconnecting') {
            statusEl.style.backgroundColor = 'rgba(255, 193, 7, 0.9)';
        } else if (status === 'connected') {
            statusEl.style.backgroundColor = 'rgba(40, 167, 69, 0.9)';
        } else if (status === 'updating') {
            statusEl.style.backgroundColor = 'rgba(0, 123, 255, 0.9)';
        }
        
        statusEl.style.color = 'white';
        statusEl.style.boxShadow = '0 0 10px rgba(0,0,0,0.3)';
        statusEl.innerHTML = message;
        
        // Remove any existing status
        const existingStatus = document.getElementById('connection-status');
        if (existingStatus) {
            existingStatus.remove();
        }
        
        // Add to DOM
        document.body.appendChild(statusEl);
        
        // Auto-remove after delay for non-error messages
        if (status !== 'error' && status !== 'failed') {
            setTimeout(() => {
                statusEl.remove();
            }, 3000);
        }
    }
}

/**
 * Handle WebSocket connection errors with graceful fallback
 * @param {WebSocket} socket - The WebSocket instance
 * @param {string} errorType - Type of error
 * @param {Error} error - Error object
 */
function handleWebSocketError(socket, errorType, error) {
    console.error(`WebSocket ${errorType} error:`, error);
    
    if (errorType === 'connect') {
        showConnectionStatus('error', 'Failed to establish connection');
    } else if (errorType === 'message') {
        // If it's a race not found error, show a more specific message
        if (error.message && error.message.includes("Race matching query does not exist")) {
            showConnectionStatus('error', 'Race not found. The race may have been deleted or hasn\'t been created yet.');
        } else {
            showConnectionStatus('error', 'Connection error');
        }
    }
    
    // Update activity timestamp to trigger auto-refresh if needed
    lastWebSocketActivity = Date.now();
}

// Export functions for use in other scripts
window.setupAutoRefresh = setupAutoRefresh;
window.showConnectionStatus = showConnectionStatus;
window.handleWebSocketError = handleWebSocketError;
window.lastWebSocketActivity = lastWebSocketActivity; 