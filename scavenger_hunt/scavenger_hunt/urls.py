from django.contrib import admin
from django.urls import path, include
from scavenger_hunt import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('hunt.urls')),
    path('lobby/<int:lobby_id>/start-race/', views.start_race, name='start_race'),
    path('studentQuestion/<int:lobby_id>/<int:question_id>/', views.student_question, name='student_question'),
    path('lobby/<int:lobby_id>/question/<int:question_id>/check/', views.check_answer, name='check_answer'),
    path('lobby/<int:lobby_id>/question/<int:question_id>/upload/', views.upload_photo, name='upload_photo'),
]
