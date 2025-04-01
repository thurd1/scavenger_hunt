/**
 * Establish a WebSocket connection for a race
 * @param {number} raceId - The ID of the race to connect to
 * @returns {WebSocket} - The WebSocket connection
 */
function connectToRaceWebsocket(raceId) {
    // Determine if we're using a secure connection
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/race/${raceId}/`;
    
    console.log(`Connecting to race WebSocket at: ${wsUrl}`);
    
    try {
        const socket = new WebSocket(wsUrl);
        
        socket.onopen = function(e) {
            console.log('Race WebSocket connection established');
            const statusElement = document.getElementById('connection-status');
            if (statusElement) {
                statusElement.textContent = 'Connected';
                statusElement.classList.remove('text-danger');
                statusElement.classList.add('text-success');
            }
            
            // Show connected message on screen for debugging
            showMessage('Race WebSocket connected!', 'success');
        };
        
        socket.onmessage = function(e) {
            try {
                const data = JSON.parse(e.data);
                console.log('Race WebSocket message received:', data);
                
                // Handle different types of messages
                if (data.type === 'race_started') {
                    console.log('🔥 Race started event received with data:', data);
                    
                    // Show a notification that we received the race started event
                    showMessage('Race started event received! Redirecting to questions page...', 'info');
                    
                    // Check if there's a custom handler defined in the page
                    if (typeof window.handleRaceStarted === 'function') {
                        // Use the custom handler from the page
                        console.log('Using custom race_started handler from page');
                        window.handleRaceStarted(data);
                    } else {
                        // Use the default handler in this file
                        console.log('Using default race_started handler');
                        handleRaceStartedEvent(data, data.race_id || raceId);
                    }
                }
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
                showMessage('Error parsing message: ' + error.message, 'error');
            }
        };
        
        socket.onclose = function(e) {
            console.log('Race WebSocket connection closed');
            const statusElement = document.getElementById('connection-status');
            if (statusElement) {
                statusElement.textContent = 'Disconnected';
                statusElement.classList.remove('text-success');
                statusElement.classList.add('text-danger');
            }
            
            // Try to reconnect after a delay
            showMessage('WebSocket disconnected. Attempting to reconnect...', 'warning');
            setTimeout(() => {
                window.raceSocket = connectToRaceWebsocket(raceId);
            }, 3000);
        };
        
        socket.onerror = function(e) {
            console.error('Race WebSocket error:', e);
            const statusElement = document.getElementById('connection-status');
            if (statusElement) {
                statusElement.textContent = 'Connection Error';
                statusElement.classList.remove('text-success');
                statusElement.classList.add('text-danger');
            }
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
 * Handle the race_started event
 * @param {Object} data - The event data
 * @param {number} raceId - The race ID
 */
function handleRaceStartedEvent(data, raceId) {
    // Create a visible notification that will persist
    const notification = document.createElement('div');
    notification.style.position = 'fixed';
    notification.style.top = '50%';
    notification.style.left = '50%';
    notification.style.transform = 'translate(-50%, -50%)';
    notification.style.zIndex = '10000';
    notification.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
    notification.style.color = 'white';
    notification.style.padding = '20px';
    notification.style.borderRadius = '10px';
    notification.style.textAlign = 'center';
    notification.style.maxWidth = '80%';
    notification.style.boxShadow = '0 0 20px rgba(0, 0, 0, 0.5)';
    
    // Add a spinner
    notification.innerHTML = `
        <h3 style="color: #90C83C; margin-bottom: 15px;">Race Starting!</h3>
        <p>You are being redirected to the questions page...</p>
        <div class="spinner" style="margin: 15px auto; border: 4px solid rgba(255,255,255,0.3); border-radius: 50%; border-top: 4px solid #90C83C; width: 40px; height: 40px; animation: spin 1s linear infinite;"></div>
        <p id="countdown">Redirecting in 3 seconds</p>
    `;
    
    // Add spinner animation
    const style = document.createElement('style');
    style.textContent = `
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    `;
    document.head.appendChild(style);
    
    // Add to document
    document.body.appendChild(notification);
    
    // Get the redirect URL
    let redirectUrl;
    if (data.redirect_url) {
        redirectUrl = data.redirect_url;
        console.log(`Using redirect URL from event: ${redirectUrl}`);
    } else {
        // Construct it from the race ID
        redirectUrl = `/race/${raceId}/questions/`;
        console.log(`Using constructed URL: ${redirectUrl}`);
    }
    
    // Create a direct link that users can click if auto-redirect fails
    const directLink = document.createElement('a');
    directLink.href = redirectUrl;
    directLink.textContent = 'Click here if you are not redirected automatically';
    directLink.style.color = '#90C83C';
    directLink.style.display = 'block';
    directLink.style.marginTop = '15px';
    directLink.style.textDecoration = 'underline';
    notification.appendChild(directLink);
    
    // Countdown for redirect
    let countdown = 3;
    const countdownElement = document.getElementById('countdown');
    const countdownInterval = setInterval(() => {
        countdown--;
        if (countdownElement) {
            countdownElement.textContent = `Redirecting in ${countdown} seconds`;
        }
        
        if (countdown <= 0) {
            clearInterval(countdownInterval);
            console.log('🔄 Redirecting to questions page:', redirectUrl);
            window.location.href = redirectUrl;
        }
    }, 1000);
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
        // Get race ID with more aggressive fallbacks to ensure connection
        let raceId = findRaceId();
        
        if (raceId) {
            console.log(`Connecting to race with ID: ${raceId}`);
            window.raceSocket = connectToRaceWebsocket(raceId);
            
            // Set up manual check for race status
            checkRaceStatus(raceId);
        } else {
            console.log('No race ID found, not connecting to WebSocket');
        }
    } catch (error) {
        console.error('Error initializing WebSocket:', error);
        showMessage('Error initializing WebSocket: ' + error.message, 'error');
    }
});

/**
 * Aggressively look for a race ID from various sources
 */
function findRaceId() {
    // Try multiple ways to find the race ID
    
    // 1. Check data attribute on body
    const bodyRaceId = document.body.getAttribute('data-race-id');
    if (bodyRaceId) {
        console.log('Found race ID from body data attribute:', bodyRaceId);
        return bodyRaceId;
    }
    
    // 2. Check race detail URL
    const raceDetailMatch = window.location.pathname.match(/\/race\/(\d+)\/detail\//);
    if (raceDetailMatch && raceDetailMatch[1]) {
        console.log('Found race ID from race detail URL:', raceDetailMatch[1]);
        return raceDetailMatch[1];
    }
    
    // 3. Check race questions URL
    const raceQuestionsMatch = window.location.pathname.match(/\/race\/(\d+)\/questions\//);
    if (raceQuestionsMatch && raceQuestionsMatch[1]) {
        console.log('Found race ID from race questions URL:', raceQuestionsMatch[1]);
        return raceQuestionsMatch[1];
    }
    
    // 4. Check if we have race ID as URL parameter
    const urlParams = new URLSearchParams(window.location.search);
    const raceIdParam = urlParams.get('race_id');
    if (raceIdParam) {
        console.log('Found race ID from URL parameter:', raceIdParam);
        return raceIdParam;
    }
    
    // 5. Check if we're in a team view to get race ID from API
    const teamMatch = window.location.pathname.match(/\/team\/(\d+)\/view\//);
    if (teamMatch && teamMatch[1]) {
        const teamId = teamMatch[1];
        console.log('Found team ID from URL:', teamId);
        
        // Make a synchronous request to get the race ID for this team
        let raceId = null;
        try {
            const xhr = new XMLHttpRequest();
            xhr.open('GET', `/api/team/${teamId}/race/`, false); // Synchronous request
            xhr.send();
            
            if (xhr.status === 200) {
                const response = JSON.parse(xhr.responseText);
                if (response.success && response.race_id) {
                    raceId = response.race_id;
                    console.log(`Found race ID ${raceId} for team ${teamId} from API`);
                }
            }
        } catch (e) {
            console.error('Error getting race ID for team:', e);
        }
        
        if (raceId) {
            return raceId;
        }
    }
    
    // 6. Check if we're in the race detail page which might have the ID in the HTML
    const raceIdElement = document.getElementById('race-id');
    if (raceIdElement && raceIdElement.value) {
        console.log('Found race ID from hidden input:', raceIdElement.value);
        return raceIdElement.value;
    }
    
    // 7. Look for debug info section
    const debugInfoElement = document.querySelector('.debug-info');
    if (debugInfoElement) {
        const raceIdText = debugInfoElement.textContent;
        const raceIdMatch = raceIdText.match(/Race ID: (\d+)/);
        if (raceIdMatch && raceIdMatch[1]) {
            console.log('Found race ID from debug info:', raceIdMatch[1]);
            return raceIdMatch[1];
        }
    }
    
    console.warn('Could not find race ID');
    return null;
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
                window.location.href = `/race/${raceId}/questions/`;
            }
        })
        .catch(error => {
            console.error('Error checking race status:', error);
        });
}