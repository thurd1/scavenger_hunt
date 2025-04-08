import re

def fix_indentation():
    with open('scavenger_hunt/hunt/views.py', 'r') as f:
        content = f.read()

    # Fix try-except in lines 809-820
    content = content.replace('            try:\n            channel_layer', '            try:\n                channel_layer')
    content = content.replace('                logger.info(f"Sent team_left event to lobby_{lobby_id}")\n            except Exception', '                logger.info(f"Sent team_left event to lobby_{lobby_id}")\n            except Exception')
    content = content.replace('            except Exception as e:\n                logger.error', '            except Exception as e:\n                logger.error')
    
    # Fix try-except in lines 921-924
    content = content.replace('                try:\n                    channel_layer', '                try:\n                    channel_layer')
    
    # Fix indentation in lines 1364-1370
    content = content.replace('        time_elapsed = timezone.now() - lobby.start_time\n            time_limit_minutes', '            time_elapsed = timezone.now() - lobby.start_time\n            time_limit_minutes')
    content = content.replace('            if time_elapsed > timedelta(minutes=time_limit_minutes):\n            return render', '            if time_elapsed > timedelta(minutes=time_limit_minutes):\n                return render')
    
    # Fix indentation in lines 1450-1457
    content = content.replace('                context[\'race_questions_url\'] = f"/race/{lobby.race.id}/questions/?team_code={team.code}&player_name={player_name}"\n                \n                return render', '                context[\'race_questions_url\'] = f"/race/{lobby.race.id}/questions/?team_code={team.code}&player_name={player_name}"\n                \n                return render')
    content = content.replace('                # Redirect to the race_questions view with appropriate parameters\n                race_id', '                # Redirect to the race_questions view with appropriate parameters\n                race_id')
    
    # Fix try-except block in lines 1836-1842
    content = content.replace('            try:\n            team = Team.objects.get(id=team_id)\n            except Team.DoesNotExist:', '            try:\n                team = Team.objects.get(id=team_id)\n            except Team.DoesNotExist:')
    content = content.replace('            except Team.DoesNotExist:\n                pass', '            except Team.DoesNotExist:\n                pass')
    
    # Fix indentation in lines 1861-1864
    content = content.replace('    # Find or create team member\n            try:', '    # Find or create team member\n    try:')
    content = content.replace('    # Find or create team member\n    try:\n                team_member', '    # Find or create team member\n    try:\n        team_member')
    content = content.replace('    except TeamMember.DoesNotExist:\n        # Create a team member entry\n                team_member', '    except TeamMember.DoesNotExist:\n        # Create a team member entry\n        team_member')
    
    # Fix nested except blocks with double indentation
    content = content.replace('        except Exception as e:\n                    logger.error', '        except Exception as e:\n            logger.error')
    
    with open('scavenger_hunt/hunt/views.py', 'w') as f:
        f.write(content)
    
    print('Fixed indentation issues in views.py')

if __name__ == "__main__":
    fix_indentation() 