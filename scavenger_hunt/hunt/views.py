from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import Team, Riddle, Submission, Lobby, TeamMember
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

logger = logging.getLogger(__name__)

@login_required
def create_lobby(request):
    if request.method == 'POST':
        form = LobbyForm(request.POST)
        if form.is_valid():
            lobby = form.save()
            return render(request, 'lobby_code_display.html', {'lobby': lobby})
    else:
        form = LobbyForm()
    return render(request, 'create_lobby.html', {'form': form})

@login_required
def lobby_details(request, lobby_id):
    lobby = get_object_or_404(Lobby, id=lobby_id)
    teams = lobby.teams.all()
    
    context = {
        'lobby': lobby,
        'teams': teams,
    }
    return render(request, 'lobby_details.html', context)

class LobbyDetailsView(DetailView):
    model = Lobby
    template_name = 'lobby_details.html'
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
            return render(request, 'team_options.html', {'lobby': lobby})
            
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
            return render(request, 'login.html', {
                'error': 'Invalid credentials',
                'form': {'username': username}
            })
    return render(request, 'login.html')

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
        print(f"Saving player name to session: {player_name}")
        request.session['player_name'] = player_name
        request.session.modified = True
        print(f"Player name in session after save: {request.session.get('player_name')}")
        
        lobby_code = request.session.get('lobby_code')
        print(f"Lobby code in session: {lobby_code}")
        
        lobby = get_object_or_404(Lobby, code=lobby_code)
        return render(request, 'team_options.html', {'lobby': lobby})
    return redirect('join_game_session')

def join_existing_team(request, lobby_id):
    if request.method == 'POST':
        team_code = request.POST.get('team_code')
        try:
            team = Team.objects.get(code=team_code, lobbies=lobby_id)
            player_name = request.session.get('player_name')
            logger.info(f"Player {player_name} attempting to join team {team.id}")
            
            if player_name:
                existing_member = TeamMember.objects.filter(
                    team=team,
                    role=player_name
                ).first()
                
                if not existing_member:
                    team_member = TeamMember.objects.create(
                        team=team,
                        role=player_name
                    )
                    messages.success(request, f'Successfully joined team {team.name}!')
                    
                    members = list(team.team_members.values_list('role', flat=True))
                    logger.info(f"Broadcasting team update for team {team.id}: {members}")
                    
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f'team_{team.id}',
                        {
                            'type': 'team_update',
                            'members': members
                        }
                    )
                else:
                    messages.info(request, 'You are already a member of this team!')
            return redirect('team_dashboard', team_id=team.id)
        except Team.DoesNotExist:
            messages.error(request, 'Invalid team code. Please try again.')
    
    lobby = get_object_or_404(Lobby, id=lobby_id)
    return render(request, 'join_team.html', {'lobby': lobby})

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})

def register_team(request):
    return render(request, 'register_team.html')

def riddle_list(request):
    return render(request, 'riddle_list.html')

def riddle_detail(request):
    return render(request, 'riddle_list.html')

def team_list(request):
    teams = Team.objects.all().prefetch_related('team_members')
    return render(request, 'team_list.html', {'teams': teams})

def assign_riddles(request):
    return HttpResponse("Riddles. wow.")
    
def manage_riddls(request):
    return render(request, 'manage_riddles.html')
    
def leaderboard(request):
    return render(request, 'leaderboard.html')

def team_details(request, team_id):
    team = Team.objects.get(id=team_id)
    return render(request, 'team_details.html', {'team': team})

@login_required
def dashboard(request):
    teams = Team.objects.all()
    return render(request, "dashboard.html", {"teams": teams})

@login_required
def team_detail(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    riddles = Riddle.objects.filter(team=team)
    return render(request, "team_detail.html", {"team": team, "riddles": riddles})

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
            player_name = request.session.get('player_name')
            if player_name:
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
    
    return render(request, 'create_team.html', {
        'form': form,
        'lobby': lobby
    })

def team_dashboard(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    team_members = TeamMember.objects.filter(team=team)
    
    print(f"Team ID: {team_id}")
    print(f"Team name: {team.name}")
    print(f"Raw SQL query: {str(team_members.query)}")
    print(f"Number of team members: {team_members.count()}")
    print(f"Team members found: {[m.role for m in team_members]}")

    all_members = TeamMember.objects.all()
    print(f"All TeamMembers in database: {[m.role for m in all_members]}")
    
    context = {
        'team': team,
        'team_members': team_members
    }
    
    return render(request, 'team_dashboard.html', context)

@login_required
def leader_dashboard(request):
    return render(request, 'leader_dashboard.html')

@login_required
def manage_lobbies(request):
    lobbies = Lobby.objects.all().order_by('-created_at')
    return render(request, 'manage_lobbies.html', {'lobbies': lobbies})

@login_required
def toggle_lobby(request, lobby_id):
    if request.method == 'POST':
        lobby = get_object_or_404(Lobby, id=lobby_id)
        lobby.is_active = not lobby.is_active
        lobby.save()
        messages.success(request, f'Lobby "{lobby.name}" has been {"activated" if lobby.is_active else "deactivated"}.')
    return redirect('manage_lobbies')

@login_required
def delete_lobby(request, lobby_id):
    if request.method == 'POST':
        lobby = get_object_or_404(Lobby, id=lobby_id)
        lobby_name = lobby.name
        lobby.delete()
        messages.success(request, f'Lobby "{lobby_name}" has been deleted.')
    return redirect('manage_lobbies')

def delete_team(request, team_id):
    if request.method == 'POST':
        team = get_object_or_404(Team, id=team_id)
        team_name = team.name
        team.delete()
        messages.success(request, f'Team "{team_name}" has been deleted.')
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
    return render(request, 'edit_team.html', {'team': team})

def view_team(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    return render(request, 'view_team.html', {
        'team': team,
        'members': team.team_members.all()
    })
