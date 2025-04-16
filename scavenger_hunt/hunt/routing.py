from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/team/(?P<team_id>\w+)/$', consumers.TeamConsumer.as_asgi()),
    re_path(r'ws/lobby/(?P<lobby_id>\w+)/$', consumers.LobbyConsumer.as_asgi()),
    re_path(r'ws/available-teams/$', consumers.AvailableTeamsConsumer.as_asgi()),
    re_path(r'ws/race/(?P<race_id>\w+)/$', consumers.RaceConsumer.as_asgi()),
    re_path(r'ws/leaderboard/$', consumers.LeaderboardConsumer.as_asgi()),
    re_path(r'ws/race-updates/(?P<race_id>\w+)/(?P<team_code>\w+)/$', consumers.RaceUpdatesConsumer.as_asgi()),
]