/**
 * Establish a WebSocket connection for lobbies management
 * This allows for real-time updates of lobbies status, teams, and race events
 */

// Set up connection when document is ready
document.addEventListener('DOMContentLoaded', function() {
    initLobbiesWebSocket();
});

/**
 * Initialize the WebSocket connection to the lobbies channel
 */
function initLobbiesWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/lobbies/`;
    
    console.log(`Connecting to lobbies WebSocket at: ${wsUrl}`);
    
    try {
        const socket = new WebSocket(wsUrl);
        
        socket.onopen = function(e) {
            console.log('Lobbies WebSocket connection established');
            showNotification('Real-time updates connected', 'success');
            
            // Store the socket for later use
            window.lobbiesSocket = socket;
        };
        
        socket.onmessage = function(e) {
            try {
                const data = JSON.parse(e.data);
                console.log('Lobbies WebSocket message received:', data);
                
                // Dispatch to the appropriate handler based on message type
                switch(data.type) {
                    case 'lobby_update':
                        handleLobbyUpdate(data);
                        break;
                    case 'team_joined':
                        handleTeamJoined(data);
                        break;
                    case 'race_started':
                        handleRaceStarted(data);
                        break;
                    case 'team_update':
                        // You can add custom handler for team updates
                        break;
                    default:
                        console.log(`Unhandled message type: ${data.type}`);
                }
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };
        
        socket.onclose = function(e) {
            console.log('Lobbies WebSocket connection closed. Reconnecting in 5 seconds...');
            showNotification('Connection lost. Reconnecting...', 'error');
            
            // Try to reconnect after a delay
            setTimeout(() => {
                window.lobbiesSocket = null;
                initLobbiesWebSocket();
            }, 5000);
        };
        
        socket.onerror = function(e) {
            console.error('Lobbies WebSocket error:', e);
            showNotification('Connection error', 'error');
        };
        
        return socket;
    } catch (error) {
        console.error('Error setting up WebSocket connection:', error);
        showNotification('Failed to establish connection', 'error');
        return null;
    }
}

/**
 * Handle lobby update events
 * @param {Object} data - The event data
 */
function handleLobbyUpdate(data) {
    const lobbyId = data.lobby_id;
    const lobbyCard = document.querySelector(`.lobby-card[data-lobby-id="${lobbyId}"]`);
    
    if (!lobbyCard) {
        console.log(`Lobby ${lobbyId} not found in the current view`);
        return;
    }
    
    // Highlight the updated lobby
    lobbyCard.classList.add('updated');
    setTimeout(() => {
        lobbyCard.classList.remove('updated');
    }, 2000);
    
    // Update activation status if changed
    if (data.is_active !== undefined) {
        const statusEl = lobbyCard.querySelector('.status-text');
        const statusIcon = statusEl.parentElement.querySelector('i');
        
        if (statusEl) {
            statusEl.textContent = data.is_active ? 'Active' : 'Inactive';
            statusIcon.className = data.is_active ? 'fas fa-check-circle' : 'fas fa-times-circle';
        }
    }
    
    // Update hunt started status if changed
    if (data.hunt_started !== undefined) {
        const huntStatusEl = lobbyCard.querySelector('.hunt-status');
        if (huntStatusEl) {
            huntStatusEl.style.display = data.hunt_started ? 'block' : 'none';
            
            const huntTextEl = huntStatusEl.querySelector('.hunt-status-text');
            if (huntTextEl) {
                huntTextEl.textContent = data.hunt_started ? 'Started' : 'Not Started';
            }
        }
        
        // Update race start button if needed
        const startBtn = lobbyCard.querySelector('.start-race-btn');
        if (startBtn && data.hunt_started) {
            startBtn.innerHTML = '<i class="fas fa-check"></i> Race Started';
            startBtn.disabled = true;
            startBtn.style.backgroundColor = 'rgba(144, 200, 60, 0.3)';
        }
    }
    
    showNotification('Lobby status updated', 'success');
}

/**
 * Handle team joined events
 * @param {Object} data - The event data
 */
function handleTeamJoined(data) {
    const lobbyId = data.lobby_id;
    const lobbyCard = document.querySelector(`.lobby-card[data-lobby-id="${lobbyId}"]`);
    
    if (!lobbyCard) return;
    
    // Update team count with the accurate count from server
    const teamCountEl = lobbyCard.querySelector('.team-count');
    if (teamCountEl) {
        // Use the team_count provided by the server instead of incrementing
        if (data.team_count !== undefined) {
            teamCountEl.textContent = data.team_count;
            lobbiesData[lobbyId].teamCount = data.team_count;
        }
        
        // Apply updated class
        lobbyCard.classList.add('updated');
        setTimeout(() => {
            lobbyCard.classList.remove('updated');
        }, 2000);
        
        showNotification(`New team joined lobby #${lobbyId}`, 'success');
    }
}

/**
 * Handle race started events
 * @param {Object} data - The event data
 */
function handleRaceStarted(data) {
    const lobbyId = data.lobby_id;
    const lobbyCard = document.querySelector(`.lobby-card[data-lobby-id="${lobbyId}"]`);
    
    if (!lobbyCard) return;
    
    // Update hunt status
    const huntStatusEl = lobbyCard.querySelector('.hunt-status');
    if (huntStatusEl) {
        huntStatusEl.style.display = 'block';
        const statusTextEl = huntStatusEl.querySelector('.hunt-status-text');
        if (statusTextEl) {
            statusTextEl.textContent = 'Started';
        }
    }
    
    // Update start race button
    const startBtn = lobbyCard.querySelector('.start-race-btn');
    if (startBtn) {
        startBtn.innerHTML = '<i class="fas fa-check"></i> Race Started';
        startBtn.disabled = true;
        startBtn.style.backgroundColor = 'rgba(144, 200, 60, 0.3)';
    }
    
    // Highlight the lobby
    lobbyCard.classList.add('updated');
    setTimeout(() => {
        lobbyCard.classList.remove('updated');
    }, 2000);
    
    showNotification(`Race started for lobby #${lobbyId}`, 'success');
}

/**
 * Display a notification message
 * @param {string} message - The message to display
 * @param {string} type - The type of notification ('success', 'error', 'info')
 */
function showNotification(message, type = 'success') {
    // Check if we have the notification element from page
    const notification = document.getElementById('notification');
    const notificationMessage = document.getElementById('notification-message');
    
    if (notification && notificationMessage) {
        // Use existing notification element
        notificationMessage.textContent = message;
        
        // Set style based on type
        if (type === 'error') {
            notification.style.background = 'rgba(220, 53, 69, 0.9)';
        } else if (type === 'success') {
            notification.style.background = 'rgba(144, 200, 60, 0.9)';
        } else if (type === 'info') {
            notification.style.background = 'rgba(13, 202, 240, 0.9)';
        }
        
        // Show notification
        notification.style.display = 'flex';
        
        // Auto-hide after delay
        setTimeout(() => {
            notification.style.display = 'none';
        }, 3000);
    } else {
        // Create an ad-hoc notification
        const newNotification = document.createElement('div');
        newNotification.style.position = 'fixed';
        newNotification.style.top = '20px';
        newNotification.style.right = '20px';
        newNotification.style.padding = '15px 25px';
        newNotification.style.borderRadius = '5px';
        newNotification.style.zIndex = '9999';
        newNotification.style.color = 'white';
        newNotification.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.2)';
        
        // Set style based on type
        if (type === 'error') {
            newNotification.style.background = 'rgba(220, 53, 69, 0.9)';
        } else if (type === 'success') {
            newNotification.style.background = 'rgba(144, 200, 60, 0.9)';
        } else if (type === 'info') {
            newNotification.style.background = 'rgba(13, 202, 240, 0.9)';
        }
        
        newNotification.textContent = message;
        document.body.appendChild(newNotification);
        
        // Auto-remove after delay
        setTimeout(() => {
            document.body.removeChild(newNotification);
        }, 3000);
    }
} 