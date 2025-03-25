def player_name(request):
    return {'player_name': request.session.get('player_name')} 