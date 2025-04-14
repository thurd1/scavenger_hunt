from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import Team, Riddle, Submission, Lobby, TeamMember, Race, Zone, Question, TeamAnswer, TeamRaceProgress, TeamProgress
from django.http import JsonResponse
from .forms import JoinLobbyForm, LobbyForm, TeamForm
from django.http import HttpResponse
from django.contrib.auth.forms import UserCreationForm
from django.views.generic import DetailView
from django.db.models import Count, Sum
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
from django.db import transaction

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
            
            # Also send to race channel but only for this specific lobby's race
            # This prevents starting all races with the same ID
            async_to_sync(channel_layer.group_send)(
                f'race_{race.id}_lobby_{lobby_id}',
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
    """API endpoint to fetch leaderboard data for AJAX updates"""
    try:
        teams = []
        
        # Check if we're filtering for a specific team
        team_code = request.GET.get('team_code')
        
        # Get teams with their progress data
        team_race_progress_list = TeamRaceProgress.objects.select_related('team', 'race').all()
        
        # Filter by team code if provided
        if team_code:
            logger.info(f"Filtering leaderboard data for team with code: {team_code}")
            team_race_progress_list = team_race_progress_list.filter(team__code=team_code)
        
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
                    'code': team.code,
                    'score': team_progress.total_points,
                    'lobby_id': lobby_id,
                    'lobby_name': lobby_name
                })
        
        # Sort teams by score (highest first)
        teams.sort(key=lambda x: x['score'], reverse=True)
        
        # Return success response with teams data
        return JsonResponse({
            'success': True,
            'teams': teams
        })
    except Exception as e:
        logger.error(f"Error in leaderboard_data_api: {str(e)}", exc_info=True)
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
    return render(request, "hunt/leader_dashboard.html", {"teams": teams})

@login_required
def team_detail(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    riddles = Riddle.objects.filter(team=team)
    return render(request, "hunt/team_detail.html", {"team": team, "riddles": riddles})

@csrf_exempt
def check_answer(request, lobby_id=None, question_id=None):
    """Check if the answer to a question is correct"""
    # Debug log
    print(f"check_answer called: lobby_id={lobby_id}, question_id={question_id}, method={request.method}")
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        # Try to parse JSON data
        try:
            data = json.loads(request.body)
            print(f"Request body: {data}")
        except json.JSONDecodeError:
            data = request.POST
            print(f"POST data: {data}")
            
        # Get question_id either from URL or from POST data
        question_id = question_id or data.get('question_id')
        answer = data.get('answer', '')
        team_code = data.get('team_code')
            
        print(f"Processing answer: question_id={question_id}, team_code={team_code}, answer={answer}")
        
        if not question_id or not team_code:
            return JsonResponse({'error': 'Missing required fields'}, status=400)
            
        try:
            # Get the question and team
            question = Question.objects.get(id=question_id)
            team = Team.objects.get(code=team_code)
                
            # Check if the question has already been answered correctly
            team_answer = TeamAnswer.objects.filter(team=team, question=question).first()
                
            if team_answer and team_answer.answered_correctly:
                # Already answered correctly
                print(f"Question {question_id} already answered correctly")
                return JsonResponse({
                    'correct': True,
                    'already_answered': True,
                    'points': team_answer.points_awarded,
                    'photo_uploaded': team_answer.photo_uploaded,
                    'message': 'Already answered correctly'
                })
                
            # If not, create or update team answer
            if not team_answer:
                team_answer = TeamAnswer.objects.create(
                    team=team,
                    question=question,
                    answered_correctly=False,
                    attempts=0,
                    points_awarded=0,
                    requires_photo=question.requires_photo
                )
                
            # Increment attempts
            team_answer.attempts += 1
                
            # Check if answer is correct
            correct_answer = question.answer.lower().strip()
            user_answer = answer.lower().strip() if answer else ""
            is_correct = user_answer == correct_answer
                
            print(f"Comparing answers: user='{user_answer}', correct='{correct_answer}', match={is_correct}")
            
            # Calculate points
            points = 0
            if is_correct:
                if team_answer.attempts == 1:
                    points = 3
                elif team_answer.attempts == 2:
                    points = 2
                elif team_answer.attempts == 3:
                    points = 1
                
            # Update the answer record
            team_answer.answered_correctly = is_correct
            if is_correct:
                team_answer.points_awarded = points
            team_answer.save()
                
            # Find the lobby this team is in
            lobby = team.participating_lobbies.first()

            # Update race progress
            if is_correct and lobby and lobby.race:
                race = lobby.race
                team_race_progress, created = TeamRaceProgress.objects.get_or_create(
                    team=team,
                    race=race,
                    defaults={
                        'total_points': points,
                        'current_question_index': 0
                    }
                )
                
                if not created:
                    # Update total points
                    total_points = TeamAnswer.objects.filter(
                        team=team,
                        question__zone__race=race,
                        answered_correctly=True
                    ).aggregate(Sum('points_awarded'))['points_awarded__sum'] or 0
                            
                    team_race_progress.total_points = total_points
                    team_race_progress.save()
                            
            # Prepare response
            response_data = {
                'correct': is_correct,
                'attempts': team_answer.attempts,
                'max_attempts': 3,
                'points': points if is_correct else 0,
                'photo_uploaded': team_answer.photo_uploaded
            }
                
            # Log response
            print(f"Sending response: {response_data}")
            
            return JsonResponse(response_data)
                
        except Question.DoesNotExist:
            print(f"Question {question_id} not found")
            return JsonResponse({'error': 'Question not found'}, status=404)
        except Team.DoesNotExist:
            print(f"Team with code {team_code} not found")
            return JsonResponse({'error': 'Team not found'}, status=404)
        except Exception as e:
            print(f"Error processing answer: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=500)
    except Exception as e:
        print(f"Outer exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)
    
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
        
        # Don't enforce photo requirement validation anymore
        # if not question.requires_photo:
        #     return JsonResponse({'error': 'This question does not require a photo'}, status=400)
        
        # Check if time limit is exceeded - use race's time limit if available or default to 60
        time_limit_minutes = lobby.race.time_limit_minutes if hasattr(lobby.race, 'time_limit_minutes') else 60
        time_elapsed = timezone.now() - lobby.start_time
        if time_elapsed > timedelta(minutes=time_limit_minutes):
            return JsonResponse({'error': 'Race time limit exceeded'}, status=400)
        
        # Check if a photo was uploaded
        if 'photo' not in request.FILES:
            return JsonResponse({'error': 'No photo uploaded'}, status=400)
        
        photo = request.FILES['photo']
        
        # Find the team for this player - more lenient search
        try:
            team_member = TeamMember.objects.filter(role=player_name).first()
            if not team_member:
                return JsonResponse({'error': 'Player not found in any team'}, status=400)
                
            team = team_member.team
            
            # Save photo to TeamAnswer
            team_answer, created = TeamAnswer.objects.get_or_create(
                team=team,
                question=question,
                defaults={
                    'answered_correctly': False,
                    'attempts': 3,  # Max attempts used
                    'requires_photo': True,
                    'photo_uploaded': True
                }
            )
            
            # Update the answer record
            team_answer.photo = photo
            team_answer.photo_uploaded = True  # This is critical!
            team_answer.save()
            
            # Also save to team progress for compatibility
            team_progress, created = TeamProgress.objects.get_or_create(
                team=team, 
                question=question,
                defaults={
                    'completed': True,
                    'completion_time': timezone.now()
                }
            )
            
            team_progress.photo = photo
            team_progress.photo_uploaded = True
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
            
            # Get next question if any
            questions = Question.objects.filter(zone__race=lobby.race).order_by('zone__created_at')
            question_ids = list(questions.values_list('id', flat=True))
            
            next_q_id = None
            try:
                current_index = question_ids.index(int(question_id))
                if current_index < len(question_ids) - 1:
                    next_q_id = question_ids[current_index + 1]
                    logger.info(f"Upload_photo: Found next question ID: {next_q_id}")
                else:
                    logger.info("Upload_photo: This is the last question")
            except (ValueError, IndexError) as e:
                logger.error(f"Upload_photo: Error finding question index: {str(e)}")
                
            next_url = ""
            if next_q_id:
                # Use direct URL path instead of reverse
                next_url = f"/studentQuestion/{lobby_id}/{next_q_id}/"
                logger.info(f"Upload_photo: Setting direct next_url to: {next_url}")
            else:
                next_url = "/race-complete/"
                logger.info(f"Upload_photo: No next question, setting next_url to: {next_url}")
            
            return JsonResponse({
                'success': True,
                'message': 'Photo uploaded successfully!',
                'show_next_button': True,  # Always show next button
                'photo_uploaded': True,    # Confirm photo is recorded
                'question_completed': True,# Mark as completed
                'next_url': next_url
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
    
    # If accessed from admin dashboard, show an example view
    if not player_name and request.user.is_authenticated:
        return render(request, 'hunt/race_complete.html', {
            'player_name': 'Example Player',
            'total_score': 1000
        })
    
    if not player_name:
        return redirect('join_game_session')
    
    return render(request, 'hunt/race_complete.html', {
        'player_name': player_name
    })

def race_questions(request, race_id):
    """View for participants to see and answer questions during a race"""
    # Get race and check if it's active
    race = get_object_or_404(Race, id=race_id)
    print(f"Found race: {race.id}")
    
    # Process query parameters first
    team_code = request.GET.get('team_code')
    player_name_param = request.GET.get('player_name')
    
    # Get player name from session or query parameter
    player_name = request.session.get('player_name') or player_name_param
    
    # If player name is in the query, save it to the session for future use
    if player_name_param and not request.session.get('player_name'):
        request.session['player_name'] = player_name_param
    
    # Check if we have a player name
    if not player_name:
        # If no player name, show join form with team code populated if provided
        return render(request, 'hunt/race_questions.html', {
            'show_join_form': True,
            'race': race,
            'team_code_prefill': team_code
        })
    
    # Try to find the team - first from the team_code parameter, then from session
    team = None
    if team_code:
        try:
            team = Team.objects.get(code=team_code)
            # Save team_id to session for future use
            request.session['team_id'] = team.id
        except Team.DoesNotExist:
                pass
    
    # If no team from parameter, try from session
    if not team:
        team_id = request.session.get('team_id')
        if team_id:
            try:
                team = Team.objects.get(id=team_id)
            except Team.DoesNotExist:
                pass
    
    # If still no team, check if player is in any team
    if not team:
        try:
            team_member = TeamMember.objects.filter(role=player_name).first()
            if team_member:
                team = team_member.team
                # Save team_id to session
                request.session['team_id'] = team.id
        except Exception as e:
            print(f"Error finding team: {e}")
    
    # If no team found at all, show join form
    if not team:
        return render(request, 'hunt/race_questions.html', {
            'show_join_form': True,
            'race': race,
            'error': 'Could not find a team for you. Please join a team first.'
        })
    
    # Find or create team member
    try:
        team_member = TeamMember.objects.get(team=team, role=player_name)
    except TeamMember.DoesNotExist:
        # Create a team member entry
        team_member = TeamMember.objects.create(team=team, role=player_name)
        print(f"Created new team member {player_name} for team {team.name}")
    
    # Get zones for this race
    zones = Zone.objects.filter(race=race).order_by('created_at')
    print(f"Found {zones.count()} zones")
    
    # Get all questions for this race
    questions = Question.objects.filter(zone__race=race).select_related('zone')
    print(f"Found {questions.count()} questions")
    
    # Print debug info for each zone and its questions
    for zone in zones:
        zone_questions = [q for q in questions if q.zone_id == zone.id]
        print(f"Zone {zone.id} ({zone.name}): {len(zone_questions)} questions")
        for q in zone_questions:
            print(f"  Question {q.id}: {q.text[:30]}")
    
    # Group questions by zone using a dictionary comprehension
    questions_by_zone = {}
    for zone in zones:
        zone_questions = [q for q in questions if q.zone_id == zone.id]
        questions_by_zone[zone.id] = zone_questions
        print(f"Added {len(zone_questions)} questions to zone {zone.id}")
    
    # Get existing team answers
    team_answers = TeamAnswer.objects.filter(team=team, question__zone__race=race)
    
    # Organize answers by question ID for easy lookup
    answers_by_question = {}
    for answer in team_answers:
        answers_by_question[answer.question_id] = {
            'answered_correctly': answer.answered_correctly,
            'attempts': answer.attempts,
            'points_awarded': answer.points_awarded,
            'photo_uploaded': answer.photo_uploaded
        }
    
    # Get team race progress
    team_race_progress = TeamRaceProgress.objects.filter(team=team, race=race).first()
    current_question_index = 0
    total_points = 0
    
    if team_race_progress:
        current_question_index = team_race_progress.current_question_index
        total_points = team_race_progress.total_points
    
    # Add debug info to context
    debug_info = {
        'zones': {z.id: z.name for z in zones},
        'question_counts': {z.id: len(questions_by_zone.get(z.id, [])) for z in zones}
    }
    
    context = {
        'race': race,
        'team': team,
        'team_member': team_member,
        'zones': zones,
        'questions_by_zone': questions_by_zone,
        'answers_by_question': answers_by_question,
        'current_question_index': current_question_index,
        'total_points': total_points,
        'debug_info': debug_info
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

def check_lobby_race_status(request, lobby_id):
    """Check if a race has started for a specific lobby - used by team view pages"""
    lobby = get_object_or_404(Lobby, id=lobby_id)
    started = lobby.hunt_started
    redirect_url = None
    race_id = None
    
    if started and lobby.race:
        race_id = lobby.race.id
        
        # Get the player name from the session
        player_name = request.session.get('player_name')
        
        # Get the team for this player
        team_code = None
        try:
            if player_name:
                team_member = TeamMember.objects.filter(role=player_name).first()
                if team_member and team_member.team:
                    team_code = team_member.team.code
        except Exception as e:
            logger.error(f"Error getting team code in check_lobby_race_status: {str(e)}")
        
        # If we have all the information, direct to race_questions instead of using hardcoded ID 1
        if team_code and player_name:
            redirect_url = f"/race/{race_id}/questions/?team_code={team_code}&player_name={player_name}"
        else:
            # Find the first question for this race instead of using hardcoded ID 1
            try:
                first_question = Question.objects.filter(
                    zone__race=lobby.race
                ).order_by('zone__created_at', 'id').first()
                
                if first_question:
                    # Use the first question we found
                    redirect_url = reverse('student_question', kwargs={
                        'lobby_id': lobby_id, 
                        'question_id': first_question.id
                    })
                    logger.info(f"Found first question ID {first_question.id} for race {race_id}")
                else:
                    # If no questions in race, just go to race_questions
                    redirect_url = f"/race/{race_id}/questions/"
                    logger.warning(f"No questions found for race {race_id}, redirecting to race_questions")
            except Exception as e:
                # If error finding question, use the basic race_questions URL
                logger.error(f"Error finding first question for race {race_id}: {str(e)}")
                redirect_url = f"/race/{race_id}/questions/"
    
    # Log the status check for debugging
    logger.info(f"Lobby {lobby_id} race status check: started={started}, race_id={race_id}, redirect_url={redirect_url}")
    
    return JsonResponse({
        'started': started,
        'redirect_url': redirect_url,
        'race_id': race_id,
        'lobby_id': lobby_id
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
                'photo_uploaded': True,  # Mark that photo is uploaded
                'points_awarded': 0  # Explicitly set to 0 points for photo uploads
            }
        )
        
        # Update the team answer with the photo
        photo = request.FILES['photo']
        team_answer.photo = photo
        team_answer.photo_uploaded = True  # Ensure this flag is set
        team_answer.points_awarded = 0  # Always ensure 0 points for photo uploads
        team_answer.save()
        
        # Also update/create team progress
        team_progress, created = TeamProgress.objects.get_or_create(
            team=team,
            question=question,
            defaults={
                'completed': True,
                'completion_time': timezone.now(),
                'photo': photo
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
                
                photo_completed = race_progress.photo_questions_completed or []
                if str(question.id) not in photo_completed:
                    photo_completed.append(str(question.id))
                    race_progress.photo_questions_completed = photo_completed
                    race_progress.save()
                    
                    # Also update total points in TeamRaceProgress to ensure consistency
                    # (this triggers the post_save signal that will update the leaderboard)
                    try:
                        total_points = TeamAnswer.objects.filter(
                            team=team,
                            question__zone__race=race,
                            answered_correctly=True
                        ).aggregate(Sum('points_awarded'))['points_awarded__sum'] or 0
                        
                        race_progress.total_points = total_points
                        race_progress.save()
                        
                        logger.info(f"Updated TeamRaceProgress for team {team.name} after photo upload, total points: {total_points}")
                    except Exception as e:
                        logger.error(f"Error updating total points: {str(e)}")
                    
                # Send leaderboard update via WebSocket
                try:
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        'leaderboard',
                        {
                            'type': 'leaderboard_update',
                            'team_id': team.id,
                            'team_name': team.name,
                            'race_id': race_id,
                            'action': 'update'
                        }
                    )
                    logger.info(f"Sent leaderboard update for team {team.id} in race {race_id} after photo upload")
                    
                    # Also trigger a complete leaderboard refresh for all clients
                    trigger_leaderboard_update_internal(race_id)
                except Exception as e:
                    logger.error(f"Error sending leaderboard update: {str(e)}")
                    
            except Exception as e:
                logger.error(f"Error updating race progress: {str(e)}")
        
        # Calculate next_url for navigation
        next_url = ""
        next_question_url = ""
        
        # Get the lobby that matches this race
        try:
            lobby = team.participating_lobbies.filter(race=race).first()
            if lobby:
                # Get next question if any
                questions = Question.objects.filter(zone__race=race).order_by('zone__created_at')
                question_ids = list(questions.values_list('id', flat=True))
                
                next_q_id = None
                try:
                    current_index = question_ids.index(int(question_id))
                    if current_index < len(question_ids) - 1:
                        next_q_id = question_ids[current_index + 1]
                except (ValueError, IndexError):
                    pass
                    
                if next_q_id:
                    # Create two URLs - one for student_question and one for race_questions
                    next_url = reverse('student_question', kwargs={
                        'lobby_id': lobby.id,
                        'question_id': next_q_id
                    })
                    
                    # Also create a direct URL to race_questions for the same team/player
                    next_question_url = f"/race/{race.id}/questions/?team_code={team.code}"
                    if player_name:
                        next_question_url += f"&player_name={player_name}"
                else:
                    next_url = reverse('race_complete')
                    next_question_url = reverse('race_complete')
        except Exception as e:
            logger.error(f"Error calculating next URL: {str(e)}")
            # Fallback: if we can't determine next question, go to race complete
            next_url = reverse('race_complete')
            next_question_url = reverse('race_complete')
        
        # Return success response with navigation info
        return JsonResponse({
            'success': True,
            'message': 'Photo uploaded successfully!',
            'show_next_button': True,  # Tell the client to show the next button
            'photo_uploaded': True,    # Confirm photo is recorded as uploaded
            'question_completed': True, # Mark question as completed for progress tracking
            'next_url': next_question_url,  # Use the race_questions URL as primary
            'legacy_next_url': next_url     # Keep the student_question URL as backup
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
                    'team_name': team_name,  # Backup field for the client-side fix
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

def csrf_failure(request, reason=""):
    """
    Custom view for CSRF verification failures that redirects to home 
    instead of showing the default Django error page.
    """
    from django.contrib import messages
    
    # Add an error message that will be displayed on the home page
    messages.error(request, "Your session has expired or there was a security issue. Please try again.")
    
    # Redirect to home page
    return redirect('home')

# Helper function for internal leaderboard updates
def trigger_leaderboard_update_internal(race_id=None):
    """Internal function to trigger leaderboard updates without HTTP request"""
    try:
        # Get all active races if no race_id specified
        if race_id:
            races = Race.objects.filter(id=race_id, is_active=True)
        else:
            races = Race.objects.filter(is_active=True)
        
        for race in races:
            # Get all teams in this race via lobbies
            lobbies = Lobby.objects.filter(race=race)
            teams = Team.objects.filter(participating_lobbies__in=lobbies).distinct()
            
            # Prepare leaderboard data
            leaderboard_data = []
            
            for team in teams:
                # Get team's score from TeamAnswer records
                team_answers = TeamAnswer.objects.filter(
                    team=team, 
                    question__zone__race=race
                )
                
                total_score = team_answers.aggregate(Sum('points_awarded'))['points_awarded__sum'] or 0
                answered_count = team_answers.filter(answered_correctly=True).count()
                photo_count = team_answers.filter(photo_uploaded=True).count()
                
                leaderboard_data.append({
                    'team_id': team.id,
                    'team_name': team.name,
                    'score': total_score,
                    'questions_answered': answered_count,
                    'photos_uploaded': photo_count
                })
            
            # Sort by score (descending)
            leaderboard_data.sort(key=lambda x: x['score'], reverse=True)
            
            # Broadcast update via WebSocket
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'leaderboard',
                {
                    'type': 'leaderboard_update',
                    'race_id': race.id,
                    'data': leaderboard_data,
                    'action': 'full_refresh'
                }
            )
        
        return True
    except Exception as e:
        logger.error(f"Error in trigger_leaderboard_update_internal: {str(e)}")
        return False

@csrf_exempt
def question_answers_api(request):
    """
    API endpoint to get answers for questions in a race for a specific team
    """
    team_code = request.GET.get('team_code')
    race_id = request.GET.get('race_id')
    
    if not team_code or not race_id:
        return JsonResponse({'success': False, 'error': 'Missing required parameters'})
    
    try:
        team = Team.objects.get(code=team_code)
        race = Race.objects.get(id=race_id)
        
        # Get all team answers for this race
        answers = TeamAnswer.objects.filter(
            team=team, 
            question__zone__race=race
        ).select_related('question')
        
        # Format the answers
        answer_data = {}
        for answer in answers:
            answer_data[answer.question.id] = {
                'attempts': answer.attempts,
                'points_awarded': answer.points_awarded,
                'answered_correctly': answer.answered_correctly,
                'photo_uploaded': answer.photo_uploaded
            }
        
        return JsonResponse({
            'success': True,
            'answers': answer_data
        })
    except Team.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Team not found'})
    except Race.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Race not found'})
    except Exception as e:
        logger.error(f"Error in question_answers_api: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

def race_detail(request, race_id):
    """View details of a race."""
    race = get_object_or_404(Race, id=race_id)
    zones = Zone.objects.filter(race=race).order_by('created_at')
    questions = Question.objects.filter(zone__race=race).order_by('zone__created_at')
    return render(request, "hunt/race_detail.html", {
        "race": race,
        "zones": zones,
        "questions": questions
    })