from django.contrib.messages import get_messages
import re

def player_name(request):
    return {'player_name': request.session.get('player_name')}

def filter_team_creation_messages(request):
    # Get all messages
    storage = get_messages(request)
    filtered_messages = []
    
    # Filter out team creation messages
    for message in storage:
        # If the message starts with "Team created! Your team code is:", don't add it to filtered_messages
        if not re.match(r'^Team created! Your team code is:', str(message)):
            filtered_messages.append(message)
    
    # Return the filtered messages
    return {'filtered_messages': filtered_messages} 