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
        };
        
        socket.onmessage = function(e) {
            try {
                const data = JSON.parse(e.data);
                console.log('Race WebSocket message received:', data);
                
                // Handle different types of messages
                if (data.type === 'race_started') {
                    console.log('Race started event received with data:', data);
                    
                    if (data.redirect_url) {
                        console.log('Redirecting to:', data.redirect_url);
                        
                        // Add a visual indicator for debugging
                        const statusEl = document.createElement('div');
                        statusEl.style.position = 'fixed';
                        statusEl.style.top = '10px';
                        statusEl.style.left = '10px';
                        statusEl.style.padding = '10px';
                        statusEl.style.background = 'rgba(0,0,0,0.8)';
                        statusEl.style.color = '#fff';
                        statusEl.style.zIndex = '9999';
                        statusEl.innerHTML = 'Redirecting to: ' + data.redirect_url;
                        document.body.appendChild(statusEl);
                        
                        // Delay redirect slightly to let the user see the message
                        setTimeout(() => {
                            window.location.href = data.redirect_url;
                        }, 500);
                    } else {
                        console.error('Missing redirect_url in race_started event');
                        alert('Race started but no redirect URL provided!');
                    }
                }
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
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
        };
        
        socket.onerror = function(e) {
            console.error('Race WebSocket error:', e);
            const statusElement = document.getElementById('connection-status');
            if (statusElement) {
                statusElement.textContent = 'Connection Error';
                statusElement.classList.remove('text-success');
                statusElement.classList.add('text-danger');
            }
        };
        
        return socket;
    } catch (error) {
        console.error('Error creating WebSocket connection:', error);
        return null;
    }
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
    }
});