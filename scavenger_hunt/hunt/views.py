from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import Team, Riddle, Submission, Lobby, TeamMember, Race, Zone, Question, TeamAnswer
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
    lobby = get_object_or_404(Lobby, id=lobby_id)
    teams = lobby.teams.all().prefetch_related('members')
    
    # Debug prints
    for team in teams:
        members = team.members.all()
        print(f"Team {team.name} (ID: {team.id}) members:")
        for member in members:
            print(f"- {member.role}")
    
    context = {
        'lobby': lobby,
        'teams': teams,
    }
    return render(request, 'hunt/lobby_details.html', context)

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

class LobbyDetailsView(DetailView):
    model = Lobby
    template_name = 'hunt/lobby_details.html'
    context_object_name = 'lobby'

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
        
        lobby_code = request.session.get('lobby_code')
        print(f"Lobby code in session: {lobby_code}")  # Debug print
        
        if lobby_code:
            lobby = get_object_or_404(Lobby, code=lobby_code)
        return render(request, 'hunt/team_options.html', {'lobby': lobby})
            
        print("No player name provided or lobby code missing")  # Debug print
    return redirect('join_game_session')

def broadcast_team_update(team_id):
    channel_layer = get_channel_layer()
    team = Team.objects.prefetch_related('team_members').get(id=team_id)
    members = list(team.team_members.values_list('role', flat=True))
                    
    async_to_sync(channel_layer.group_send)(
        f'team_{team_id}',
                        {
                            'type': 'team_update',
                            'members': members
                        }
                    )

def join_team(request):
    # Make sure player name is in session
    if 'player_name' not in request.session or not request.session['player_name']:
        # Debug log for troubleshooting
        print("Session data:", dict(request.session))
        
        # Get player name from POST if available
        if request.method == 'POST' and 'player_name' in request.POST:
            request.session['player_name'] = request.POST.get('player_name')
            request.session.modified = True
        else:
            # Default fallback
            request.session['player_name'] = 'Player'
            request.session.modified = True
    
    # Get all active teams
    teams = Team.objects.all().prefetch_related('members')
    
    return render(request, 'hunt/join_team.html', {
        'teams': teams,
        'player_name': request.session['player_name']
    })

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
            if TeamMember.objects.filter(team=team, role=player_name).exists():
                return JsonResponse({'success': False, 'error': 'You are already in this team'})
                
            # Create team member
            TeamMember.objects.create(team=team, role=player_name, name=player_name)
            
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

@require_http_methods(["POST"])
def create_standalone_team(request):
    """Create a new team with the current player as a member."""
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
            
        team_name = data.get('team_name')
        player_name = data.get('player_name')
        
        if not team_name or not player_name:
            return JsonResponse({
                'success': False,
                'error': 'Both team name and player name are required'
            })
            
        # Check if team name already exists
        if Team.objects.filter(name=team_name).exists():
            return JsonResponse({
                'success': False,
                'error': 'A team with this name already exists'
            })
            
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
        
        # Create the team member
        TeamMember.objects.create(
            team=team,
            role=player_name,
            name=player_name
        )
        
        # Store in session
        request.session['team_id'] = team.id
        request.session['player_name'] = player_name
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'team_code': team.code,
            'redirect_url': reverse('view_team', args=[team.id])
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

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
    return render(request, 'hunt/leaderboard.html')

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
    
    if request.method == 'POST':
        form = TeamForm(request.POST)
        if form.is_valid():
            team = form.save()
            lobby.teams.add(team)
            
            # Create a team member for the creator
            player_name = request.session.get('player_name')
            if player_name:
                # Check if this player is already a member
                existing_member = TeamMember.objects.filter(
                    team=team,
                    role=player_name
                ).first()
                
                if not existing_member:
                    team_member = TeamMember.objects.create(
                        team=team,
                        role=player_name,
                        name=player_name
                    )
            
            request.session['team_id'] = team.id
            messages.success(request, f'Team created! Your team code is: {team.code}')
            return redirect('view_team', team_id=team.id)
    else:
        form = TeamForm()
    
    return render(request, 'hunt/create_team.html', {
        'form': form,
        'lobby': lobby
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
        lobby = get_object_or_404(Lobby, id=lobby_id)
        lobby.delete()
        return JsonResponse({'status': 'success'})

@require_POST
def delete_team(request, team_id):
    try:
        team = get_object_or_404(Team, id=team_id)
        
        # Get lobby ID if team has any participating lobbies
        lobby = team.participating_lobbies.first()
        lobby_id = lobby.id if lobby else None
        
        team_name = team.name
        team.delete()
        
        # Broadcast update if lobby exists
        if lobby_id:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'lobby_{lobby_id}',
                {
                    'type': 'lobby_update',
                    'message': 'team_deleted'
                }
            )
        
        messages.success(request, f'Team "{team_name}" has been deleted.')
        return redirect('team_list')
        
    except Exception as e:
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
    team = get_object_or_404(Team.objects.prefetch_related('members'), id=team_id)
    members = team.members.all()
    
    context = {
        'team': team,
        'members': members
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
            team_member = TeamMember.objects.get(name=player_name, team__lobby=lobby)
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
            
            # Check if the answer is correct (case-insensitive comparison)
            is_correct = answer.lower() == question.answer.lower()
            
            # If correct, record the answer
            if is_correct:
                # Check if we already have this answer recorded
                answer_record, created = TeamAnswer.objects.get_or_create(
                    team=team,
                    question=question,
                    defaults={'answered_correctly': True}
                )
                
                if not created:
                    # Update existing record
                    answer_record.answered_correctly = True
                    answer_record.save()
            
            return JsonResponse({
                'success': True,
                'correct': is_correct
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
            team_member = TeamMember.objects.get(name=player_name, team__lobby=lobby)
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
    try:
        team_code = request.session.get('team_code')
        player_name = request.session.get('player_name')
        
        if team_code and player_name:
            team = Team.objects.get(code=team_code)
            team_member = TeamMember.objects.get(team=team, name=player_name)
        else:
            return redirect('join_game_session')
    except (Team.DoesNotExist, TeamMember.DoesNotExist):
        messages.error(request, "You are not part of a team in this race.")
        return redirect('join_game_session')
    
    # Get zones and questions for this race
    zones = Zone.objects.filter(race=race).order_by('created_at')
    questions = Question.objects.filter(zone__race=race).select_related('zone').order_by('zone__created_at')
    
    # Group questions by zone
    questions_by_zone = {}
    for zone in zones:
        questions_by_zone[zone.id] = []
    
    for question in questions:
        questions_by_zone[question.zone.id].append(question)
    
    context = {
        'race': race,
        'team': team_member.team,
        'team_member': team_member,
        'zones': zones,
        'questions_by_zone': questions_by_zone,
    }
    
    return render(request, 'hunt/race_questions.html', context)