from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/lobby/(?P<lobby_id>\d+)/$', consumers.LobbyConsumer.as_asgi()),
    re_path(r'ws/team/(?P<team_id>\w+)/$', consumers.TeamConsumer.as_asgi()),
] 