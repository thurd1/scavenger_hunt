import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from hunt.routing import websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scavenger_hunt.settings')
django.setup()

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})

if __name__ == "__main__":
    from daphne.server import Server
    from daphne.endpoints import build_endpoint_description_strings

    Server(
        application=application,
        endpoints=build_endpoint_description_strings(host="0.0.0.0", port=8000),
    ).run() 
