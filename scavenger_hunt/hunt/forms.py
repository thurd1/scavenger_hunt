from django import forms
from .models import Team, Lobby

class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name']

class LobbyForm(forms.ModelForm):
    class Meta:
        model = Lobby
        fields = ['name']

class JoinLobbyForm(forms.Form):
    team_code = forms.CharField(max_length=6)

class JoinTeamForm(forms.Form):
    team_code = forms.CharField(max_length=6, label='Team Code')
    player_name = forms.CharField(max_length=100, label='Your Name')