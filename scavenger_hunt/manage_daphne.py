import os
import sys
import django
from django.core.asgi import get_asgi_application

# Configuration
HOST = "0.0.0.0"  # Listen on all interfaces
PORT = 8000       # Default port

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
    print("Starting Daphne server...")
    
    # First, make sure to collect static files
    if len(sys.argv) > 1 and sys.argv[1] == "restart":
        print("Collecting static files...")
        os.system(f"{sys.executable} manage.py collectstatic --noinput")
    else:
        # Always collect static files to ensure they're up to date
        print("Collecting static files...")
        os.system(f"{sys.executable} manage.py collectstatic --noinput")
        
    # Set up Django settings
    print(f"Settings module: {os.environ['DJANGO_SETTINGS_MODULE']}")
    
    # Run Daphne with proper settings
    cmd = (
        f"{sys.executable} -m daphne "
        f"-p {PORT} "
        f"-b {HOST} "
        "scavenger_hunt.asgi:application"
    )
    
    # Execute the command
    os.system(cmd) 