/**
 * Leaderboard WebSocket Handler
 * Manages real-time updates for the leaderboard page
 */

// Connection variable
let leaderboardConnection = null;
let pollingInterval = null;

// Debug mode flag
const DEBUG_MODE = true;

// Function to show debug info on page
function showDebugInfo(message, isError = false) {
    console.log(message);
    
    // Skip if debug mode is off
    if (!DEBUG_MODE) return;
    
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
    // Create WebSocket URL using WebSocketUtils
    const socketUrl = WebSocketUtils.createSocketUrl('ws/leaderboard/');
    showDebugInfo(`Initializing WebSocket to: ${socketUrl}`);
    
    // Create connection using WebSocketUtils
    leaderboardConnection = WebSocketUtils.createConnection(
        socketUrl,
        handleSocketMessage,
        handleSocketOpen,
        handleSocketClose,
        handleSocketError
    );
    
    // Make accessible to window for external access
    window.leaderboardConnection = leaderboardConnection;
    
    return leaderboardConnection;
}

// Handle WebSocket open event
function handleSocketOpen(event, socket) {
    showDebugInfo('WebSocket connection established successfully');
    
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
        rtIndicator.style.backgroundColor = 'rgba(144, 200, 60, 0.2)';
        rtIndicator.style.color = '#90C83C';
        rtIndicator.innerHTML = '<span class="pulse-dot">●</span> Live Updates Active';
    }
    
    // Request initial data
    showDebugInfo('Requesting initial leaderboard data...');
    if (socket) {
        socket.send(JSON.stringify({
            action: 'get_data'
        }));
    }
    
    // Stop polling if active
    stopPolling();
}

// Handle incoming WebSocket messages
function handleSocketMessage(event) {
    try {
        const data = JSON.parse(event.data);
        showDebugInfo(`Received message: ${data.type}`);
        
        if (data.type === 'leaderboard_update') {
            showDebugInfo(`Updating leaderboard with ${data.teams ? data.teams.length : 'unknown'} teams`);
            
            if (data.teams && Array.isArray(data.teams)) {
                updateLeaderboard(data.teams);
            } else if (data.action === 'refresh') {
                // Server is requesting a refresh
                fetchLeaderboardData();
            }
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
        rtIndicator.style.backgroundColor = 'rgba(220, 53, 69, 0.2)';
        rtIndicator.style.color = '#dc3545';
        rtIndicator.innerHTML = '<span class="pulse-dot">●</span> Reconnecting...';
    }
    
    // If we've lost connection too many times, start polling as fallback
    if (event.code !== 1000 && event.code !== 1001) {
        // Start API polling as fallback if socket doesn't reconnect
        setTimeout(() => {
            if (!leaderboardConnection || 
                !leaderboardConnection.socket || 
                leaderboardConnection.socket.readyState !== WebSocket.OPEN) {
                startPolling();
            }
        }, 5000);
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
        rtIndicator.style.backgroundColor = 'rgba(220, 53, 69, 0.2)';
        rtIndicator.style.color = '#dc3545';
        rtIndicator.innerHTML = '<span class="pulse-dot">●</span> Connection Error';
    }
}

// Start polling for leaderboard updates as fallback
function startPolling() {
    showDebugInfo('Starting polling fallback mechanism');
    
    // Make sure we only have one polling interval
    stopPolling();
    
    // Update the real-time indicator to show we're using polling
    const rtIndicator = document.getElementById('realtime-indicator');
    if (rtIndicator) {
        rtIndicator.style.backgroundColor = 'rgba(255, 193, 7, 0.2)';
        rtIndicator.style.color = '#ffc107';
        rtIndicator.innerHTML = '<span class="pulse-dot">●</span> Using Polling (Slower)';
    }
    
    // Set up polling interval
    pollingInterval = setInterval(fetchLeaderboardData, 10000); // Every 10 seconds
    
    // Fetch data immediately
    fetchLeaderboardData();
}

// Stop polling if it's active
function stopPolling() {
    if (pollingInterval) {
        showDebugInfo('Stopping polling mechanism');
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

// Fetch leaderboard data from API
function fetchLeaderboardData() {
    showDebugInfo('Fetching leaderboard data via API...');
    
    // Get the current race ID if available
    let raceId = '';
    if (window.raceId) {
        raceId = `?race_id=${window.raceId}`;
    }
    
    // Fetch the data
    fetch(`/api/leaderboard/${raceId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            showDebugInfo(`Received API data with ${data.teams.length} teams`);
            updateLeaderboard(data.teams);
        })
        .catch(error => {
            showDebugInfo(`API fetch error: ${error.message}`, true);
        });
}

// Update the leaderboard with team data
function updateLeaderboard(teams) {
    if (!teams || !Array.isArray(teams)) {
        showDebugInfo('Invalid teams data received', true);
        return;
    }
    
    showDebugInfo(`Updating leaderboard with ${teams.length} teams`);
    
    // Sort teams by points (highest first)
    const sortedTeams = [...teams].sort((a, b) => (b.points || 0) - (a.points || 0));
    
    // Get the leaderboard container
    const leaderboardContainer = document.getElementById('leaderboard-container');
    if (!leaderboardContainer) {
        showDebugInfo('Leaderboard container not found', true);
        return;
    }
    
    // Clear existing content
    leaderboardContainer.innerHTML = '';
    
    // Check if we have teams
    if (sortedTeams.length === 0) {
        leaderboardContainer.innerHTML = '<div class="no-teams">No teams have started yet.</div>';
        return;
    }
    
    // Create table
    const table = document.createElement('table');
    table.className = 'leaderboard-table';
    
    // Create table header
    const thead = document.createElement('thead');
    thead.innerHTML = `
        <tr>
            <th>Rank</th>
            <th>Team</th>
            <th>Points</th>
            <th>Progress</th>
        </tr>
    `;
    table.appendChild(thead);
    
    // Create table body
    const tbody = document.createElement('tbody');
    
    // Add rows for each team
    sortedTeams.forEach((team, index) => {
        const row = document.createElement('tr');
        
        // Add special class for top 3 teams
        if (index < 3) {
            row.className = `top-${index + 1}`;
        }
        
        // Calculate progress percentage
        const progress = team.progress || 0;
        const totalQuestions = team.total_questions || 10;
        const progressPercent = Math.min(100, Math.round((progress / totalQuestions) * 100));
        
        // Create row content
        row.innerHTML = `
            <td class="rank">${index + 1}</td>
            <td class="team-name">${team.name}</td>
            <td class="points">${team.points || 0}</td>
            <td class="progress">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${progressPercent}%"></div>
                    <span class="progress-text">${progressPercent}%</span>
                </div>
            </td>
        `;
        
        tbody.appendChild(row);
    });
    
    table.appendChild(tbody);
    leaderboardContainer.appendChild(table);
    
    // Apply animation to newly updated rows
    const rows = tbody.querySelectorAll('tr');
    rows.forEach(row => {
        row.classList.add('updated');
        setTimeout(() => {
            row.classList.remove('updated');
        }, 2000);
    });
    
    // Update last refresh time
    const refreshTime = document.getElementById('last-refresh-time');
    if (refreshTime) {
        const now = new Date();
        refreshTime.textContent = now.toLocaleTimeString();
    }
}

// Add leaderboard-specific styles
function addLeaderboardStyles() {
    const existingStyle = document.getElementById('leaderboard-styles');
    if (existingStyle) return;
    
    const style = document.createElement('style');
    style.id = 'leaderboard-styles';
    style.textContent = `
        .websocket-status {
            padding: 5px 15px;
            margin-bottom: 15px;
            border-radius: 4px;
            display: inline-block;
            font-size: 14px;
        }
        
        #realtime-indicator {
            position: fixed;
            top: 10px;
            right: 10px;
            background-color: rgba(33, 37, 41, 0.8);
            padding: 8px 12px;
            border-radius: 4px;
            z-index: 9999;
            font-size: 12px;
            display: flex;
            align-items: center;
        }
        
        .pulse-dot {
            display: inline-block;
            margin-right: 5px;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 0.3; }
            50% { opacity: 1; }
            100% { opacity: 0.3; }
        }
        
        .leaderboard-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        
        .leaderboard-table th {
            background-color: rgba(33, 37, 41, 0.8);
            color: #90C83C;
            font-weight: bold;
            padding: 12px;
            text-align: left;
        }
        
        .leaderboard-table td {
            padding: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .leaderboard-table tr.top-1 {
            background-color: rgba(255, 215, 0, 0.2);
        }
        
        .leaderboard-table tr.top-2 {
            background-color: rgba(192, 192, 192, 0.2);
        }
        
        .leaderboard-table tr.top-3 {
            background-color: rgba(205, 127, 50, 0.2);
        }
        
        .leaderboard-table tr.updated {
            animation: highlight 2s;
        }
        
        .progress-bar {
            width: 100%;
            background-color: rgba(0, 0, 0, 0.2);
            border-radius: 10px;
            height: 20px;
            position: relative;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background-color: #90C83C;
            border-radius: 10px;
            transition: width 0.5s;
        }
        
        .progress-text {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 12px;
            font-weight: bold;
        }
        
        @keyframes highlight {
            0% { background-color: rgba(144, 200, 60, 0.3); }
            100% { background-color: transparent; }
        }
        
        .rank {
            font-weight: bold;
            width: 60px;
        }
        
        .team-name {
            font-weight: bold;
        }
        
        .points {
            font-weight: bold;
            color: #90C83C;
            width: 100px;
        }
        
        .no-teams {
            text-align: center;
            padding: 40px;
            color: #aaa;
            font-size: 18px;
        }
    `;
    document.head.appendChild(style);
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing leaderboard WebSocket handler');
    
    // Add styles
    addLeaderboardStyles();
    
    // Create the real-time indicator
    const rtIndicator = document.createElement('div');
    rtIndicator.id = 'realtime-indicator';
    rtIndicator.innerHTML = '<span class="pulse-dot">●</span> Connecting...';
    rtIndicator.style.backgroundColor = 'rgba(255, 193, 7, 0.2)';
    rtIndicator.style.color = '#ffc107';
    document.body.appendChild(rtIndicator);
    
    // Create connection status indicator if it doesn't exist
    if (!document.getElementById('connection-status')) {
        const statusIndicator = document.createElement('div');
        statusIndicator.id = 'connection-status';
        statusIndicator.className = 'connecting';
        statusIndicator.innerHTML = '<span>Connecting...</span>';
        document.body.appendChild(statusIndicator);
    }
    
    // Initialize WebSocket connection
    initLeaderboardWebSocket();
}); 