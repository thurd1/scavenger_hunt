Hierarchy

    A. home.html --> Enter Game Code 
        b. join_game_session.html
    
    B.Enter Player Name
        c. team_options.html
    
    C. Create New Team
        d. create_team.html
        
    C. Join Existing Team
        e. join_team.html
    
    D. Submit Team
        f. team_dashboard.html
    E. Enter Team Code 
    
    G. leader_dashboard.html --> Manage Teams 
        h. team_list.html
        
    H. View Team
    
    H. Edit Team
        i. edit_team.html
    
    subgraph "Team Dashboard View"
        F. Real-time Updates (Daphne)
        F. Back to Join
        F. Home
    
    subgraph "Leader Views"
        G. Create Game
            j. create_game.html
        G. View Games
            k. game_list.html.
            
Resources/documentation:
Setting up Django app on AWS EC2:
https://youtu.be/PzSUOyshA6k?si=GpsANKUWb7Mu7mUE

Setting up Daphne with Django:
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/daphne/

Admin interface:
https://docs.djangoproject.com/en/stable/ref/contrib/admin/

Web Socket:
https://developer.mozilla.org/en-US/docs/Web/API/WebSocket
