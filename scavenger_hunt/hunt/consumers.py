import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Team, TeamMember, Lobby, TeamRaceProgress
import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from asgiref.sync import sync_to_async
from django.utils import timezone
import asyncio
from datetime import datetime
from django.db.models import Sum, Count
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)

class TeamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.team_id = self.scope['url_route']['kwargs']['team_id']
        self.team_group_name = f'team_{self.team_id}'
        self.player_name = self.scope.get('session', {}).get('player_name')
        logger.info(f"DEBUG: WebSocket connecting for team {self.team_id} with player {self.player_name}")

        await self.channel_layer.group_add(
            self.team_group_name,
            self.channel_name
        )
        await self.accept()
        logger.info(f"DEBUG: WebSocket connection accepted for team {self.team_id}, player {self.player_name}")

        # Send initial state
        await self.send_team_state()

    async def disconnect(self, close_code):
        logger.info(f"DEBUG: WebSocket disconnecting for team {self.team_id} with player {self.player_name}, code: {close_code}")
        
        if self.player_name:
            # Remove the team member
            logger.info(f"DEBUG: Removing player {self.player_name} from team {self.team_id} due to disconnect")
            await self.remove_team_member()
            
            # Broadcast the update to all connected clients
            logger.info(f"DEBUG: Broadcasting leave event for player {self.player_name} from team {self.team_id}")
            await self.channel_layer.group_send(
                self.team_group_name,
                {
                    'type': 'team_update',
                    'action': 'leave',
                    'player_name': self.player_name
                }
            )

        await self.channel_layer.group_discard(
            self.team_group_name,
            self.channel_name
        )
        logger.info(f"DEBUG: Channel {self.channel_name} removed from group {self.team_group_name}")

    @database_sync_to_async
    def remove_team_member(self):
        try:
            team = Team.objects.get(id=self.team_id)
            count, _ = TeamMember.objects.filter(
                team=team,
                role=self.player_name
            ).delete()
            logger.info(f"DEBUG: Removed {count} instances of player {self.player_name} from team {self.team_id} - {team.name}")
            
            # Get the lobby code to include in the broadcast
            lobby_code = None
            lobbies = team.participating_lobbies.all()
            for lobby in lobbies:
                lobby_code = lobby.code
                logger.info(f"DEBUG: Broadcasting team update to lobby {lobby.id} with code {lobby_code}")
                
                # Broadcast directly to lobby
                lobby_group_name = f'lobby_{lobby.id}'
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    lobby_group_name,
                    {
                        'type': 'team_member_left',
                        'member_id': self.player_name,
                        'team_id': team.id
                    }
                )
            
            # Also broadcast to available teams
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'available_teams',
                {
                    'type': 'teams_update',
                    'lobby_code': lobby_code
                }
            )
            logger.info(f"DEBUG: Broadcasted team update to available_teams with lobby_code {lobby_code}")
        except Exception as e:
            logger.error(f"DEBUG ERROR: Error removing team member: {e}")

    @database_sync_to_async
    def get_team_members(self):
        team = Team.objects.get(id=self.team_id)
        members = list(team.members.all().values_list('role', flat=True))
        logger.info(f"Retrieved team members for team {self.team_id}: {members}")
        return members

    @database_sync_to_async
    def get_team_state(self):
        team = Team.objects.prefetch_related('members').get(id=self.team_id)
        members = list(team.members.values('id', 'role'))
        return {
            'members': members,
            'team_name': team.name,
            'team_code': team.code
        }

    async def send_team_state(self):
        state = await self.get_team_state()
        await self.send(text_data=json.dumps({
            'type': 'team_update',
            'action': 'state',
            **state
        }))
        
        # Also notify the available_teams channel to stay in sync
        # Get the lobby code
        team = await database_sync_to_async(Team.objects.prefetch_related('participating_lobbies').get)(id=self.team_id)
        lobbies = await database_sync_to_async(lambda: list(team.participating_lobbies.all()))()
        
        if lobbies:
            for lobby in lobbies:
                lobby_code = await database_sync_to_async(lambda: lobby.code)()
                if lobby_code:
                    await self.channel_layer.group_send(
                        'available_teams',
                        {
                            'type': 'teams_update',
                            'lobby_code': lobby_code
                        }
                    )
                    
                    # Also update the lobby group
                    await self.channel_layer.group_send(
                        f'lobby_{lobby.id}',
                        {
                            'type': 'lobby_updated',
                            'lobby': {
                                'id': lobby.id,
                                'teams_updated': True
                            }
                        }
                    )

    async def team_update(self, event):
        # Forward the update to the WebSocket
        await self.send(text_data=json.dumps(event))

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            logger.info(f"DEBUG: WebSocket received data for team {self.team_id}: {data}")
            
            if data.get('action') == 'join':
                self.player_name = data.get('player_name')
                logger.info(f"DEBUG: Join request from player {self.player_name} for team {self.team_id}")
                
                if self.player_name:
                    # Try to create team member, which returns success/failure
                    creation_success = await self.create_team_member()
                    
                    if creation_success:
                        # Only broadcast if successfully created
                        logger.info(f"DEBUG: Successfully added {self.player_name} to team {self.team_id}, broadcasting join event")
                        await self.channel_layer.group_send(
                            self.team_group_name,
                            {
                                'type': 'team_update',
                                'action': 'join',
                                'player_name': self.player_name
                            }
                        )
                    else:
                        # Send error response back to this client only
                        logger.info(f"DEBUG: Failed to add {self.player_name} to team {self.team_id} (already exists), sending error")
                        await self.send(text_data=json.dumps({
                            'type': 'error',
                            'action': 'join',
                            'message': f'Player {self.player_name} is already in this team'
                        }))
            elif data.get('action') == 'leave':
                if self.player_name:
                    logger.info(f"DEBUG: Leave request from player {self.player_name} for team {self.team_id}")
                    await self.remove_team_member()
                    await self.channel_layer.group_send(
                        self.team_group_name,
                        {
                            'type': 'team_update',
                            'action': 'leave',
                            'player_name': self.player_name
                        }
                    )
            elif data.get('action') == 'get_state':
                logger.info(f"DEBUG: State request for team {self.team_id}")
                await self.send_team_state()
                
        except json.JSONDecodeError:
            logger.error(f"DEBUG ERROR: Invalid JSON received for team {self.team_id}")
        except Exception as e:
            logger.error(f"DEBUG ERROR: Error in receive for team {self.team_id}: {e}")
            # Send error response
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'An error occurred: {str(e)}'
            }))

    @database_sync_to_async
    def create_team_member(self):
        try:
            # Use a transaction to ensure atomic operation
            with transaction.atomic():
                team = Team.objects.get(id=self.team_id)
                logger.info(f"DEBUG: Attempting to add player {self.player_name} to team {self.team_id} - {team.name}")
                
                # Check if this player name already exists in the team - use select_for_update to lock the row
                existing_member = TeamMember.objects.select_for_update().filter(team=team, role=self.player_name).first()
                
                if existing_member:
                    # Already exists - don't create a duplicate
                    logger.info(f"DEBUG: Player {self.player_name} already exists in team {self.team_id}, not creating duplicate")
                    return False
                
                # Create new team member
                member = TeamMember.objects.create(team=team, role=self.player_name)
                logger.info(f"DEBUG: Created team member {self.player_name} (ID: {member.id}) for team {self.team_id} - {team.name}")
                
                # Get the lobby code to include in the broadcast
                lobby_code = None
                lobbies = team.participating_lobbies.all()
                for lobby in lobbies:
                    lobby_code = lobby.code
                    logger.info(f"DEBUG: Team {team.id} belongs to lobby {lobby.id} with code {lobby_code}")
                    
                    # Send team_member_joined event to the lobby
                    lobby_group_name = f'lobby_{lobby.id}'
                    channel_layer = get_channel_layer()
                    
                    # Send an event to the lobby group
                    async_to_sync(channel_layer.group_send)(
                        lobby_group_name,
                        {
                            'type': 'team_member_joined',
                            'member': {'role': self.player_name, 'id': member.id},
                            'team_id': str(team.id),
                            'team_name': team.name
                        }
                    )
                    logger.info(f"DEBUG: Sent team_member_joined event to lobby {lobby.id}")
                
                # Also broadcast to available teams
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    'available_teams',
                    {
                        'type': 'teams_update',
                        'lobby_code': lobby_code
                    }
                )
                logger.info(f"DEBUG: Sent teams_update event to available_teams channel with lobby_code {lobby_code}")
                
                return True
        except Exception as e:
            logger.error(f"DEBUG ERROR: Error creating team member: {e}")
            return False


class AvailableTeamsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Handle connection to available teams websocket"""
        self.group_name = 'available_teams'
        self.player_name = self.scope.get('session', {}).get('player_name')
        self.lobby_code = None  # Will be set when receiving a request
        
        logger.info(f"DEBUG: WebSocket connecting for available teams with player {self.player_name}, channel: {self.channel_name}")
        
        # Join the group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        logger.info(f"DEBUG: Added channel {self.channel_name} to group {self.group_name}")
        
        # Accept the connection
        await self.accept()
        logger.info(f"DEBUG: WebSocket connection accepted for available teams, channel: {self.channel_name}")
        
        # Send a heartbeat immediately to ensure connection
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to available teams WebSocket',
            'channel': self.channel_name
        }))
        logger.info(f"DEBUG: Sent connection confirmation to client")

    async def disconnect(self, close_code):
        """Handle disconnection"""
        logger.info(f"DEBUG: WebSocket disconnecting from available teams for player {self.player_name}, code: {close_code}, channel: {self.channel_name}")
        
        # Only remove player from teams if explicit disconnect is intended
        if close_code == 1000 and self.player_name:
            logger.info(f"DEBUG: Clean disconnect detected for player {self.player_name}, removing from teams")
            # Remove player from all teams they're in
            await self.remove_player_from_all_teams()
        else:
            logger.info(f"DEBUG: Non-clean disconnect (code {close_code}) for player {self.player_name}, not removing from teams")
        
        # Leave the group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        logger.info(f"DEBUG: Removed channel {self.channel_name} from group {self.group_name}")

    @database_sync_to_async
    def remove_player_from_all_teams(self):
        """Remove the player from all teams they're in"""
        try:
            deleted_count = TeamMember.objects.filter(role=self.player_name).delete()[0]
            logger.info(f"DEBUG: Removed player {self.player_name} from {deleted_count} teams")
            return deleted_count
        except Exception as e:
            logger.error(f"DEBUG ERROR: Error removing player from teams: {e}")
            return 0

    @database_sync_to_async
    def get_available_teams(self, lobby_code=None):
        """Get teams with their members, filtered by lobby code if provided"""
        teams_data = []
        
        try:
            # Filter teams by lobby code if provided
            if lobby_code:
                logger.info(f"DEBUG: Filtering teams by lobby code: {lobby_code}")
                try:
                    lobby = Lobby.objects.get(code=lobby_code)
                    teams = lobby.teams.prefetch_related('members').all()
                    logger.info(f"DEBUG: Found {teams.count()} teams in lobby {lobby.name} (ID: {lobby.id})")
                    
                    # Log team details
                    for team in teams:
                        member_count = team.members.count()
                        member_roles = [m.role for m in team.members.all()]
                        logger.info(f"DEBUG: Team {team.name} (ID: {team.id}) has {member_count} members: {member_roles}")
                        
                except Lobby.DoesNotExist:
                    logger.warning(f"DEBUG: Lobby with code {lobby_code} not found")
                    return []
            else:
                # Get all teams (fallback, should not happen with updated code)
                logger.warning("DEBUG: No lobby code provided, fetching all teams")
                teams = Team.objects.prefetch_related('members', 'participating_lobbies').all()
            
            for team in teams:
                lobbies = list(team.participating_lobbies.values_list('id', flat=True))
                # Get full member data to include IDs
                members = list(team.members.values('id', 'role'))
                
                teams_data.append({
                    'id': team.id,
                    'name': team.name,
                    'code': team.code,
                    'members': members,
                    'members_count': len(members),
                    'lobby_id': lobbies[0] if lobbies else None,
                })
                
            logger.info(f"DEBUG: Processed {len(teams_data)} teams for available_teams consumer")
        except Exception as e:
            logger.error(f"DEBUG ERROR: Error getting available teams: {e}")
            
        return teams_data

    async def send_teams_state(self, lobby_code=None):
        """Send the current state of teams filtered by lobby code"""
        logger.info(f"DEBUG: Fetching team state for lobby {lobby_code}")
        teams = await self.get_available_teams(lobby_code)
        logger.info(f"DEBUG: Sending {len(teams)} teams to client")
        
        await self.send(text_data=json.dumps({
            'type': 'teams_update',
            'teams': teams,
            'lobby_code': lobby_code,
            'timestamp': timezone.now().isoformat(),  # Add timestamp to help clients detect stale data
            'channel': self.channel_name
        }))
        logger.info(f"DEBUG: Sent teams state to client for lobby {lobby_code}")

    async def teams_update(self, event):
        """Handle teams update event"""
        logger.info(f"DEBUG: Received teams_update event: {event}")
        
        # Forward the update to the WebSocket only if it matches our lobby
        if not self.lobby_code or not event.get('lobby_code') or self.lobby_code == event.get('lobby_code'):
            logger.info(f"DEBUG: Processing teams_update for lobby {event.get('lobby_code')}, our lobby is {self.lobby_code}")
            
            # If a full teams list is not provided, fetch it
            if not event.get('teams'):
                logger.info(f"DEBUG: No teams data in event, fetching teams for lobby {event.get('lobby_code')}")
                teams = await self.get_available_teams(event.get('lobby_code'))
                event['teams'] = teams
                event['full_refresh'] = True
                logger.info(f"DEBUG: Added {len(teams)} teams to event")
            
            # Add channel info for debugging
            event['channel'] = self.channel_name
            
            await self.send(text_data=json.dumps(event))
            logger.info(f"DEBUG: Forwarded teams_update to client, channel: {self.channel_name}")
        else:
            logger.info(f"DEBUG: Ignoring teams_update for lobby {event.get('lobby_code')} as we're subscribed to {self.lobby_code}")

    async def receive(self, text_data):
        """Handle received messages"""
        try:
            data = json.loads(text_data)
            logger.info(f"DEBUG: Received data in AvailableTeamsConsumer, channel {self.channel_name}: {data}")
            
            if data.get('type') == 'request_update' or data.get('type') == 'ping':
                # Store the lobby code for future updates
                lobby_code = data.get('lobby_code', self.lobby_code)
                if lobby_code:
                    old_lobby = self.lobby_code
                    self.lobby_code = lobby_code
                    logger.info(f"DEBUG: Setting lobby_code for this connection from {old_lobby} to {self.lobby_code}, channel: {self.channel_name}")
                
                # Send filtered teams based on lobby code
                logger.info(f"DEBUG: Sending teams state for lobby {self.lobby_code}")
                await self.send_teams_state(self.lobby_code)
            
        except json.JSONDecodeError:
            logger.error(f"DEBUG ERROR: Failed to decode JSON in AvailableTeamsConsumer, channel: {self.channel_name}")
        except Exception as e:
            logger.error(f"DEBUG ERROR: Error in AvailableTeamsConsumer receive: {e}, channel: {self.channel_name}")
            # Send error response
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'An error occurred: {str(e)}',
                'channel': self.channel_name
            }))


class LobbyConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for lobbies
    Handles real-time updates related to a specific lobby
    """
    async def connect(self):
        self.lobby_id = self.scope['url_route']['kwargs']['lobby_id']
        self.lobby_group_name = f'lobby_{self.lobby_id}'
        self.player_name = self.scope.get('session', {}).get('player_name')
        
        # Additional detailed logging for WebSocket connections
        logger.info(f"WebSocket connecting for lobby {self.lobby_id}. Path: {self.scope['path']}, Player: {self.player_name}")
        logger.info(f"Adding channel {self.channel_name} to group {self.lobby_group_name}")
        
        # Join lobby group
        await self.channel_layer.group_add(
            self.lobby_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"WebSocket connection accepted for lobby {self.lobby_id}")
        
        # Get initial lobby state
        lobby = await self.get_lobby_data()
        
        # Send connection confirmation message to client
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': f'Connected to lobby {self.lobby_id} WebSocket',
            'lobby_id': self.lobby_id,
            'lobby': lobby,
            'timestamp': timezone.now().isoformat()
        }))

    async def disconnect(self, close_code):
        # Leave the lobby group
        logger.info(f"WebSocket disconnecting from lobby {self.lobby_id} with code: {close_code}")
        await self.channel_layer.group_discard(
            self.lobby_group_name,
            self.channel_name
        )
        logger.info(f"Channel {self.channel_name} removed from group {self.lobby_group_name}")

    async def receive(self, text_data):
        # Handle messages from clients
        try:
            data = json.loads(text_data)
            logger.info(f"Received message in lobby {self.lobby_id}: {data}")
            
            if data.get('action') == 'get_teams' or data.get('type') == 'request_update' or data.get('type') == 'ping':
                # Client requesting fresh team data
                lobby = await self.get_lobby_data()
                await self.send(text_data=json.dumps({
                    'type': 'lobby_data',
                    'lobby': lobby,
                    'timestamp': timezone.now().isoformat()
                }))
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received in lobby {self.lobby_id}")
        except Exception as e:
            logger.error(f"Error processing message in lobby {self.lobby_id}: {str(e)}")
            # Send error response
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'An error occurred: {str(e)}'
            }))

    @database_sync_to_async
    def get_lobby_data(self):
        """Get full lobby data including teams for initial state"""
        try:
            lobby = Lobby.objects.prefetch_related('teams', 'teams__members').get(id=self.lobby_id)
            
            # Format for JSON
            teams_data = []
            for team in lobby.teams.all():
                # Get full member data with IDs
                members = list(team.members.values('id', 'role'))
                
                teams_data.append({
                    'id': team.id,
                    'name': team.name,
                    'code': team.code,
                    'members_count': len(members),
                    'members': members
                })
            
            return {
                'id': lobby.id,
                'name': lobby.name,
                'code': lobby.code,
                'is_active': lobby.is_active,
                'hunt_started': lobby.hunt_started,
                'teams': teams_data,
                'teams_count': len(teams_data)
            }
        except Lobby.DoesNotExist:
            logger.error(f"Lobby {self.lobby_id} does not exist")
            return None
        except Exception as e:
            logger.error(f"Error getting lobby data: {str(e)}")
            return None
    
    async def team_joined(self, event):
        logger.info(f"Broadcasting team_joined event in lobby {self.lobby_id}: {event}")
        
        # Send message to WebSocket with team data
        try:
            await self.send(text_data=json.dumps({
                'type': 'team_joined',
                'team': event['team']
            }))
            logger.info(f"Successfully sent team_joined event to client")
        except Exception as e:
            logger.error(f"Error sending team_joined event: {str(e)}")

    async def team_left(self, event):
        logger.info(f"Broadcasting team_left event in lobby {self.lobby_id}: {event}")
        
        # Send message to WebSocket with team id
        try:
            await self.send(text_data=json.dumps({
                'type': 'team_left',
                'team_id': event['team_id']
            }))
            logger.info(f"Successfully sent team_left event to client")
        except Exception as e:
            logger.error(f"Error sending team_left event: {str(e)}")

    async def team_member_joined(self, event):
        logger.info(f"Broadcasting team_member_joined event in lobby {self.lobby_id}: {event}")
        
        # Send message to WebSocket with member data
        try:
            await self.send(text_data=json.dumps({
                'type': 'team_member_joined',
                'member': event['member'],
                'team_id': event['team_id'],
                'team_name': event['team_name']
            }))
            logger.info(f"Successfully sent team_member_joined event to client")
        except Exception as e:
            logger.error(f"Error sending team_member_joined event: {str(e)}")

    async def team_member_left(self, event):
        logger.info(f"Broadcasting team_member_left event in lobby {self.lobby_id}")
        
        # Send message to WebSocket with member data
        try:
            await self.send(text_data=json.dumps({
                'type': 'team_member_left',
                'member_id': event['member_id'],
                'team_id': event['team_id']
            }))
            logger.info(f"Successfully sent team_member_left event to client")
        except Exception as e:
            logger.error(f"Error sending team_member_left event: {str(e)}")

    async def lobby_updated(self, event):
        logger.info(f"Broadcasting lobby_updated event")
        
        # Send message to WebSocket with updated lobby data
        try:
            await self.send(text_data=json.dumps({
                'type': 'lobby_updated',
                'lobby': event['lobby']
            }))
            logger.info(f"Successfully sent lobby_updated event to client")
        except Exception as e:
            logger.error(f"Error sending lobby_updated event: {str(e)}")
    
    async def race_status_changed(self, event):
        logger.info(f"Broadcasting race_status_changed event in lobby {self.lobby_id}: {event}")
        
        # Send message to WebSocket with status data
        try:
            await self.send(text_data=json.dumps({
                'type': 'race_status_changed',
                'status': event['status'],
                'race_id': event['race_id']
            }))
            logger.info(f"Successfully sent race_status_changed event to client")
        except Exception as e:
            logger.error(f"Error sending race_status_changed event: {str(e)}")

    async def race_started(self, event):
        logger.info(f"Broadcasting race_started event in lobby {self.lobby_id}")
        
        # Send message to WebSocket with redirect URL
        try:
            await self.send(text_data=json.dumps({
                'type': 'race_started',
                'redirect_url': event['redirect_url']
            }))
            # Send it again after a delay to ensure delivery
            await asyncio.sleep(0.5)
            await self.send(text_data=json.dumps({
                'type': 'race_started',
                'redirect_url': event['redirect_url']
            }))
            logger.info(f"Successfully sent race_started event to client")
        except Exception as e:
            logger.error(f"Error sending race_started event: {str(e)}")
            
class RaceConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for race updates.
    Handles real-time updates when race status changes.
    """
    async def connect(self):
        self.race_id = self.scope['url_route']['kwargs']['race_id']
        self.race_group_name = f'race_{self.race_id}'
        
        # Join the race group
        await self.channel_layer.group_add(
            self.race_group_name,
            self.channel_name
        )
        
        # Accept the connection
        await self.accept()
        
        # Log for debugging
        logger.info(f"WebSocket CONNECTED: Race {self.race_id}, channel: {self.channel_name}")
        
        # Check if race is already started and notify client immediately
        try:
            from hunt.models import Race, Lobby
            race = await database_sync_to_async(Race.objects.get)(id=self.race_id)
            lobbies = await database_sync_to_async(lambda: list(Lobby.objects.filter(race=race, hunt_started=True)))()
            
            if lobbies:
                logger.info(f"Race {self.race_id} already started - sending immediate notification")
                redirect_url = f'/lobby/{lobbies[0].id}/question/1/'
                await self.send(text_data=json.dumps({
                    'type': 'race_started',
                    'race_id': self.race_id,
                    'redirect_url': redirect_url,
                    'message': 'Race has started! Redirecting to questions page.'
                }))
        except Exception as e:
            logger.error(f"Error checking race status on connect: {str(e)}")
    
    async def disconnect(self, close_code):
        # Leave the race group
        await self.channel_layer.group_discard(
            self.race_group_name,
            self.channel_name
        )
        logger.info(f"WebSocket DISCONNECTED: Race {self.race_id}")

    async def receive(self, text_data):
        # Process messages from clients
        try:
            data = json.loads(text_data)
            action = data.get('action')
            
            if action == 'check_status':
                # Check if race is already started
                from hunt.models import Race, Lobby
                race = await database_sync_to_async(Race.objects.get)(id=self.race_id)
                lobbies = await database_sync_to_async(lambda: list(Lobby.objects.filter(race=race, hunt_started=True)))()
                
                if lobbies:
                    redirect_url = f'/lobby/{lobbies[0].id}/question/1/'
                    await self.send(text_data=json.dumps({
                        'type': 'race_started',
                        'race_id': self.race_id,
                        'redirect_url': redirect_url,
                        'message': 'Race has started! Redirecting to questions page.'
                    }))
        except Exception as e:
            logger.error(f"Error in race consumer receive: {str(e)}")

    async def race_started(self, event):
        """
        Handles when a race is started and sends the redirect URL to clients
        This is called when a 'race_started' event is received through the group.
        """
        try:
            race_id = event.get('race_id', self.race_id)
            redirect_url = event.get('redirect_url', f'/race/{race_id}/questions/')
            message = event.get('message', 'Race has started! Redirecting to questions page.')
            
            # Log the event for debugging
            logger.info(f"RaceConsumer: Sending race_started event to client for race {race_id} on channel {self.channel_name}")
            
            # Send the event to the WebSocket client
            await self.send(text_data=json.dumps({
                'type': 'race_started',
                'race_id': race_id,
                'redirect_url': redirect_url,
                'message': message
            }))
            
            # Send it a second time after a brief delay to ensure delivery
            await asyncio.sleep(1)
            
            # Send again
            await self.send(text_data=json.dumps({
                'type': 'race_started',
                'race_id': race_id,
                'redirect_url': redirect_url,
                'message': message
            }))
            
            # And a third time after another delay
            await asyncio.sleep(2)
            await self.send(text_data=json.dumps({
                'type': 'race_started',
                'race_id': race_id,
                'redirect_url': redirect_url,
                'message': message
            }))
            
            logger.info(f"Successfully sent all race_started events to client for race {race_id}")
        except Exception as e:
            logger.error(f"Error in RaceConsumer.race_started: {str(e)}")

    async def team_members_update(self, event):
        """
        Handle team members update events in the general race channel
        This forwards team member updates to all clients watching the race
        """
        try:
            # Forward the team members update message to the client
            logger.info(f"RaceConsumer: Forwarding team members update for team {event.get('team_id')} in race {self.race_id}")
            
            await self.send(text_data=json.dumps({
                'type': 'team_members_update',
                'team_id': event.get('team_id'),
                'team_code': event.get('team_code'),
                'members': event.get('members', [])
            }))
            
            logger.info(f"Successfully forwarded team members update in race {self.race_id}")
        except Exception as e:
            logger.error(f"Error in RaceConsumer.team_members_update: {str(e)}")

class LeaderboardConsumer(AsyncWebsocketConsumer):
    """
    Consumer for the leaderboard page.
    Handles real-time updates for team scores across all lobbies.
    """
    
    async def connect(self):
        """
        Connect to the leaderboard group and send initial data.
        """
        self.group_name = "leaderboard"
        
        # Log connection
        logging.info(f"Leaderboard WebSocket connecting: {self.channel_name}")
        
        # Join leaderboard group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        logging.info(f"Leaderboard WebSocket connection accepted: {self.channel_name}")
        
        # Send initial leaderboard data
        await self.send_initial_leaderboard_data()
        
    async def disconnect(self, close_code):
        """
        Leave the leaderboard group.
        """
        logging.info(f"Leaderboard WebSocket disconnecting: {self.channel_name}, code: {close_code}")
        
        # Leave leaderboard group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """
        Receive message from WebSocket.
        """
        try:
            text_data_json = json.loads(text_data)
            action = text_data_json.get('action', '')
            
            logging.info(f"Leaderboard received message: {action}")
            
            if action == 'get_data':
                # Refresh leaderboard data
                await self.send_initial_leaderboard_data()
                
        except json.JSONDecodeError:
            logging.error(f"Invalid JSON received in LeaderboardConsumer: {text_data}")
        except Exception as e:
            logging.error(f"Error processing message in LeaderboardConsumer: {str(e)}")
    
    async def leaderboard_update(self, event):
        """Handle leaderboard update message"""
        try:
            # Extract data from event and prepare response
            data = {
                'type': 'leaderboard_update',
            }
            
            # Check if we have full teams data
            if 'teams' in event and isinstance(event['teams'], list):
                # We have a full teams list - use it directly
                data['teams'] = event['teams']
                logging.info(f"Sending complete teams list to leaderboard client: {len(event['teams'])} teams")
                
            # For full refresh with 'data' attribute (older format)
            elif 'action' in event and event['action'] == 'full_refresh' and 'data' in event:
                data['action'] = 'full_refresh'
                data['data'] = event['data']
                data['race_id'] = event.get('race_id')
                logging.info(f"Sending full refresh data to leaderboard client")
                
            # For single team update (older format)
            elif 'team_id' in event:
                data['action'] = event.get('action', 'update')
                data['team_id'] = event.get('team_id')
                data['team_name'] = event.get('team_name')
                data['race_id'] = event.get('race_id')
                logging.info(f"Sending single team update to leaderboard client: team_id={event.get('team_id')}")
                
            # Empty data case - trigger a refresh from client
            else:
                data['action'] = 'refresh'
                logging.info("Sending refresh request to leaderboard client")
            
            # Send message to WebSocket (async)
            await self.send(text_data=json.dumps(data))
        except Exception as e:
            logging.error(f"Error in leaderboard_update consumer: {str(e)}")
    
    async def send_initial_leaderboard_data(self):
        """
        Send initial leaderboard data to the client.
        """
        try:
            # Get leaderboard data
            teams = await database_sync_to_async(self.get_leaderboard_data)()
            
            # Send to WebSocket
            await self.send(text_data=json.dumps({
                'type': 'leaderboard_update',
                'teams': teams
            }))
            
            logging.info(f"Initial leaderboard data sent: {len(teams)} teams")
        except Exception as e:
            logging.error(f"Error sending initial leaderboard data: {str(e)}")
            # Send error message
        await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to load leaderboard data'
            }))
    
    def get_leaderboard_data(self):
        """
        Get all team data for the leaderboard.
        """
        # Get all teams with their score from all lobbies
        teams_data = []
        
        try:
            # Get all active lobbies - FIXED: Use is_active instead of status
            lobbies = Lobby.objects.filter(is_active=True)
            
            for lobby in lobbies:
                # Skip lobbies without a race
                if not lobby.race:
                    continue
                    
                # Get teams in this lobby with extra validation
                valid_teams = []
                try:
                    # Use prefetch_related to optimize query
                    teams = Team.objects.filter(participating_lobbies=lobby).prefetch_related('race_progress')
                    
                    # Verify each team exists and is valid
                    for team in teams:
                        try:
                            # Verify team still exists in this lobby
                            if team.participating_lobbies.filter(id=lobby.id).exists():
                                valid_teams.append(team)
                        except Exception as e:
                            logging.error(f"Error validating team {team.id} in lobby {lobby.id}: {str(e)}")
                except Exception as e:
                    logging.error(f"Error getting teams for lobby {lobby.id}: {str(e)}")
                    continue  # Skip to next lobby if we hit an error
                
                for team in valid_teams:
                    try:
                        # Get team's progress in the race
                        progress = TeamRaceProgress.objects.filter(team=team, race=lobby.race).first()
                        if progress:
                            total_points = progress.total_points
                        else:
                            # If no progress exists, score is 0
                            total_points = 0
                        
                        # Ensure we're using a valid team name (not an ID or object reference)
                        # This fixes the "Team: 30" display issue
                        team_name = team.name
                        if not team_name or team_name == "None" or not isinstance(team_name, str):
                            team_name = f"Team {team.id}"
                        
                        teams_data.append({
                            'id': team.id,
                            'name': team_name,
                            'team_name': team_name,  # Add backup field for the client-side fix
                            'score': total_points,
                            'lobby_id': str(lobby.id),
                            'lobby_name': lobby.race.name if lobby.race else 'Unknown Race'
                        })
                    except Exception as e:
                        logging.error(f"Error processing team {team.id} for leaderboard: {str(e)}")
            
            # Sort by score
            teams_data.sort(key=lambda x: x['score'], reverse=True)
            
            logging.info(f"Generated leaderboard data with {len(teams_data)} teams")
            return teams_data
        except Exception as e:
            logging.error(f"Error getting leaderboard data: {str(e)}")
            return []

class RaceUpdatesConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for race updates specific to a team.
    Handles real-time updates for a team in a race.
    """
    async def connect(self):
        # Extract parameters from URL
        try:
            self.race_id = self.scope['url_route']['kwargs']['race_id']
            self.team_code = self.scope['url_route']['kwargs']['team_code']
            self.race_team_group_name = f'race_updates_{self.race_id}_{self.team_code}'
            
            # Log the connection attempt
            logger.info(f"WebSocket connection attempt: Race Updates for race {self.race_id}, team {self.team_code}")
            
            # Join both the race-specific and team-specific groups
            await self.channel_layer.group_add(
                self.race_team_group_name,
                self.channel_name
            )
            
            # Also join the general race group
            self.race_group_name = f'race_{self.race_id}'
            await self.channel_layer.group_add(
                self.race_group_name,
                self.channel_name
            )
            
            # Accept the connection
            await self.accept()
            
            # Log for debugging
            logger.info(f"WebSocket CONNECTED: Race Updates for race {self.race_id}, team {self.team_code}, channel: {self.channel_name}")
            
            # Initialize last activity timestamp
            self.lastWebSocketActivity = timezone.now()
            
            # Send initial state
            await self.send_initial_state()
            
        except Exception as e:
            logger.error(f"Error in RaceUpdatesConsumer connect: {str(e)}")
            # Accept connection so we can send error message
            await self.accept()
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error_type': 'connection_error',
                'message': f"Error connecting: {str(e)}"
            }))
            # Close the connection after sending error
            await self.close(code=1011)

    async def disconnect(self, close_code):
        # Leave the race-team specific group
        await self.channel_layer.group_discard(
            self.race_team_group_name,
            self.channel_name
        )
        
        # Leave the general race group
        await self.channel_layer.group_discard(
            self.race_group_name,
            self.channel_name
        )
        
        logger.info(f"WebSocket DISCONNECTED: Race Updates for race {self.race_id}, team {self.team_code}")

    async def receive(self, text_data):
        """Handle messages from clients"""
        try:
            data = json.loads(text_data)
            
            # Handle heartbeat messages
            if data.get('type') == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': datetime.now().isoformat()
                }))
                # Update the last activity timestamp
                self.lastWebSocketActivity = timezone.now()
                return
                
            # Handle request for initial state
            if data.get('type') == 'request_race_update':
                await self.send_initial_state()
                return
                
            # Handle other messages as needed
            logger.info(f"Received message in race updates consumer: {data}")
            
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received in RaceUpdatesConsumer")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error_type': 'invalid_json',
                'message': 'Invalid JSON data received'
            }))
        except Exception as e:
            logger.error(f"Error in RaceUpdatesConsumer receive: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error_type': 'receive_error',
                'message': str(e)
            }))
    
    @database_sync_to_async
    def get_race_data(self):
        """Get race data including team progress"""
        try:
            from hunt.models import Race, Team, TeamRaceProgress, Question, Answer
            
            # Get the race - add specific exception handling
            try:
                race = Race.objects.get(id=self.race_id)
            except Race.DoesNotExist:
                logger.error(f"Race with ID {self.race_id} does not exist")
                return {
                    'error': True,
                    'message': f"Race with ID {self.race_id} does not exist",
                    'error_type': 'race_not_found'
                }
            
            # Get the team - add specific exception handling
            try:
                team = Team.objects.get(code=self.team_code)
            except Team.DoesNotExist:
                logger.error(f"Team with code {self.team_code} does not exist")
                return {
                    'error': True,
                    'message': f"Team with code {self.team_code} does not exist",
                    'error_type': 'team_not_found'
                }
            
            # Get team's progress in this race
            try:
                progress = TeamRaceProgress.objects.get(team=team, race=race)
                total_points = progress.total_points
                current_question_index = progress.current_question_index
            except TeamRaceProgress.DoesNotExist:
                total_points = 0
                current_question_index = 0
            
            # Get team members
            members = list(team.members.values('id', 'role'))
            
            # Get questions and answers for this team
            questions_data = {}
            for question in Question.objects.filter(race=race):
                try:
                    answer = Answer.objects.get(team=team, question=question)
                    questions_data[str(question.id)] = {
                        'attempts': answer.attempts,
                        'points_awarded': answer.points_awarded,
                        'answered_correctly': answer.answered_correctly,
                        'photo_uploaded': answer.photo_uploaded
                    }
                except Answer.DoesNotExist:
                    questions_data[str(question.id)] = {
                        'attempts': 0,
                        'points_awarded': 0,
                        'answered_correctly': False,
                        'photo_uploaded': False
                    }
            
            # Get race timer data
            remaining_seconds = None
            if race.time_limit_minutes and race.started_at:
                elapsed_seconds = (timezone.now() - race.started_at).total_seconds()
                time_limit_seconds = race.time_limit_minutes * 60
                remaining_seconds = max(0, time_limit_seconds - elapsed_seconds)
            
            return {
                'race_id': race.id,
                'race_name': race.name,
                'team_id': team.id,
                'team_name': team.name,
                'team_code': team.code,
                'total_points': total_points,
                'current_question_index': current_question_index,
                'members': members,
                'question_data': questions_data,
                'remaining_seconds': remaining_seconds,
                'race_status': 'active' if race.is_active else 'inactive'
            }
        except Exception as e:
            logger.error(f"Error getting race data: {str(e)}")
            return {
                'error': True,
                'message': str(e),
                'error_type': 'general_error'
            }
    
    async def send_initial_state(self):
        """Send initial state to the client"""
        try:
            race_data = await self.get_race_data()
            if race_data:
                # Check if there was an error
                if race_data.get('error'):
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'error_type': race_data.get('error_type', 'unknown'),
                        'message': race_data.get('message', 'An unknown error occurred')
                    }))
                else:
                    await self.send(text_data=json.dumps({
                        'type': 'race_update',
                        'data': race_data
                    }))
        except Exception as e:
            logger.error(f"Error sending initial state: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error_type': 'initial_state_error',
                'message': str(e)
            }))
    
    # Event handlers from the channel layer
    async def score_update(self, event):
        """Handle score update event"""
        await self.send(text_data=json.dumps({
            'type': 'score_update',
            'score': event.get('score', 0),
            'team_id': event.get('team_id')
        }))
    
    async def question_update(self, event):
        """Handle question update event"""
        await self.send(text_data=json.dumps({
            'type': 'question_update',
            'question_data': event.get('question_data', {}),
            'question_id': event.get('question_id')
        }))
    
    async def race_time_update(self, event):
        """Handle race timer update event"""
        await self.send(text_data=json.dumps({
            'type': 'race_time_update',
            'remaining_seconds': event.get('remaining_seconds')
        }))
    
    async def navigate_to_question(self, event):
        """Handle navigation event"""
        await self.send(text_data=json.dumps({
            'type': 'navigate_to_question',
            'question_index': event.get('question_index')
        }))
    
    async def race_status_update(self, event):
        """Handle race status update event"""
        await self.send(text_data=json.dumps({
            'type': 'race_status_update',
            'status': event.get('status'),
            'message': event.get('message', '')
        }))
    
    async def team_members_update(self, event):
        """Handle team members update event"""
        await self.send(text_data=json.dumps({
            'type': 'team_members_update',
            'members': event.get('members', [])
        }))
    
    async def race_complete(self, event):
        """Handle race completion event"""
        await self.send(text_data=json.dumps({
            'type': 'race_complete',
            'redirect_url': event.get('redirect_url', '/race-complete/')
        }))
    
    # This handler is to ensure we also receive events from the general race group
    async def race_started(self, event):
        """Handle race started event from the general race group"""
        await self.send(text_data=json.dumps({
            'type': 'race_started',
            'race_id': event.get('race_id', self.race_id),
            'redirect_url': event.get('redirect_url', f'/race/{self.race_id}/questions/'),
            'message': event.get('message', 'Race has started! Redirecting to questions page.')
        })) 