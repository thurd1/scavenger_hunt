/**
 * Establish a WebSocket connection for a race
 * @param {number} raceId - The ID of the race to connect to
 * @returns {WebSocket} - The WebSocket connection
 */
function connectToRaceWebsocket(raceId) {
    // Determine if we're using a secure connection
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/race/${raceId}/`;
    
    console.log(`Connecting to race WebSocket at: ${wsUrl}`);
    
    try {
        const socket = new WebSocket(wsUrl);
        
        socket.onopen = function(e) {
            console.log('Race WebSocket connection established');
            const statusElement = document.getElementById('connection-status');
            if (statusElement) {
                statusElement.textContent = 'Connected';
                statusElement.classList.remove('text-danger');
                statusElement.classList.add('text-success');
            }
            
            // Show connected message on screen for debugging
            showMessage('WebSocket connected!', 'success');
        };
        
        socket.onmessage = function(e) {
            try {
                const data = JSON.parse(e.data);
                console.log('Race WebSocket message received:', data);
                
                // Handle different types of messages
                if (data.type === 'race_started') {
                    console.log('Race started event received with data:', data);
                    
                    // Show a notification that we received the race started event
                    showMessage('Race started event received! Redirecting...', 'info');
                    
                    // Check if there's a custom handler defined in the page
                    if (typeof window.handleRaceStarted === 'function') {
                        // Use the custom handler from the page
                        console.log('Using custom race_started handler from page');
                        window.handleRaceStarted(data);
                    } else {
                        // Use the default handler in this file
                        console.log('Using default race_started handler');
                        if (data.redirect_url) {
                            console.log('Redirecting to:', data.redirect_url);
                            
                            // Redirect with a small delay to allow the message to be seen
                            setTimeout(() => {
                                window.location.href = data.redirect_url;
                            }, 1000);
                        } else {
                            // If redirect URL is missing, try a fallback
                            console.error('Missing redirect_url in race_started event');
                            showMessage('Race started but no redirect URL provided! Trying fallback...', 'warning');
                            
                            // Try to build a fallback URL based on the race ID
                            const fallbackUrl = `/race/${raceId}/questions/`;
                            console.log('Using fallback URL:', fallbackUrl);
                            
                            setTimeout(() => {
                                window.location.href = fallbackUrl;
                            }, 2000);
                        }
                    }
                }
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
                showMessage('Error parsing message: ' + error.message, 'error');
            }
        };
        
        socket.onclose = function(e) {
            console.log('Race WebSocket connection closed');
            const statusElement = document.getElementById('connection-status');
            if (statusElement) {
                statusElement.textContent = 'Disconnected';
                statusElement.classList.remove('text-success');
                statusElement.classList.add('text-danger');
            }
            
            // Try to reconnect after a delay
            showMessage('WebSocket disconnected. Attempting to reconnect...', 'warning');
            setTimeout(() => {
                window.raceSocket = connectToRaceWebsocket(raceId);
            }, 3000);
        };
        
        socket.onerror = function(e) {
            console.error('Race WebSocket error:', e);
            const statusElement = document.getElementById('connection-status');
            if (statusElement) {
                statusElement.textContent = 'Connection Error';
                statusElement.classList.remove('text-success');
                statusElement.classList.add('text-danger');
            }
            showMessage('WebSocket error. Check console for details.', 'error');
        };
        
        return socket;
    } catch (error) {
        console.error('Error creating WebSocket connection:', error);
        showMessage('Failed to create WebSocket: ' + error.message, 'error');
        return null;
    }
}

/**
 * Display a message on the screen for debugging/user feedback
 */
function showMessage(message, type = 'info') {
    // Create or reuse message container
    let container = document.getElementById('ws-message-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'ws-message-container';
        container.style.position = 'fixed';
        container.style.top = '10px';
        container.style.right = '10px';
        container.style.zIndex = '10000';
        container.style.maxWidth = '300px';
        document.body.appendChild(container);
    }
    
    // Create message element
    const msgEl = document.createElement('div');
    msgEl.style.margin = '5px';
    msgEl.style.padding = '10px';
    msgEl.style.borderRadius = '5px';
    msgEl.style.boxShadow = '0 2px 5px rgba(0,0,0,0.2)';
    msgEl.style.wordBreak = 'break-word';
    
    // Set colors based on message type
    switch (type) {
        case 'success':
            msgEl.style.backgroundColor = 'rgba(40, 167, 69, 0.9)';
            break;
        case 'warning':
            msgEl.style.backgroundColor = 'rgba(255, 193, 7, 0.9)';
            msgEl.style.color = '#000';
            break;
        case 'error':
            msgEl.style.backgroundColor = 'rgba(220, 53, 69, 0.9)';
            break;
        default: // info
            msgEl.style.backgroundColor = 'rgba(23, 162, 184, 0.9)';
    }
    
    msgEl.style.color = type === 'warning' ? '#000' : '#fff';
    msgEl.textContent = message;
    
    // Add to container
    container.appendChild(msgEl);
    
    // Remove after 5 seconds
    setTimeout(() => {
        if (container.contains(msgEl)) {
            container.removeChild(msgEl);
        }
        
        // Remove container if empty
        if (container.children.length === 0) {
            document.body.removeChild(container);
        }
    }, 5000);
}

// Initialize WebSocket connection when DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    try {
        // Check if we have a race ID (either from a button or from URL)
        const startRaceBtn = document.getElementById('start-race-btn');
        let raceId = null;
        
        if (startRaceBtn && startRaceBtn.dataset.raceId) {
            raceId = startRaceBtn.dataset.raceId;
            console.log(`Found race ID from button: ${raceId}`);
        } else {
            // Try to get race ID from URL path (e.g., /race/123/)
            const pathMatch = window.location.pathname.match(/\/race\/(\d+)\//);
            if (pathMatch && pathMatch[1]) {
                raceId = pathMatch[1];
                console.log(`Found race ID from URL: ${raceId}`);
            }
            
            // If still no race ID, check if we're in a lobby
            if (!raceId) {
                const lobbyMatch = window.location.pathname.match(/\/lobby\/(\d+)\//);
                if (lobbyMatch && lobbyMatch[1]) {
                    const lobbyId = lobbyMatch[1];
                    console.log(`Found lobby ID from URL: ${lobbyId}`);
                    // Use lobby ID as race ID (they're often the same in this app context)
                    raceId = lobbyId;
                }
            }
        }
        
        if (raceId) {
            console.log(`Connecting to race with ID: ${raceId}`);
            window.raceSocket = connectToRaceWebsocket(raceId);
        } else {
            console.log('No race ID found, not connecting to WebSocket');
        }
    } catch (error) {
        console.error('Error initializing WebSocket:', error);
        showMessage('Error initializing WebSocket: ' + error.message, 'error');
    }
});