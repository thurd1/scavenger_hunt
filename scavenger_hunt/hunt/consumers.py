import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Team, TeamMember, Lobby
import logging

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
            
            # Also broadcast to available teams
            await self.channel_layer.group_send(
                'available_teams',
                {
                    'type': 'teams_update',
                    'action': 'leave',
                    'team_id': self.team_id,
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
            return True
        except Exception as e:
            logger.error(f"Error removing team member: {e}")
            return False

    @database_sync_to_async
    def get_team_members(self):
        team = Team.objects.get(id=self.team_id)
        members = list(team.members.all().values('id', 'role'))
        logger.info(f"Retrieved team members for team {self.team_id}: {members}")
        return members

    @database_sync_to_async
    def get_team_state(self):
        team = Team.objects.prefetch_related('members').get(id=self.team_id)
        # Return members as simple string array of roles for easier client handling
        return list(team.members.values_list('role', flat=True))

    async def send_team_state(self):
        members = await self.get_team_members()
        await self.send(text_data=json.dumps({
            'type': 'team_update',
            'members': members
        }))

    async def team_update(self, event):
        # Forward the update to WebSocket
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def get_team_data(self):
        team = Team.objects.prefetch_related('members').get(id=self.team_id)
        return {
            'id': team.id,
            'name': team.name,
            'members': list(team.members.values_list('role', flat=True))
        }

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            logger.info(f"WebSocket received data: {data}")
            
            if 'player_name' in data:
                self.player_name = data['player_name']
                logger.info(f"Received player name: {self.player_name} for team {self.team_id}")
                
                # Create team member
                await self.create_team_member()
                
                # Send updated state to all clients
                await self.channel_layer.group_send(
                    self.team_group_name,
                    {
                        'type': 'team_update'
                    }
                )
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")

    @database_sync_to_async
    def create_team_member(self):
        try:
            if self.player_name:
                team = Team.objects.get(id=self.team_id)
                # Check if already exists
                if not TeamMember.objects.filter(team=team, role=self.player_name).exists():
                    TeamMember.objects.create(
                        team=team,
                        role=self.player_name
                    )
                    logger.info(f"Created team member: {self.player_name} for team {self.team_id}")
        except Exception as e:
            logger.error(f"Error creating team member: {e}")


class AvailableTeamsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'available_teams'
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()
        
        # Send initial state
        await self.send_teams_state()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    @database_sync_to_async
    def get_available_teams(self):
        teams = Team.objects.prefetch_related('members').all()
        teams_data = []
        for team in teams:
            teams_data.append({
                'id': team.id,
                'name': team.name,
                'code': team.code,
                'members': list(team.members.values('id', 'role'))
            })
        return teams_data

    async def send_teams_state(self):
        teams = await self.get_available_teams()
        await self.send(text_data=json.dumps({
            'type': 'teams_update',
            'teams': teams
        }))

    async def teams_update(self, event):
        # If we have specific action (join/leave), forward as is
        if 'action' in event:
            await self.send(text_data=json.dumps(event))
        else:
            # Otherwise send full state
            await self.send_teams_state()

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if data.get('type') == 'request_update':
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