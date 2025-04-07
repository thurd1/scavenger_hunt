/**
 * Establish a WebSocket connection for a lobby
 * @param {number} lobbyId - The ID of the lobby to connect to
 * @returns {WebSocket} - The WebSocket connection
 */
function connectToLobbyWebsocket(lobbyId) {
    // Determine if we're using a secure connection
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/lobby/${lobbyId}/`;
    
    console.log(`Connecting to lobby WebSocket at: ${wsUrl}`);
    
    try {
        const socket = new WebSocket(wsUrl);
        
        socket.onopen = function(e) {
            console.log('Lobby WebSocket connection established');
            showMessage('Lobby WebSocket connected!', 'success');
        };
        
        socket.onmessage = function(e) {
            try {
                const data = JSON.parse(e.data);
                console.log('Lobby WebSocket message received:', data);
                
                // Handle different types of messages
                if (data.type === 'team_joined') {
                    console.log('New team joined the lobby:', data.team);
                    handleTeamJoined(data.team);
                } else if (data.type === 'race_status_changed') {
                    console.log('Race status changed:', data.status);
                    handleRaceStatusChanged(data.status);
                } else if (data.type === 'team_member_joined') {
                    console.log('New team member joined:', data.member);
                    handleTeamMemberJoined(data.member, data.team_id);
                }
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
                showMessage('Error parsing message: ' + error.message, 'error');
            }
        };
        
        socket.onclose = function(e) {
            console.log('Lobby WebSocket connection closed');
            
            // Try to reconnect after a delay
            showMessage('WebSocket disconnected. Attempting to reconnect...', 'warning');
            setTimeout(() => {
                window.lobbySocket = connectToLobbyWebsocket(lobbyId);
            }, 3000);
        };
        
        socket.onerror = function(e) {
            console.error('Lobby WebSocket error:', e);
            showMessage('WebSocket error. Check console for details.', 'error');
        };
        
        return socket;
    } catch (error) {
        console.error('Error creating WebSocket connection:', error);
        showMessage('Failed to create WebSocket: ' + error.message, 'error');
        return null;
    }
}

/**
 * Handle a team joined event
 */
function handleTeamJoined(team) {
    const teamsGrid = document.querySelector('.teams-grid');
    const noTeamsMessage = document.querySelector('.no-teams');
    
    // If there were no teams before, remove the "no teams" message
    if (noTeamsMessage) {
        noTeamsMessage.style.display = 'none';
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
        
        // Add animation effect
        setTimeout(() => {
            teamCard.style.transform = 'translateY(-5px)';
            teamCard.style.boxShadow = '0 5px 15px rgba(144, 200, 60, 0.2)';
        }, 100);
        
        // Show a notification
        showMessage(`Team "${team.name}" has joined the lobby!`, 'success');
    }
}

/**
 * Handle a race status change event
 */
function handleRaceStatusChanged(status) {
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
                
                // Make it flash to draw attention
                setInterval(() => {
                    alert.style.opacity = alert.style.opacity === '0.7' ? '1' : '0.7';
                }, 800);
            }
            
            // Show a notification
            showMessage('The race has started!', 'success');
        } else {
            statusIndicator.textContent = 'Inactive';
            statusIndicator.classList.remove('active');
            statusIndicator.classList.add('inactive');
        }
    }
}

/**
 * Handle a team member joined event
 */
function handleTeamMemberJoined(member, teamId) {
    const teamCard = document.querySelector(`.team-card[data-team-id="${teamId}"]`);
    if (teamCard) {
        const membersList = teamCard.querySelector('.members-list');
        const noMembersItem = membersList.querySelector('.no-members');
        
        // Remove "no members" message if it exists
        if (noMembersItem) {
            noMembersItem.remove();
        }
        
        // Add the new member
        const memberItem = document.createElement('li');
        memberItem.textContent = member.role;
        membersList.appendChild(memberItem);
        
        // Update member count
        const membersCount = teamCard.querySelector('.team-body p strong').nextSibling;
        const currentCount = parseInt(membersCount.textContent, 10) || 0;
        membersCount.textContent = ` ${currentCount + 1}`;
        
        // Show a notification
        showMessage(`${member.role} has joined team "${member.team_name}"!`, 'info');
    }
}

/**
 * Display a message on the screen for debugging/user feedback
 */
function showMessage(message, type = 'info') {
    // Create or reuse message container
    let container = document.getElementById('ws-message-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'ws-message-container';
        container.style.position = 'fixed';
        container.style.top = '10px';
        container.style.right = '10px';
        container.style.zIndex = '10000';
        container.style.maxWidth = '300px';
        document.body.appendChild(container);
    }
    
    // Create message element
    const msgEl = document.createElement('div');
    msgEl.style.margin = '5px';
    msgEl.style.padding = '10px';
    msgEl.style.borderRadius = '5px';
    msgEl.style.boxShadow = '0 2px 5px rgba(0,0,0,0.2)';
    msgEl.style.wordBreak = 'break-word';
    
    // Set colors based on message type
    switch (type) {
        case 'success':
            msgEl.style.backgroundColor = 'rgba(40, 167, 69, 0.9)';
            break;
        case 'warning':
            msgEl.style.backgroundColor = 'rgba(255, 193, 7, 0.9)';
            msgEl.style.color = '#000';
            break;
        case 'error':
            msgEl.style.backgroundColor = 'rgba(220, 53, 69, 0.9)';
            break;
        default: // info
            msgEl.style.backgroundColor = 'rgba(23, 162, 184, 0.9)';
    }
    
    msgEl.style.color = type === 'warning' ? '#000' : '#fff';
    msgEl.textContent = message;
    
    // Add to container
    container.appendChild(msgEl);
    
    // Remove after 5 seconds
    setTimeout(() => {
        if (container.contains(msgEl)) {
            container.removeChild(msgEl);
        }
        
        // Remove container if empty
        if (container.children.length === 0) {
            document.body.removeChild(container);
        }
    }, 5000);
}

// Initialize WebSocket connection when DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    try {
        // Get lobby ID from URL
        const lobbyMatch = window.location.pathname.match(/\/lobby\/(\d+)\//);
        if (lobbyMatch && lobbyMatch[1]) {
            const lobbyId = lobbyMatch[1];
            console.log(`Connecting to lobby with ID: ${lobbyId}`);
            window.lobbySocket = connectToLobbyWebsocket(lobbyId);
        } else {
            console.log('No lobby ID found in URL, not connecting to WebSocket');
        }
    } catch (error) {
        console.error('Error initializing WebSocket:', error);
        showMessage('Error initializing WebSocket: ' + error.message, 'error');
    }
}); 