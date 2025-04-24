# Scavenger Hunt Application Hierarchy

## Player Flow (Student/Participant)
- **A. Home Page** (`home.html`)
  - Enter Game/Lobby Code 
  - → **B. Join Game Session** (`join_game_session.html`)
    - Enter Player Name
    - → **C. Team Options** (`team_options.html`)
      - **C1. Create New Team**
        - → **Create Team Form** (`create_team.html`)
      - **C2. Join Existing Team** 
        - → **Team Selection** (`join_team.html`)

- **D. Team Dashboard** (`team_dashboard.html`)
  - View team status and members
  - Access current race/hunt
  - Real-time updates via WebSockets (Daphne)

- **E. Race Questions** (`race_questions.html`, `student_question.html`)
  - Answer questions organized by zones
  - Submit photo evidence when needed
  - Track attempts and points
  - Navigate between questions

- **F. Race Complete** (`race_complete.html`)
  - Final score and results
  - Team performance summary

## Leader/Admin Flow

- **G. Login** (`login.html`)
  - Admin authentication

- **H. Leader Dashboard** (`leader_dashboard.html`)
  - Overview of all activities
  - Links to management functions

- **I. Team Management**
  - **I1. Team List** (`team_list.html`)
    - View all teams
    - → **View Team Details** (`view_team.html`, `team_details.html`)
    - → **Edit Team** (`edit_team.html`)
    - → **Delete Team** action

- **J. Lobby Management** (`manage_lobbies.html`)
  - Create, edit, delete lobbies
  - → **Create Lobby** (`create_lobby.html`)
  - → **View Lobby Details** (`lobby_details.html`)
  - → **Start Hunt** for a lobby

- **K. Race Management**
  - **K1. Race List** (part of leader dashboard)
    - → **Create Race** (`create_race.html`)
    - → **Race Details** (`race_detail.html`)
      - Add/edit zones
      - Add/edit questions
    - → **Edit Race** (`edit_race.html`)

- **L. Riddle Management** (`manage_riddles.html`)
  - Create, edit, delete riddles/questions
  - Assign riddles to races

## Additional Components

- **Real-time Communication** (WebSockets via Daphne)
  - Team score updates
  - Race status changes
  - Player activity tracking

- **Leaderboard** (`leaderboard.html`)
  - Display team rankings


Resources/documentation:
Setting up Django app on AWS EC2:
https://youtu.be/PzSUOyshA6k?si=GpsANKUWb7Mu7mUE

Setting up Daphne with Django:
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/daphne/
https://channels.readthedocs.io/en/latest/deploying.html

Admin interface:
https://docs.djangoproject.com/en/stable/ref/contrib/admin/

Web Socket:
https://developer.mozilla.org/en-US/docs/Web/API/WebSocket

# Migration Fix Instructions

If you encounter migration errors related to duplicate columns, you can use the included management commands to fix them.

## For duplicated `updated_at` column in Lobby table
If you see an error like: `duplicate column name: updated_at`, run:

```bash
python manage.py fake_migration
```

## For duplicated `photo_questions_completed` column in TeamRaceProgress table
If you see an error like: `duplicate column name: photo_questions_completed`, run:

```bash
python manage.py fake_photo_migration
```

These commands will mark the problematic migrations as applied in the database without actually running them, allowing you to continue using the application.

## Checking migration status
To check the status of migrations:

```bash
python manage.py showmigrations hunt
```

## Database structure
To verify the columns in a specific table:

```bash
# For sqlite3 databases
python -c "import sqlite3; conn = sqlite3.connect('db.sqlite3'); cursor = conn.cursor(); cursor.execute('PRAGMA table_info(hunt_teamraceprogress)'); columns = cursor.fetchall(); [print(column) for column in columns]; conn.close()"
```

## After fixing migrations
Once you've successfully fixed the migrations, you should be able to run:

```bash
python manage.py migrate
```

Without encountering any duplicate column errors.

Required dependencies:
pip install django
pip install whitenoise
pip install channels
pip install channels-redis
pip install daphne
