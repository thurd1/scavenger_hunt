/**
 * Race WebSocket Connection
 * Handles real-time communication for race events.
 */

// Function to establish WebSocket connection for a race
function connectToRaceWebsocket(raceId) {
    if (!raceId) {
        console.error('No race ID provided for WebSocket connection');
        return;
    }

    // Determine if we're using secure WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    const wsUrl = `${protocol}${window.location.host}/ws/race/${raceId}/`;

    console.log(`Connecting to race WebSocket at: ${wsUrl}`);
    
    const raceSocket = new WebSocket(wsUrl);

    raceSocket.onopen = function(e) {
        console.log('Race WebSocket connection established');
    };

    raceSocket.onmessage = function(e) {
        console.log('Race WebSocket message received:', e.data);
        
        try {
            const data = JSON.parse(e.data);
            
            // Handle different message types
            if (data.type === 'race_started') {
                console.log('Race started event received:', data);
                handleRaceStartedEvent(data);
            } else if (data.message && data.message.type === 'race_started') {
                console.log('Race started message received:', data.message);
                handleRaceStartedEvent(data.message);
            }
            
        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
        }
    };

    raceSocket.onclose = function(e) {
        console.log('Race WebSocket connection closed');
        // Attempt to reconnect after a delay
        setTimeout(function() {
            console.log('Attempting to reconnect to race WebSocket...');
            connectToRaceWebsocket(raceId);
        }, 5000);
    };

    raceSocket.onerror = function(err) {
        console.error('Race WebSocket error:', err);
    };

    return raceSocket;
}

// Function to handle race started event
function handleRaceStartedEvent(data) {
    // Show notification to user
    const notification = document.createElement('div');
    notification.className = 'race-notification';
    notification.innerHTML = `
        <div class="notification-content">
            <h3>Race has started!</h3>
            <p>You will be redirected to the questions page in <span id="countdown">5</span> seconds...</p>
            <div class="spinner"></div>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Countdown timer for redirection
    let countdown = 5;
    const countdownElement = document.getElementById('countdown');
    
    const timer = setInterval(() => {
        countdown--;
        if (countdownElement) {
            countdownElement.textContent = countdown;
        }
        
        if (countdown <= 0) {
            clearInterval(timer);
            
            // Determine redirect URL
            let redirectUrl = '';
            if (data.redirect_url) {
                redirectUrl = data.redirect_url;
            } else {
                const raceId = data.race_id || window.raceId;
                if (raceId) {
                    redirectUrl = `/race/${raceId}/questions/`;
                }
            }
            
            console.log(`Redirecting to: ${redirectUrl}`);
            
            if (redirectUrl) {
                window.location.href = redirectUrl;
            } else {
                console.error('No redirect URL available');
                // Add a direct link for user to click
                if (notification) {
                    notification.innerHTML += `
                        <p>Automatic redirect failed. <a href="/race/${data.race_id}/questions/">Click here</a> to go to the questions page.</p>
                    `;
                }
            }
        }
    }, 1000);
}

// Initialize race WebSocket if race ID is available
document.addEventListener('DOMContentLoaded', function() {
    // Check if race ID is defined in the page
    const raceId = window.raceId || document.body.getAttribute('data-race-id');
    
    if (raceId) {
        console.log(`Initializing race WebSocket for race ID: ${raceId}`);
        window.raceSocket = connectToRaceWebsocket(raceId);
    }
});

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

/**
 * Periodically check if the race has started via REST API
 */
function checkRaceStatus(raceId) {
    if (!raceId) return;
    
    console.log(`Setting up periodic race status check for race ${raceId}`);
    
    // Check immediately first
    fetchRaceStatus(raceId);
    
    // Then check every 10 seconds
    setInterval(() => {
        fetchRaceStatus(raceId);
    }, 10000);
}

/**
 * Fetch race status from server
 */
function fetchRaceStatus(raceId) {
    fetch(`/race/${raceId}/status/`)
        .then(response => response.json())
        .then(data => {
            console.log('Race status check:', data);
            if (data.started) {
                console.log('Race has started according to status check!');
                // Redirect to questions page if race has started
                window.location.href = data.redirect_url || `/race/${raceId}/questions/`;
            }
        })
        .catch(error => {
            console.error('Error checking race status:', error);
        });
}