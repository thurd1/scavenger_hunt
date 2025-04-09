@csrf_exempt
def leaderboard_data_api(request):
    """API endpoint to fetch leaderboard data for AJAX updates"""
    try:
        teams = []
        
        # Check if we're filtering for a specific team
        team_code = request.GET.get('team_code')
        
        # Get teams with their progress data
        team_race_progress_list = TeamRaceProgress.objects.select_related('team', 'race').all()
        
        # Filter by team code if provided
        if team_code:
            logger.info(f"Filtering leaderboard data for team with code: {team_code}")
            team_race_progress_list = team_race_progress_list.filter(team__code=team_code)
        
        logger.info(f"Found {team_race_progress_list.count()} team race progress records")
        
        # Organize teams by their total scores
        for team_progress in team_race_progress_list:
            team = team_progress.team
            race = team_progress.race
            if team:
                # Get the lobby for this team that's associated with the race
                lobby = Lobby.objects.filter(teams=team, race=race).first()
                lobby_id = lobby.id if lobby else None
                lobby_name = race.name if race else 'Unknown Race'
                
                logger.debug(f"Team: {team.name}, Score: {team_progress.total_points}, Race: {race.name if race else 'None'}, Lobby ID: {lobby_id}")
                
                teams.append({
                    'id': team.id,
                    'name': team.name,
                    'code': team.code,  # Add code to help identify specific teams
                    'score': team_progress.total_points,
                    'lobby_id': lobby_id,
                    'lobby_name': lobby_name
                })
        
        # Sort teams by score (highest first)
        teams.sort(key=lambda x: x['score'], reverse=True)
        
        # Return success response with teams data
        return JsonResponse({
            'success': True,
            'teams': teams
        })
    except Exception as e:
        logger.error(f"Error in leaderboard_data_api: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }) 