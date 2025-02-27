Hierarchy

    A[home.html] -->|Enter Game Code| B[join_game_session.html]
    
    B -->|Enter Player Name| C[team_options.html]
    
    C -->|Create New Team| D[create_team.html]
    C -->|Join Existing Team| E[join_team.html]
    
    D -->|Submit Team| F[team_dashboard.html]
    E -->|Enter Team Code| F
    
    G[leader_dashboard.html] -->|Manage Teams| H[team_list.html]
    H -->|View Team| F
    H -->|Edit Team| I[edit_team.html]
    
    subgraph "Team Dashboard View"
        F -->|Real-time Updates| F
        F -->|Back to Join| E
        F -->|Home| A
    end
    
    subgraph "Leader Views"
        G -->|Create Game| J[create_game.html]
        G -->|View Games| K[game_list.html]
    end
