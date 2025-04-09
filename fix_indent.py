"""
Fix indentation errors in views.py
"""
import re

# Read the file
with open('scavenger_hunt/hunt/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix indentation for line 277 (logger.info)
content = re.sub(r'(\n\s+request\.session\[\'team_id\'\] = team\.id\n\s+request\.session\.modified = True\n)\s+\n\s+# Log the join\n\s+logger\.info', 
                r'\1\n                    # Log the join\n                    logger.info', 
                content)

# Fix indentation for line 307 (else)
content = re.sub(r'(\n\s+except Exception as e:\n\s+logger\.error\(f\"Error broadcasting team update: {str\(e\)}\"\)\n)\s+else:', 
                r'\1                else:', 
                content)

# Fix indentation for line 480 (form = UserCreationForm())
content = re.sub(r'(\n\s+return redirect\(\'home\'\)\n\s+else:\n)\s+form = UserCreationForm\(\)', 
                r'\1            form = UserCreationForm()', 
                content)

# Fix indentation for line 503 (teams = [])
content = re.sub(r'(Display the leaderboard for all races\.\n\s+\"\"\"\n)\s+teams = \[\]', 
                r'\1    teams = []', 
                content)

# Fix indentation for line 549 (try without except/finally)
content = re.sub(r'(\n\s+\"\"\"API endpoint to fetch leaderboard data for AJAX updates\"\"\"\n)\s+try:', 
                r'\1    try:', 
                content)
content = re.sub(r'(\n\s+\}\n\s+\}\n\s+\}\n\s+\]\n\s+\}\n\s+\}\n)\s+except Exception as e:', 
                r'\1    except Exception as e:', 
                content)

# Fix indentation for line 795 (try without except/finally)
content = re.sub(r'(\n\s+# Broadcast updates if needed\n\s+if lobby_id:\n)\s+try:', 
                r'\1        try:', 
                content)
content = re.sub(r'(f\'lobby_{lobby_id}\',\n\s+\{\n\s+\'type\': \'team_left\',\n\s+\'team_id\': team\.id,\n\s+\'team_name\': team\.name\n\s+\}\n\s+\)\n)\s+logger\.info', 
                r'\1                logger.info', 
                content)
content = re.sub(r'(\n\s+logger\.info\(f\"Sent team_left event to lobby_{lobby_id}\"\)\n)\s+except Exception as e:', 
                r'\1            except Exception as e:', 
                content)
content = re.sub(r'(\n\s+logger\.error\(f\"Error sending team_left event: {str\(e\)}\"\)\n)\s+\n\s+# Also send update to leaderboard', 
                r'\1        \n        # Also send update to leaderboard', 
                content)

# Fix indentation for line 907 (try without except/finally)
content = re.sub(r'(\n\s+# Broadcast the update to any connected clients\n)\s+try:', 
                r'\1                try:', 
                content)

# Fix indentation for line 1349-1352 (time_elapsed)
content = re.sub(r'(\n\s+# Check if time limit is exceeded - time_limit is on the race object, not lobby\n\s+if lobby\.race and lobby\.start_time:\n)\s+time_elapsed = timezone\.now\(\) - lobby\.start_time', 
                r'\1            time_elapsed = timezone.now() - lobby.start_time', 
                content)
content = re.sub(r'(\n\s+time_limit_minutes = lobby\.race\.time_limit_minutes if hasattr\(lobby\.race, \'time_limit_minutes\'\) else 60  # Default to 60 minutes\n\s+if time_elapsed > timedelta\(minutes=time_limit_minutes\):\n)\s+return render', 
                r'\1                return render', 
                content)

# Fix indentation for line 1480-1490 (context['race_questions_url'])
content = re.sub(r'(\n\s+# Add a direct link to switch to race_questions\.html style\n)\s+context', 
                r'\1                context', 
                content)
content = re.sub(r'(\n\s+return render\(request, \'hunt/student_question\.html\', context\)\n\s+else:\n)\s+# Redirect to the race_questions view with appropriate parameters', 
                r'\1                # Redirect to the race_questions view with appropriate parameters', 
                content)
content = re.sub(r'(\n\s+# Redirect to the race_questions view with appropriate parameters\n)\s+race_id = lobby\.race\.id if lobby\.race else None', 
                r'\1                race_id = lobby.race.id if lobby.race else None', 
                content)

# Fix indentation for line 1958 (try without except/finally)
content = re.sub(r'(\n\s+team_id = request\.session\.get\(\'team_id\'\)\n\s+if team_id:\n)\s+try:', 
                r'\1            try:', 
                content)
content = re.sub(r'(\n\s+try:\n)\s+team = Team\.objects\.get\(id=team_id\)', 
                r'\1                team = Team.objects.get(id=team_id)', 
                content)
content = re.sub(r'(\n\s+team = Team\.objects\.get\(id=team_id\)\n)\s+except Team\.DoesNotExist:', 
                r'\1            except Team.DoesNotExist:', 
                content)
content = re.sub(r'(\n\s+except Team\.DoesNotExist:\n)\s+pass', 
                r'\1                pass', 
                content)

# Fix indentation for line 1983 (try statement)
content = re.sub(r'(\n\s+# Find or create team member\n)\s+try:', 
                r'\1            try:', 
                content)

# Write the fixed content to a new file
with open('scavenger_hunt/hunt/views.py.fixed', 'w', encoding='utf-8') as f:
    f.write(content)

print('Indentation fixes applied and saved to scavenger_hunt/hunt/views.py.fixed') 