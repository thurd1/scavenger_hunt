/**
 * Lobby WebSocket Handler
 * Manages real-time updates for the lobby details page
 */

// Connection variable
let lobbyConnection = null;

// Function to initialize the WebSocket connection
function initLobbyWebSocket() {
    // Ensure we have a lobby ID to connect to
    if (!window.lobbyId) {
        console.error('Lobby ID not found in window object');
        
        // Auto-refresh after a brief delay as fallback
        setTimeout(() => {
            console.log('No lobby ID found, refreshing page...');
            window.location.reload();
        }, 5000);
        
        return null;
    }
    
    // Create WebSocket URL using WebSocketUtils
    const socketUrl = WebSocketUtils.createSocketUrl(`ws/lobby/${window.lobbyId}/`);
    console.log(`Initializing lobby WebSocket connection to: ${socketUrl}`);
    
    // Create connection using WebSocketUtils
    lobbyConnection = WebSocketUtils.createConnection(
        socketUrl,
        handleSocketMessage,
        handleSocketOpen,
        handleSocketClose,
        handleSocketError
    );
    
    return lobbyConnection;
}

// Handle WebSocket open event
function handleSocketOpen(event, socket) {
    console.log('Lobby WebSocket connection established successfully');
    
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
        statusIndicator.style.color = '#90C83C';
        dashboardBox.prepend(statusIndicator);
    }
    
    // Send an initial message to ensure the connection is working
    if (socket) {
        socket.send(JSON.stringify({
            'type': 'join',
            'lobby_id': window.lobbyId
        }));
    }
}

// Handle incoming WebSocket messages
function handleSocketMessage(event) {
    try {
        const data = JSON.parse(event.data);
        console.log('Received lobby WebSocket message:', data);
        
        // Handle different types of messages
        switch (data.type) {
            case 'team_joined':
                console.log('Team joined event received:', data.team);
                handleTeamJoined(data.team);
                break;
            case 'team_left':
                console.log('Team left event received:', data.team_id);
                handleTeamLeft(data.team_id);
                break;
            case 'team_member_joined':
                console.log('Team member joined event received:', data.team_id, data.member);
                handleTeamMemberJoined(data.team_id, data.member);
                break;
            case 'race_status_changed':
                console.log('Race status changed event received:', data.status);
                handleRaceStatusChanged(data.status);
                break;
            case 'race_started':
                console.log('Race started event received with redirect URL:', data.redirect_url);
                handleRaceStarted(data.redirect_url);
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
function handleSocketClose(event) {
    console.log(`Lobby WebSocket connection closed. Code: ${event.code}, Reason: ${event.reason}`);
    
    // Update status indicator
    const statusIndicator = document.getElementById('websocket-status');
    if (statusIndicator) {
        statusIndicator.className = 'websocket-status disconnected';
        statusIndicator.textContent = '● Live Updates Disconnected - Reconnecting...';
        statusIndicator.style.color = '#dc3545';
    }
}

// Handle WebSocket errors
function handleSocketError(error) {
    console.error('Lobby WebSocket error:', error);
    
    // Update status indicator
    const statusIndicator = document.getElementById('websocket-status');
    if (statusIndicator) {
        statusIndicator.className = 'websocket-status error';
        statusIndicator.textContent = '● Connection Error';
        statusIndicator.style.color = '#dc3545';
    }
}

// Handle a team joining the lobby
function handleTeamJoined(team) {
    console.log('Team joined lobby:', team);
    
    const teamsGrid = document.querySelector('.teams-grid');
    const noTeamsMessage = document.querySelector('.no-teams');
    
    // If there were no teams before, remove the "no teams" message
    if (noTeamsMessage) {
        noTeamsMessage.style.display = 'none';
    }
    
    // Do not add if team already exists
    if (document.querySelector(`.team-card[data-team-id="${team.id}"]`)) {
        console.log(`Team ${team.id} already in the DOM`);
        return;
    }
    
    // Create team card if teams grid exists
    if (teamsGrid) {
        const teamCard = document.createElement('div');
        teamCard.className = 'team-card animated-team-card';
        teamCard.setAttribute('data-team-id', team.id);
        
        teamCard.innerHTML = `
            <div class="team-header">
                <h3>${team.name}</h3>
                <span class="team-code">Code: ${team.code}</span>
            </div>
            <div class="team-body">
                <p><strong>Members:</strong> ${team.members ? team.members.length : 0}</p>
                <ul class="members-list">
                    ${team.members && team.members.length > 0 ? 
                        team.members.map(member => `<li>${member.role}</li>`).join('') : 
                        '<li class="no-members">No members</li>'}
                </ul>
            </div>
            <div class="team-actions">
                <a href="/team/${team.id}/" class="btn btn-view">View Team</a>
                <button class="btn btn-delete" data-team-id="${team.id}" onclick="confirmDeleteTeam('${team.id}')">Delete Team</button>
            </div>
        `;
        
        teamsGrid.appendChild(teamCard);
        
        // Update team count
        const teamCountElement = document.querySelector('.team-count');
        if (teamCountElement) {
            const currentCount = parseInt(teamCountElement.textContent) || 0;
            teamCountElement.textContent = currentCount + 1;
        }
        
        // Show notification
        showNotification(`Team "${team.name}" joined the lobby!`, 'success');
    }
}

// Handle a team leaving the lobby
function handleTeamLeft(teamId) {
    console.log('Team left lobby:', teamId);
    
    const teamCard = document.querySelector(`.team-card[data-team-id="${teamId}"]`);
    if (teamCard) {
        // Get team name for notification
        const teamName = teamCard.querySelector('.team-header h3').textContent;
        
        // Remove with animation
        teamCard.classList.add('fade-out');
        setTimeout(() => {
            teamCard.remove();
            
            // Update team count
            const teamCountElement = document.querySelector('.team-count');
            if (teamCountElement) {
                const currentCount = parseInt(teamCountElement.textContent) || 0;
                if (currentCount > 0) {
                    teamCountElement.textContent = currentCount - 1;
                }
            }
            
            // Check if there are no teams left
            const teamsGrid = document.querySelector('.teams-grid');
            if (teamsGrid && !teamsGrid.querySelector('.team-card')) {
                const noTeamsMessage = document.querySelector('.no-teams');
                if (noTeamsMessage) {
                    noTeamsMessage.style.display = 'block';
                }
            }
        }, 500);
        
        // Show notification
        showNotification(`Team "${teamName}" left the lobby`, 'warning');
    }
}

// Handle a team member joining
function handleTeamMemberJoined(teamId, member) {
    console.log('Team member joined:', teamId, member);
    
    const teamCard = document.querySelector(`.team-card[data-team-id="${teamId}"]`);
    if (teamCard) {
        const membersList = teamCard.querySelector('.members-list');
        const noMembersItem = membersList.querySelector('.no-members');
        
        // If there was a "no members" message, remove it
        if (noMembersItem) {
            noMembersItem.remove();
        }
        
        // Add the new member to the list
        const memberItem = document.createElement('li');
        memberItem.textContent = member.role;
        membersList.appendChild(memberItem);
        
        // Update member count
        const membersCountEl = teamCard.querySelector('.team-body p strong');
        if (membersCountEl && membersCountEl.nextSibling) {
            const currentText = membersCountEl.nextSibling.textContent.trim();
            const currentCount = parseInt(currentText) || 0;
            membersCountEl.nextSibling.textContent = ` ${currentCount + 1}`;
        }
        
        // Highlight the team card with animation
        teamCard.classList.add('animated-team-card');
        setTimeout(() => {
            teamCard.classList.remove('animated-team-card');
        }, 2000);
        
        // Show notification
        const teamName = teamCard.querySelector('.team-header h3').textContent;
        showNotification(`New player "${member.role}" joined team "${teamName}"`, 'info');
    }
}

// Handle race status changes
function handleRaceStatusChanged(status) {
    console.log('Race status changed:', status);
    
    const statusIndicator = document.querySelector('.status-indicator');
    
    if (statusIndicator) {
        if (status === 'active' || status === 'started') {
            statusIndicator.textContent = 'Active';
            statusIndicator.classList.remove('inactive');
            statusIndicator.classList.add('active');
            
            // Add a notification that the race has started
            const infoCard = document.querySelector('.info-card');
            if (infoCard && !document.querySelector('.race-started-alert')) {
                const alert = document.createElement('div');
                alert.className = 'alert alert-success race-started-alert';
                alert.innerHTML = '<strong>Race has started!</strong> Teams are now playing.';
                infoCard.appendChild(alert);
            }
        } else {
            statusIndicator.textContent = 'Inactive';
            statusIndicator.classList.remove('active');
            statusIndicator.classList.add('inactive');
            
            // Remove any race started alerts
            const alert = document.querySelector('.race-started-alert');
            if (alert) {
                alert.remove();
            }
        }
    }
}

// Handle race started event with countdown and redirect
function handleRaceStarted(redirectUrl) {
    console.log('Race started with redirect URL:', redirectUrl);
    
    // Show the race started notification
    const notification = document.getElementById('race-started-notification');
    if (notification) {
        notification.style.display = 'block';
        
        // Update the redirect button
        const redirectButton = document.getElementById('go-to-race-btn');
        if (redirectButton) {
            redirectButton.href = redirectUrl;
        }
        
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
    } else {
        // No notification element found, redirect immediately
        window.location.href = redirectUrl;
    }
}

// Add WebSocket-related styles
function addWebSocketStyles() {
    const style = document.createElement('style');
    style.textContent = `
        .websocket-status {
            padding: 5px 15px;
            font-size: 14px;
            margin-bottom: 15px;
            border-radius: 4px;
            display: inline-block;
        }
        
        .fade-out {
            opacity: 0;
            transform: scale(0.8);
            transition: opacity 0.5s, transform 0.5s;
        }
        
        #race-started-notification {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.8);
            z-index: 1000;
            display: flex;
            align-items: center;
            justify-content: center;
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
    `;
    document.head.appendChild(style);
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing lobby WebSocket handler');
    
    // Extract lobby ID from page
    window.lobbyId = window.location.pathname.split('/').filter(Boolean)[1];
    console.log(`Lobby ID extracted from URL: ${window.lobbyId}`);
    
    // Add WebSocket styles
    addWebSocketStyles();
    
    // Initialize WebSocket connection
    initLobbyWebSocket();
    
    // Create connection status indicator if it doesn't exist
    if (!document.getElementById('connection-status')) {
        const statusIndicator = document.createElement('div');
        statusIndicator.id = 'connection-status';
        statusIndicator.className = 'connecting';
        statusIndicator.innerHTML = '<span>Connecting...</span>';
        document.body.appendChild(statusIndicator);
    }
}); 