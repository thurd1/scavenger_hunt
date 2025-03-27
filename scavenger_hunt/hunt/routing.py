from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/team/(?P<team_id>\d+)/$', consumers.TeamConsumer.as_asgi()),
    re_path(r'ws/lobby/(?P<lobby_id>\d+)/$', consumers.LobbyConsumer.as_asgi()),
    re_path(r'ws/available-teams/$', consumers.AvailableTeamsConsumer.as_asgi()),
    re_path(r'ws/race/(?P<race_id>\d+)/$', consumers.RaceConsumer.as_asgi()),
] 