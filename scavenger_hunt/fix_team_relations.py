import os
import django
import random
import string

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scavenger_hunt.settings')
django.setup()

# Import models
from hunt.models import Team, Lobby, Race, TeamMember

def fix_team_race_relation():
    # Find the specific team
    try:
        team = Team.objects.get(id=3)
        print(f"Found team: {team.name} (ID: {team.id})")
        
        # Find Race 2
        try:
            race = Race.objects.get(id=2)
            print(f"Found race: {race.name} (ID: {race.id})")
            
            # Check if team has members
            members_count = team.members.count()
            print(f"Team has {members_count} members")
            
            # Add a member if needed (using a default name)
            if members_count == 0:
                player_name = "Player1"
                new_member = TeamMember.objects.create(
                    team=team,
                    role=player_name,
                    name=player_name
                )
                print(f"Added new team member: {player_name}")
            
            # Check if team is already part of a lobby with this race
            lobbies = Lobby.objects.filter(teams=team, race=race)
            
            if lobbies.exists():
                lobby = lobbies.first()
                print(f"Team is already in lobby {lobby.name} (ID: {lobby.id}) with race {race.name}")
            else:
                # Check if there are any lobbies with this race
                race_lobbies = Lobby.objects.filter(race=race)
                
                if race_lobbies.exists():
                    # Add team to an existing lobby
                    lobby = race_lobbies.first()
                    lobby.teams.add(team)
                    print(f"Added team to existing lobby {lobby.name} (ID: {lobby.id})")
                else:
                    # Create a new lobby
                    code = ''.join(random.choices(string.digits, k=6))
                    lobby = Lobby.objects.create(
                        name=f"Lobby for {race.name}",
                        code=code,
                        race=race,
                        is_active=True
                    )
                    lobby.teams.add(team)
                    print(f"Created new lobby {lobby.name} (ID: {lobby.id}) with race {race.name}")
            
            print("Relationship fixed successfully!")
            
        except Race.DoesNotExist:
            print("Race with ID 2 not found")
            
    except Team.DoesNotExist:
        print("Team with ID 3 not found")

if __name__ == "__main__":
    fix_team_race_relation() 