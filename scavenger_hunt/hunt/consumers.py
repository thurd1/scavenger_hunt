import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Team, TeamMember

class TeamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.team_id = self.scope['url_route']['kwargs']['team_id']
        self.team_group_name = f'team_{self.team_id}'

        # Join team group
        await self.channel_layer.group_add(
            self.team_group_name,
            self.channel_name
        )
        await self.accept()

        # Send initial team members list
        team_members = await self.get_team_members()
        await self.send(text_data=json.dumps({
            'type': 'team_members',
            'members': team_members
        }))

    async def disconnect(self, close_code):
        # Leave team group
        await self.channel_layer.group_discard(
            self.team_group_name,
            self.channel_name
        )

    @database_sync_to_async
    def get_team_members(self):
        team = Team.objects.get(id=self.team_id)
        return [member.role for member in team.team_members.all()]

    async def team_update(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'team_members',
            'members': event['members']
        })) 
