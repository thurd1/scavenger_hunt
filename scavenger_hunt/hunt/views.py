from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import Team, Riddle, Submission, Lobby, TeamMember, Race, Zone, Question, TeamAnswer, TeamRaceProgress, TeamProgress
from django.http import JsonResponse
from .forms import JoinLobbyForm, LobbyForm, TeamForm
from django.http import HttpResponse
from django.contrib.auth.forms import UserCreationForm
from django.views.generic import DetailView
from django.db.models import Count
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseRedirect
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync  
import logging
from django.views.decorators.http import require_POST, require_http_methods
from django.utils import timezone
import random
import string
import json
from django.core.serializers.json import DjangoJSONEncoder
from datetime import datetime, timedelta
from django.db import models
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
import time
import uuid

logger = logging.getLogger(__name__)

@login_required
def create_lobby(request):
    if request.method == 'POST':
        race_id = request.POST.get('race')
        
        # Get the code from the form if provided
        code = request.POST.get('code')
        if not code:
            # Generate a unique code
            while True:
                code = generate_lobby_code()
                if not Lobby.objects.filter(code=code).exists():
                    break
        
        try:
            race = Race.objects.get(id=race_id)
            lobby = Lobby.objects.create(
                code=code,
                race=race,
                is_active=True
            )
            return redirect('lobby_details', lobby_id=lobby.id)
        except Race.DoesNotExist:
            messages.error(request, 'Selected race does not exist.')
    
    # Get all active races
    races = Race.objects.filter(is_active=True)
    
    # Generate a code for the form
    generated_code = generate_lobby_code()
    
    return render(request, 'hunt/create_lobby.html', {
        'races': races,
        'generated_code': generated_code
    })

@login_required
def lobby_details(request, lobby_id):
    """
    View to display lobby details and teams.
    Optimized to ensure fresh data on each request.
    """
    try:
        # Get lobby with prefetched teams and members to reduce DB queries
        lobby = Lobby.objects.prefetch_related(
            'teams', 
            'teams__members'
        ).get(id=lobby_id)
        
        # Log access for debugging
        logger.info(f"User {request.user.username} accessed lobby details for {lobby.name} ({lobby_id})")
        
        # Mark as accessed to help with debugging
        lobby.last_accessed = timezone.now()
        lobby.save(update_fields=['last_accessed'])
        
        # Add a timestamp to prevent browser caching
        response = render(request, 'hunt/lobby_details.html', {
            'lobby': lobby,
            'timestamp': timezone.now().timestamp(),
        })
        
        # Set cache control headers to prevent caching
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        
        return response
        
    except Lobby.DoesNotExist:
        messages.error(request, "Lobby not found")
        return redirect('manage_lobbies')
    except Exception as e:
        logger.error(f"Error in lobby_details view: {str(e)}")
        messages.error(request, "An error occurred while loading the lobby")
        return redirect('manage_lobbies')

@login_required
def start_race(request, lobby_id):
    if request.method == 'POST':
        try:
            lobby = get_object_or_404(Lobby, id=lobby_id)
            
            # Validate user permissions (must be leader/admin)
            if not request.user.is_authenticated:
                return JsonResponse({'success': False, 'error': 'Authentication required'})
            
            # Update lobby state
            lobby.hunt_started = True
            lobby.start_time = timezone.now()
            lobby.save()
            
            # Get the race
            race = lobby.race
            if not race:
                return JsonResponse({'success': False, 'error': 'No race assigned to this lobby'})
            
            # Build the redirect URL for participants
            redirect_url = reverse('race_questions', kwargs={'race_id': race.id})
            
            # Notify all connected clients through WebSocket
            channel_layer = get_channel_layer()
            
            # Send to lobby channel
            async_to_sync(channel_layer.group_send)(
                f'lobby_{lobby_id}',
                {
                    'type': 'race_started',
                    'redirect_url': redirect_url
                }
            )
            
            # Also send to race channel
            async_to_sync(channel_layer.group_send)(
                f'race_{race.id}',
                {
                    'type': 'race_started',
                    'redirect_url': redirect_url
                }
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Race started successfully',
                'redirect_url': redirect_url
            })
            
        except Exception as e:
            logger.error(f"Error starting race: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@require_POST
def notify_race_started(request, lobby_id):
    """
    Extra endpoint to manually trigger race started notifications
    in case the WebSocket notifications from the original start_race call fail
    """
    try:
        lobby = get_object_or_404(Lobby, id=lobby_id)
        
        # Check if the race has actually started
        if not lobby.hunt_started:
            return JsonResponse({'success': False, 'error': 'Race has not been started yet'})
        
        # Get the race
        race = lobby.race
        if not race:
            return JsonResponse({'success': False, 'error': 'No race assigned to this lobby'})
        
        # Build the redirect URL for participants
        redirect_url = reverse('race_questions', kwargs={'race_id': race.id})
        
        # Get channel layer and send notifications again
        channel_layer = get_channel_layer()
        
        # Try multiple times to ensure delivery
        for _ in range(3):
            try:
                # Send to lobby channel
                async_to_sync(channel_layer.group_send)(
                    f'lobby_{lobby_id}',
                    {
                        'type': 'race_started',
                        'redirect_url': redirect_url
                    }
                )
                
                # Also send to race channel
                async_to_sync(channel_layer.group_send)(
                    f'race_{race.id}',
                    {
                        'type': 'race_started',
                        'redirect_url': redirect_url
                    }
                )
                
                # Small delay between attempts
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Error in notification attempt: {e}")
        
        return JsonResponse({
            'success': True,
            'message': 'Notifications sent successfully',
            'redirect_url': redirect_url
        })
        
    except Exception as e:
        logger.error(f"Error in notify_race_started: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

class LobbyDetailsView(DetailView):
    model = Lobby
    template_name = 'hunt/lobby_details.html'
    context_object_name = 'lobby'

def join_team(request, team_id=None):
    # This function can be called in multiple ways:
    # 1. Without team_id - for choosing a team from a list
    # 2. With team_id - for joining a specific team

    # Check if we have a player name in the session
    player_name = request.session.get('player_name')
    
    # If no player name, try to get it from POST data
    if not player_name and request.method == 'POST':
        player_name = request.POST.get('player_name')
        if player_name:
            request.session['player_name'] = player_name
            request.session.modified = True
            logger.info(f"Saved player name to session: {player_name}")

    # Handle joining a specific team
    if team_id and request.method == 'POST':
        try:
            team = get_object_or_404(Team, id=team_id)
            logger.info(f"Attempting to join team: {team.name}")

            # If player has a name but no team, create the team member
            if player_name:
                # Check if player already has a membership in any team
                existing_team_memberships = TeamMember.objects.filter(role=player_name)
                
                # Delete any existing memberships to prevent one player in multiple teams
                if existing_team_memberships.exists():
                    logger.info(f"Removing player {player_name} from {existing_team_memberships.count()} other teams")
                    existing_team_memberships.delete()
                
                # Check if this player is already in this team
                if not TeamMember.objects.filter(team=team, role=player_name).exists():
                    # Add player to team
                    team_member = TeamMember.objects.create(
                        team=team,
                        role=player_name
                    )
                    
                    # Update session
                    request.session['team_member_id'] = team_member.id
                    request.session['team_role'] = player_name
                    request.session['team_id'] = team.id
                    request.session.modified = True
                    
                    # Log the join
                    logger.info(f"Player {player_name} joined team {team.name}")
                    
                    # Broadcast the update
                    try:
                        channel_layer = get_channel_layer()
                        
                        # Send update to team channel
                        async_to_sync(channel_layer.group_send)(
                            f'team_{team.id}',
                            {
                                'type': 'team_member_joined',
                                'member': player_name
                            }
                        )
                        
                        # Also send to any connected lobbies
                        for lobby in team.participating_lobbies.all():
                            async_to_sync(channel_layer.group_send)(
                                f'lobby_{lobby.id}',
                                {
                                    'type': 'team_member_joined',
                                    'member': {
                                        'role': player_name,
                                    },
                                    'team_id': team.id,
                                    'team_name': team.name
                                }
                            )
                    except Exception as e:
                        logger.error(f"Error broadcasting team update: {str(e)}")
                else:
                    # Player is already in this team, just update session
                    team_member = TeamMember.objects.get(team=team, role=player_name)
                    request.session['team_member_id'] = team_member.id
                    request.session['team_role'] = player_name
                    request.session['team_id'] = team.id
                    request.session.modified = True
                    logger.info(f"Player {player_name} was already in team {team.name}, updated session")
                
                # Redirect to the team page
                return redirect('view_team', team_id=team.id)
            else:
                # If no player name, redirect to team selection with a message
                messages.error(request, 'Please enter your name to join a team.')
                return redirect('join_team')
        except Exception as e:
            logger.error(f"Error joining team: {str(e)}")
            messages.error(request, f"Error joining team: {str(e)}")
            return redirect('join_team')

    # If not joining a specific team, show the team selection page
    teams = []
    lobby_code = request.session.get('lobby_code')
    
    # If we have a lobby code, get all teams for that lobby
    if lobby_code:
        try:
            lobby = Lobby.objects.filter(code=lobby_code).first()
            if lobby:
                teams = lobby.teams.all()
                logger.info(f"Found {teams.count()} teams for lobby {lobby_code}")
        except Exception as e:
            logger.error(f"Error finding teams for lobby {lobby_code}: {str(e)}")
    
    context = {
        'teams': teams,
        'lobby_code': lobby_code,
        'player_name': player_name,
    }
    
    return render(request, 'hunt/join_team.html', context)

def generate_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def home(request):
    print("Home view accessed")
    if request.method == 'POST':
        code = request.POST.get('code') or request.POST.get('lobby_code')
        print(f"Received code: {code}")
        
        if not code:
            print("No code received in POST request")
            return render(request, 'hunt/join_game_session.html', {'error': 'Please enter a game code.'})
            
        try:
            lobby = Lobby.objects.filter(code=code).first()
            if lobby is None:
                print(f"No lobby found with code: {code}")
                return render(request, 'hunt/join_game_session.html', {'error': 'Invalid lobby code. Please try again.'})
            
            if not lobby.is_active:
                print(f"Lobby found but inactive: {lobby.name}")
                return render(request, 'hunt/join_game_session.html', {'error': 'This lobby is no longer active.'})
            
            print(f"Found active lobby: {lobby.name}")
            request.session['lobby_code'] = code
            return render(request, 'hunt/team_options.html', {'lobby': lobby})
            
        except Exception as e:
            print(f"Error looking up lobby: {str(e)}")
            return render(request, 'hunt/join_game_session.html', {'error': 'An error occurred. Please try again.'})
    return render(request, 'hunt/join_game_session.html')

def user_login(request):
    print("Login view accessed")
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('leader_dashboard')
        else:
            return render(request, 'hunt/login.html', {
                'error': 'Invalid credentials',
                'form': {'username': username}
            })
    return render(request, 'hunt/login.html')

def user_logout(request):
    logout(request)
    return redirect('login')

def join_game_session(request):
    if request.method == 'POST':
        lobby_code = request.POST.get('lobby_code')
        try:
            lobby = Lobby.objects.get(code=lobby_code, is_active=True)
            request.session['lobby_code'] = lobby_code
            return render(request, 'hunt/team_options.html', {'lobby': lobby})
        except Lobby.DoesNotExist:
            messages.error(request, 'Invalid lobby code. Please try again.')
    return render(request, 'hunt/join_game_session.html')

def save_player_name(request):
    if request.method == 'POST':
        player_name = request.POST.get('player_name')
        print(f"Attempting to save player name: {player_name}")  # Debug print
        
        if player_name:
            request.session['player_name'] = player_name
            request.session.modified = True
            print(f"Player name saved in session: {request.session.get('player_name')}")  # Debug print
        
            # For AJAX requests, return JSON response
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'player_name': player_name})
        
            # If not AJAX and we have a lobby_code, render team_options
            lobby_code = request.session.get('lobby_code')
            if lobby_code:
                try:
                    lobby = Lobby.objects.get(code=lobby_code)
                    return render(request, 'hunt/team_options.html', {'lobby': lobby})
                except Lobby.DoesNotExist:
                    # Lobby not found, redirect to join_game_session
                    pass
        
        # If we got here, either no player_name was provided, or no valid lobby_code in session
        print("No player name provided or lobby code missing")  # Debug print
    
    # Default fallback
    return redirect('join_game_session')

def broadcast_team_update(team_id):
    """Send team update to websocket channel"""
    channel_layer = get_channel_layer()
    team = Team.objects.prefetch_related('members').get(id=team_id)
    members = list(team.members.values_list('role', flat=True))
    
    async_to_sync(channel_layer.group_send)(
        f'team_{team_id}',
        {
            'type': 'team_update',
            'members': members
        }
    )

def get_lobby_by_code(request):
    """API endpoint to get a lobby by its code"""
    code = request.GET.get('code')
    if not code:
        return JsonResponse({'success': False, 'error': 'No code provided'})
    
    try:
        lobby = Lobby.objects.get(code=code)
        return JsonResponse({
            'success': True,
            'lobby_id': lobby.id,
            'lobby_name': lobby.name
        })
    except Lobby.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Lobby not found'})

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'hunt/register.html', {'form': form})

def register_team(request):
    return render(request, 'hunt/register_team.html')

def riddle_list(request):
    return render(request, 'hunt/riddle_list.html')

def riddle_detail(request):
    return render(request, 'hunt/riddle_list.html')

def team_list(request):
    teams = Team.objects.all().prefetch_related('members')
    return render(request, 'hunt/team_list.html', {'teams': teams})

def assign_riddles(request):
    return HttpResponse("Riddles. wow.")

def leaderboard(request):
    """
    Display the leaderboard for all races.
    """
    teams = []
    
    # Debug logging
    logger.info("Leaderboard view accessed")
    
    # Get teams with their progress data
    team_race_progress_list = TeamRaceProgress.objects.select_related('team', 'race').all()
    logger.info(f"Found {team_race_progress_list.count()} team race progress records")
    
    # Organize teams by their total scores
    for team_progress in team_race_progress_list:
        team = team_progress.team
        race = team_progress.race
        if team:
            # Get the lobby for this team that's associated with the race
            lobby = Lobby.objects.filter(teams=team, race=race).first()
            lobby_id = lobby.id if lobby else None
            lobby_name = race.name if race else 'Unknown Race'
            
            logger.debug(f"Team: {team.name}, Score: {team_progress.total_points}, Race: {race.name if race else 'None'}, Lobby ID: {lobby_id}")
            
            teams.append({
                'id': team.id,
                'name': team.name,
                'score': team_progress.total_points,
                'lobby_id': lobby_id,
                'lobby_name': lobby_name
            })
    
    # Sort teams by score (highest first)
    teams.sort(key=lambda x: x['score'], reverse=True)
    
    # Get all active lobbies for the selector
    lobbies = Lobby.objects.filter(is_active=True).select_related('race')
    logger.info(f"Found {lobbies.count()} active lobbies")
    
    context = {
        'teams': teams,
        'lobbies': lobbies
    }
    
    return render(request, 'hunt/leaderboard.html', context)

@csrf_exempt
def leaderboard_data_api(request):
    """API endpoint to get leaderboard data"""
    try:
        lobby_filter = request.GET.get('lobby')
        
        teams = []
        if not lobby_filter or lobby_filter == 'all':
            # Get all teams with their progress data
            team_race_progress_list = TeamRaceProgress.objects.select_related('team', 'race').all()
        else:
            # Filter to specific lobby
            try:
                lobby = Lobby.objects.get(id=lobby_filter)
                race = lobby.race
                if not race:
                    return JsonResponse({
                        'success': False,
                        'error': 'Selected lobby has no race assigned'
                    })
                team_race_progress_list = TeamRaceProgress.objects.filter(
                    race=race,
                    team__in=lobby.teams.all()
                ).select_related('team', 'race')
            except Lobby.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Lobby not found'
                })
        
        # Organize teams by their total scores
        for team_progress in team_race_progress_list:
            team = team_progress.team
            race = team_progress.race
            if team:
                # Get the lobby for this team that's associated with the race
                lobby = Lobby.objects.filter(teams=team, race=race).first()
                lobby_id = lobby.id if lobby else None
                lobby_name = race.name if race else 'Unknown Race'
                
                # Ensure we're using a valid team name (not an ID or object reference)
                # This fixes the "Team: 30" display issue
                team_name = team.name
                if not team_name or team_name == "None" or not isinstance(team_name, str):
                    team_name = f"Team {team.id}"
                
                teams.append({
                    'id': team.id,
                    'name': team_name,
                    'team_name': team_name,  # Add backup field for the client-side fix
                    'score': team_progress.total_points,
                    'lobby_id': str(lobby_id) if lobby_id else '',
                    'lobby_name': lobby_name
                })
        
        # Sort teams by score (highest first)
        teams.sort(key=lambda x: x['score'], reverse=True)
        
        return JsonResponse({
            'success': True,
            'teams': teams
        })
    
    except Exception as e:
        logger.error(f"Error retrieving leaderboard data: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

def team_details(request, team_id):
    team = Team.objects.get(id=team_id)
    return render(request, 'hunt/team_details.html', {'team': team})

@login_required
def dashboard(request):
    teams = Team.objects.all()
    return render(request, "hunt/dashboard.html", {"teams": teams})

@login_required
def team_detail(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    riddles = Riddle.objects.filter(team=team)
    return render(request, "hunt/team_detail.html", {"team": team, "riddles": riddles})

@login_required
def submit_answer(request, riddle_id):
    if request.method == "POST":
        riddle = get_object_or_404(Riddle, id=riddle_id)
        answer = request.POST.get("answer")
        is_correct = answer.strip().lower() == riddle.answer.strip().lower()
        Submission.objects.create(riddle=riddle, is_correct=is_correct)
        return JsonResponse({"correct": is_correct})
    return JsonResponse({"error": "Invalid request"}, status=400)

def create_team(request, lobby_id):
    lobby = get_object_or_404(Lobby, id=lobby_id)
    
    # Ensure we have a player name in session
    player_name = request.session.get('player_name')
    if not player_name:
        messages.error(request, "Please set your player name first.")
        return redirect('join_game_session')
    
    if request.method == 'POST':
        form = TeamForm(request.POST)
        if form.is_valid():
            team = form.save()
            lobby.teams.add(team)
            
            # Create a team member for the creator - removed name field
            team_member = TeamMember.objects.create(
                team=team,
                role=player_name
            )
            print(f"Created team member: {player_name} for team {team.name}")
            
            # Store team info in session
            request.session['team_id'] = team.id
            messages.success(request, f'Team created! Your team code is: {team.code}')
            return redirect('view_team', team_id=team.id)
    else:
        form = TeamForm()
    
    return render(request, 'hunt/create_team.html', {
        'form': form,
        'lobby': lobby,
        'player_name': player_name
    })

def team_dashboard(request, team_id):
    team = get_object_or_404(Team.objects.prefetch_related('participating_lobbies', 'members'), id=team_id)
    members = list(team.members.all())
    
    # Prepare members data for JSON
    members_data = [{'id': member.id, 'role': member.role} for member in members]
    
    context = {
        'team': team,
        'members': members,
        'members_json': json.dumps(members_data, cls=DjangoJSONEncoder)
    }
    return render(request, 'hunt/team_dashboard.html', context)

@login_required
def leader_dashboard(request):
    return render(request, 'hunt/leader_dashboard.html')

@login_required
def manage_lobbies(request):
    lobbies = Lobby.objects.all().order_by('-created_at')
    return render(request, 'hunt/manage_lobbies.html', {'lobbies': lobbies})

@login_required
def toggle_lobby(request, lobby_id):
    if request.method == 'POST':
        lobby = get_object_or_404(Lobby, id=lobby_id)
        lobby.is_active = not lobby.is_active
        lobby.save()
        messages.success(request, f'Lobby "{lobby.name}" has been {"activated" if lobby.is_active else "deactivated"}.')
    return redirect('manage_lobbies')

@require_POST
def delete_lobby(request, lobby_id):
    """Delete a lobby and all teams associated with it"""
    try:
        lobby = Lobby.objects.get(id=lobby_id)
        
        # Get all teams that are only in this lobby and no other lobbies
        teams_to_delete = []
        for team in lobby.teams.all():
            # Check if this team is part of any other lobbies
            other_lobbies_count = team.participating_lobbies.exclude(id=lobby_id).count()
            if other_lobbies_count == 0:
                teams_to_delete.append(team)
        
        # Log deletion for debugging
        logger.info(f"Deleting lobby {lobby.id} ({lobby.code}) and {len(teams_to_delete)} associated teams")
        
        # Remove all teams from this lobby
        lobby.teams.clear()
        
        # Delete the lobby
        lobby_name = lobby.name if hasattr(lobby, 'name') else lobby.code
        lobby.delete()
        
        # Now delete all the teams that were only in this lobby
        for team in teams_to_delete:
            # Delete team progress and answers first to avoid foreign key issues
            team.race_progress.all().delete()
            team.question_answers.all().delete()
            team.answers.all().delete()
            team.members.all().delete()
            team.delete()
            logger.info(f"Deleted team {team.id} ({team.name})")
        
        # Send update to leaderboard to refresh data
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "leaderboard",
            {
                "type": "leaderboard_update",
                "teams": []  # Empty to trigger a refresh
            }
        )
        
        messages.success(request, f'Lobby "{lobby_name}" and associated teams have been deleted.')
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Error deleting lobby: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@require_POST
def delete_team(request, team_id):
    try:
        from django.db import connection
        
        # Get team details first for messaging
        team = get_object_or_404(Team, id=team_id)
        team_name = team.name
        
        # Get lobby ID if team has any participating lobbies (for later notification)
        lobby = team.participating_lobbies.first()
        lobby_id = lobby.id if lobby else None
        
        # Manual deletion using raw SQL to avoid cascade issues with non-existent tables
        with connection.cursor() as cursor:
            # First, remove team from any lobbies (M2M relationship)
            cursor.execute("DELETE FROM hunt_lobby_teams WHERE team_id = %s", [team_id])
            
            # Get tables in the database
            tables = connection.introspection.table_names()
            
            # Delete related objects in the correct order
            if 'hunt_teamanswer' in tables:
                cursor.execute("DELETE FROM hunt_teamanswer WHERE team_id = %s", [team_id])
            
            if 'hunt_teamprogress' in tables:
                cursor.execute("DELETE FROM hunt_teamprogress WHERE team_id = %s", [team_id])
                
            if 'hunt_teamraceprogress' in tables:
                cursor.execute("DELETE FROM hunt_teamraceprogress WHERE team_id = %s", [team_id])
            
            # Delete any other potential related tables
            for table in tables:
                if table.startswith('hunt_') and table != 'hunt_team' and table != 'hunt_teammember' and 'team' in table.lower():
                    try:
                        sql = f"DELETE FROM {table} WHERE team_id = %s"
                        cursor.execute(sql, [team_id])
                        logger.info(f"Deleted related data from {table} for team {team_id}")
                    except Exception as e:
                        logger.error(f"Error deleting from {table}: {str(e)}")
            
            # Delete team members last (before the team itself)
            cursor.execute("DELETE FROM hunt_teammember WHERE team_id = %s", [team_id])
            
            # Finally delete the team
            cursor.execute("DELETE FROM hunt_team WHERE id = %s", [team_id])
        
        logger.info(f"Team {team_id} ({team_name}) successfully deleted using raw SQL")
        
        # Broadcast updates if needed
        if lobby_id:
            try:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f'lobby_{lobby_id}',
                    {
                        'type': 'team_left',
                        'team_id': team_id
                    }
                )
                logger.info(f"Sent team_left event to lobby_{lobby_id}")
            except Exception as e:
                logger.error(f"Error sending team_left event: {str(e)}")
        
        # Also send update to leaderboard
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "leaderboard",
                {
                    "type": "leaderboard_update",
                    "teams": []  # Empty to trigger a refresh
                }
            )
            logger.info("Sent leaderboard refresh signal")
        except Exception as e:
            logger.error(f"Error sending leaderboard update: {str(e)}")
        
        messages.success(request, f'Team "{team_name}" has been deleted.')
        return redirect('team_list')
        
    except Exception as e:
        logger.error(f"Error deleting team {team_id}: {str(e)}", exc_info=True)
        messages.error(request, f'Error deleting team: {str(e)}')
    
    return redirect('team_list')

def edit_team(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    if request.method == 'POST':
        team_name = request.POST.get('team_name')
        if team_name:
            team.name = team_name
            team.save()
            messages.success(request, f'Team "{team_name}" updated successfully!')
        return redirect('team_list')
    return render(request, 'hunt/edit_team.html', {'team': team})

def view_team(request, team_id):
    # Get team with all related information
    team = get_object_or_404(Team.objects.prefetch_related('members'), id=team_id)
    
    # Get the team members
    members = list(team.members.all())
    
    # Check if the current player is part of this team
    joined_team = False
    team_member_id = request.session.get('team_member_id')
    team_role = request.session.get('team_role')
    player_name = request.session.get('player_name')
    
    # Debug logging
    logger.info(f"view_team: Team {team.name}, Player {player_name}, Role {team_role}")
    logger.info(f"Team members: {[m.role for m in members]}")
    
    # Clear any stale team membership from other teams if joining this team
    if player_name and not joined_team:
        # Find if player has membership in other teams
        other_memberships = TeamMember.objects.filter(
            role=player_name
        ).exclude(team=team)
        
        if other_memberships.exists():
            # Delete memberships in other teams
            logger.info(f"Removing player {player_name} from {other_memberships.count()} other teams")
            other_memberships.delete()
    
    if team_role:
        # Check if there's a team member with this role in this team
        for member in members:
            if member.role == team_role:
                joined_team = True
                # Store the team member ID in session if not already there
                if not team_member_id:
                    request.session['team_member_id'] = member.id
                    request.session.modified = True
                break
    
    # If the player has a name in the session but isn't in the team yet, add them
    if player_name and not joined_team:
        # Create a new team member
        try:
            # Check if this name is already used
            if not TeamMember.objects.filter(team=team, role=player_name).exists():
                # Create the new team member
                new_member = TeamMember.objects.create(
                    team=team,
                    role=player_name
                )
                
                # Update session to track membership
                request.session['team_member_id'] = new_member.id
                request.session['team_role'] = player_name
                request.session['team_id'] = team.id
                request.session.modified = True
                
                # Add to local list for rendering
                members.append(new_member)
                joined_team = True
                
                logger.info(f"Created new team member: {player_name} for team {team.name}")
                
                # Broadcast the update to any connected clients
                try:
                    channel_layer = get_channel_layer()
                    
                    # Send update to team channel
                    async_to_sync(channel_layer.group_send)(
                        f'team_{team.id}',
                        {
                            'type': 'team_member_joined',
                            'member': player_name
                        }
                    )
                    
                    # Also send to any connected lobbies
                    for lobby in team.participating_lobbies.all():
                        async_to_sync(channel_layer.group_send)(
                            f'lobby_{lobby.id}',
                            {
                                'type': 'team_member_joined',
                                'member': {
                                    'role': player_name,
                                },
                                'team_id': team.id,
                                'team_name': team.name
                            }
                        )
                except Exception as e:
                    logger.error(f"Error broadcasting team update: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating team member: {e}")
    
    # Try to find a lobby with a race
    lobby = None
    race = None
    lobby_code = None
    race_id = None  # Initialize race_id separately
    
    # Check if team is part of any lobbies
    lobbies = Lobby.objects.filter(teams=team).select_related('race')
    if lobbies.exists():
        lobby = lobbies.first()
        lobby_code = lobby.code
        race = lobby.race if hasattr(lobby, 'race') else None
        if race:
            race_id = race.id
    
    # If we have a race ID but no race object, try to find it directly
    race_id_in_page = request.GET.get('race_id')
    if race_id_in_page:
        race_id = race_id_in_page
        try:
            race = Race.objects.get(id=race_id_in_page)
            logger.info(f"Found race from URL parameter: {race.id}")
        except Race.DoesNotExist:
            pass
    
    # Make sure we store the team ID in session
    request.session['team_id'] = team.id
    request.session.modified = True
    
    # Re-fetch members to ensure list is up to date
    members = list(team.members.all())
    
    # Debug logging
    logger.info(f"Final state: Team {team.name}, Members: {len(members)}")
    logger.info(f"Lobby: {lobby.name if lobby else 'None'}, Race: {race.id if race else 'None'}")
    
    context = {
        'team': team,
        'members': members,
        'lobby': lobby,
        'lobby_code': lobby_code,
        'race': race,
        'race_id': race_id,  # Always include race_id
        'joined_team': joined_team,  # Add this for the template
    }
    return render(request, 'hunt/view_team.html', context)

@require_POST
def start_hunt(request, lobby_id):
    """Handle the start hunt button press"""
    lobby = get_object_or_404(Lobby, id=lobby_id)
    
    # Check if user is the host
    if request.user != lobby.host:
        return JsonResponse({
            'success': False,
            'error': 'Only the host can start the hunt'
        })
    
    # Checks for teams
    if not lobby.teams.exists():
        return JsonResponse({
            'success': False,
            'error': 'Cannot start hunt without any teams'
        })
    
    # Check for teams with at least one member
    empty_teams = lobby.teams.filter(members__isnull=True).exists()
    if empty_teams:
        return JsonResponse({
            'success': False,
            'error': 'All teams must have at least one member'
        })

    # Starts the scavenger hunt
    lobby.hunt_started = True
    lobby.start_time = timezone.now()
    lobby.save()

    # Get race ID if available
    race_id = lobby.race.id if lobby.race else None
    
    # Send WebSocket message to notify all clients that the race has started
    if race_id:
        channel_layer = get_channel_layer()
        race_group_name = f'race_{race_id}'
        
        # Log that we're sending the race_started event
        print(f"Sending race_started event to group {race_group_name}")
        
        try:
            # Send to the race group
            async_to_sync(channel_layer.group_send)(
                race_group_name,
                {
                    'type': 'race_started',
                    'race_id': race_id,
                    'message': 'Race has started! Redirecting to questions page.'
                }
            )
            print(f"Successfully sent race_started event to group {race_group_name}")
        except Exception as e:
            print(f"Error sending race_started event: {str(e)}")

    # Return success sending them to the first zone
    return JsonResponse({
        'success': True,
        'redirect_url': reverse('first_zone', args=[lobby_id])
    })

def check_hunt_status(request, lobby_id):
    """Check if the hunt has started - called by the JavaScript polling"""
    lobby = get_object_or_404(Lobby, id=lobby_id)
    return JsonResponse({
        'hunt_started': lobby.hunt_started,
        'redirect_url': reverse('first_zone', args=[lobby_id]) if lobby.hunt_started else None
    })

def manage_riddles(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        start_location = request.POST.get('start_location')
        time_limit_minutes = request.POST.get('time_limit_minutes')
        
        if not name:
            messages.error(request, 'Race name is required')
            return redirect('manage_riddles')
            
        try:
            race = Race.objects.create(
                name=name,
                start_location=start_location,
                time_limit_minutes=time_limit_minutes,
                created_by=request.user,
                is_active=True
            )
            messages.success(request, f'Race "{name}" created successfully!')
        except Exception as e:
            messages.error(request, f'Error creating race: {str(e)}')
        
        return redirect('manage_riddles')
    
    races = Race.objects.all().order_by('-created_at')
    return render(request, 'hunt/manage_riddles.html', {'races': races})

@login_required
def race_detail(request, race_id):
    race = get_object_or_404(Race, id=race_id)
    try:
        zones = Zone.objects.filter(race=race).order_by('created_at')
    except:
        zones = []
    
    try:
        questions = Question.objects.filter(zone__race=race).select_related('zone').order_by('zone__created_at')
    except:
        questions = []
    
    # Count questions per zone for the template
    question_counts = {}
    for question in questions:
        zone_id = question.zone.id
        if zone_id in question_counts:
            question_counts[zone_id] += 1
        else:
            question_counts[zone_id] = 1
    
    context = {
        'race': race,
        'zones': zones,
        'questions': questions,
        'question_counts': question_counts,
    }
    return render(request, 'hunt/race_detail.html', context)

@login_required
def edit_zone(request, race_id):
    """Edit an existing zone"""
    if request.method == 'POST':
        race = get_object_or_404(Race, id=race_id)
        zone_id = request.POST.get('zone_id')
        name = request.POST.get('name')
        location = request.POST.get('location')
        
        try:
            zone = Zone.objects.get(id=zone_id, race=race)
            zone.name = name
            zone.location = location
            zone.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Zone "{name}" updated successfully!',
                    'zone': {
                        'id': zone.id,
                        'name': zone.name,
                        'location': zone.location
                    }
                })
            
            messages.success(request, f'Zone "{name}" updated successfully!')
        except Zone.DoesNotExist:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Zone not found'
                })
            
            messages.error(request, 'Zone not found')
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                })
            
            messages.error(request, f'Error updating zone: {str(e)}')
            
    return redirect('race_detail', race_id=race_id)

@login_required
def delete_zone(request, race_id):
    """Delete a zone and its associated questions"""
    if request.method == 'POST':
        race = get_object_or_404(Race, id=race_id)
        zone_id = request.POST.get('zone_id')
        
        try:
            zone = Zone.objects.get(id=zone_id, race=race)
            zone_name = zone.name
            zone.delete()
            
            messages.success(request, f'Zone "{zone_name}" and all its questions have been deleted.')
        except Zone.DoesNotExist:
            messages.error(request, 'Zone not found')
        except Exception as e:
            messages.error(request, f'Error deleting zone: {str(e)}')
            
    return redirect('race_detail', race_id=race_id)

@login_required
def edit_question(request, race_id):
    """Edit an existing question"""
    if request.method == 'POST':
        race = get_object_or_404(Race, id=race_id)
        question_id = request.POST.get('question_id')
        text = request.POST.get('text')
        answer = request.POST.get('answer')
        zone_id = request.POST.get('zone')
        
        try:
            # Ensure the zone belongs to the race
            zone = Zone.objects.get(id=zone_id, race=race)
            question = Question.objects.get(id=question_id, zone__race=race)
            
            question.text = text
            question.answer = answer
            question.zone = zone
            question.save()
            
            messages.success(request, 'Question updated successfully!')
        except Zone.DoesNotExist:
            messages.error(request, 'Selected zone does not exist')
        except Question.DoesNotExist:
            messages.error(request, 'Question not found')
        except Exception as e:
            messages.error(request, f'Error updating question: {str(e)}')
            
    return redirect('race_detail', race_id=race_id)

@login_required
def delete_question(request, race_id):
    """Delete a question"""
    if request.method == 'POST':
        question_id = request.POST.get('question_id')
        
        try:
            question = Question.objects.get(id=question_id, zone__race_id=race_id)
            question.delete()
            
            messages.success(request, 'Question deleted successfully!')
        except Question.DoesNotExist:
            messages.error(request, 'Question not found')
        except Exception as e:
            messages.error(request, f'Error deleting question: {str(e)}')
            
    return redirect('race_detail', race_id=race_id)

@login_required
def delete_race(request, race_id):
    if request.method == 'POST':
        race = get_object_or_404(Race, id=race_id)
        race.delete()
        return redirect('manage_riddles')
    return redirect('manage_riddles')

@login_required
def toggle_race(request, race_id):
    if request.method == 'POST':
        race = get_object_or_404(Race, id=race_id, created_by=request.user)
        race.is_active = not race.is_active
        race.save()
        status = 'activated' if race.is_active else 'deactivated'
        messages.success(request, f'Race {status} successfully!')
    return redirect('race_detail', race_id=race_id)

@login_required
def edit_race(request, race_id):
    race = get_object_or_404(Race, id=race_id)
    
    if request.method == 'POST':
        race.name = request.POST.get('race_name', race.name)
        race.start_location = request.POST.get('start_location', race.start_location)
        race.time_limit_minutes = request.POST.get('time_limit_minutes', race.time_limit_minutes)
        race.save()
        
        messages.success(request, f'Race "{race.name}" has been updated.')
        return redirect('race_detail', race_id=race.id)
        
    return render(request, 'hunt/edit_race.html', {'race': race})

def generate_lobby_code():
    return ''.join(random.choices(string.digits, k=6))

def create_race(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        start_location = request.POST.get('start_location')
        time_limit_minutes = request.POST.get('time_limit_minutes')
        
        race = Race.objects.create(
            name=name,
            start_location=start_location,
            time_limit_minutes=time_limit_minutes,
            created_by=request.user,
            is_active=True
        )
        return redirect('race_detail', race_id=race.id)
    
    return render(request, 'hunt/create_race.html')

def add_zone(request, race_id):
    if request.method == 'POST':
        race = get_object_or_404(Race, id=race_id)
        name = request.POST.get('name')
        location = request.POST.get('location')
        
        try:
            zone = Zone.objects.create(
                race=race,
                name=name,
                location=location
            )
            return JsonResponse({
                'success': True,
                'message': f'Zone "{name}" added successfully!',
                'zone': {
                    'id': zone.id,
                    'name': zone.name,
                    'location': zone.location
                }
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
            
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

def add_question(request, race_id):
    if request.method == 'POST':
        race = get_object_or_404(Race, id=race_id)
        text = request.POST.get('text')
        answer = request.POST.get('answer')
        zone_id = request.POST.get('zone')
        
        try:
            zone = Zone.objects.get(id=zone_id, race=race)
            Question.objects.create(
                zone=zone,
                text=text,
                answer=answer
            )
            messages.success(request, 'Question added successfully!')
        except Zone.DoesNotExist:
            messages.error(request, 'Selected zone does not exist.')
        except Exception as e:
            messages.error(request, f'Error adding question: {str(e)}')
            
    return redirect('race_detail', race_id=race_id)

def student_question(request, lobby_id, question_id):
    """Display a question to the student"""
    # Check if the player has a name
    player_name = request.session.get('player_name')
    if not player_name:
        return redirect('join_game_session')
    
    try:
        lobby = Lobby.objects.get(id=lobby_id)
        question = Question.objects.get(id=question_id)
        
        # Check if race has started
        if not lobby.hunt_started:
            return render(request, 'hunt/error.html', {
                'error': 'Race has not started yet. Please wait for the leader to start the race.'
            })
        
        # Check if time limit is exceeded
        time_elapsed = timezone.now() - lobby.start_time
        if time_elapsed > timedelta(minutes=lobby.time_limit):
            return render(request, 'hunt/error.html', {
                'error': 'Race time limit has been exceeded.'
            })
        
        # Get the team for this player
        try:
            team_member = TeamMember.objects.get(role=player_name, team__lobby=lobby)
            team = team_member.team
            
            # Prepare the context
            context = {
                'lobby': lobby,
                'question': question,
                'player_name': player_name,
                'team': team,
                'requires_photo': question.requires_photo
            }
            
            return render(request, 'hunt/student_question.html', context)
            
        except TeamMember.DoesNotExist:
            return render(request, 'hunt/error.html', {
                'error': 'You are not a member of any team in this lobby.'
            })
            
    except Lobby.DoesNotExist:
        return render(request, 'hunt/error.html', {
            'error': 'Lobby not found.'
        })
    except Question.DoesNotExist:
        return render(request, 'hunt/error.html', {
            'error': 'Question not found.'
        })

def check_answer(request):
    """API to check if an answer is correct"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            question_id = data.get('question_id')
            answer = data.get('answer')
            team_code = data.get('team_code')
            attempt_number = data.get('attempt_number', 1)
            
            if not all([question_id, answer, team_code]):
                return JsonResponse({'success': False, 'error': 'Missing required fields'})
            
            # Get the question and team
            try:
                question = Question.objects.get(id=question_id)
                team = Team.objects.get(code=team_code)
            except Question.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Question not found'})
            except Team.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Team not found'})
            
            # First check if this question has already been answered correctly by this team
            existing_answer = TeamAnswer.objects.filter(
                team=team,
                question=question,
                answered_correctly=True
            ).first()
            
            if existing_answer:
                # Question already answered correctly, return the previous points without adding new ones
                return JsonResponse({
                    'success': True,
                    'correct': True,
                    'points': existing_answer.points_awarded,
                    'already_answered': True,
                    'message': 'You have already answered this question correctly'
                })
            
            # Check if the answer is correct (case-insensitive comparison)
            is_correct = answer.lower().strip() == question.answer.lower().strip()
            
            # Calculate points based on attempt number (3 for first, 2 for second, 1 for third)
            points = max(4 - attempt_number, 0) if is_correct else 0
            
            # If correct, record the answer
            if is_correct:
                # Get or create the answer record
                answer_record, created = TeamAnswer.objects.get_or_create(
                    team=team,
                    question=question,
                    defaults={
                        'answered_correctly': True,
                        'attempts': attempt_number,
                        'points_awarded': points
                    }
                )
                
                if not created:
                    # Update existing record if not already correct
                    if not answer_record.answered_correctly:
                        answer_record.answered_correctly = True
                        answer_record.attempts = attempt_number
                        answer_record.points_awarded = points
                        answer_record.save()
                    else:
                        # Already answered correctly, don't add points again
                        points = answer_record.points_awarded
                
                # Update team's total score for this race (if applicable)
                try:
                    team_race_progress, created = TeamRaceProgress.objects.get_or_create(
                        team=team,
                        race=question.zone.race,
                        defaults={'total_points': points}
                    )
                    
                    if not created:
                        # Only update points if this is the first time answering correctly
                        if created or (answer_record and answer_record.answered_correctly and not answer_record.answered_at):
                            team_race_progress.total_points += points
                            team_race_progress.save()
                    
                    # Update team progress for this specific question
                    team_progress, created = TeamProgress.objects.get_or_create(
                        team=team,
                        question=question,
                        defaults={'completed': is_correct}
                    )
                    
                    # If the answer is correct, mark this question as completed
                    if is_correct and not team_progress.completed:
                        team_progress.completed = True
                        team_progress.completion_time = timezone.now()
                        team_progress.save()
                        
                except Exception as e:
                    print(f"Error updating team race progress: {e}")
            else:
                # Record the failed attempt
                answer_record, created = TeamAnswer.objects.get_or_create(
                    team=team,
                    question=question,
                    defaults={
                        'answered_correctly': False,
                        'attempts': attempt_number
                    }
                )
                
                if not created and not answer_record.answered_correctly:
                    # Update attempt count for existing record
                    answer_record.attempts = attempt_number
                    answer_record.save()
            
            return JsonResponse({
                'success': True,
                'correct': is_correct,
                'points': points
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Only POST method is allowed'})

def upload_photo(request, lobby_id, question_id):
    """Handle photo upload for a question"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    # Check if player has a name
    player_name = request.session.get('player_name')
    if not player_name:
        return JsonResponse({'error': 'No player name found'}, status=400)
    
    try:
        lobby = Lobby.objects.get(id=lobby_id)
        question = Question.objects.get(id=question_id)
        
        # Check if race has started
        if not lobby.hunt_started:
            return JsonResponse({'error': 'Race has not started yet'}, status=400)
        
        # Check if the question requires a photo
        if not question.requires_photo:
            return JsonResponse({'error': 'This question does not require a photo'}, status=400)
        
        # Check if time limit is exceeded
        time_elapsed = timezone.now() - lobby.start_time
        if time_elapsed > timedelta(minutes=lobby.time_limit):
            return JsonResponse({'error': 'Race time limit exceeded'}, status=400)
        
        # Check if a photo was uploaded
        if 'photo' not in request.FILES:
            return JsonResponse({'error': 'No photo uploaded'}, status=400)
        
        photo = request.FILES['photo']
        
        # Find the team for this player
        try:
            team_member = TeamMember.objects.get(role=player_name, team__lobby=lobby)
            team = team_member.team
            
            # Save the photo
            team_progress, created = TeamProgress.objects.get_or_create(team=team, question=question)
            team_progress.photo = photo
            team_progress.completed = True
            team_progress.completion_time = timezone.now()
            team_progress.save()
            
            # Send WebSocket update
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'team_{team.id}',
                {
                    'type': 'team_update',
                    'message': {
                        'type': 'question_completed',
                        'question_id': question_id,
                        'team_id': team.id
                    }
                }
            )
            
            # Send update to lobby
            async_to_sync(channel_layer.group_send)(
                f'lobby_{lobby.id}',
                {
                    'type': 'lobby_update',
                    'message': {
                        'type': 'team_progress',
                        'team_id': team.id,
                        'question_id': question_id,
                        'completed': True
                    }
                }
            )
            
            # Check if all questions are completed
            total_questions = Question.objects.filter(race=lobby.race).count()
            completed_questions = TeamProgress.objects.filter(team=team, completed=True).count()
            
            all_completed = total_questions <= completed_questions
            
            return JsonResponse({
                'success': True,
                'message': 'Photo uploaded successfully!',
                'all_completed': all_completed,
                'next_url': reverse('race_complete') if all_completed else ''
            })
            
        except TeamMember.DoesNotExist:
            return JsonResponse({'error': 'Player not found in any team'}, status=400)
        
    except Lobby.DoesNotExist:
        return JsonResponse({'error': 'Lobby not found'}, status=404)
    except Question.DoesNotExist:
        return JsonResponse({'error': 'Question not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def race_complete(request):
    """Display race completion page"""
    player_name = request.session.get('player_name')
    
    if not player_name:
        return redirect('join_game_session')
    
    return render(request, 'hunt/race_complete.html', {
        'player_name': player_name
    })

def race_questions(request, race_id):
    """View for participants to see and answer questions during a race"""
    # Get race and check if it's active
    race = get_object_or_404(Race, id=race_id)
    
    # Check if user is part of a team in this race
    team_member = None
    player_name = request.session.get('player_name')
    
    if not player_name:
        messages.error(request, "Please set your player name first.")
        return redirect('join_game_session')
    
    try:
        # First try to get team from session (team_id)
        team_id = request.session.get('team_id')
        if team_id:
            team = Team.objects.get(id=team_id)
            
            # Check if the team is part of a lobby with this race
            team_in_race = team.participating_lobbies.filter(race=race).exists()
            
            if not team_in_race:
                # Team is not part of this race
                messages.warning(request, "Your team is not participating in this race.")
                # Continue anyway to show questions
            
            try:
                team_member = TeamMember.objects.get(team=team, role=player_name)
                print(f"Found team member {player_name} in team {team.name}")
            except TeamMember.DoesNotExist:
                # Create a team member if they don't exist yet - removed name field
                team_member = TeamMember.objects.create(team=team, role=player_name)
                print(f"Created new team member {player_name} for team {team.name}")
        else:
            # Fallback: try to find any team this player is part of
            team_member = TeamMember.objects.filter(role=player_name).first()
            
            if not team_member:
                print(f"No team found for player {player_name}")
                messages.error(request, "You are not part of any team. Please join a team first.")
                return redirect('join_team')
            
            team = team_member.team
            print(f"Found team {team.name} for player {player_name}")
    except Team.DoesNotExist:
        messages.error(request, "Team not found.")
        return redirect('join_team')
    except Exception as e:
        print(f"Error finding team: {e}")
        messages.error(request, f"Error finding your team: {str(e)}")
        return redirect('join_team')
    
    # Get zones and questions for this race
    zones = Zone.objects.filter(race=race).order_by('created_at')
    questions = Question.objects.filter(zone__race=race).select_related('zone').order_by('zone__created_at')
    
    # Group questions by zone
    questions_by_zone = {}
    for zone in zones:
        questions_by_zone[zone.id] = []
    
    for question in questions:
        questions_by_zone[question.zone.id].append(question)
    
    # Get existing team answers
    team_answers = TeamAnswer.objects.filter(team=team, question__zone__race=race)
    
    # Organize answers by question ID for easy lookup
    answers_by_question = {}
    for answer in team_answers:
        answers_by_question[answer.question_id] = {
            'answered_correctly': answer.answered_correctly,
            'attempts': answer.attempts,
            'points_awarded': answer.points_awarded
        }
    
    # Get team race progress
    team_race_progress = TeamRaceProgress.objects.filter(team=team, race=race).first()
    current_question_index = 0
    total_points = 0
    
    if team_race_progress:
        current_question_index = team_race_progress.current_question_index
        total_points = team_race_progress.total_points
    
    context = {
        'race': race,
        'team': team,
        'team_member': team_member,
        'zones': zones,
        'questions_by_zone': questions_by_zone,
        'answers_by_question': answers_by_question,
        'current_question_index': current_question_index,
        'total_points': total_points
    }
    
    return render(request, 'hunt/race_questions.html', context)

def check_race_status(request, race_id):
    """Check if the race has started - called by client-side polling"""
    race = get_object_or_404(Race, id=race_id)
    
    # Check if the race is connected to any lobby that has started
    started = False
    redirect_url = None
    
    try:
        # Check if any lobby with this race has started the hunt
        lobbies = Lobby.objects.filter(race=race)
        for lobby in lobbies:
            if lobby.hunt_started:
                started = True
                redirect_url = reverse('race_questions', kwargs={'race_id': race_id})
                break
                
        # If we don't have lobbies, check the race directly
        if not lobbies.exists():
            started = race.is_active
            if started:
                redirect_url = reverse('race_questions', kwargs={'race_id': race_id})
    except Exception as e:
        print(f"Error checking race status: {e}")
    
    return JsonResponse({
        'started': started,
        'redirect_url': redirect_url,
        'race_id': race_id
    })

def get_team_race(request, team_id):
    """API endpoint to get race associated with a team"""
    try:
        team = get_object_or_404(Team, id=team_id)
        
        # Try to find race through lobby
        race_id = None
        
        # Check if team is part of any lobbies with races
        lobbies = Lobby.objects.filter(teams=team).select_related('race')
        if lobbies.exists():
            for lobby in lobbies:
                if lobby.race:
                    race_id = lobby.race.id
                    break
        
        # If no race found via lobbies, check active races for the most recent one
        if not race_id:
            try:
                # Find most recently created active race
                most_recent_race = Race.objects.filter(is_active=True).order_by('-created_at').first()
                if most_recent_race:
                    race_id = most_recent_race.id
                    print(f"Using most recent active race (ID: {race_id}) for team {team_id}")
            except Exception as e:
                print(f"Error finding active race: {e}")
        
        return JsonResponse({
            'success': True,
            'team_id': team_id,
            'race_id': race_id,
            'has_race': race_id is not None
        })
    except Team.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Team not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def upload_photo_api(request):
    """API to handle photo uploads from the race questions page"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)
    
    # Check if a photo was uploaded
    if 'photo' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'No photo uploaded'}, status=400)
    
    # Get question ID from POST data
    question_id = request.POST.get('question_id')
    if not question_id:
        return JsonResponse({'success': False, 'error': 'Missing question ID'}, status=400)
    
    try:
        # Get the question
        question = Question.objects.get(id=question_id)
        
        # Get the team from the session or team code in POST
        team_code = request.POST.get('team_code', None)
        team_id = request.session.get('team_id', None)
        player_name = request.session.get('player_name')
        
        if not player_name:
            return JsonResponse({'success': False, 'error': 'No player name found'}, status=400)
        
        # Try to get the team
        if team_code:
            try:
                team = Team.objects.get(code=team_code)
            except Team.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Team not found with provided code'}, status=404)
        elif team_id:
            try:
                team = Team.objects.get(id=team_id)
            except Team.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Team not found with session ID'}, status=404)
        else:
            # Try to find the team based on player name
            try:
                team_member = TeamMember.objects.get(role=player_name)
                team = team_member.team
            except TeamMember.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Team not found for player'}, status=404)
        
        # Get or create a team answer record
        team_answer, created = TeamAnswer.objects.get_or_create(
            team=team,
            question=question,
            defaults={
                'answered_correctly': False,
                'attempts': 3,  # Assume they've used all attempts if they're uploading a photo
                'requires_photo': True,
                'photo_uploaded': True  # Mark that photo is uploaded
            }
        )
        
        # Update the team answer with the photo
        photo = request.FILES['photo']
        team_answer.photo = photo
        team_answer.photo_uploaded = True  # Ensure this flag is set
        team_answer.save()
        
        # Also update/create team progress
        team_progress, created = TeamProgress.objects.get_or_create(
            team=team,
            question=question,
            defaults={
                'completed': True,
                'completion_time': timezone.now(),
                'photo': photo,
                'photo_uploaded': True
            }
        )
        
        if not created:
            team_progress.completed = True
            team_progress.completion_time = timezone.now()
            team_progress.photo = photo
            team_progress.photo_uploaded = True
            team_progress.save()
        
        # Get the race ID from question for progress tracking
        race = None
        race_id = None
        
        # If question is in a zone, get the race from the zone
        if hasattr(question, 'zone') and question.zone:
            race = question.zone.race
            race_id = race.id
        
        # If race found, update team race progress
        if race_id:
            try:
                race_progress = TeamRaceProgress.objects.get(team=team, race=race)
                if not hasattr(race_progress, 'photo_questions_completed'):
                    race_progress.photo_questions_completed = []
                
                # Add this question ID to completed photo questions if not already there
                photo_completed = race_progress.photo_questions_completed or []
                if str(question.id) not in photo_completed:
                    photo_completed.append(str(question.id))
                    race_progress.photo_questions_completed = photo_completed
                    race_progress.save()
            except Exception as e:
                logger.error(f"Error updating race progress: {str(e)}")
        
        # Return success response with navigation info
        return JsonResponse({
            'success': True,
            'message': 'Photo uploaded successfully!',
            'show_next_button': True,  # Tell the client to show the next button
            'photo_uploaded': True,    # Confirm photo is recorded as uploaded
            'question_completed': True # Mark question as completed for progress tracking
        })
        
    except Question.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Question not found'}, status=404)
    except Exception as e:
        logger.error(f"Error uploading photo: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
def save_question_index(request):
    """API to save the current question index for a team in a race"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)
    
    try:
        data = json.loads(request.body)
        team_code = data.get('team_code')
        race_id = data.get('race_id')
        question_index = data.get('question_index')
        
        if not all([team_code, race_id, question_index is not None]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'}, status=400)
        
        try:
            team = Team.objects.get(code=team_code)
            race = Race.objects.get(id=race_id)
        except Team.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Team not found'}, status=404)
        except Race.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Race not found'}, status=404)
        
        # Update or create team race progress
        team_race_progress, created = TeamRaceProgress.objects.update_or_create(
            team=team,
            race=race,
            defaults={'current_question_index': question_index}
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Question index saved successfully',
            'team_id': team.id,
            'race_id': race.id,
            'question_index': question_index
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def join_lobby(request):
    if request.method == 'POST':
        team_code = request.POST.get('team_code')
        try:
            team = Team.objects.get(code=team_code)
            
            if 'teams' not in request.session:
                request.session['teams'] = []
            
            if team.id not in request.session['teams']:
                request.session['teams'].append(team.id)
                request.session.modified = True
            
            return redirect('team_details', team_id=team.id)
        except Team.DoesNotExist:
            messages.error(request, 'Invalid team code')
            return render(request, 'hunt/join_game_session.html', {'error': 'Invalid team code'})
    
    return redirect('join_game_session')

@require_http_methods(["POST"])
def join_existing_team(request):
    try:
        # Try to parse JSON data first
        if request.content_type == 'application/json':
            if request.body:
                data = json.loads(request.body)
            else:
                return JsonResponse({'success': False, 'error': 'Empty request body'})
        else:
            # Fall back to form data
            data = request.POST
            
        team_code = data.get('team_code')
        player_name = data.get('player_name')

        if not team_code or not player_name:
            return JsonResponse({'success': False, 'error': 'Missing team code or player name'})

        try:
            team = Team.objects.get(code=team_code)
            
            # Check if player already exists in team
            existing_member = TeamMember.objects.filter(team=team, role=player_name).first()
            if existing_member:
                # If they exist but are marked for deletion, reactivate them
                # For now, we'll just return their current team info
                print(f"Player {player_name} is already in team {team.name}")
                
                # Store player name in session
                request.session['player_name'] = player_name
                request.session.modified = True
                
                return JsonResponse({
                    'success': True,
                    'redirect_url': reverse('view_team', args=[team.id])
                })
                
            # Create team member - removed name field
            TeamMember.objects.create(team=team, role=player_name)
            
            # Store player name in session
            request.session['player_name'] = player_name
            request.session.modified = True
            
            return JsonResponse({
                'success': True,
                'redirect_url': reverse('view_team', args=[team.id])
            })
        except Team.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Team not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Server error: {str(e)}'})

@require_http_methods(["GET", "POST"])
def create_standalone_team(request):
    """Create a new team with the current player as a member."""
    # For GET requests, render the form
    if request.method == 'GET':
        # Ensure player has a name in session
        player_name = request.session.get('player_name')
        if not player_name:
            messages.error(request, "Please set your player name first.")
            return redirect('join_game_session')
        
        # Get lobby code from session if available
        lobby_code = request.session.get('lobby_code')
        
        return render(request, 'hunt/create_standalone_team.html', {'lobby_code': lobby_code})
        
    # For POST requests, create the team
    elif request.method == 'POST':
        try:
            # Get data from form 
            team_name = request.POST.get('team_name')
            player_name = request.POST.get('player_name') or request.session.get('player_name')
            
            if not team_name or not player_name:
                messages.error(request, 'Both team name and player name are required')
                return render(request, 'hunt/create_standalone_team.html')
                
            # Check if team name already exists
            if Team.objects.filter(name=team_name).exists():
                messages.error(request, 'A team with this name already exists')
                return render(request, 'hunt/create_standalone_team.html')
                
            # Generate a unique code
            while True:
                code = generate_code()
                if not Team.objects.filter(code=code).exists():
                    break
                    
            # Create the team
            team = Team.objects.create(
                name=team_name,
                code=code
            )
            
            # Create the team member - removed name field
            TeamMember.objects.create(
                team=team,
                role=player_name
            )
            
            # Associate with lobby if a lobby code is in session
            lobby_code = request.session.get('lobby_code')
            if lobby_code:
                try:
                    lobby = Lobby.objects.get(code=lobby_code)
                    lobby.teams.add(team)
                    print(f"Added team {team.name} to lobby {lobby.name}")
                except Lobby.DoesNotExist:
                    print(f"Lobby with code {lobby_code} not found")
            
            # Store in session
            request.session['team_id'] = team.id
            request.session['player_name'] = player_name
            request.session.modified = True
            
            messages.success(request, f'Team "{team_name}" created successfully! Your team code is: {code}')
            return redirect('view_team', team_id=team.id)
            
        except Exception as e:
            messages.error(request, f'Error creating team: {str(e)}')
            return render(request, 'hunt/create_standalone_team.html')
    
    # Should never reach here
    return render(request, 'hunt/create_standalone_team.html')

def leave_team(request, team_id):
    """Allow a player to leave a team they've joined"""
    # Get the team
    team = get_object_or_404(Team, id=team_id)
    
    # Get the player's role from session
    player_role = request.session.get('team_role')
    
    if player_role:
        # Try to find and remove the team member
        try:
            team_member = TeamMember.objects.filter(
                team=team,
                role=player_role
            ).first()
            
            if team_member:
                team_member.delete()
                print(f"Removed player {player_role} from team {team.name}")
                
                # Clear session variables related to team membership
                if 'team_member_id' in request.session:
                    del request.session['team_member_id']
                if 'team_role' in request.session:
                    del request.session['team_role']
                request.session.modified = True
                
                messages.success(request, f"You have left team {team.name}.")
            else:
                messages.error(request, "You are not a member of this team.")
        except Exception as e:
            print(f"Error removing team member: {e}")
            messages.error(request, f"Error leaving team: {str(e)}")
    else:
        messages.error(request, "You are not part of any team.")
    
    # Redirect back to the lobby or the team view
    lobby_code = request.session.get('lobby_code')
    if lobby_code:
        return redirect('join_team')
    else:
        return redirect('view_team', team_id=team_id)

@csrf_exempt
def trigger_leaderboard_update(request):
    """
    API endpoint to manually trigger a leaderboard update broadcast.
    This is useful for testing WebSocket functionality.
    """
    try:
        logger.info("Manual leaderboard update triggered via API")
        
        # Get all teams with their progress data (similar to leaderboard_data_api)
        teams = []
        team_race_progress_list = TeamRaceProgress.objects.select_related('team', 'race').all()
        
        # Organize teams by their total scores
        for team_progress in team_race_progress_list:
            team = team_progress.team
            race = team_progress.race
            if team:
                # Get the lobby for this team that's associated with the race
                lobby = Lobby.objects.filter(teams=team, race=race).first()
                lobby_id = lobby.id if lobby else None
                lobby_name = race.name if race else 'Unknown Race'
                
                # Ensure we're using a valid team name (not an ID or object reference)
                # This fixes the "Team: 30" display issue
                team_name = team.name
                if not team_name or team_name == "None" or not isinstance(team_name, str):
                    team_name = f"Team {team.id}"
                
                teams.append({
                    'id': team.id,
                    'name': team_name,  # Use the validated name
                    'team_name': team_name,  # Add backup field for the client-side fix
                    'score': team_progress.total_points,
                    'lobby_id': lobby_id,
                    'lobby_name': lobby_name
                })
        
        # Sort teams by score (highest first)
        teams.sort(key=lambda x: x['score'], reverse=True)
        
        # Send update to channel layer
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "leaderboard",
            {
                "type": "leaderboard_update",
                "teams": teams
            }
        )
        
        logger.info(f"Sent manual leaderboard update with {len(teams)} teams")
        
        return JsonResponse({
            'success': True,
            'message': f'Leaderboard update triggered with {len(teams)} teams'
        })
    
    except Exception as e:
        logger.error(f"Error triggering leaderboard update: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        })