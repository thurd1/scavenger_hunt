# Fix for WebSocket and API Issues

## 1. Add RaceUpdatesConsumer to hunt/routing.py

Make sure this route exists in `hunt/routing.py`:

```python
re_path(r'ws/race-updates/(?P<race_id>\w+)/(?P<team_code>\w+)/$', consumers.RaceUpdatesConsumer.as_asgi()),
```

## 2. Add additional URL pattern for question_answers_api

Add this URL pattern to `hunt/urls.py`:

```python
path('api/race/<int:race_id>/question-answers/<str:team_code>/', views.question_answers_api, name='question_answers_specific'),
```

## 3. Update question_answers_api function in hunt/views.py

Replace the function with this updated version that handles both URL parameter formats:

```python
@csrf_exempt
def question_answers_api(request, race_id=None, team_code=None):
    """API endpoint to get a team's answers for a race"""
    # Debug logging
    print(f"question_answers_api called with method={request.method}")
    print(f"URL params: race_id={race_id}, team_code={team_code}")
    print(f"GET params: {request.GET}")
    
    # Check if method is GET
    if request.method != 'GET':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)
    
    # Get parameters from request if not provided in URL
    if team_code is None:
        team_code = request.GET.get('team_code')
    if race_id is None:
        race_id = request.GET.get('race_id')
    
    print(f"Final params: race_id={race_id}, team_code={team_code}")
    
    if not team_code or not race_id:
        return JsonResponse({
            'success': False, 
            'error': 'Missing required parameters. Both team_code and race_id are required.'
        }, status=400)
    
    try:
        # Get the team and race
        team = Team.objects.get(code=team_code)
        race = Race.objects.get(id=race_id)
        
        # Get all answers for this team in this race
        answers = TeamAnswer.objects.filter(
            team=team,
            question__zone__race=race
        ).select_related('question')
        
        # Format the answers data
        answers_data = {}
        for answer in answers:
            answers_data[answer.question.id] = {
                'attempts': answer.attempts,
                'points_awarded': answer.points_awarded,
                'answered_correctly': answer.answered_correctly,
                'photo_uploaded': answer.photo_uploaded,
                'question_text': answer.question.text[:50] + '...'  # Include a snippet for debugging
            }
        
        # Calculate total score
        total_score = answers.filter(answered_correctly=True).aggregate(
            total=Sum('points_awarded'))['total'] or 0
        
        # Get team race progress
        progress = TeamRaceProgress.objects.filter(team=team, race=race).first()
        current_question_index = progress.current_question_index if progress else 0
        
        return JsonResponse({
            'success': True,
            'answers': answers_data,
            'total_score': total_score,
            'current_question_index': current_question_index,
            'team_code': team_code,
            'race_id': race_id
        })
        
    except Team.DoesNotExist:
        print(f"Team not found: {team_code}")
        return JsonResponse({'success': False, 'error': f'Team with code {team_code} not found'}, status=404)
    except Race.DoesNotExist:
        print(f"Race not found: {race_id}")
        return JsonResponse({'success': False, 'error': f'Race with ID {race_id} not found'}, status=404)
    except Exception as e:
        # Log the error
        print(f"Error in question_answers_api: {str(e)}")
        logger.error(f"Error in question_answers_api: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
```

## 4. Update manage_daphne.py

Update manage_daphne.py to include the RaceUpdatesConsumer:

```python
import os
import sys
import django
from django.core.asgi import get_asgi_application

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scavenger_hunt.settings')
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from hunt.consumers import TeamConsumer, AvailableTeamsConsumer, LobbyConsumer, RaceConsumer, LeaderboardConsumer, RaceUpdatesConsumer

# Import the websocket patterns directly from the routing module
from hunt.routing import websocket_urlpatterns

# Print out the available WebSocket routes for debugging
print("WebSocket routes:")
for pattern in websocket_urlpatterns:
    print(f" - {pattern.pattern}")

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                websocket_urlpatterns
            )
        )
    ),
})

if __name__ == "__main__":
    from daphne.server import Server
    from daphne.endpoints import build_endpoint_description_strings

    print("Starting Daphne server...")
    print("Settings module:", os.environ['DJANGO_SETTINGS_MODULE'])
    
    Server(
        application=application,
        endpoints=build_endpoint_description_strings(host="0.0.0.0", port=8000),
    ).run()
```

## 5. After making these changes:

1. Restart the Daphne server by stopping the current process and running:
   ```
   python manage_daphne.py
   ```

2. Verify that the WebSocket routes are printed correctly in the console output

These changes will address:
1. The WebSocket connection failures
2. The 404 errors for the question_answers API
3. Add fallback mechanisms in the frontend code for when server connections fail 