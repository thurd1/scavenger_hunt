from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import logging

from .models import Team, TeamMember, Lobby, Race, Zone, Question

logger = logging.getLogger(__name__)

def save_player_name(request):
    """Save the player name in the session."""
    if request.method == 'POST':
        player_name = request.POST.get('player_name')
        if player_name:
            request.session['player_name'] = player_name
            return JsonResponse({'success': True})
    return JsonResponse({'success': False})

def join_game_session(request):
    """Handle joining a game session."""
    if request.method == 'POST':
        lobby_code = request.POST.get('lobby_code')
        try:
            lobby = Lobby.objects.get(code=lobby_code)
            request.session['lobby_code'] = lobby_code
            return redirect('join_team')
        except Lobby.DoesNotExist:
            messages.error(request, 'Invalid lobby code')
            return redirect('join_game_session')
    
    return render(request, 'hunt/join_game_session.html')

def join_team(request):
    """Render the join team page with available teams and forms to join or create teams."""
    # Get lobby code from session
    lobby_code = request.session.get('lobby_code')
    if not lobby_code:
        return redirect('join_game_session')
        
    try:
        # Get the lobby and its teams
        lobby = Lobby.objects.get(code=lobby_code)
        teams = lobby.teams.all().prefetch_related('members')
        
        # Get player name from session
        player_name = request.session.get('player_name', '')
        
        return render(request, 'hunt/join_team.html', {
            'teams': teams,
            'player_name': player_name,
            'lobby': lobby
        })
    except Lobby.DoesNotExist:
        messages.error(request, 'Invalid lobby code')
        return redirect('join_game_session')

def join_existing_team(request):
    """Join an existing team."""
    if request.method == 'POST':
        team_id = request.POST.get('team_id')
        player_name = request.session.get('player_name')
        
        if not player_name:
            messages.error(request, 'Please enter your name first.')
            return redirect('join_team')
            
        try:
            team = Team.objects.get(id=team_id)
            
            # Check if this player is already a member
            existing_member = TeamMember.objects.filter(
                team=team,
                role=player_name
            ).first()
            
            if not existing_member:
                team_member = TeamMember.objects.create(
                    team=team,
                    role=player_name
                )
                
            request.session['team_id'] = team.id
            messages.success(request, f'Successfully joined team {team.name}!')
            return redirect('view_team', team_id=team.id)
            
        except Team.DoesNotExist:
            messages.error(request, 'Team not found.')
            return redirect('join_team')
    
    return redirect('join_team')

@login_required
def start_race(request, lobby_id):
    """Start a race in a lobby and redirect to the first question."""
    try:
        data = json.loads(request.body) if request.body else {}
        race_id = data.get('race_id')
        
        lobby = get_object_or_404(Lobby, id=lobby_id)
        race = get_object_or_404(Race, id=race_id) if race_id else lobby.race

        if not race:
            return JsonResponse({
                'success': False,
                'error': 'No race selected.'
            })

        # Update lobby with race info
        lobby.race = race
        lobby.hunt_started = True
        lobby.start_time = timezone.now()
        lobby.save()

        # Get the first zone and question
        first_zone = race.zones.first()
        if not first_zone:
            return JsonResponse({
                'success': False,
                'error': 'No zones found in this race.'
            })
        
        first_question = first_zone.questions.first()
        if not first_question:
            return JsonResponse({
                'success': False,
                'error': 'No questions found in the first zone.'
            })
        
        # Get the URL for the first question
        redirect_url = f"/studentQuestion/{lobby_id}/{first_question.id}/"
        
        # Notify all connected clients through WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'lobby_{lobby_id}',
            {
                'type': 'race_started',
                'redirect_url': redirect_url
            }
        )
        
        return JsonResponse({
            'success': True,
            'redirect_url': redirect_url
        })
        
    except Exception as e:
        logger.error(f"Error starting race: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

def student_question(request, lobby_id, question_id):
    """Display a question to the student."""
    lobby = get_object_or_404(Lobby, id=lobby_id)
    question = get_object_or_404(Question, id=question_id)
    
    if not lobby.hunt_started or not lobby.race:
        messages.error(request, 'Race has not started yet.')
        return redirect('lobby_details', lobby_id=lobby_id)
    
    # Check if time is up
    time_elapsed = timezone.now() - lobby.start_time
    if time_elapsed.total_seconds() > (lobby.race.time_limit_minutes * 60):
        messages.error(request, 'Time is up!')
        return redirect('lobby_details', lobby_id=lobby_id)
    
    context = {
        'lobby': lobby,
        'question': question,
        'time_limit_minutes': lobby.race.time_limit_minutes,
        'start_time': lobby.start_time.isoformat()
    }
    return render(request, 'hunt/studentQuestion.html', context) 