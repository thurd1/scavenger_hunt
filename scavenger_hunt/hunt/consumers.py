import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Team, TeamMember, Lobby
import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

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
            
            # Also broadcast to available teams
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'available_teams',
                {
                    'type': 'teams_update'
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
                
                # Also broadcast to available teams
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    'available_teams',
                    {
                        'type': 'teams_update'
                    }
                )
        except Exception as e:
            logger.error(f"Error creating team member: {e}")


class AvailableTeamsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'available_teams'
        self.player_name = self.scope.get('session', {}).get('player_name')
        logger.info(f"WebSocket connecting for available teams page with player {self.player_name}")

        # Join the group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()
        
        # Send initial state
        await self.send_teams_state()

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnected from available teams page for player {self.player_name}")
        
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
        try:
            # Delete all team memberships for this player
            deleted_count = TeamMember.objects.filter(role=self.player_name).delete()[0]
            logger.info(f"Removed player {self.player_name} from {deleted_count} teams")
        except Exception as e:
            logger.error(f"Error removing player from teams: {e}")

    @database_sync_to_async
    def get_available_teams(self):
        """Get all active teams with their members"""
        teams = Team.objects.all().prefetch_related('members')
        teams_data = []
        
        for team in teams:
            # Get unique members only
            members = list(TeamMember.objects.filter(team=team).values_list('role', flat=True).distinct())
            
            # Only include teams that have members
            if members:
                teams_data.append({
                    'id': team.id,
                    'name': team.name,
                    'code': team.code,
                    'members': members,
                    'member_count': len(members)
                })
        
        return teams_data

    async def send_teams_state(self):
        """Send current teams state to the client"""
        teams = await self.get_available_teams()
        await self.send(text_data=json.dumps({
            'type': 'teams_update',
            'teams': teams
        }))

    async def teams_update(self, event):
        """Send teams update to the client"""
        await self.send_teams_state()

    async def receive(self, text_data):
        """Handle messages from client"""
        try:
            data = json.loads(text_data)
            if data.get('type') == 'request_update':
                await self.send_teams_state()
            elif data.get('action') == 'leave_all_teams':
                if self.player_name:
                    await self.remove_player_from_all_teams()
                    await self.send_teams_state()
        except json.JSONDecodeError:
            pass


class LobbyConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.lobby_id = self.scope['url_route']['kwargs']['lobby_id']
        self.lobby_group_name = f'lobby_{self.lobby_id}'

        # Join lobby group
        await self.channel_layer.group_add(
            self.lobby_group_name,
            self.channel_name
        )
        await self.accept()
        
        # Send initial state
        await self.send_lobby_state()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.lobby_group_name,
            self.channel_name
        )

    @database_sync_to_async
    def get_lobby_state(self):
        lobby = Lobby.objects.get(id=self.lobby_id)
        teams_data = []
        for team in lobby.teams.all().prefetch_related('members'):
            teams_data.append({
                'id': team.id,
                'name': team.name,
                'code': team.code,
                'members': [{'id': m.id, 'role': m.role} for m in team.members.all()]
            })
        return teams_data

    async def send_lobby_state(self):
        teams_data = await self.get_lobby_state()
        await self.send(text_data=json.dumps({
            'type': 'lobby_state',
            'teams': teams_data
        }))

    async def lobby_update(self, event):
        await self.send_lobby_state()

    async def receive(self, text_data):
        # Handle received messages if needed
        pass

    @database_sync_to_async
    def get_lobby_data(self):
        lobby = Lobby.objects.prefetch_related('teams__members').get(id=self.lobby_id)
        teams = []
        for team in lobby.teams.all():
            members = list(team.members.values_list('role', flat=True))
            teams.append({
                'id': team.id,
                'name': team.name,
                'members': members
            })
        return teams 