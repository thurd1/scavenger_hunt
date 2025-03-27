from django.urls import re_path
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from hunt.consumers import TeamConsumer, AvailableTeamsConsumer, LobbyConsumer, RaceConsumer
from django.core.asgi import get_asgi_application

websocket_urlpatterns = [
    re_path(r'^ws/team/(?P<team_id>\d+)/?$', TeamConsumer.as_asgi()),
    re_path(r'^ws/available-teams/?$', AvailableTeamsConsumer.as_asgi()),
    re_path(r'^ws/lobby/(?P<lobby_id>\d+)/?$', LobbyConsumer.as_asgi()),
    re_path(r'^ws/race/(?P<race_id>\w+)/$', RaceConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
}) 