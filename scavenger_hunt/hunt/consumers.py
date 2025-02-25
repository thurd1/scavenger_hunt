import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Team, TeamMember
import logging

logger = logging.getLogger(__name__)

class TeamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.team_id = self.scope['url_route']['kwargs']['team_id']
        self.team_group_name = f'team_{self.team_id}'
        logger.info(f"WebSocket connecting for team {self.team_id}")

        # Join team group
        await self.channel_layer.group_add(
            self.team_group_name,
            self.channel_name
        )
        await self.accept()
        logger.info(f"WebSocket connected for team {self.team_id}")

        # Send initial team members list
        team_members = await self.get_team_members()
        logger.info(f"Initial team members for team {self.team_id}: {team_members}")
        await self.send(text_data=json.dumps({
            'type': 'team_members',
            'members': team_members
        }))

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnected for team {self.team_id}")
        await self.channel_layer.group_discard(
            self.team_group_name,
            self.channel_name
        )

    @database_sync_to_async
    def get_team_members(self):
        team = Team.objects.get(id=self.team_id)
        members = list(team.team_members.all().values_list('role', flat=True))
        logger.info(f"Retrieved team members for team {self.team_id}: {members}")
        return members

    async def team_update(self, event):
        logger.info(f"Received team update for team {self.team_id}: {event}")
        await self.send(text_data=json.dumps({
            'type': 'team_members',
            'members': event['members']
        }))
