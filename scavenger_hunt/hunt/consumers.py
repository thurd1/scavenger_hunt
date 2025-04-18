import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Team, TeamMember, Lobby, TeamRaceProgress
import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from asgiref.sync import sync_to_async
from django.utils import timezone
from django.db import models
import asyncio
from datetime import datetime
from django.db.models import Sum, Count

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
    """
    WebSocket consumer for lobbies
    Handles real-time updates related to a specific lobby
    """
    async def connect(self):
        self.lobby_id = self.scope['url_route']['kwargs']['lobby_id']
        self.lobby_group_name = f'lobby_{self.lobby_id}'
        
        # Additional detailed logging for WebSocket connections
        logger.info(f"WebSocket connecting for lobby {self.lobby_id}. Path: {self.scope['path']}")
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
            'lobby': lobby
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
            
            if data.get('action') == 'get_teams':
                # Client requesting fresh team data
                lobby = await self.get_lobby_data()
                await self.send(text_data=json.dumps({
                    'type': 'lobby_data',
                    'lobby': lobby
                }))
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received in lobby {self.lobby_id}")
        except Exception as e:
            logger.error(f"Error processing message in lobby {self.lobby_id}: {str(e)}")

    @database_sync_to_async
    def get_lobby_data(self):
        """Get full lobby data including teams for initial state"""
        try:
            lobby = Lobby.objects.prefetch_related('teams', 'teams__members').get(id=self.lobby_id)
            
            # Format for JSON
            teams_data = []
            for team in lobby.teams.all():
                teams_data.append({
                    'id': team.id,
                    'name': team.name,
                    'code': team.code,
                    'members_count': team.members.count(),
                    'members': list(team.members.values('id', 'role'))
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
    WebSocket consumer for team-specific race updates.
    Provides real-time updates about score, question status, and timer for a specific team in a race.
    """
    async def connect(self):
        self.race_id = self.scope['url_route']['kwargs']['race_id']
        self.team_code = self.scope['url_route']['kwargs']['team_code']
        self.race_team_group_name = f'race_updates_{self.race_id}_{self.team_code}'
        
        # Also join the general race group
        self.race_group_name = f'race_{self.race_id}'
        
        logger.info(f"WebSocket connecting for race updates: Race {self.race_id}, Team {self.team_code}")
        
        # Join the team-specific race group
        await self.channel_layer.group_add(
            self.race_team_group_name,
            self.channel_name
        )
        
        # Also join the general race group
        await self.channel_layer.group_add(
            self.race_group_name,
            self.channel_name
        )
        
        # Accept the connection
        await self.accept()
        
        # Get and send initial state
        try:
            await self.send_initial_state()
        except Exception as e:
            logger.error(f"Error in race consumer connect: {str(e)}")
    
    async def disconnect(self, close_code):
        # Leave the race groups
        await self.channel_layer.group_discard(
            self.race_team_group_name,
            self.channel_name
        )
        
        await self.channel_layer.group_discard(
            self.race_group_name,
            self.channel_name
        )
        
        logger.info(f"WebSocket disconnected: Race {self.race_id}, Team {self.team_code}")
    
    async def receive(self, text_data):
        """Handle messages from the client"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'request_race_update':
                # Client is requesting updated data
                await self.send_initial_state()
            
        except Exception as e:
            logger.error(f"Error in race consumer receive: {str(e)}")
    
    @database_sync_to_async
    def get_initial_state(self):
        """Get the current state of the team's progress in the race"""
        try:
            # Get the team and race
            from hunt.models import Team, Race, TeamAnswer, TeamRaceProgress
            
            team = Team.objects.get(code=self.team_code)
            race = Race.objects.get(id=self.race_id)
            
            # Get the team's progress in this race
            progress = TeamRaceProgress.objects.filter(team=team, race=race).first()
            
            # Get all the team's answers for this race
            answers = TeamAnswer.objects.filter(
                team=team,
                question__zone__race=race
            ).select_related('question')
            
            # Format the answers data
            question_data = {}
            for answer in answers:
                question_data[answer.question.id] = {
                    'attempts': answer.attempts,
                    'points_awarded': answer.points_awarded,
                    'answered_correctly': answer.answered_correctly,
                    'photo_uploaded': answer.photo_uploaded
                }
            
            # Calculate total score
            total_score = answers.filter(answered_correctly=True).aggregate(
                total=models.Sum('points_awarded'))['total'] or 0
            
            # Get race start time and time limit
            start_time = None
            time_limit_minutes = 0
            remaining_seconds = 0
            
            if race:
                # Get start time from the first lobby with this race that has started
                from hunt.models import Lobby
                lobby = Lobby.objects.filter(race=race, hunt_started=True).first()
                if lobby and lobby.hunt_start_time:
                    start_time = lobby.hunt_start_time
                    time_limit_minutes = race.time_limit_minutes or 20
                    
                    # Calculate remaining time
                    if start_time:
                        from django.utils import timezone
                        elapsed = timezone.now() - start_time
                        elapsed_seconds = elapsed.total_seconds()
                        total_seconds = time_limit_minutes * 60
                        remaining_seconds = max(0, total_seconds - elapsed_seconds)
            
            # Return formatted state
            return {
                'score': total_score,
                'current_question_index': progress.current_question_index if progress else 0,
                'question_data': question_data,
                'remaining_seconds': int(remaining_seconds),
                'race_id': race.id,
                'team_code': team.code,
                'team_name': team.name
            }
            
        except Team.DoesNotExist:
            logger.error(f"Team with code {self.team_code} not found")
            return {'error': 'Team not found'}
            
        except Race.DoesNotExist:
            logger.error(f"Race with ID {self.race_id} not found")
            return {'error': 'Race not found'}
            
        except Exception as e:
            logger.error(f"Error getting race updates state: {str(e)}")
            return {'error': str(e)}
    
    async def send_initial_state(self):
        """Send the initial state to the client"""
        state = await self.get_initial_state()
        
        if 'error' in state:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': state['error']
            }))
            return
        
        # Send score update
        await self.send(text_data=json.dumps({
            'type': 'score_update',
            'score': state['score']
        }))
        
        # Send question data update
        await self.send(text_data=json.dumps({
            'type': 'question_update',
            'question_data': state['question_data'],
            'current_question_index': state['current_question_index']
        }))
        
        # Send timer update
        await self.send(text_data=json.dumps({
            'type': 'time_update',
            'remaining_seconds': state['remaining_seconds']
        }))
    
    async def score_update(self, event):
        """Handle score update events"""
        await self.send(text_data=json.dumps({
            'type': 'score_update',
            'score': event['score']
        }))
    
    async def question_update(self, event):
        """Handle question update events"""
        await self.send(text_data=json.dumps({
            'type': 'question_update',
            'question_data': event.get('question_data', {}),
            'current_question_index': event.get('current_question_index', 0)
        }))
    
    async def time_update(self, event):
        """Handle time update events"""
        await self.send(text_data=json.dumps({
            'type': 'time_update',
            'remaining_seconds': event.get('remaining_seconds', 0)
        }))
    
    async def race_complete(self, event):
        """Handle race completion events"""
        await self.send(text_data=json.dumps({
            'type': 'race_complete',
            'redirect_url': event.get('redirect_url', '/race-complete/')
        })) 