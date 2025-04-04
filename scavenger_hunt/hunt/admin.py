from django.contrib import admin
from hunt.models import Team, Riddle, Clue, GameSession, CustomUser

admin.site.register(Team)
admin.site.register(Riddle)
admin.site.register(Clue)
admin.site.register(GameSession)
admin.site.register(CustomUser)
