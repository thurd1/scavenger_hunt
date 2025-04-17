from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home, name='home'),
    path('admin/', admin.site.urls),
    path('join-lobby/', views.join_lobby, name='join_lobby'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('leader-dashboard/', views.leader_dashboard, name='leader_dashboard'),
    path('teams/', views.team_list, name='team_list'),
    path('teams/<int:team_id>/', views.team_details, name='team_details'),
    path('riddles/', views.riddle_list, name='riddle_list'),
    path('riddles/<int:riddle_id>/', views.riddle_detail, name='riddle_detail'),
    path('join-game-session/', views.join_game_session, name='join_game_session'),
    path('join-team/', views.join_team, name='join_team'),
    path('join-team/<int:team_id>/', views.join_team, name='join_team'),
    path('leave-team/<int:team_id>/', views.leave_team, name='leave_team'),
    path('register-team/', views.register_team, name='register_team'),
    path('assign-riddles/', views.assign_riddles, name='assign_riddles'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('create-lobby/', views.create_lobby, name='create_lobby'),
    path('lobby/<int:lobby_id>/', views.lobby_details, name='lobby_details'),
    path('lobby/<int:lobby_id>/create-team/', views.create_team, name='create_team'),
    path('create-standalone-team/', views.create_standalone_team, name='create_standalone_team'),
    path('team/<int:team_id>/', views.team_dashboard, name='team_dashboard'),
    path('save-player-name/', views.save_player_name, name='save_player_name'),
    path('join-existing-team/', views.join_existing_team, name='join_existing_team'),
    path('lobby/<int:lobby_id>/join-team/', views.join_existing_team, name='join_existing_team'),
    path('manage-lobbies/', views.manage_lobbies, name='manage_lobbies'),
    path('lobby/<int:lobby_id>/toggle/', views.toggle_lobby, name='toggle_lobby'),
    path('lobby/<int:lobby_id>/delete/', views.delete_lobby, name='delete_lobby'),
    path('team/<int:team_id>/delete/', views.delete_team, name='delete_team'),
    path('team/<int:team_id>/edit/', views.edit_team, name='edit_team'),
    path('team/<int:team_id>/view/', views.view_team, name='view_team'),
    path('lobby/<int:lobby_id>/start/', views.start_hunt, name='start_hunt'),
    path('lobby/<int:lobby_id>/status/', views.check_hunt_status, name='check_hunt_status'),
    path('manage-riddles/', views.manage_riddles, name='manage_riddles'),
    path('race/<int:race_id>/', views.race_detail, name='race_detail'),
    path('race/<int:race_id>/toggle/', views.toggle_race, name='toggle_race'),
    path('delete-race/<int:race_id>/', views.delete_race, name='delete_race'),
    path('race/<int:race_id>/edit/', views.edit_race, name='edit_race'),
    path('race/create/', views.create_race, name='create_race'),
    path('race/<int:race_id>/add-zone/', views.add_zone, name='add_zone'),
    path('race/<int:race_id>/add-question/', views.add_question, name='add_question'),
    path('race/<int:race_id>/edit-zone/', views.edit_zone, name='edit_zone'),
    path('race/<int:race_id>/delete-zone/', views.delete_zone, name='delete_zone'),
    path('race/<int:race_id>/edit-question/', views.edit_question, name='edit_question'),
    path('race/<int:race_id>/delete-question/', views.delete_question, name='delete_question'),
    
    # Race gameplay URLs
    path('lobby/<int:lobby_id>/start-race/', views.start_race, name='start_race'),
    path('lobby/<int:lobby_id>/notify-race-started/', views.notify_race_started, name='notify_race_started'),
    path('studentQuestion/<int:lobby_id>/<int:question_id>/', views.student_question, name='student_question'),
    path('lobby/<int:lobby_id>/question/<int:question_id>/check/', views.check_answer, name='check_answer'),
    path('lobby/<int:lobby_id>/question/<int:question_id>/upload/', views.upload_photo, name='upload_photo'),
    path('lobby/<int:lobby_id>/question/<int:question_id>/upload-photo/', views.upload_photo, name='upload_photo_student'),
    path('race-complete/', views.race_complete, name='race_complete'),
    path('race/<int:race_id>/questions/', views.race_questions, name='race_questions'),
    path('check-answer/', views.check_answer, name='check_answer'),
    
    # API endpoints
    path('api/get-lobby-by-code/', views.get_lobby_by_code, name='get_lobby_by_code'),
    path('race/<int:race_id>/status/', views.check_race_status, name='check_race_status'),
    path('api/lobby/<int:lobby_id>/race-status/', views.check_lobby_race_status, name='check_lobby_race_status'),
    path('api/team/<int:team_id>/race/', views.get_team_race, name='get_team_race'),
    path('api/upload-photo/', views.upload_photo_api, name='upload_photo_api'),
    path('api/leaderboard-data/', views.leaderboard_data_api, name='leaderboard_data_api'),
    path('api/save-question-index/', views.save_question_index, name='save_question_index'),
    path('api/trigger-leaderboard-update/', views.trigger_leaderboard_update, name='trigger_leaderboard_update'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)