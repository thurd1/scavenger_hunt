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
from django.views.decorators.http import require_POST
from django.utils import timezone

logger = logging.getLogger(__name__)

@login_required
def create_lobby(request):
    if request.method == 'POST':
        form = LobbyForm(request.POST)
        if form.is_valid():
            lobby = form.save()
            return render(request, 'hunt/lobby_code_display.html', {'lobby': lobby})
    else:
        form = LobbyForm()
    return render(request, 'hunt/create_lobby.html', {'form': form})

@login_required
def lobby_details(request, lobby_id):
    lobby = get_object_or_404(Lobby, id=lobby_id)
    teams = lobby.teams.all()
    
    context = {
        'lobby': lobby,
        'teams': teams,
    }
    return render(request, 'hunt/lobby_details.html', context)

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
        print(f"Saving player name to session: {player_name}")  # Debug print
        request.session['player_name'] = player_name
        request.session.modified = True  # Force session save
        print(f"Player name in session after save: {request.session.get('player_name')}")  # Verify save
        
        lobby_code = request.session.get('lobby_code')
        print(f"Lobby code in session: {lobby_code}")  # Debug print
        
        lobby = get_object_or_404(Lobby, code=lobby_code)
        return render(request, 'hunt/team_options.html', {'lobby': lobby})
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
                    
                    # Get updated list of team members
                    members = list(team.team_members.values_list('role', flat=True))
                    logger.info(f"Broadcasting team update for team {team.id}: {members}")
                    
                    # Broadcast team update
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
    return render(request, 'hunt/register.html', {'form': form})

def register_team(request):
    return render(request, 'hunt/register_team.html')

def riddle_list(request):
    return render(request, 'hunt/riddle_list.html')

def riddle_detail(request):
    return render(request, 'hunt/riddle_list.html')

def team_list(request):
    teams = Team.objects.all().prefetch_related('team_members')
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
    team = get_object_or_404(Team, id=team_id)
    team_members = TeamMember.objects.filter(team=team)
    
    print(f"Team ID: {team_id}")
    print(f"Team name: {team.name}")
    print(f"Raw SQL query: {str(team_members.query)}")  # Print the SQL query
    print(f"Number of team members: {team_members.count()}")
    print(f"Team members found: {[m.role for m in team_members]}")
    
    # Try to get all TeamMember objects for debugging
    all_members = TeamMember.objects.all()
    print(f"All TeamMembers in database: {[m.role for m in all_members]}")
    
    context = {
        'team': team,
        'team_members': team_members
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
    return render(request, 'hunt/edit_team.html', {'team': team})

def view_team(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    return render(request, 'hunt/view_team.html', {
        'team': team,
        'members': team.team_members.all()
    })

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

@login_required
def manage_riddles(request):
    if request.method == 'POST':
        race_name = request.POST.get('race_name')
        time_limit = request.POST.get('time_limit')
        start_location = request.POST.get('start_location')
        zone_count = int(request.POST.get('zoneCount', 0))
        
        # Convert time_limit from string format to minutes (integer)
        try:
            # Check if the time_limit is in HH:MM:SS format
            if ':' in time_limit:
                # Split the time string and convert to minutes
                time_parts = time_limit.split(':')
                if len(time_parts) == 3:  # HH:MM:SS format
                    hours = int(time_parts[0])
                    minutes = int(time_parts[1])
                    seconds = int(time_parts[2])
                    # Convert to total minutes (round up if there are seconds)
                    total_minutes = hours * 60 + minutes
                    if seconds > 0:
                        total_minutes += 1  # Round up to the next minute
                    time_limit = total_minutes
                elif len(time_parts) == 2:  # MM:SS format
                    minutes = int(time_parts[0])
                    seconds = int(time_parts[1])
                    # Convert to total minutes (round up if there are seconds)
                    total_minutes = minutes
                    if seconds > 0:
                        total_minutes += 1  # Round up to the next minute
                    time_limit = total_minutes
            else:
                # If it's already a number (e.g., "90"), convert to integer
                time_limit = int(time_limit)
                
            print(f"Converted time_limit to {time_limit} minutes")
            
        except ValueError as e:
            messages.error(request, f"Invalid time format. Please use HH:MM:SS format or enter minutes directly. Error: {str(e)}")
            return redirect('manage_riddles')
        
        # Create the race
        try:
            race = Race.objects.create(
                name=race_name,
                time_limit=time_limit,  # Now this is an integer in minutes
                start_location=start_location,
                created_by=request.user,
                is_active=False  # Default to inactive
            )
            
            # Process zones and questions
            for i in range(1, zone_count + 1):
                # Get questions and answers for this zone
                questions = request.POST.getlist(f'zone-{i}-questions[]')
                answers = request.POST.getlist(f'zone-{i}-answers[]')
                
                if questions and answers and len(questions) == len(answers):
                    # Create the zone
                    zone = Zone.objects.create(
                        race=race,
                        number=i  # Set the zone number explicitly
                    )
                    
                    # Create all questions for this zone
                    for j in range(len(questions)):
                        question_text = questions[j]
                        answer_text = answers[j]
                        
                        # Create question with appropriate field name
                        try:
                            question = Question(zone=zone, answer=answer_text)
                            
                            # Try to find the right field for question text
                            available_fields = [f.name for f in Question._meta.get_fields()]
                            
                            field_set = False
                            for field_name in ['question_text', 'content', 'text', 'question', 'body', 'prompt']:
                                if field_name in available_fields:
                                    setattr(question, field_name, question_text)
                                    field_set = True
                                    break
                            
                            # If no field was set, use any non-standard field
                            if not field_set:
                                for field in Question._meta.get_fields():
                                    if field.name not in ['id', 'zone', 'answer']:
                                        setattr(question, field.name, question_text)
                                        field_set = True
                                        break
                            
                            question.save()
                        except Exception as e:
                            messages.warning(request, f"Error creating question in zone {i}: {str(e)}")
            
            messages.success(request, f"Race '{race_name}' created successfully with {zone_count} zones.")
            return redirect('manage_riddles')
            
        except Exception as e:
            messages.error(request, f"Error creating race: {str(e)}")
            return redirect('manage_riddles')
    
    # Get all races for display
    races = Race.objects.filter(created_by=request.user).order_by('-created_at')
    
    context = {
        'races': races
    }
    
    return render(request, 'hunt/manage_riddles.html', context)

@login_required
def race_detail(request, race_id):
    race = get_object_or_404(Race, id=race_id)
    
    # Check if user is authorized to view this race
    if race.created_by != request.user:
        messages.error(request, "You don't have permission to view this race.")
        return redirect('manage_riddles')
    
    # Process form submissions
    if request.method == 'POST':
        # Edit race details
        if 'edit_race' in request.POST:
            race.name = request.POST.get('race_name')
            race.start_location = request.POST.get('start_location')
            race.time_limit = request.POST.get('time_limit')
            race.save()
            messages.success(request, "Race details updated successfully.")
            return redirect('race_detail', race_id=race.id)
        
        # Add new zone
        elif 'add_zone' in request.POST:
            try:
                initial_question = request.POST.get('initial_question')
                initial_answer = request.POST.get('initial_answer')
                
                # First calculate the next zone number for this race
                try:
                    # Get the highest zone number for this race
                    highest_zone = Zone.objects.filter(race=race).order_by('-number').first()
                    next_zone_number = 1
                    if highest_zone:
                        next_zone_number = highest_zone.number + 1
                    
                    print(f"Creating zone #{next_zone_number} for race ID {race.id}")
                    
                    # Create new zone with the calculated number
                    zone = Zone()
                    zone.race = race
                    zone.number = next_zone_number  # Set the zone number
                    zone.save()
                    print(f"Created zone ID {zone.id} with number {zone.number}")
                except Exception as e:
                    error_msg = f"Error creating zone: {str(e)}"
                    print(error_msg)
                    messages.error(request, error_msg)
                    return redirect('race_detail', race_id=race.id)
                
                # Try to create the question
                try:
                    question = Question()
                    question.zone = zone
                    question.answer = initial_answer
                    
                    # Try to set the question text with multiple field names
                    available_fields = [f.name for f in Question._meta.get_fields()]
                    print(f"Available Question fields: {available_fields}")
                    
                    field_set = False
                    for field_name in ['question_text', 'content', 'text', 'question', 'body', 'prompt']:
                        if field_name in available_fields:
                            print(f"Setting question field '{field_name}' to '{initial_question}'")
                            setattr(question, field_name, initial_question)
                            field_set = True
                            break
                    
                    # If no field was set, use any non-standard field
                    if not field_set:
                        for field in Question._meta.get_fields():
                            if field.name not in ['id', 'zone', 'answer']:
                                print(f"Using fallback field '{field.name}' for question text")
                                setattr(question, field.name, initial_question)
                                field_set = True
                                break
                    
                    # Save the question
                    question.save()
                    print(f"Saved question with ID {question.id}")
                    
                except Exception as e:
                    error_msg = f"Zone created but error adding question: {str(e)}"
                    print(error_msg)
                    messages.warning(request, error_msg)
                    # Attempt to delete the zone since the question failed
                    try:
                        zone.delete()
                        messages.warning(request, "Deleted zone since question creation failed")
                    except:
                        pass
                    # Don't redirect yet - we still want to show all zones
                
                messages.success(request, "New zone added successfully.")
                
            except Exception as e:
                error_msg = f"Unexpected error adding zone: {str(e)}"
                print(error_msg)
                messages.error(request, error_msg)
            
            # In any case, we want to show the page with all zones
            # so we continue through to the display code below
        
        # Add question to existing zone
        elif 'add_question' in request.POST:
            try:
                zone_id = request.POST.get('zone_id')
                question_text = request.POST.get('question_text')
                question_answer = request.POST.get('question_answer')
                
                zone = get_object_or_404(Zone, id=zone_id, race=race)
                print(f"Adding question to zone ID {zone.id}")
                
                # Create the question with similar robust approach
                question = Question()
                question.zone = zone
                question.answer = question_answer
                
                # Try to set the question field
                available_fields = [f.name for f in Question._meta.get_fields()]
                field_set = False
                for field_name in ['question_text', 'content', 'text', 'question', 'body', 'prompt']:
                    if field_name in available_fields:
                        setattr(question, field_name, question_text)
                        field_set = True
                        break
                
                # If no field was set, use fallback
                if not field_set:
                    for field in Question._meta.get_fields():
                        if field.name not in ['id', 'zone', 'answer']:
                            setattr(question, field.name, question_text)
                            field_set = True
                            break
                
                question.save()
                messages.success(request, "Question added successfully.")
                
            except Exception as e:
                error_msg = f"Error adding question: {str(e)}"
                print(error_msg)
                messages.error(request, error_msg)
    
    # Get all zones for this race - explicitly print count for debugging
    zones = Zone.objects.filter(race=race).order_by('id')
    print(f"Found {zones.count()} zones for race ID {race.id}")
    for z in zones:
        print(f"Zone ID: {z.id}, Race ID: {z.race.id}")
    
    # Build a structured data set with zones and their questions
    zones_with_questions = []
    
    for zone in zones:
        questions = Question.objects.filter(zone=zone)
        print(f"Zone {zone.id} has {questions.count()} questions")
        
        # For each question, get all of its fields and values
        question_data = []
        for q in questions:
            q_data = {'id': q.id}
            q_data['answer'] = q.answer
            
            # Try to get the question text field
            for field_name in ['question_text', 'content', 'text', 'question', 'body', 'prompt']:
                if hasattr(q, field_name):
                    q_data['question_text'] = getattr(q, field_name, '')
                    break
            
            # If we still don't have question text, get all non-standard fields
            if 'question_text' not in q_data:
                for field in q._meta.fields:
                    field_name = field.name
                    if field_name not in ['id', 'zone', 'answer']:
                        q_data['question_text'] = getattr(q, field_name, '')
                        break
            
            question_data.append(q_data)
        
        zone_data = {
            'id': zone.id,
            'questions': question_data
        }
        zones_with_questions.append(zone_data)
    
    # Print final count for debugging
    print(f"Sending {len(zones_with_questions)} zones to template")
    
    context = {
        'race': race,
        'zones': zones_with_questions,
        'zones_count': len(zones_with_questions),
    }
    
    return render(request, 'hunt/race_detail.html', context)

@login_required
def assign_riddles(request):
    return render(request, 'hunt/assign_riddles.html')

@login_required
def leaderboard(request):
    return render(request, 'hunt/leaderboard.html')

@login_required
def team_list(request):
    return render(request, 'hunt/team_list.html')

@login_required
def register_team(request):
    return render(request, 'hunt/register_team.html')

@login_required
def create_lobby(request):
    return render(request, 'hunt/create_lobby.html')

@login_required
def manage_lobbies(request):
    return render(request, 'hunt/manage_lobbies.html')

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
def delete_race(request, race_id):
    race = get_object_or_404(Race, id=race_id)
    
    # Check if the user is authorized to delete this race
    if race.created_by != request.user:
        messages.error(request, "You don't have permission to delete this race.")
        return redirect('manage_riddles')
    
    if request.method == 'POST' and request.POST.get('delete_race') == 'true':
        race_name = race.name
        # Delete the race
        race.delete()
        messages.success(request, f"Race '{race_name}' has been deleted successfully.")
    
    return redirect('manage_riddles')
