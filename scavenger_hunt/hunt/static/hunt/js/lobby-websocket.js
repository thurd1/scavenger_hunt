/**
 * Lobby WebSocket Handler
 * Manages real-time updates for the lobby details page
 */

// Initialize with a maximum of 3 reconnect attempts
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 3;
let socket = null;

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
    
    // Set up WebSocket connection
    const wsScheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socketUrl = `${wsScheme}//${window.location.host}/ws/lobby/${window.lobbyId}/`;
    
    console.log(`Initializing lobby WebSocket connection to: ${socketUrl}`);
    
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
    console.log('Lobby WebSocket connection established successfully');
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
        statusIndicator.style.color = '#90C83C';
        dashboardBox.prepend(statusIndicator);
    }
}

// Handle incoming WebSocket messages
function handleSocketMessage(event) {
    try {
        const data = JSON.parse(event.data);
        console.log('Received lobby WebSocket message:', data);
        
        // Reset reconnect counter on successful message
        reconnectAttempts = 0;
        
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
    
    // Attempt to reconnect if not closing intentionally
    if (event.code !== 1000) {
        attemptReconnect();
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

// Attempt to reconnect with exponential backoff
function attemptReconnect() {
    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
        console.log('Maximum reconnection attempts reached. Falling back to page reload...');
        
        // Update status indicator
        const statusIndicator = document.getElementById('websocket-status');
        if (statusIndicator) {
            statusIndicator.className = 'websocket-status error';
            statusIndicator.textContent = '● Live Updates Failed - Page will refresh shortly';
            statusIndicator.style.color = '#dc3545';
        }
        
        // Reload page after a delay as fallback
        setTimeout(() => {
            window.location.reload();
        }, 5000);
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
        statusIndicator.style.color = '#ffc107';
    }
    
    setTimeout(() => {
        reconnectAttempts++;
        initLobbyWebSocket();
    }, delay);
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
        teamCard.className = 'team-card';
        teamCard.setAttribute('data-team-id', team.id);
        
        teamCard.innerHTML = `
            <div class="team-header">
                <h3>${team.name}</h3>
                <span class="team-code">Code: ${team.code}</span>
            </div>
            <div class="team-body">
                <p><strong>Members:</strong> ${team.members_count || 0}</p>
                <ul class="members-list">
                    ${team.members && team.members.length ? 
                      team.members.map(member => `<li>${member.role}</li>`).join('') : 
                      '<li class="no-members">No members</li>'}
                </ul>
            </div>
            <div class="team-actions">
                <a href="/team/${team.id}/view/" class="btn btn-view">View Team</a>
                <button class="btn btn-delete" onclick="deleteTeam(${team.id})">Delete Team</button>
            </div>
        `;
        
        teamsGrid.appendChild(teamCard);
        
        // Add animation class
        teamCard.classList.add('new-team');
        
        // Remove animation class after animation completes
        setTimeout(() => {
            teamCard.classList.remove('new-team');
        }, 3000);
    }
}

// Handle a team leaving the lobby
function handleTeamLeft(teamId) {
    console.log('Team left lobby:', teamId);
    
    const teamCard = document.querySelector(`.team-card[data-team-id="${teamId}"]`);
    if (teamCard) {
        // Add fade-out animation
        teamCard.style.transition = 'opacity 0.5s, transform 0.5s';
        teamCard.style.opacity = '0';
        teamCard.style.transform = 'scale(0.9)';
        
        // Remove the element after animation completes
        setTimeout(() => {
            if (teamCard.parentElement) {
                teamCard.parentElement.removeChild(teamCard);
            }
        }, 500);
    }
}

// Handle a new member joining a team
function handleTeamMemberJoined(teamId, member) {
    console.log('Team member joined:', teamId, member);
    
    const teamCard = document.querySelector(`.team-card[data-team-id="${teamId}"]`);
    if (teamCard) {
        const membersList = teamCard.querySelector('.members-list');
        const membersCount = teamCard.querySelector('.team-body p strong').nextSibling;
        const noMembersItem = membersList.querySelector('.no-members');
        
        // Update the members count
        const currentCount = parseInt(membersCount.textContent.trim()) || 0;
        membersCount.textContent = ` ${currentCount + 1}`;
        
        // Remove the "no members" message if it exists
        if (noMembersItem) {
            noMembersItem.remove();
        }
        
        // Add the new member to the list
        const memberItem = document.createElement('li');
        memberItem.textContent = member.role;
        memberItem.classList.add('new-member');
        membersList.appendChild(memberItem);
        
        // Highlight the new member briefly
        setTimeout(() => {
            memberItem.classList.remove('new-member');
        }, 3000);
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

// Add CSS styles for WebSocket status and animations
function addWebSocketStyles() {
    const styleElement = document.createElement('style');
    styleElement.textContent = `
        .websocket-status {
            margin-bottom: 15px;
            font-size: 14px;
            padding: 5px 10px;
            border-radius: 4px;
            display: inline-block;
        }
        
        .team-card.new-team {
            animation: fadeIn 1s;
        }
        
        .new-member {
            animation: highlight 3s;
        }
        
        @keyframes fadeIn {
            0% { opacity: 0; transform: translateY(20px); }
            100% { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes highlight {
            0% { background-color: rgba(144, 200, 60, 0.4); }
            100% { background-color: transparent; }
        }
    `;
    document.head.appendChild(styleElement);
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
});

// Initialize WebSocket when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Add styles for WebSocket status indicator
    addWebSocketStyles();
    
    console.log('DOM loaded, initializing WebSocket connection');
    
    // Wait a moment for any other scripts to set lobbyId
    setTimeout(() => {
        initLobbyWebSocket();
    }, 100);
    
    // As a fallback, manually refresh the page every 2 minutes
    // This ensures updates even if WebSockets fail silently
    setTimeout(() => {
        console.log('Periodic refresh timeout reached, reloading page');
        window.location.reload();
    }, 120000);
}); 