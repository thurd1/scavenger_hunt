from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import Team, Riddle, Submission, Lobby, TeamMember, Race, Zone, Question
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

logger = logging.getLogger(__name__)

@login_required
def create_lobby(request):
    if request.method == 'POST':
        race_id = request.POST.get('race')
        
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
    races = Race.objects.filter(is_active=True).order_by('-created_at')
    
    if request.method == 'POST':
        if 'start_race' in request.POST:
            race_id = request.POST.get('race_id')
            if race_id:
                race = get_object_or_404(Race, id=race_id)
                lobby.race = race
                lobby.hunt_started = True
                lobby.start_time = timezone.now()
                lobby.save()
                
                # Redirect teams to their first question
                return redirect('start_race', lobby_id=lobby.id)
    
    context = {
        'lobby': lobby,
        'teams': teams,
        'races': races,
    }
    return render(request, 'hunt/lobby_details.html', context)

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
        redirect_url = reverse('start_race', args=[lobby_id])
        if first_question:
            redirect_url = f"{redirect_url}?question_id={first_question.id}"
        
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
            return render(request, 'team_options.html', {'lobby': lobby})
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
    """Render the join team page with available teams and forms to join or create teams."""
    # Get all active teams
    teams = Team.objects.all().prefetch_related('members')
    
    # Get player name from session
    player_name = request.session.get('player_name', '')
    
    return render(request, 'hunt/join_team.html', {
        'teams': teams,
        'player_name': player_name
    })

@require_http_methods(["POST"])
def join_existing_team(request):
    data = json.loads(request.body)
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

@require_http_methods(["POST"])
def create_standalone_team(request):
    """Create a new team with the current player as a member."""
    try:
        data = json.loads(request.body)
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
            role=player_name
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
                        role=player_name
                    )
            
            request.session['team_id'] = team.id
            messages.success(request, f'Team created! Your team code is: {team.code}')
            return redirect('team_dashboard', team_id=team.id)
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

@require_http_methods(["POST"])
def check_answer(request, lobby_id, question_id):
    """Check if the submitted answer is correct."""
    try:
        data = json.loads(request.body)
        answer = data.get('answer', '').strip()
        
        lobby = get_object_or_404(Lobby, id=lobby_id)
        question = get_object_or_404(Question, id=question_id)
        
        if not lobby.hunt_started or not lobby.race:
            return JsonResponse({
                'correct': False,
                'error': 'Race has not started.'
            })
            
        # Check if time is up
        time_elapsed = timezone.now() - lobby.start_time
        if time_elapsed.total_seconds() > (lobby.race.time_limit_minutes * 60):
            return JsonResponse({
                'correct': False,
                'error': 'Time is up!'
            })
        
        is_correct = answer.lower() == question.answer.lower()
        
        if is_correct:
            # Get next question in the same zone
            next_question = Question.objects.filter(
                zone=question.zone,
                created_at__gt=question.created_at
            ).first()
            
            # If no more questions in this zone, get first question of next zone
            if not next_question:
                next_zone = Zone.objects.filter(
                    race=lobby.race,
                    created_at__gt=question.zone.created_at
                ).first()
                
                if next_zone:
                    next_question = next_zone.questions.first()
            
            next_url = reverse('start_race', args=[lobby_id])
            if next_question:
                next_url = f"{next_url}?question_id={next_question.id}"
            
            return JsonResponse({
                'correct': True,
                'next_question_url': next_url
            })
        
        return JsonResponse({
            'correct': False
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'correct': False,
            'error': 'Invalid request format'
        })
    except Exception as e:
        return JsonResponse({
            'correct': False,
            'error': str(e)
        })

@require_http_methods(["POST"])
def upload_photo(request, lobby_id, question_id):
    """Handle photo upload for a question."""
    try:
        lobby = get_object_or_404(Lobby, id=lobby_id)
        question = get_object_or_404(Question, id=question_id)
        
        if not lobby.hunt_started or not lobby.race:
            return JsonResponse({
                'success': False,
                'error': 'Race has not started.'
            })
        
        # Check if time is up
        time_elapsed = timezone.now() - lobby.start_time
        if time_elapsed.total_seconds() > (lobby.race.time_limit_minutes * 60):
            return JsonResponse({
                'success': False,
                'error': 'Time is up!'
            })
        
        if 'photo' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'No photo uploaded'
            })
        
        # Save the photo submission
        photo = request.FILES['photo']
        submission = Submission.objects.create(
            user=request.user,
            question=question,
            photo=photo,
            is_correct=False  # Admin will review later
        )
        
        # Get next question
        next_question = Question.objects.filter(
            zone=question.zone,
            created_at__gt=question.created_at
        ).first()
        
        # If no more questions in this zone, get first question of next zone
        if not next_question:
            next_zone = Zone.objects.filter(
                race=lobby.race,
                created_at__gt=question.zone.created_at
            ).first()
            
            if next_zone:
                next_question = next_zone.questions.first()
        
        next_url = reverse('start_race', args=[lobby_id])
        if next_question:
            next_url = f"{next_url}?question_id={next_question.id}"
        
        return JsonResponse({
            'success': True,
            'next_question_url': next_url
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })