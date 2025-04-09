from django.contrib import admin
from django.urls import path, include
from hunt import views  # Import the views module directly

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('hunt.urls')),
    # Add the URL pattern directly in the project's URLs as a fallback
    path('lobby/<int:lobby_id>/question/<int:question_id>/upload-photo/', views.upload_photo, name='upload_photo_student'),
]
