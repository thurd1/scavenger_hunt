from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from scavenger_hunt.models import Race, Team, Question, Answer, TeamMember, RaceProgress, Zone

@api_view(['POST'])
@permission_classes([AllowAny])
def check_answer(request):
    """
    Check if the provided answer is correct for a given question.
    
    POST parameters:
    - question_id: The ID of the question
    - answer: The answer provided by the team
    - team_code: The team's unique code
    - attempt_number: The attempt number (1-based)
    
    Returns:
    - correct: True if the answer is correct, False otherwise
    - points: Points awarded for the correct answer
    - already_answered: True if the question was already answered correctly
    """
    print("Checking answer, request data:", request.data)
    
    # Extract data from request
    question_id = request.data.get('question_id')
    provided_answer = request.data.get('answer', '').strip().lower()
    team_code = request.data.get('team_code')
    attempt_number = request.data.get('attempt_number', 1)
    
    # Get the team
    try:
        team = Team.objects.get(code=team_code)
    except Team.DoesNotExist:
        return Response({'error': 'Invalid team code'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Get the question
    try:
        question = Question.objects.get(id=question_id)
    except Question.DoesNotExist:
        return Response({'error': 'Question not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Get or create answer object
    answer_obj, created = Answer.objects.get_or_create(
        team=team,
        question=question,
        defaults={
            'attempts': 1,
            'answered_correctly': False,
            'points_awarded': 0
        }
    )
    
    # Check if already answered correctly
    if answer_obj.answered_correctly:
        return Response({
            'correct': True,
            'already_answered': True,
            'points': answer_obj.points_awarded,
        }, status=status.HTTP_200_OK)
    
    # If not created, update attempts
    if not created:
        answer_obj.attempts = attempt_number
        answer_obj.save()
    
    # Check if the answer is correct
    is_correct = False
    correct_answers = [a.strip().lower() for a in question.answer.split('|')]
    
    for correct_answer in correct_answers:
        if provided_answer == correct_answer:
            is_correct = True
            break
    
    # If correct, update the answer object and calculate points
    if is_correct:
        # Calculate points (more points for fewer attempts)
        max_points = question.points
        points_awarded = max(int(max_points * (1 - (attempt_number - 1) * 0.3)), max_points // 3)
        
        # Update answer object
        answer_obj.answered_correctly = True
        answer_obj.points_awarded = points_awarded
        answer_obj.save()
        
        # Log the successful answer
        print(f"Team {team.name} answered question {question_id} correctly and earned {points_awarded} points")
        
        # Create RaceProgress record if it doesn't exist
        race = question.zone.race
        race_progress, created = RaceProgress.objects.get_or_create(
            race=race,
            team=team,
            defaults={
                'score': points_awarded,
                'questions_answered': 1,
                'last_update': timezone.now()
            }
        )
        
        # Update existing race progress
        if not created:
            race_progress.score += points_awarded
            race_progress.questions_answered += 1
            race_progress.last_update = timezone.now()
            race_progress.save()
        
        # Return success response
        return Response({
            'correct': True,
            'already_answered': False,
            'points': points_awarded,
        }, status=status.HTTP_200_OK)
    else:
        # Return incorrect response
        return Response({
            'correct': False,
            'already_answered': False,
            'points': 0,
        }, status=status.HTTP_200_OK) 