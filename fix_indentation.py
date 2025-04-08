import re

def fix_indentation():
    with open('scavenger_hunt/hunt/views.py', 'r') as f:
        content = f.read()

    # Fix try-except in lines 809-820
    content = content.replace('            try:\n            channel_layer', '            try:\n                channel_layer')
    content = content.replace('                logger.info(f"Sent team_left event to lobby_{lobby_id}")\n            except Exception', '                logger.info(f"Sent team_left event to lobby_{lobby_id}")\n            except Exception')
    content = content.replace('            except Exception as e:\n                logger.error', '            except Exception as e:\n                logger.error')
    
    # Fix try-except in lines 921-924 (missing except clause)
    content = content.replace('                try:\n                    channel_layer', '                try:\n                    channel_layer')
    content = content.replace('                        }\n                    )\n        except Exception as e:', '                        }\n                    )\n                except Exception as e:')
    
    # Fix indentation in lines 1364-1370
    content = content.replace('        if lobby.race and lobby.start_time:\n            time_elapsed = timezone.now() - lobby.start_time\n            time_limit_minutes', '        if lobby.race and lobby.start_time:\n            time_elapsed = timezone.now() - lobby.start_time\n            time_limit_minutes')
    content = content.replace('            if time_elapsed > timedelta(minutes=time_limit_minutes):\n            return render', '            if time_elapsed > timedelta(minutes=time_limit_minutes):\n                return render')
    
    # Fix indentation in lines 1450-1457
    content = content.replace('                context[\'race_questions_url\'] = f"/race/{lobby.race.id}/questions/?team_code={team.code}&player_name={player_name}"\n                \n                return render', '                context[\'race_questions_url\'] = f"/race/{lobby.race.id}/questions/?team_code={team.code}&player_name={player_name}"\n                \n                return render')
    content = content.replace('                # Redirect to the race_questions view with appropriate parameters\n                race_id', '                # Redirect to the race_questions view with appropriate parameters\n                race_id')
    
    # Fix try-except block in lines 1836-1842
    content = content.replace('            try:\n            team = Team.objects.get(id=team_id)\n            except Team.DoesNotExist:', '            try:\n                team = Team.objects.get(id=team_id)\n            except Team.DoesNotExist:')
    content = content.replace('            except Team.DoesNotExist:\n                pass', '            except Team.DoesNotExist:\n                pass')
    
    # Fix indentation in lines 1861-1866
    content = content.replace('    # Find or create team member\n            try:', '    # Find or create team member\n    try:')
    content = content.replace('    # Find or create team member\n    try:\n                team_member', '    # Find or create team member\n    try:\n        team_member')
    content = content.replace('    except TeamMember.DoesNotExist:\n        # Create a team member entry\n                team_member', '    except TeamMember.DoesNotExist:\n        # Create a team member entry\n        team_member')
    content = content.replace('        team_member = TeamMember.objects.create(team=team, role=player_name)\n                print', '        team_member = TeamMember.objects.create(team=team, role=player_name)\n        print')
    
    # Fix try statement in line 2118 (missing except clause)
    content = content.replace('            try:\n                race_progress', '            try:\n                race_progress')
    content = content.replace('                    race_progress.photo_questions_completed = []\n\n                    # Save it', '                    race_progress.photo_questions_completed = []\n\n                # Save it')
    
    # Fix indentation in lines 2143-2152 directly
    pattern = r'logger\.info\(f"Sent leaderboard update for team \{team\.id\} in race \{race_id\}"\)\n                except Exception as e:\n            logger\.error\(f"Error sending leaderboard update: \{str\(e\)\}"\)'
    replacement = r'logger.info(f"Sent leaderboard update for team {team.id} in race {race_id}")\n                except Exception as e:\n                    logger.error(f"Error sending leaderboard update: {str(e)}")'
    content = re.sub(pattern, replacement, content)
    
    pattern = r'# Also trigger an HTTP-based leaderboard update for redundancy\n                try:\n                    trigger_leaderboard_update_internal\(race_id\)\n                except Exception as e:\n            logger\.error\(f"Error triggering HTTP leaderboard update: \{str\(e\)\}"\)'
    replacement = r'# Also trigger an HTTP-based leaderboard update for redundancy\n                try:\n                    trigger_leaderboard_update_internal(race_id)\n                except Exception as e:\n                    logger.error(f"Error triggering HTTP leaderboard update: {str(e)}")'
    content = re.sub(pattern, replacement, content)
    
    pattern = r'logger\.error\(f"Error triggering HTTP leaderboard update: \{str\(e\)\}"\)\n            except Exception as e:'
    replacement = r'logger.error(f"Error triggering HTTP leaderboard update: {str(e)}")\n            except Exception as e:'
    content = re.sub(pattern, replacement, content)
    
    with open('scavenger_hunt/hunt/views.py', 'w') as f:
        f.write(content)
    
    print('Fixed indentation issues in lines 2143-2152')

if __name__ == "__main__":
    fix_indentation() 