import os
import sys
import django
from django.core.asgi import get_asgi_application

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scavenger_hunt.settings')
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from hunt.routing import websocket_urlpatterns

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

    print("Starting Daphne server...")
    print("Settings module:", os.environ['DJANGO_SETTINGS_MODULE'])
    
    Server(
        application=application,
        endpoints=build_endpoint_description_strings(host="0.0.0.0", port=8000),
    ).run() 