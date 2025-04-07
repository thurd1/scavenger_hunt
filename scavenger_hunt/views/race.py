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
    
    print(f"Processing answer: '{provided_answer}' for question {question_id} by team {team_code}")
    
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
    
    # Log the expected answers for debugging
    correct_answers = [a.strip().lower() for a in question.answer.split('|')]
    print(f"Correct answers for question {question_id}: {correct_answers}")
    print(f"User provided: '{provided_answer}'")
    
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
    
    # Handle empty answers
    if not provided_answer:
        return Response({
            'correct': False,
            'already_answered': False,
            'points': 0,
            'message': 'Please provide an answer.'
        }, status=status.HTTP_200_OK)
    
    # Log more debugging information
    print(f"Comparing provided answer '{provided_answer}' with correct answers: {correct_answers}")
    
    # Do a more flexible comparison
    for correct_answer in correct_answers:
        print(f"Comparing with correct answer: '{correct_answer}'")
        
        # Try exact match
        if provided_answer == correct_answer:
            is_correct = True
            print(f"CORRECT: Exact match found for '{provided_answer}'")
            break
        
        # Try case-insensitive match (should already be handled by .lower() but just to be safe)
        if provided_answer.lower() == correct_answer.lower():
            is_correct = True
            print(f"CORRECT: Case-insensitive match found for '{provided_answer}'")
            break
        
        # Try stripping spaces
        if provided_answer.strip() == correct_answer.strip():
            is_correct = True
            print(f"CORRECT: Match found after stripping spaces for '{provided_answer}'")
            break
            
        # Try removing punctuation
        import re
        clean_provided = re.sub(r'[^\w\s]', '', provided_answer).lower().strip()
        clean_correct = re.sub(r'[^\w\s]', '', correct_answer).lower().strip()
        
        if clean_provided == clean_correct:
            is_correct = True
            print(f"CORRECT: Match found after removing punctuation '{provided_answer}'")
            break
            
        # Try fuzzy matching for small differences (typos)
        from difflib import SequenceMatcher
        similarity = SequenceMatcher(None, clean_provided, clean_correct).ratio()
        if similarity > 0.9:  # 90% similarity is considered a match
            is_correct = True
            print(f"CORRECT: Fuzzy match found with {similarity*100:.1f}% similarity: '{provided_answer}'")
            break
            
    if is_correct:
        print(f"FINAL RESULT: '{provided_answer}' is CORRECT!")
    else:
        print(f"FINAL RESULT: '{provided_answer}' is INCORRECT. Correct answers were: {correct_answers}")
        
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