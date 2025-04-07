/**
 * Leaderboard WebSocket Handler
 * Manages real-time updates for the leaderboard page
 */

// Initialize with a maximum of 3 reconnect attempts
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 3;
let socket = null;

// Function to initialize the WebSocket connection
function initLeaderboardWebSocket() {
    // Set up WebSocket connection
    const wsScheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socketUrl = `${wsScheme}//${window.location.host}/ws/leaderboard/`;
    
    console.log(`Initializing leaderboard WebSocket connection to: ${socketUrl}`);
    
    // Create new WebSocket connection
    socket = new WebSocket(socketUrl);
    
    // Setup event handlers
    socket.onopen = handleSocketOpen;
    socket.onmessage = handleSocketMessage;
    socket.onclose = handleSocketClose;
    socket.onerror = handleSocketError;
    
    return socket;
}

// Handle WebSocket open event
function handleSocketOpen(event) {
    console.log('Leaderboard WebSocket connection established');
    reconnectAttempts = 0; // Reset reconnect attempts on successful connection
    
    // Add a connected indicator to the page
    const dashboardBox = document.querySelector('.dashboard-box');
    if (dashboardBox) {
        const statusIndicator = document.createElement('div');
        statusIndicator.id = 'websocket-status';
        statusIndicator.className = 'websocket-status connected';
        statusIndicator.textContent = '● Live Updates Active';
        dashboardBox.prepend(statusIndicator);
    }
    
    // Request initial data
    socket.send(JSON.stringify({
        action: 'get_data'
    }));
}

// Handle incoming WebSocket messages
function handleSocketMessage(event) {
    try {
        const data = JSON.parse(event.data);
        console.log('Received leaderboard WebSocket message:', data);
        
        if (data.type === 'leaderboard_update') {
            updateLeaderboard(data.teams);
        }
    } catch (error) {
        console.error('Error processing WebSocket message:', error);
    }
}

// Handle WebSocket close event
function handleSocketClose(event) {
    console.log(`Leaderboard WebSocket connection closed. Code: ${event.code}, Reason: ${event.reason}`);
    
    // Update status indicator
    const statusIndicator = document.getElementById('websocket-status');
    if (statusIndicator) {
        statusIndicator.className = 'websocket-status disconnected';
        statusIndicator.textContent = '● Live Updates Disconnected - Reconnecting...';
    }
    
    // Attempt to reconnect if not closing intentionally
    if (event.code !== 1000) {
        attemptReconnect();
    }
}

// Handle WebSocket errors
function handleSocketError(error) {
    console.error('Leaderboard WebSocket error:', error);
    
    // Update status indicator
    const statusIndicator = document.getElementById('websocket-status');
    if (statusIndicator) {
        statusIndicator.className = 'websocket-status error';
        statusIndicator.textContent = '● Connection Error';
    }
}

// Attempt to reconnect with exponential backoff
function attemptReconnect() {
    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
        console.log('Maximum reconnection attempts reached. Falling back to API polling...');
        
        // Update status indicator
        const statusIndicator = document.getElementById('websocket-status');
        if (statusIndicator) {
            statusIndicator.className = 'websocket-status error';
            statusIndicator.textContent = '● Live Updates Failed - Using Polling';
        }
        
        // Start polling as fallback
        startPolling();
        return;
    }
    
    // Calculate backoff delay: 1s, 2s, 4s, etc.
    const delay = Math.pow(2, reconnectAttempts) * 1000;
    console.log(`Attempting to reconnect in ${delay}ms (attempt ${reconnectAttempts + 1}/${MAX_RECONNECT_ATTEMPTS})`);
    
    // Update status indicator
    const statusIndicator = document.getElementById('websocket-status');
    if (statusIndicator) {
        statusIndicator.className = 'websocket-status reconnecting';
        statusIndicator.textContent = `● Reconnecting (${reconnectAttempts + 1}/${MAX_RECONNECT_ATTEMPTS})...`;
    }
    
    setTimeout(() => {
        reconnectAttempts++;
        initLeaderboardWebSocket();
    }, delay);
}

// Start polling API as fallback
let pollingInterval = null;
function startPolling() {
    if (pollingInterval) return; // Don't start multiple intervals
    
    console.log('Starting API polling for leaderboard data');
    
    // Poll every 3 seconds
    pollingInterval = setInterval(() => {
        fetchLeaderboardData();
    }, 3000);
}

// Stop polling
function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
        console.log('Stopped API polling');
    }
}

// Fetch leaderboard data via API
function fetchLeaderboardData() {
    console.log('Fetching leaderboard data via API');
    
    fetch('/api/leaderboard-data/')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateLeaderboard(data.teams);
            } else {
                console.error('API returned error:', data.error);
            }
        })
        .catch(error => {
            console.error('Error fetching leaderboard data:', error);
        });
}

// Update the leaderboard with new data
function updateLeaderboard(teams) {
    const leaderboardBody = document.getElementById('leaderboard-body');
    const selectedLobbyId = document.getElementById('lobby-select')?.value || 'all';
    
    if (!leaderboardBody) {
        console.error('Leaderboard body element not found');
        return;
    }
    
    if (!teams || teams.length === 0) {
        leaderboardBody.innerHTML = '<tr><td colspan="3" class="text-center">No teams available</td></tr>';
        return;
    }
    
    // Get current teams for comparison (to highlight changes)
    const currentTeams = {};
    document.querySelectorAll('.team-row').forEach(row => {
        const teamId = row.getAttribute('data-team-id');
        const scoreElement = row.querySelector('.team-score');
        if (teamId && scoreElement) {
            currentTeams[teamId] = {
                score: parseInt(scoreElement.textContent) || 0,
                element: row
            };
        }
    });
    
    // Sort teams by score (highest first)
    teams.sort((a, b) => b.score - a.score);
    
    // Clear the table to rebuild it in correct order
    leaderboardBody.innerHTML = '';
    
    // Add each team to the table
    teams.forEach(team => {
        // Create new row for this team
        const row = document.createElement('tr');
        row.className = 'team-row';
        row.dataset.teamId = team.id;
        row.dataset.lobbyId = team.lobby_id || '';
        
        const nameCell = document.createElement('td');
        nameCell.className = 'team-name';
        nameCell.textContent = team.name;
        
        const scoreCell = document.createElement('td');
        scoreCell.className = 'team-score';
        scoreCell.textContent = team.score;
        
        const lobbyCell = document.createElement('td');
        lobbyCell.className = 'team-lobby';
        lobbyCell.textContent = team.lobby_name || 'Unknown';
        
        row.appendChild(nameCell);
        row.appendChild(scoreCell);
        row.appendChild(lobbyCell);
        
        // Apply filter based on current selection
        if (selectedLobbyId !== 'all' && team.lobby_id !== selectedLobbyId) {
            row.style.display = 'none';
        }
        
        // Highlight changed scores
        if (currentTeams[team.id]) {
            const currentScore = currentTeams[team.id].score;
            if (team.score > currentScore) {
                scoreCell.classList.add('score-increased');
                
                // Add animation class
                row.classList.add('updated');
                
                // Remove the highlight class after animation completes
                setTimeout(() => {
                    row.classList.remove('updated');
                    scoreCell.classList.remove('score-increased');
                }, 3000);
            }
        } else {
            // New team added
            row.classList.add('new-team');
            
            // Remove the highlight class after animation completes
            setTimeout(() => {
                row.classList.remove('new-team');
            }, 3000);
        }
        
        leaderboardBody.appendChild(row);
    });
}

// Close WebSocket when page is unloaded
window.addEventListener('beforeunload', () => {
    if (socket && socket.readyState === WebSocket.OPEN) {
        // Use 1000 code for normal closure
        socket.close(1000, 'Page navigation');
    }
    
    // Also stop polling if active
    stopPolling();
});

// Initialize WebSocket when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initLeaderboardWebSocket();
}); 