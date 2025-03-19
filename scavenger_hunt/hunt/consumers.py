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
        
        # Send initial team data
        team_data = await self.get_team_data()
        await self.send(text_data=json.dumps({
            'type': 'team_update',
            'members': team_data['members']
        }))

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnected for team {self.team_id} with player {self.player_name}")
        
        if self.player_name:
            # Remove the team member
            await self.remove_team_member()
            
            # Get updated list of team members
            team_members = await self.get_team_members()
            
            # Broadcast the update to all connected clients
            await self.channel_layer.group_send(
                self.team_group_name,
                {
                    'type': 'team_update',
                    'members': team_members
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
        except Exception as e:
            logger.error(f"Error removing team member: {e}")

    @database_sync_to_async
    def get_team_members(self):
        team = Team.objects.get(id=self.team_id)
        members = list(team.team_members.all().values_list('role', flat=True))
        logger.info(f"Retrieved team members for team {self.team_id}: {members}")
        return members

    async def team_update(self, event):
        logger.info(f"Sending team update for team {self.team_id}: {event}")
        await self.send(text_data=json.dumps({
            'type': 'team_update',
            'members': event['members']
        }))

    @database_sync_to_async
    def get_team_data(self):
        team = Team.objects.prefetch_related('team_members').get(id=self.team_id)
        return {
            'id': team.id,
            'name': team.name,
            'members': list(team.team_members.values_list('role', flat=True))
        }

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

    async def disconnect(self, close_code):
        # Leave lobby group
        await self.channel_layer.group_discard(
            self.lobby_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        # Handle received messages if needed
        pass

    @database_sync_to_async
    def get_lobby_data(self):
        lobby = Lobby.objects.prefetch_related('teams__team_members').get(id=self.lobby_id)
        teams = []
        for team in lobby.teams.all():
            members = list(team.team_members.values_list('role', flat=True))
            teams.append({
                'id': team.id,
                'name': team.name,
                'members': members
            })
        return teams

    async def lobby_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'lobby_update',
            'teams': event['teams']
        })) 