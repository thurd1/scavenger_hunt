/**
 * Establish a WebSocket connection for a race
 * @param {number} raceId - The ID of the race to connect to
 * @returns {WebSocket} - The WebSocket connection
 */
function connectToRaceWebsocket(raceId) {
    const wsScheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const raceSocket = new WebSocket(
        wsScheme + '://' + window.location.host + '/ws/race/' + raceId + '/'
    );
    
    raceSocket.onopen = function(e) {
        console.log('Race socket connected');
    };
    
    raceSocket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        console.log('Race socket message:', data);
        
        if (data.type === 'race_started') {
            if (data.redirect_url) {
                window.location.href = data.redirect_url;
            }
        }
    };
    
    raceSocket.onclose = function(e) {
        console.log('Race socket closed');
    };
    
    raceSocket.onerror = function(e) {
        console.error('Race socket error:', e);
    };
    
    return raceSocket;
}

// Initialize race websocket if race ID is available
document.addEventListener('DOMContentLoaded', function() {
    // For lobby details page
    const startRaceBtn = document.getElementById('start-race-btn');
    if (startRaceBtn && startRaceBtn.dataset.raceId) {
        connectToRaceWebsocket(startRaceBtn.dataset.raceId);
    }
    
    // For race page with ID in URL
    const pathMatch = window.location.pathname.match(/\/race\/(\d+)\//);
    if (pathMatch && pathMatch[1]) {
        connectToRaceWebsocket(pathMatch[1]);
    }
});