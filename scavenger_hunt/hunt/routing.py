from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/team/(?P<team_id>\w+)/$', consumers.TeamConsumer.as_asgi()),
]
