from django.contrib import admin
from django.urls import path
from hunt import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('join-lobby/', views.join_lobby, name='join_lobby'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('register/', views.register, name='register'),
    path('leader-dashboard/', views.leader_dashboard, name='leader_dashboard'),
    path('teams/', views.team_list, name='team_list'),
    path('teams/<int:team_id>/', views.team_details, name='team_details'),
    path('riddles/', views.riddle_list, name='riddle_list'),
    path('riddles/<int:riddle_id>/', views.riddle_detail, name='riddle_detail'),
    path('join-game-session/', views.join_game_session, name='join_game_session'),
    path('register-team/', views.register_team, name='register_team'),
    path('assign-riddles/', views.assign_riddles, name='assign_riddles'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('create-lobby/', views.create_lobby, name='create_lobby'),
    path('lobby/<int:lobby_id>/', views.lobby_details, name='lobby_details'),
    path('lobby/<int:lobby_id>/create-team/', views.create_team, name='create_team'),
    path('team/<int:team_id>/', views.team_dashboard, name='team_dashboard'),
    path('save-player-name/', views.save_player_name, name='save_player_name'),
    path('lobby/<int:lobby_id>/join-team/', views.join_existing_team, name='join_existing_team'),
    path('manage-lobbies/', views.manage_lobbies, name='manage_lobbies'),
    path('lobby/<int:lobby_id>/toggle/', views.toggle_lobby, name='toggle_lobby'),
    path('lobby/<int:lobby_id>/delete/', views.delete_lobby, name='delete_lobby'),
    path('team/<int:team_id>/delete/', views.delete_team, name='delete_team'),
    path('team/<int:team_id>/edit/', views.edit_team, name='edit_team'),
    path('team/<int:team_id>/view/', views.view_team, name='view_team'),
]