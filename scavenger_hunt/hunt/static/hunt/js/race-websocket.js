/**
 * Race WebSocket Handler
 * Manages real-time updates for race pages (waiting for race to start, questions, leaderboard)
 */

// Connection variable
let raceConnection = null;

// Function to initialize the WebSocket connection for a race
function initRaceWebSocket() {
    // Ensure we have a race ID to connect to
    if (!window.raceId) {
        console.error('Race ID not found in window object');
        
        // Try to extract from URL path
        const pathParts = window.location.pathname.split('/');
        const raceIndex = pathParts.indexOf('race');
        if (raceIndex !== -1 && raceIndex + 1 < pathParts.length) {
            window.raceId = pathParts[raceIndex + 1];
            console.log(`Extracted race ID from URL: ${window.raceId}`);
        } else {
            console.error('Could not extract race ID from URL');
            return null;
        }
    }
    
    // Create WebSocket URL using WebSocketUtils
    const socketUrl = WebSocketUtils.createSocketUrl(`ws/race/${window.raceId}/`);
    console.log(`Initializing race WebSocket connection to: ${socketUrl}`);
    
    // Create connection using WebSocketUtils
    raceConnection = WebSocketUtils.createConnection(
        socketUrl,
        handleRaceSocketMessage,
        handleRaceSocketOpen,
        handleRaceSocketClose,
        handleRaceSocketError
    );
    
    return raceConnection;
}

// Handle WebSocket open event
function handleRaceSocketOpen(event, socket) {
    console.log('Race WebSocket connection established successfully');
    
    // Create or update the connection status indicator
    updateRaceConnectionStatus('connected');
    
    // Send an initial message to check race status
    if (socket) {
        console.log(`Sending initial check_status message for race ${window.raceId}`);
        socket.send(JSON.stringify({
            'action': 'check_status',
            'race_id': window.raceId
        }));
    }
}

// Handle incoming WebSocket messages
function handleRaceSocketMessage(event) {
    try {
        const data = JSON.parse(event.data);
        console.log('Received race WebSocket message:', data);
        
        // Handle different types of messages
        switch (data.type) {
            case 'race_started':
                console.log('Race started event received with redirect URL:', data.redirect_url);
                handleRaceStarted(data.redirect_url, data.message || 'Race has started!');
                break;
            case 'team_progress':
                console.log('Team progress update received:', data);
                updateTeamProgress(data);
                break;
            case 'leaderboard_update':
                console.log('Leaderboard update received:', data);
                updateLeaderboard(data);
                break;
            case 'connection_established':
                console.log('Connection confirmation received from server');
                break;
            default:
                console.log(`Unhandled message type: ${data.type}`);
        }
    } catch (error) {
        console.error('Error processing WebSocket message:', error);
        console.error('Raw message data:', event.data);
    }
}

// Handle WebSocket close event
function handleRaceSocketClose(event) {
    console.log(`Race WebSocket connection closed. Code: ${event.code}, Reason: ${event.reason}`);
    updateRaceConnectionStatus('disconnected');
}

// Handle WebSocket errors
function handleRaceSocketError(error) {
    console.error('Race WebSocket error:', error);
    updateRaceConnectionStatus('disconnected');
}

// Update the connection status indicator
function updateRaceConnectionStatus(status) {
    let statusIndicator = document.getElementById('race-connection-status');
    
    // Create the status indicator if it doesn't exist
    if (!statusIndicator) {
        statusIndicator = document.createElement('div');
        statusIndicator.id = 'race-connection-status';
        statusIndicator.className = 'connecting';
        document.body.appendChild(statusIndicator);
    }
    
    // Clear existing classes
    statusIndicator.classList.remove('connected', 'disconnected', 'connecting');
    
    // Add appropriate class and text
    if (status === 'connected') {
        statusIndicator.classList.add('connected');
        statusIndicator.innerHTML = '<span>Connected ✓</span>';
    } else if (status === 'disconnected') {
        statusIndicator.classList.add('disconnected');
        statusIndicator.innerHTML = '<span>Disconnected - Reconnecting...</span>';
    } else {
        statusIndicator.classList.add('connecting');
        statusIndicator.innerHTML = '<span>Connecting...</span>';
    }
}

// Handle race started event with countdown and redirect
function handleRaceStarted(redirectUrl, message) {
    console.log('Race started with redirect URL:', redirectUrl);
    
    // Check if we're already on the questions page
    if (window.location.pathname.includes('/question/')) {
        console.log('Already on questions page, no redirect needed');
        return;
    }
    
    // Create a race started overlay if it doesn't exist
    let notification = document.getElementById('race-started-notification');
    if (!notification) {
        notification = document.createElement('div');
        notification.id = 'race-started-notification';
        notification.style.position = 'fixed';
        notification.style.top = '0';
        notification.style.left = '0';
        notification.style.width = '100%';
        notification.style.height = '100%';
        notification.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
        notification.style.zIndex = '10000';
        notification.style.display = 'flex';
        notification.style.alignItems = 'center';
        notification.style.justifyContent = 'center';
        
        const content = document.createElement('div');
        content.className = 'race-started-content';
        content.innerHTML = `
            <h2 class="race-title">Race Started!</h2>
            <p class="race-description">${message}</p>
            <div class="countdown-container">
                <div class="countdown-circle">
                    <div class="countdown-spinner"></div>
                    <span id="countdown" class="countdown-number">5</span>
                </div>
            </div>
            <p id="race-countdown">Redirecting in 5 seconds...</p>
            <p class="mt-4">
                <a href="${redirectUrl}" class="btn btn-success btn-lg">Go to Race Now</a>
            </p>
        `;
        
        notification.appendChild(content);
        document.body.appendChild(notification);
        
        // Add styles
        addRaceNotificationStyles();
    }
    
    // Show the notification
    notification.style.display = 'flex';
    
    // Start countdown
    let countdownValue = 5;
    const countdownEl = document.getElementById('countdown');
    const countdownTextEl = document.getElementById('race-countdown');
    
    if (countdownEl) {
        const countdownInterval = setInterval(() => {
            countdownValue--;
            countdownEl.textContent = countdownValue;
            
            if (countdownTextEl) {
                countdownTextEl.textContent = `Redirecting in ${countdownValue} seconds...`;
            }
            
            if (countdownValue <= 0) {
                clearInterval(countdownInterval);
                window.location.href = redirectUrl;
            }
        }, 1000);
    } else {
        // If countdown element not found, redirect immediately
        setTimeout(() => {
            window.location.href = redirectUrl;
        }, 1000);
    }
}

// Update team progress on the race page
function updateTeamProgress(data) {
    // Check if there's a team progress element
    const progressElement = document.getElementById('team-progress');
    if (!progressElement) return;
    
    // Update progress info
    if (data.current_question) {
        const currentQuestionEl = document.getElementById('current-question-number');
        if (currentQuestionEl) {
            currentQuestionEl.textContent = data.current_question;
        }
    }
    
    if (data.total_points !== undefined) {
        const pointsEl = document.getElementById('total-score');
        if (pointsEl) {
            pointsEl.textContent = data.total_points;
        }
    }
}

// Update leaderboard on the race page
function updateLeaderboard(data) {
    // Check if there's a leaderboard element
    const leaderboardElement = document.getElementById('race-leaderboard');
    if (!leaderboardElement) return;
    
    // If we have a teams array, update the leaderboard
    if (data.teams && Array.isArray(data.teams)) {
        // Sort teams by points (highest first)
        const sortedTeams = data.teams.sort((a, b) => b.points - a.points);
        
        // Clear existing leaderboard
        leaderboardElement.innerHTML = '';
        
        // Create leaderboard table
        const table = document.createElement('table');
        table.className = 'leaderboard-table';
        
        // Create header
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
        
        // Create body
        const tbody = document.createElement('tbody');
        
        // Add each team
        sortedTeams.forEach((team, index) => {
            const row = document.createElement('tr');
            row.className = index < 3 ? `top-${index + 1}` : '';
            
            // Calculate progress percentage
            const progressPercent = team.total_questions ? 
                Math.round((team.current_question / team.total_questions) * 100) : 0;
            
            row.innerHTML = `
                <td>${index + 1}</td>
                <td>${team.name}</td>
                <td>${team.points}</td>
                <td>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${progressPercent}%"></div>
                        <span class="progress-text">${progressPercent}%</span>
                    </div>
                </td>
            `;
            
            tbody.appendChild(row);
        });
        
        table.appendChild(tbody);
        leaderboardElement.appendChild(table);
    }
}

// Add styles for race notification
function addRaceNotificationStyles() {
    const existingStyle = document.getElementById('race-websocket-styles');
    if (existingStyle) return;
    
    const style = document.createElement('style');
    style.id = 'race-websocket-styles';
    style.textContent = `
        #race-connection-status {
            position: fixed;
            bottom: 10px;
            left: 10px;
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 12px;
            z-index: 9999;
        }
        
        #race-connection-status.connected {
            background-color: rgba(40, 167, 69, 0.8);
            color: white;
        }
        
        #race-connection-status.disconnected {
            background-color: rgba(220, 53, 69, 0.8);
            color: white;
        }
        
        #race-connection-status.connecting {
            background-color: rgba(255, 193, 7, 0.8);
            color: black;
        }
        
        .race-started-content {
            background-color: rgba(33, 37, 41, 0.95);
            border: 2px solid #90C83C;
            border-radius: 10px;
            padding: 40px;
            text-align: center;
            max-width: 500px;
            animation: pulse 2s infinite;
        }
        
        .race-title {
            color: #90C83C;
            font-size: 32px;
            margin-bottom: 20px;
        }
        
        .race-description {
            font-size: 18px;
            margin-bottom: 30px;
        }
        
        .countdown-container {
            display: flex;
            justify-content: center;
            margin: 30px 0;
        }
        
        .countdown-circle {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            background-color: rgba(144, 200, 60, 0.2);
            border: 3px solid #90C83C;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }
        
        .countdown-number {
            font-size: 36px;
            font-weight: bold;
            color: #90C83C;
        }
        
        .countdown-spinner {
            position: absolute;
            width: 100%;
            height: 100%;
            border-radius: 50%;
            border: 3px solid transparent;
            border-top-color: #90C83C;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(144, 200, 60, 0.4); }
            70% { box-shadow: 0 0 0 20px rgba(144, 200, 60, 0); }
            100% { box-shadow: 0 0 0 0 rgba(144, 200, 60, 0); }
        }
        
        .leaderboard-table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        
        .leaderboard-table th,
        .leaderboard-table td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .leaderboard-table th {
            background-color: rgba(33, 37, 41, 0.8);
            color: #90C83C;
            font-weight: bold;
        }
        
        .leaderboard-table .top-1 {
            background-color: rgba(255, 215, 0, 0.2);
        }
        
        .leaderboard-table .top-2 {
            background-color: rgba(192, 192, 192, 0.2);
        }
        
        .leaderboard-table .top-3 {
            background-color: rgba(205, 127, 50, 0.2);
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
    `;
    document.head.appendChild(style);
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing race WebSocket handler');
    
    // Extract race ID from page
    const pathParts = window.location.pathname.split('/');
    const raceIndex = pathParts.indexOf('race');
    if (raceIndex !== -1 && raceIndex + 1 < pathParts.length) {
        window.raceId = pathParts[raceIndex + 1];
        console.log(`Race ID extracted from URL: ${window.raceId}`);
    } else {
        console.warn('Could not extract race ID from URL path');
    }
    
    // Add styles
    addRaceNotificationStyles();
    
    // Initialize WebSocket connection
    initRaceWebSocket();
}); 