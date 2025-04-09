from django.contrib import admin
from django.urls import path, include
from hunt import views  # Import the views module directly
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('hunt.urls')),
    # Add the URL pattern directly in the project's URLs as a fallback
    path('lobby/<int:lobby_id>/question/<int:question_id>/upload-photo/', views.upload_photo, name='upload_photo_student'),
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
