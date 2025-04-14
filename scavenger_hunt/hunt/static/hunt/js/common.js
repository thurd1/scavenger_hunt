/**
 * Common JavaScript utility functions
 */

// Function to get CSRF cookie
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Helper function for making API requests
function makeApiRequest(url, data, method = 'POST', contentType = 'application/json') {
    return fetch(url, {
        method: method,
        headers: {
            'Content-Type': contentType,
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: contentType === 'application/json' ? JSON.stringify(data) : data
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    });
} 