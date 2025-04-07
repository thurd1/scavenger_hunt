/**
 * Leaderboard WebSocket Handler
 * Manages real-time updates for the leaderboard page
 */

// Initialize with a maximum of 3 reconnect attempts
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 3;
let socket = null;

// Export socket to window for external access
window.socket = null;

// Function to show debug info on page
function showDebugInfo(message, isError = false) {
    console.log(message);
    
    // Check if debug container exists, create if not
    let debugContainer = document.getElementById('debug-container');
    if (!debugContainer) {
        debugContainer = document.createElement('div');
        debugContainer.id = 'debug-container';
        debugContainer.style.position = 'fixed';
        debugContainer.style.bottom = '10px';
        debugContainer.style.right = '10px';
        debugContainer.style.width = '300px';
        debugContainer.style.maxHeight = '150px';
        debugContainer.style.overflowY = 'auto';
        debugContainer.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
        debugContainer.style.color = '#fff';
        debugContainer.style.padding = '10px';
        debugContainer.style.borderRadius = '5px';
        debugContainer.style.zIndex = '9999';
        debugContainer.style.fontSize = '12px';
        document.body.appendChild(debugContainer);
    }
    
    // Add message
    const msgElement = document.createElement('div');
    msgElement.style.marginBottom = '5px';
    msgElement.style.borderBottom = '1px solid rgba(255,255,255,0.2)';
    msgElement.style.paddingBottom = '5px';
    msgElement.style.color = isError ? '#ff6b6b' : '#90C83C';
    msgElement.textContent = `${new Date().toLocaleTimeString()}: ${message}`;
    
    // Add to container (at top)
    debugContainer.insertBefore(msgElement, debugContainer.firstChild);
    
    // Limit number of messages
    if (debugContainer.children.length > 5) {
        debugContainer.removeChild(debugContainer.lastChild);
    }
}

// Function to initialize the WebSocket connection
function initLeaderboardWebSocket() {
    // Set up WebSocket connection
    const wsScheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socketUrl = `${wsScheme}//${window.location.host}/ws/leaderboard/`;
    
    showDebugInfo(`Initializing WebSocket to: ${socketUrl}`);
    
    try {
        // Create new WebSocket connection
        socket = new WebSocket(socketUrl);
        window.socket = socket; // Make accessible to window
        
        // Setup event handlers
        socket.onopen = handleSocketOpen;
        socket.onmessage = handleSocketMessage;
        socket.onclose = handleSocketClose;
        socket.onerror = handleSocketError;
        
        return socket;
    } catch (error) {
        showDebugInfo(`Error creating WebSocket: ${error.message}`, true);
        return null;
    }
}

// Handle WebSocket open event
function handleSocketOpen(event) {
    showDebugInfo('WebSocket connection established successfully');
    reconnectAttempts = 0; // Reset reconnect attempts on successful connection
    
    // Add a connected indicator to the page
    const dashboardBox = document.querySelector('.dashboard-box');
    if (dashboardBox) {
        // Remove any existing status indicator
        const existingStatus = document.getElementById('websocket-status');
        if (existingStatus) {
            existingStatus.remove();
        }
        
        const statusIndicator = document.createElement('div');
        statusIndicator.id = 'websocket-status';
        statusIndicator.className = 'websocket-status connected';
        statusIndicator.textContent = '● Live Updates Active';
        dashboardBox.prepend(statusIndicator);
    }
    
    // Update the real-time indicator if it exists
    const rtIndicator = document.getElementById('realtime-indicator');
    if (rtIndicator) {
        rtIndicator.style.backgroundColor = 'rgba(144, 200, 60, 0.2) !important';
        rtIndicator.style.color = '#90C83C !important';
        rtIndicator.innerHTML = '<span class="pulse-dot">●</span> Live Updates Active';
    }
    
    // Request initial data
    showDebugInfo('Requesting initial leaderboard data...');
    socket.send(JSON.stringify({
        action: 'get_data'
    }));
}

// Handle incoming WebSocket messages
function handleSocketMessage(event) {
    try {
        const data = JSON.parse(event.data);
        showDebugInfo(`Received message: ${data.type}`);
        
        if (data.type === 'leaderboard_update') {
            showDebugInfo(`Updating leaderboard with ${data.teams.length} teams`);
            updateLeaderboard(data.teams);
        } else if (data.type === 'error') {
            showDebugInfo(`Server reported error: ${data.message}`, true);
        } else {
            showDebugInfo(`Unhandled message type: ${data.type}`);
        }
    } catch (error) {
        showDebugInfo(`Error processing message: ${error.message}`, true);
        showDebugInfo(`Raw message data: ${event.data}`, true);
    }
}

// Handle WebSocket close event
function handleSocketClose(event) {
    showDebugInfo(`WebSocket closed. Code: ${event.code}, Reason: ${event.reason}`, true);
    
    // Update status indicator
    const statusIndicator = document.getElementById('websocket-status');
    if (statusIndicator) {
        statusIndicator.className = 'websocket-status disconnected';
        statusIndicator.textContent = '● Live Updates Disconnected - Reconnecting...';
    }
    
    // Update the real-time indicator if it exists
    const rtIndicator = document.getElementById('realtime-indicator');
    if (rtIndicator) {
        rtIndicator.style.backgroundColor = 'rgba(220, 53, 69, 0.2) !important';
        rtIndicator.style.color = '#dc3545 !important';
        rtIndicator.innerHTML = '<span class="pulse-dot">●</span> Reconnecting...';
    }
    
    // Attempt to reconnect if not closing intentionally
    if (event.code !== 1000) {
        attemptReconnect();
    }
}

// Handle WebSocket errors
function handleSocketError(error) {
    showDebugInfo(`WebSocket error: ${error.message || 'Unknown error'}`, true);
    
    // Update status indicator
    const statusIndicator = document.getElementById('websocket-status');
    if (statusIndicator) {
        statusIndicator.className = 'websocket-status error';
        statusIndicator.textContent = '● Connection Error';
    }
    
    // Update the real-time indicator if it exists
    const rtIndicator = document.getElementById('realtime-indicator');
    if (rtIndicator) {
        rtIndicator.style.backgroundColor = 'rgba(220, 53, 69, 0.2) !important';
        rtIndicator.style.color = '#dc3545 !important';
        rtIndicator.innerHTML = '<span class="pulse-dot">●</span> Connection Error';
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
                
                // If API doesn't exist, try a simple page refresh as last resort
                if (reconnectAttempts > MAX_RECONNECT_ATTEMPTS * 2) {
                    console.log('API polling failed too many times, refreshing page...');
                    window.location.reload();
                }
            }
        })
        .catch(error => {
            console.error('Error fetching leaderboard data:', error);
            reconnectAttempts++;
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
    
    console.log(`Updating leaderboard with ${teams.length} teams, filtering by lobby: ${selectedLobbyId}`);
    
    // Validate and fix team data if necessary
    teams = teams.map(team => {
        // Ensure team name is proper - fix the "Team: 30" format issue
        if (team.name && team.name.toString().includes(':')) {
            // Log the issue for debugging
            console.warn(`Found malformed team name: "${team.name}", extracting actual name`);
            
            // If it's in the format "Team: ID" but we have the actual name elsewhere
            if (team.team_name) {
                team.name = team.team_name;
            }
        }
        
        // Ensure the team has a valid name
        if (!team.name || team.name === 'null' || team.name === 'undefined') {
            console.warn(`Team with ID ${team.id} has invalid name: "${team.name}"`);
            team.name = `Team ${team.id}`;
        }
        
        // Make sure score is a number
        team.score = parseInt(team.score) || 0;
        
        return team;
    });
    
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
                console.log(`Team ${team.name} score increased from ${currentScore} to ${team.score}`);
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
            console.log(`New team added: ${team.name}`);
            row.classList.add('new-team');
            
            // Remove the highlight class after animation completes
            setTimeout(() => {
                row.classList.remove('new-team');
            }, 3000);
        }
        
        leaderboardBody.appendChild(row);
    });
}

// Force a reload if we've been sitting here too long
setTimeout(() => {
    if (reconnectAttempts > 0) {
        console.log('Page has been inactive for too long, refreshing...');
        window.location.reload();
    }
}, 60000); // 1 minute

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
    showDebugInfo('DOM loaded, initializing WebSocket connection');
    
    // Create a toggle button for debug container
    const toggleBtn = document.createElement('button');
    toggleBtn.textContent = 'Debug';
    toggleBtn.style.position = 'fixed';
    toggleBtn.style.bottom = '10px';
    toggleBtn.style.right = '10px';
    toggleBtn.style.zIndex = '10000';
    toggleBtn.style.padding = '5px 10px';
    toggleBtn.style.backgroundColor = '#90C83C';
    toggleBtn.style.color = 'white';
    toggleBtn.style.border = 'none';
    toggleBtn.style.borderRadius = '3px';
    toggleBtn.style.cursor = 'pointer';
    toggleBtn.onclick = function() {
        const debugContainer = document.getElementById('debug-container');
        if (debugContainer) {
            debugContainer.style.display = debugContainer.style.display === 'none' ? 'block' : 'none';
        }
    };
    document.body.appendChild(toggleBtn);
    
    initLeaderboardWebSocket();
    
    // As a fallback, request an update every 30 seconds even if websocket is working
    setInterval(() => {
        showDebugInfo('Requesting periodic leaderboard refresh');
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({
                action: 'get_data'
            }));
        } else {
            showDebugInfo('WebSocket not connected, falling back to API');
            fetchLeaderboardData();
        }
    }, 30000);
}); 