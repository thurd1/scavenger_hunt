from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json

from .models import Team, TeamMember, Lobby, Race, TeamProgress, Question, Zone

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
    if action == 'post_add':
        channel_layer = get_channel_layer()
        
        if not reverse:
            # A team was added to lobbies (from Team side)
            team = instance
            lobby_ids = pk_set
            
            for lobby_id in lobby_ids:
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
        else:
            # A lobby was added to teams (from Lobby side)
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
            
    elif action == 'post_remove':
        channel_layer = get_channel_layer()
        
        if not reverse:
            # A team was removed from lobbies
            team = instance
            lobby_ids = pk_set
            
            for lobby_id in lobby_ids:                
                print(f"SIGNAL: Team {team.name} left lobby {lobby_id}")
                
                # Send to the lobby group
                async_to_sync(channel_layer.group_send)(
                    f'lobby_{lobby_id}',
                    {
                        'type': 'team_left',
                        'team_id': team.id
                    }
                )
        else:
            # A lobby was removed from teams
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
                    print(f"SIGNAL ERROR in team_left: {str(e)}") 