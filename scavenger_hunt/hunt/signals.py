from django.db.models.signals import post_save, m2m_changed, post_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import logging
from django.db import transaction
from django.db import connection
from django.db import models

from .models import Team, TeamMember, Lobby, Race, TeamProgress, Question, Zone, TeamRaceProgress, TeamAnswer

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Team)
def team_created(sender, instance, created, **kwargs):
    """
    Signal handler to notify connected clients when a team is created
    """
    if created:
        print(f"SIGNAL: Team {instance.name} (ID: {instance.id}) created")
        
        # Get the lobby this team belongs to
        lobbies = instance.participating_lobbies.all()
        
        # For each lobby, send a WebSocket message
        for lobby in lobbies:
            channel_layer = get_channel_layer()
            
            # Format the team data for the WebSocket message
            team_data = {
                'id': instance.id,
                'name': instance.name,
                'code': instance.code,
                'members_count': instance.members.count(),
                'members': [{'role': member.role} for member in instance.members.all()]
            }
            
            print(f"SIGNAL: Broadcasting team_joined event to lobby_{lobby.id}")
            
            # Send to the lobby group
            async_to_sync(channel_layer.group_send)(
                f'lobby_{lobby.id}',
                {
                    'type': 'team_joined',
                    'team': team_data
                }
            )

@receiver(post_save, sender=TeamMember)
def team_member_created(sender, instance, created, **kwargs):
    """
    Signal handler to notify connected clients when a team member is created
    """
    if created and instance.team:
        print(f"SIGNAL: New member {instance.role} joined team {instance.team.name}")
        
        # Get the lobby this team belongs to
        lobbies = instance.team.participating_lobbies.all()
        
        # For each lobby, send a WebSocket message
        for lobby in lobbies:
            channel_layer = get_channel_layer()
            
            # Format the member data
            member_data = {
                'role': instance.role,
                'team_name': instance.team.name
            }
            
            # Send to the lobby group
            async_to_sync(channel_layer.group_send)(
                f'lobby_{lobby.id}',
                {
                    'type': 'team_member_joined',
                    'member': member_data,
                    'team_id': instance.team.id,
                    'team_name': instance.team.name
                }
            )

@receiver(post_save, sender=Lobby)
def lobby_status_changed(sender, instance, created, **kwargs):
    """
    Signal handler to notify connected clients when a lobby's status changes
    """
    if not created:  # Only for updates, not creation
        print(f"SIGNAL: Lobby {instance.name} (ID: {instance.id}) status changed to: hunt_started={instance.hunt_started}")
        
        channel_layer = get_channel_layer()
        
        # First, broadcast race status change to lobby members
        async_to_sync(channel_layer.group_send)(
            f'lobby_{instance.id}',
            {
                'type': 'race_status_changed',
                'status': 'started' if instance.hunt_started else 'inactive',
                'race_id': instance.race.id if instance.race else None
            }
        )
        
        # If hunt started, also broadcast race_started event to race channel
        if instance.hunt_started and instance.race:
            print(f"SIGNAL: Race {instance.race.id} started from lobby {instance.id}")
            async_to_sync(channel_layer.group_send)(
                f'race_{instance.race.id}',
                {
                    'type': 'race_started',
                    'redirect_url': f'/race/{instance.race.id}/questions/'
                }
            )

@receiver(m2m_changed, sender=Team.participating_lobbies.through)
def team_lobby_association_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
    """
    Signal handler to notify connected clients when a team joins or leaves a lobby
    """
    try:
        if action == 'post_add':
            channel_layer = get_channel_layer()
            
            if not reverse:
                # A team was added to lobbies (from Team side)
                if not isinstance(instance, Team):
                    # Don't show a warning, but handle appropriately based on instance type
                    if isinstance(instance, Lobby):
                        # Handle the case where a Lobby instance is passed
                        lobby = instance
                        team_ids = pk_set
                        
                        for team_id in team_ids:
                            try:
                                team = Team.objects.get(id=team_id)
                                # Format the team data
                                team_data = {
                                    'id': team.id,
                                    'name': team.name,
                                    'code': team.code,
                                    'members_count': team.members.count(),
                                    'members': [{'role': member.role} for member in team.members.all()]
                                }
                                
                                # Send to the lobby group
                                async_to_sync(channel_layer.group_send)(
                                    f'lobby_{lobby.id}',
                                    {
                                        'type': 'team_joined',
                                        'team': team_data
                                    }
                                )
                            except Exception as e:
                                print(f"ERROR in team_lobby_association_changed (Lobby instance): {str(e)}")
                    return
                
                team = instance
                lobby_ids = pk_set
                
                for lobby_id in lobby_ids:
                    try:
                        # Format the team data
                        team_data = {
                            'id': team.id,
                            'name': team.name,
                            'code': team.code,
                            'members_count': team.members.count(),
                            'members': [{'role': member.role} for member in team.members.all()]
                        }
                        
                        print(f"SIGNAL: Team {team.name} joined lobby {lobby_id}")
                        
                        # Send to the lobby group
                        async_to_sync(channel_layer.group_send)(
                            f'lobby_{lobby_id}',
                            {
                                'type': 'team_joined',
                                'team': team_data
                            }
                        )
                    except Exception as e:
                        print(f"ERROR in team_lobby_association_changed (forward direction): {str(e)}")
            else:
                # A lobby was added to teams (from Lobby side)
                if not isinstance(instance, Lobby):
                    # Don't show a warning, but handle appropriately based on instance type
                    if isinstance(instance, Team):
                        # Handle the case where a Team instance is passed
                        team = instance
                        lobby_ids = pk_set
                        
                        for lobby_id in lobby_ids:
                            try:
                                lobby = Lobby.objects.get(id=lobby_id)
                                team_data = {
                                    'id': team.id,
                                    'name': team.name,
                                    'code': team.code,
                                    'members_count': team.members.count(),
                                    'members': [{'role': member.role} for member in team.members.all()]
                                }
                                
                                # Send to the lobby group
                                async_to_sync(channel_layer.group_send)(
                                    f'lobby_{lobby.id}',
                                    {
                                        'type': 'team_joined',
                                        'team': team_data
                                    }
                                )
                            except Exception as e:
                                print(f"ERROR in team_lobby_association_changed (Team instance): {str(e)}")
                    return
                
                lobby = instance
                team_ids = pk_set
                
                for team_id in team_ids:
                    try:
                        # Explicitly get the Team object to use its methods
                        team = Team.objects.get(id=team_id)
                        
                        # Format the team data
                        team_data = {
                            'id': team.id,
                            'name': team.name,
                            'code': team.code,
                            'members_count': team.members.count(),
                            'members': [{'role': member.role} for member in team.members.all()]
                        }
                        
                        print(f"SIGNAL: Team {team.name} joined lobby {lobby.id}")
                        
                        # Send to the lobby group
                        async_to_sync(channel_layer.group_send)(
                            f'lobby_{lobby.id}',
                            {
                                'type': 'team_joined',
                                'team': team_data
                            }
                        )
                    except Team.DoesNotExist:
                        print(f"SIGNAL ERROR: Team with ID {team_id} not found")
                    except Exception as e:
                        print(f"SIGNAL ERROR in team_joined: {str(e)}")
                
        elif action == 'post_remove':
            channel_layer = get_channel_layer()
            
            if not reverse:
                # A team was removed from lobbies
                if not isinstance(instance, Team):
                    print(f"WARNING: Expected Team instance but got {type(instance).__name__}")
                    return
                    
                team = instance
                lobby_ids = pk_set
                
                for lobby_id in lobby_ids:                
                    try:
                        print(f"SIGNAL: Team {team.name} left lobby {lobby_id}")
                        
                        # Send to the lobby group
                        async_to_sync(channel_layer.group_send)(
                            f'lobby_{lobby_id}',
                            {
                                'type': 'team_left',
                                'team_id': team.id
                            }
                        )
                    except Exception as e:
                        print(f"ERROR in team_left (forward direction): {str(e)}")
            else:
                # A lobby was removed from teams
                if not isinstance(instance, Lobby):
                    print(f"WARNING: Expected Lobby instance but got {type(instance).__name__}")
                    return
                    
                lobby = instance
                team_ids = pk_set
                
                for team_id in team_ids:
                    try:
                        print(f"SIGNAL: Team {team_id} left lobby {lobby.id}")
                        
                        # Send to the lobby group
                        async_to_sync(channel_layer.group_send)(
                            f'lobby_{lobby.id}',
                            {
                                'type': 'team_left',
                                'team_id': team_id
                            }
                        )
                    except Exception as e:
                        print(f"ERROR in team_left (reverse direction): {str(e)}")
    except Exception as e:
        print(f"CRITICAL ERROR in team_lobby_association_changed: {str(e)}") 

@receiver(post_save, sender=TeamRaceProgress)
def team_score_changed(sender, instance, created, **kwargs):
    """
    Signal handler to notify connected clients when a team's score changes
    """
    try:
        team = instance.team
        race = instance.race
        
        if not team or not race:
            logging.warning(f"TeamRaceProgress missing team or race: team_id={getattr(team, 'id', None)}, race_id={getattr(race, 'id', None)}")
            return
            
        logging.info(f"SIGNAL: Team {team.name} score updated to {instance.total_points} in race {race.name}")
        
        # Send update to the leaderboard
        channel_layer = get_channel_layer()
        
        # Get all teams to refresh the entire leaderboard
        # This is more reliable than just updating a single team's score
        teams_data = []
        
        # Get all active lobbies - Use is_active instead of status
        lobbies = Lobby.objects.filter(is_active=True)
        
        for lobby in lobbies:
            # Skip lobbies without a race
            if not lobby.race:
                continue
                
            # Get teams in this lobby
            lobby_teams = Team.objects.filter(participating_lobbies=lobby)
            
            for team_obj in lobby_teams:
                try:
                    # Get team's progress in the race
                    progress = TeamRaceProgress.objects.get(team=team_obj, race=lobby.race)
                    total_points = progress.total_points
                except TeamRaceProgress.DoesNotExist:
                    # If no progress exists, score is 0
                    total_points = 0
                
                teams_data.append({
                    'id': team_obj.id,
                    'name': team_obj.name,
                    'score': total_points,
                    'lobby_id': str(lobby.id),
                    'lobby_name': lobby.race.name if lobby.race else 'Unknown Race'
                })
        
        # Sort by score
        teams_data.sort(key=lambda x: x['score'], reverse=True)
        
        # Send update to leaderboard group
        async_to_sync(channel_layer.group_send)(
            'leaderboard',
            {
                'type': 'leaderboard_update',
                'teams': teams_data
            }
        )
        
        # Also send to the race-specific group if it exists
        async_to_sync(channel_layer.group_send)(
            f'race_{race.id}',
            {
                'type': 'team_score_update',
                'team_id': team.id,
                'team_name': team.name,
                'score': instance.total_points
            }
        )
        
        logging.info(f"SIGNAL: Sent leaderboard update with {len(teams_data)} teams")
    except Exception as e:
        logging.error(f"ERROR in team_score_changed signal: {str(e)}", exc_info=True) 

@receiver(post_save, sender=TeamAnswer)
def update_team_race_progress(sender, instance, created, **kwargs):
    """
    Signal handler to update TeamRaceProgress when a team answers correctly
    and trigger leaderboard updates
    """
    try:
        # Only process if this is a correct answer with points
        if not instance.answered_correctly or instance.points_awarded <= 0:
            return
            
        team = instance.team
        question = instance.question
        
        # Find the race from the question's zone
        if not question.zone or not question.zone.race:
            logging.warning(f"Question {question.id} has no zone or race - can't update progress")
            return
            
        race = question.zone.race
        
        logging.info(f"Updating race progress for team {team.name} in race {race.name}, adding {instance.points_awarded} points")
        
        # Update or create TeamRaceProgress
        progress, created = TeamRaceProgress.objects.get_or_create(
            team=team,
            race=race,
            defaults={
                'total_points': instance.points_awarded,
                'current_question_index': 0
            }
        )
        
        if not created:
            # Add these points to the total
            progress.total_points = TeamAnswer.objects.filter(
                team=team,
                question__zone__race=race,
                answered_correctly=True
            ).aggregate(models.Sum('points_awarded'))['points_awarded__sum'] or 0
            
            # Save to trigger post_save signal on TeamRaceProgress
            progress.save()
            
        # Also directly trigger a leaderboard update via WebSocket for immediate feedback
        channel_layer = get_channel_layer()
        
        # Get all teams to refresh the entire leaderboard
        teams_data = []
        
        # Get all active lobbies
        lobbies = Lobby.objects.filter(is_active=True)
        
        for lobby in lobbies:
            # Skip lobbies without a race
            if not lobby.race:
                continue
                
            # Get teams in this lobby
            lobby_teams = Team.objects.filter(participating_lobbies=lobby)
            
            for team_obj in lobby_teams:
                try:
                    # Get team's progress in the race
                    team_progress = TeamRaceProgress.objects.get(team=team_obj, race=lobby.race)
                    total_points = team_progress.total_points
                except TeamRaceProgress.DoesNotExist:
                    # If no progress exists, score is 0
                    total_points = 0
                
                teams_data.append({
                    'id': team_obj.id,
                    'name': team_obj.name,
                    'score': total_points,
                    'lobby_id': str(lobby.id),
                    'lobby_name': lobby.race.name if lobby.race else 'Unknown Race'
                })
        
        # Sort by score
        teams_data.sort(key=lambda x: x['score'], reverse=True)
        
        # Send update to leaderboard group
        async_to_sync(channel_layer.group_send)(
            'leaderboard',
            {
                'type': 'leaderboard_update',
                'teams': teams_data
            }
        )
        
        logging.info(f"SIGNAL: Sent leaderboard update from TeamAnswer with {len(teams_data)} teams")
        
    except Exception as e:
        logging.error(f"ERROR in update_team_race_progress signal: {str(e)}", exc_info=True)

# Signal handler for when a lobby is deleted
@receiver(post_delete, sender=Lobby)
def cleanup_after_lobby_deletion(sender, instance, **kwargs):
    """Clean up orphaned teams and related data when a lobby is deleted"""
    try:
        logger.info(f"Lobby {instance.id} was deleted. Running cleanup...")
        
        # Get channel layer for broadcasting updates
        channel_layer = get_channel_layer()
        
        # Send update to leaderboard to refresh data
        try:
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
            
        # Find orphaned teams (not associated with any lobby)
        orphaned_teams = Team.objects.filter(participating_lobbies__isnull=True)
        team_ids = list(orphaned_teams.values_list('id', flat=True))
        logger.info(f"Found {len(team_ids)} orphaned teams to clean up: {team_ids}")
        
        if not team_ids:
            logger.info("No orphaned teams to delete.")
            return
            
        # Use raw SQL to avoid cascade issues with non-existent tables
        with connection.cursor() as cursor:
            # Get tables in the database
            tables = connection.introspection.table_names()
            
            for team_id in team_ids:
                try:
                    logger.info(f"Deleting orphaned team {team_id} with raw SQL")
                    
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
                    
                    logger.info(f"Successfully deleted orphaned team {team_id}")
                except Exception as e:
                    logger.error(f"Error deleting orphaned team {team_id}: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error in cleanup_after_lobby_deletion: {str(e)}") 