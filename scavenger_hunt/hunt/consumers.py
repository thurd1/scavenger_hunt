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
from django.db.models import Sum

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
    WebSocket consumer for lobby updates.
    Handles real-time updates when teams join/leave and when race status changes.
    """
    async def connect(self):
        self.lobby_id = self.scope['url_route']['kwargs']['lobby_id']
        self.lobby_group_name = f'lobby_{self.lobby_id}'
        
        # Join the lobby group
        await self.channel_layer.group_add(
            self.lobby_group_name,
            self.channel_name
        )
        
        # Accept the connection
        await self.accept()
        
        # Log for debugging
        print(f"WebSocket CONNECTED: Lobby {self.lobby_id}")
        
        # Send a confirmation message
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': f'Connected to lobby {self.lobby_id}'
        }))

    async def disconnect(self, close_code):
        # Leave the lobby group
        await self.channel_layer.group_discard(
            self.lobby_group_name,
            self.channel_name
        )
        print(f"WebSocket DISCONNECTED: Lobby {self.lobby_id}")

    async def receive(self, text_data):
        # We don't expect to receive messages from clients
        # This is mainly for broadcasting from server to clients
        pass

    async def team_joined(self, event):
        """
        Broadcast to clients when a team joins the lobby
        """
        print(f"BROADCASTING team_joined event in lobby {self.lobby_id}")
        await self.send(text_data=json.dumps({
            'type': 'team_joined',
            'team': event['team']
        }))

    async def team_left(self, event):
        """
        Broadcast to clients when a team leaves the lobby
        """
        await self.send(text_data=json.dumps({
            'type': 'team_left',
            'team_id': event['team_id']
        }))

    async def team_member_joined(self, event):
        """
        Broadcast to clients when a new member joins a team
        """
        await self.send(text_data=json.dumps({
            'type': 'team_member_joined',
            'member': event['member'],
            'team_id': event['team_id'],
            'team_name': event['team_name']
        }))

    async def race_status_changed(self, event):
        """
        Broadcast to clients when race status changes
        """
        print(f"BROADCASTING race_status_changed event in lobby {self.lobby_id} - status: {event['status']}")
        await self.send(text_data=json.dumps({
            'type': 'race_status_changed',
            'status': event['status'],
            'race_id': event.get('race_id')
        }))

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
        print(f"WebSocket CONNECTED: Race {self.race_id}")

    async def disconnect(self, close_code):
        # Leave the race group
        await self.channel_layer.group_discard(
            self.race_group_name,
            self.channel_name
        )
        print(f"WebSocket DISCONNECTED: Race {self.race_id}")

    async def receive(self, text_data):
        # We don't expect to receive messages from clients
        # This is mainly for broadcasting from server to clients
        pass

    async def race_started(self, event):
        """
        Broadcast to clients when race starts
        """
        print(f"BROADCASTING race_started event for race {self.race_id}")
        await self.send(text_data=json.dumps({
            'type': 'race_started',
            'race_id': self.race_id,
            'redirect_url': event.get('redirect_url', f'/race/{self.race_id}/questions/')
        }))

class LeaderboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Join the leaderboard group
        await self.channel_layer.group_add(
            "leaderboard",
            self.channel_name
        )
        await self.accept()
        
        # Send initial leaderboard data
        await self.send_initial_leaderboard_data()

    async def disconnect(self, close_code):
        # Leave the leaderboard group
        await self.channel_layer.group_discard(
            "leaderboard",
            self.channel_name
        )

    # Receive message from WebSocket (not used but needed for completeness)
    async def receive(self, text_data):
        # If the client sends a request for data, refresh the leaderboard
        if text_data:
            try:
                data = json.loads(text_data)
                if data.get('action') == 'get_data':
                    await self.send_initial_leaderboard_data()
            except json.JSONDecodeError:
                pass

    # Receive message from the leaderboard group
    async def leaderboard_update(self, event):
        teams = event['teams']
        
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'leaderboard_update',
            'teams': teams
        }))
    
    # Send initial leaderboard data
    async def send_initial_leaderboard_data(self):
        teams_data = await self.get_teams_data()
        
        await self.send(text_data=json.dumps({
            'type': 'leaderboard_update',
            'teams': teams_data
        }))
        
    @database_sync_to_async
    def get_teams_data(self):
        from .models import TeamRaceProgress, Team, Lobby, Race
        
        teams_data = []
        
        # Get all teams that are in lobbies with races
        teams = Team.objects.prefetch_related('participating_lobbies').all()
        
        for team in teams:
            # Get the lobby for this team
            lobby = team.participating_lobbies.first()
            
            if lobby and lobby.race:
                # Look for existing race progress
                try:
                    progress = TeamRaceProgress.objects.get(team=team, race=lobby.race)
                    total_points = progress.total_points
                except TeamRaceProgress.DoesNotExist:
                    # If no progress exists, score is 0
                    total_points = 0
                
                teams_data.append({
                    'id': team.id,
                    'name': team.name,
                    'score': total_points,
                    'lobby_id': str(lobby.id),
                    'lobby_name': lobby.race.name if lobby.race else 'Unknown Race'
                })
        
        # Sort by score
        teams_data.sort(key=lambda x: x['score'], reverse=True)
        
        return teams_data 