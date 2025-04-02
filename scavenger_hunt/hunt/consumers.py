import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Team, TeamMember, Lobby
import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from asgiref.sync import sync_to_async
from django.utils import timezone
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class TeamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.team_id = self.scope['url_route']['kwargs']['team_id']
        self.team_group_name = f'team_{self.team_id}'
        self.player_name = self.scope.get('session', {}).get('player_name')
        logger.info(f"WebSocket connecting for team {self.team_id} with player {self.player_name}")

        await self.channel_layer.group_add(
            self.team_group_name,
            self.channel_name
        )
        await self.accept()

        # Send initial state
        await self.send_team_state()

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnected for team {self.team_id} with player {self.player_name}")
        
        if self.player_name:
            # Remove the team member
            await self.remove_team_member()
            
            # Broadcast the update to all connected clients
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

    @database_sync_to_async
    def remove_team_member(self):
        try:
            team = Team.objects.get(id=self.team_id)
            TeamMember.objects.filter(
                team=team,
                role=self.player_name
            ).delete()
            logger.info(f"Removed player {self.player_name} from team {self.team_id}")
            
            # Get the lobby code to include in the broadcast
            lobby_code = None
            lobby = team.participating_lobbies.first()
            if lobby:
                lobby_code = lobby.code
            
            # Also broadcast to available teams
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'available_teams',
                {
                    'type': 'teams_update',
                    'lobby_code': lobby_code
                }
            )
        except Exception as e:
            logger.error(f"Error removing team member: {e}")

    @database_sync_to_async
    def get_team_members(self):
        team = Team.objects.get(id=self.team_id)
        members = list(team.members.all().values_list('role', flat=True))
        logger.info(f"Retrieved team members for team {self.team_id}: {members}")
        return members

    @database_sync_to_async
    def get_team_state(self):
        team = Team.objects.prefetch_related('members').get(id=self.team_id)
        return {
            'members': list(team.members.values_list('role', flat=True)),
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

    async def team_update(self, event):
        # Forward the update to the WebSocket
        await self.send(text_data=json.dumps(event))

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            logger.info(f"WebSocket received data: {data}")
            
            if data.get('action') == 'join':
                self.player_name = data.get('player_name')
                if self.player_name:
                    await self.create_team_member()
                    await self.channel_layer.group_send(
                        self.team_group_name,
                        {
                            'type': 'team_update',
                            'action': 'join',
                            'player_name': self.player_name
                        }
                    )
            elif data.get('action') == 'leave':
                if self.player_name:
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
                await self.send_team_state()
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
        except Exception as e:
            logger.error(f"Error in receive: {e}")

    @database_sync_to_async
    def create_team_member(self):
        try:
            team = Team.objects.get(id=self.team_id)
            if not TeamMember.objects.filter(team=team, role=self.player_name).exists():
                TeamMember.objects.create(team=team, role=self.player_name)
                logger.info(f"Created team member {self.player_name} for team {self.team_id}")
                
                # Get the lobby code to include in the broadcast
                lobby_code = None
                lobby = team.participating_lobbies.first()
                if lobby:
                    lobby_code = lobby.code
                
                # Also broadcast to available teams
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    'available_teams',
                    {
                        'type': 'teams_update',
                        'lobby_code': lobby_code
                    }
                )
        except Exception as e:
            logger.error(f"Error creating team member: {e}")


class AvailableTeamsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Handle connection to available teams websocket"""
        self.group_name = 'available_teams'
        self.player_name = self.scope.get('session', {}).get('player_name')
        self.lobby_code = None  # Will be set when receiving a request
        
        logger.info(f"WebSocket connecting for available teams with player {self.player_name}")
        
        # Join the group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        # Accept the connection
        await self.accept()

    async def disconnect(self, close_code):
        """Handle disconnection"""
        logger.info(f"WebSocket disconnected from available teams for player {self.player_name}")
        
        if self.player_name:
            # Remove player from all teams they're in
            await self.remove_player_from_all_teams()
        
        # Leave the group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    @database_sync_to_async
    def remove_player_from_all_teams(self):
        """Remove the player from all teams they're in"""
        try:
            deleted_count = TeamMember.objects.filter(role=self.player_name).delete()[0]
            logger.info(f"Removed player {self.player_name} from {deleted_count} teams")
        except Exception as e:
            logger.error(f"Error removing player from teams: {e}")

    @database_sync_to_async
    def get_available_teams(self, lobby_code=None):
        """Get teams with their members, filtered by lobby code if provided"""
        teams_data = []
        
        try:
            # Filter teams by lobby code if provided
            if lobby_code:
                logger.info(f"Filtering teams by lobby code: {lobby_code}")
                try:
                    lobby = Lobby.objects.get(code=lobby_code)
                    teams = lobby.teams.prefetch_related('members').all()
                    logger.info(f"Found {teams.count()} teams in lobby {lobby.name}")
                except Lobby.DoesNotExist:
                    logger.warning(f"Lobby with code {lobby_code} not found")
                    return []
            else:
                # Get all teams (fallback, should not happen with updated code)
                logger.warning("No lobby code provided, fetching all teams")
                teams = Team.objects.prefetch_related('members', 'participating_lobbies').all()
            
            for team in teams:
                lobbies = list(team.participating_lobbies.values_list('id', flat=True))
                members = list(team.members.all().values('role'))
                
                teams_data.append({
                    'id': team.id,
                    'name': team.name,
                    'code': team.code,
                    'members': members,
                    'lobby_id': lobbies[0] if lobbies else None,
                })
        except Exception as e:
            logger.error(f"Error getting available teams: {e}")
            
        return teams_data

    async def send_teams_state(self, lobby_code=None):
        """Send the current state of teams filtered by lobby code"""
        teams = await self.get_available_teams(lobby_code)
        await self.send(text_data=json.dumps({
            'type': 'teams_update',
            'teams': teams,
            'lobby_code': lobby_code
        }))

    async def teams_update(self, event):
        """Handle teams update event"""
        # Forward the update to the WebSocket only if it matches our lobby
        if not self.lobby_code or not event.get('lobby_code') or self.lobby_code == event.get('lobby_code'):
            await self.send(text_data=json.dumps(event))

    async def receive(self, text_data):
        """Handle received messages"""
        try:
            data = json.loads(text_data)
            logger.info(f"Received data in AvailableTeamsConsumer: {data}")
            
            if data.get('type') == 'request_update':
                # Store the lobby code for future updates
                self.lobby_code = data.get('lobby_code')
                logger.info(f"Setting lobby_code for this connection: {self.lobby_code}")
                
                # Send filtered teams based on lobby code
                await self.send_teams_state(self.lobby_code)
            
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON in AvailableTeamsConsumer")
        except Exception as e:
            logger.error(f"Error in AvailableTeamsConsumer receive: {e}")


class LobbyConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Handle connection to lobby websocket"""
        self.lobby_id = self.scope['url_route']['kwargs']['lobby_id']
        self.lobby_group_name = f'lobby_{self.lobby_id}'
        self.player_name = self.scope.get('session', {}).get('player_name')
        
        logger.info(f"WebSocket connecting for lobby {self.lobby_id} with player {self.player_name}")
        
        # Join the group
        await self.channel_layer.group_add(
            self.lobby_group_name,
            self.channel_name
        )
        
        # Accept the connection
        await self.accept()
        
        # Send initial state
        await self.send_lobby_state()

    async def disconnect(self, close_code):
        """Handle disconnection from lobby"""
        logger.info(f"WebSocket disconnected from lobby {self.lobby_id} for player {self.player_name}")
        
        # Leave the group
        await self.channel_layer.group_discard(
            self.lobby_group_name,
            self.channel_name
        )

    @database_sync_to_async
    def get_lobby_state(self):
        """Get the current state of the lobby"""
        try:
            lobby = Lobby.objects.get(id=self.lobby_id)
            teams = []
            
            for team in lobby.teams.all().prefetch_related('members'):
                team_data = {
                    'id': team.id,
                    'name': team.name,
                    'code': team.code,
                    'members': list(team.members.all().values('role'))
                }
                teams.append(team_data)
            
            return {
                'lobby_id': lobby.id,
                'name': lobby.name,
                'code': lobby.code,
                'teams': teams,
                'race_in_progress': lobby.race is not None and lobby.hunt_started,
                'start_time': lobby.start_time.isoformat() if lobby.start_time else None,
                'time_limit_minutes': lobby.race.time_limit_minutes if lobby.race else 60
            }
        except Lobby.DoesNotExist:
            logger.error(f"Lobby {self.lobby_id} not found")
            return {
                'error': 'Lobby not found'
            }
        except Exception as e:
            logger.error(f"Error getting lobby state: {e}")
            return {
                'error': str(e)
            }

    async def send_lobby_state(self):
        """Send the current state of the lobby"""
        state = await self.get_lobby_state()
        await self.send(text_data=json.dumps({
            'type': 'lobby_update',
            **state
        }))

    async def lobby_update(self, event):
        """Handle lobby update event"""
        # Forward the update to the WebSocket
        await self.send(text_data=json.dumps(event))

    async def race_started(self, event):
        """Handle race started event"""
        # Forward the race started event to the WebSocket
        await self.send(text_data=json.dumps({
            'type': 'race_started',
            'redirect_url': event.get('redirect_url')
        }))
        
        # Also send updated lobby state
        await self.send_lobby_state()

    async def receive(self, text_data):
        """Handle received messages"""
        try:
            data = json.loads(text_data)
            logger.info(f"Received data in LobbyConsumer: {data}")
            
            if data.get('type') == 'request_update':
                await self.send_lobby_state()
            
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON in LobbyConsumer")
        except Exception as e:
            logger.error(f"Error in LobbyConsumer receive: {e}")

    @database_sync_to_async
    def get_lobby_data(self):
        """Get detailed lobby data"""
        lobby = Lobby.objects.get(id=self.lobby_id)
        return {
            'id': lobby.id,
            'name': lobby.name,
            'code': lobby.code,
            'hunt_started': lobby.hunt_started,
            'start_time': lobby.start_time.isoformat() if lobby.start_time else None,
            'race': {
                'id': lobby.race.id,
                'name': lobby.race.name,
                'time_limit_minutes': lobby.race.time_limit_minutes
            } if lobby.race else None
        }

# Add this new consumer class
class RaceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Get race ID from URL
        self.race_id = self.scope['url_route']['kwargs']['race_id']
        self.race_group_name = f'race_{self.race_id}'
        
        # Join race group
        await self.channel_layer.group_add(
            self.race_group_name,
            self.channel_name
        )
        
        await self.accept()
        logging.info(f"WebSocket connected to race {self.race_id}")
    
    async def disconnect(self, close_code):
        # Leave race group
        await self.channel_layer.group_discard(
            self.race_group_name,
            self.channel_name
        )
        logging.info(f"WebSocket disconnected from race {self.race_id} with code {close_code}")
    
    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': datetime.now().isoformat()
                }))
            
            logging.info(f"Received message in race {self.race_id}: {text_data_json}")
        except json.JSONDecodeError:
            logging.error(f"Failed to decode JSON in race {self.race_id}: {text_data}")
        except Exception as e:
            logging.error(f"Error in race {self.race_id} receive: {str(e)}")
    
    async def race_started(self, event):
        """Event handler for when a race starts"""
        # Construct redirect URL
        redirect_url = f"/race/{self.race_id}/questions/"
        
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'race_started',
            'race_id': self.race_id,
            'redirect_url': redirect_url,
            'message': 'Race has started! Get ready to answer questions.'
        }))
        
        logging.info(f"Sent race_started event to client in race {self.race_id}")

# Add this new consumer class
class LobbiesConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for managing multiple lobbies in real-time.
    This consumer doesn't track a specific lobby, but instead broadcasts
    updates about all lobbies to connected clients.
    """
    
    async def connect(self):
        # Group name for all lobbies management connections
        self.group_name = 'lobbies_management'
        
        logger.info(f"WebSocket connecting to lobbies management")
        
        # Join the group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        # Accept the connection
        await self.accept()
        
        # Send current lobbies data
        await self.send_lobbies_data()
    
    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnected from lobbies management with code {close_code}")
        
        # Leave the group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
    
    @database_sync_to_async
    def get_all_lobbies_data(self):
        """Get data for all lobbies"""
        lobbies_data = []
        
        try:
            lobbies = Lobby.objects.all().prefetch_related('teams', 'race')
            
            for lobby in lobbies:
                lobbies_data.append({
                    'id': lobby.id,
                    'name': lobby.name if hasattr(lobby, 'name') else f"Lobby {lobby.id}",
                    'code': lobby.code,
                    'is_active': lobby.is_active,
                    'hunt_started': lobby.hunt_started,
                    'teams_count': lobby.teams.count(),
                    'race_id': lobby.race.id if lobby.race else None,
                    'race_name': lobby.race.name if lobby.race else None,
                    'created_at': lobby.created_at.isoformat() if lobby.created_at else None
                })
            
            return lobbies_data
        except Exception as e:
            logger.error(f"Error getting lobbies data: {e}")
            return []
    
    async def send_lobbies_data(self):
        """Send current lobbies data to connected client"""
        lobbies = await self.get_all_lobbies_data()
        
        await self.send(text_data=json.dumps({
            'type': 'lobbies_update',
            'lobbies': lobbies
        }))
    
    async def receive(self, text_data):
        """Handle received messages"""
        try:
            data = json.loads(text_data)
            logger.info(f"Received data in LobbiesConsumer: {data}")
            
            # Handle message types
            if data.get('type') == 'request_update':
                await self.send_lobbies_data()
            
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON in LobbiesConsumer")
        except Exception as e:
            logger.error(f"Error in LobbiesConsumer receive: {e}")
    
    async def lobby_update(self, event):
        """Handle lobby update event - broadcast to all clients"""
        # Forward the update to the client
        await self.send(text_data=json.dumps(event))
    
    async def team_joined(self, event):
        """Handle team joined event"""
        lobby_id = event.get('lobby_id')
        
        # Get the current accurate team count from the database
        team_count = await self.get_lobby_team_count(lobby_id)
        
        # Update the event with the accurate count
        event['team_count'] = team_count
        
        # Forward the event with accurate data
        await self.send(text_data=json.dumps(event))
    
    @database_sync_to_async
    def get_lobby_team_count(self, lobby_id):
        """Get accurate team count for a lobby"""
        try:
            lobby = Lobby.objects.get(id=lobby_id)
            return lobby.teams.count()
        except Lobby.DoesNotExist:
            logger.error(f"Lobby {lobby_id} not found when trying to get team count")
            return 0
        except Exception as e:
            logger.error(f"Error getting team count for lobby {lobby_id}: {e}")
            return 0
    
    async def race_started(self, event):
        """Handle race started event"""
        await self.send(text_data=json.dumps(event)) 