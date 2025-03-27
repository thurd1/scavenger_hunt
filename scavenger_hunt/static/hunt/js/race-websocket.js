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
        const data = JSON.parse(e.data);
        console.log('Race WebSocket message received:', data);
        
        // Handle different types of messages
        if (data.type === 'race_started') {
            console.log('Race started, redirecting to:', data.redirect_url);
            window.location.href = data.redirect_url;
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
}

// Initialize WebSocket connection when DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Check if we have a race ID (either from a button or from URL)
    const startRaceBtn = document.getElementById('start-race-btn');
    let raceId = null;
    
    if (startRaceBtn && startRaceBtn.dataset.raceId) {
        raceId = startRaceBtn.dataset.raceId;
    } else {
        // Try to get race ID from URL path (e.g., /race/123/)
        const pathMatch = window.location.pathname.match(/\/race\/(\d+)\//);
        if (pathMatch && pathMatch[1]) {
            raceId = pathMatch[1];
        }
    }
    
    if (raceId) {
        console.log(`Found race ID: ${raceId}`);
        window.raceSocket = connectToRaceWebsocket(raceId);
    }
});