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
import re
from difflib import SequenceMatcher

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
    provided_answer = request.data.get('answer', '').strip()
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
    
    # Handle empty answers
    if not provided_answer:
        return Response({
            'correct': False,
            'already_answered': False,
            'points': 0,
            'message': 'Please provide an answer.'
        }, status=status.HTTP_200_OK)
    
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
    
    # Prepare correct answers and the provided answer for comparison
    # Keep original answers for logging
    original_correct_answers = question.answer.split('|')
    original_provided = provided_answer
    
    # Normalized answers (lowercase, trimmed)
    correct_answers = [a.strip().lower() for a in original_correct_answers]
    provided_normalized = provided_answer.strip().lower()
    
    # Clean answers (lowercase, trimmed, no punctuation, normalized whitespace)
    clean_correct_answers = [re.sub(r'[^\w\s]', '', a).lower().strip() for a in correct_answers]
    clean_provided = re.sub(r'[^\w\s]', '', provided_normalized).lower().strip()
    
    # Super clean answers (no spaces, lowercase, alphanumeric only)
    super_clean_correct = [''.join(re.findall(r'\w', a.lower())) for a in correct_answers]
    super_clean_provided = ''.join(re.findall(r'\w', provided_normalized))
    
    # Log extensive debug information
    print("\n==== ANSWER VALIDATION DEBUG ====")
    print(f"Question ID: {question_id}, Question Text: {question.question_text[:50]}...")
    print(f"Original correct answers: {original_correct_answers}")
    print(f"Original provided answer: '{original_provided}'")
    print(f"Normalized correct answers: {correct_answers}")
    print(f"Normalized provided answer: '{provided_normalized}'")
    print(f"Clean correct answers: {clean_correct_answers}")
    print(f"Clean provided answer: '{clean_provided}'")
    print(f"Super clean correct answers: {super_clean_correct}")
    print(f"Super clean provided answer: '{super_clean_provided}'")
    
    # Initialize is_correct and match_type for tracking
    is_correct = False
    match_type = None
    matched_answer = None
    
    # Perform increasingly flexible matching
    # 1. Exact match (case-sensitive)
    for i, correct in enumerate(original_correct_answers):
        if provided_answer == correct:
            is_correct = True
            match_type = "exact"
            matched_answer = correct
            print(f"MATCH: Exact match found with answer option {i+1}")
            break
    
    # 2. Case-insensitive match
    if not is_correct:
        for i, correct in enumerate(correct_answers):
            if provided_normalized == correct:
                is_correct = True
                match_type = "case-insensitive"
                matched_answer = original_correct_answers[i]
                print(f"MATCH: Case-insensitive match found with answer option {i+1}")
                break
    
    # 3. Whitespace-insensitive match
    if not is_correct:
        provided_nospace = provided_normalized.replace(" ", "")
        for i, correct in enumerate(correct_answers):
            correct_nospace = correct.replace(" ", "")
            if provided_nospace == correct_nospace:
                is_correct = True
                match_type = "whitespace-insensitive"
                matched_answer = original_correct_answers[i]
                print(f"MATCH: Whitespace-insensitive match found with answer option {i+1}")
                break
    
    # 4. Punctuation-insensitive match
    if not is_correct:
        for i, clean_correct in enumerate(clean_correct_answers):
            if clean_provided == clean_correct:
                is_correct = True
                match_type = "punctuation-insensitive"
                matched_answer = original_correct_answers[i]
                print(f"MATCH: Punctuation-insensitive match found with answer option {i+1}")
                break
    
    # 5. Super clean match (alphanumeric only, no spaces)
    if not is_correct:
        for i, super_clean in enumerate(super_clean_correct):
            if super_clean_provided == super_clean:
                is_correct = True
                match_type = "alphanumeric-only"
                matched_answer = original_correct_answers[i]
                print(f"MATCH: Alphanumeric-only match found with answer option {i+1}")
                break
    
    # 6. Fuzzy matching (for typos)
    if not is_correct:
        best_ratio = 0
        best_index = -1
        
        for i, clean_correct in enumerate(clean_correct_answers):
            # Skip if lengths are too different
            if abs(len(clean_provided) - len(clean_correct)) > max(3, len(clean_correct) * 0.3):
                continue
                
            ratio = SequenceMatcher(None, clean_provided, clean_correct).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_index = i
        
        # Accept if similarity is high enough
        if best_ratio >= 0.8:  # Lowered from 0.9 to 0.8 for better matching
            is_correct = True
            match_type = f"fuzzy-{best_ratio:.2f}"
            matched_answer = original_correct_answers[best_index]
            print(f"MATCH: Fuzzy match found with answer option {best_index+1}, similarity: {best_ratio:.2f}")
    
    # 7. Contained-in match (for cases where the answer is part of a longer correct answer)
    if not is_correct:
        for i, correct in enumerate(correct_answers):
            # Check if the provided answer is completely contained in the correct answer
            # (useful for partial answers or abbreviations)
            if len(provided_normalized) >= 3 and provided_normalized in correct:
                # Check that it's at least 50% the length of the correct answer or at least 5 chars
                if len(provided_normalized) >= max(5, len(correct) * 0.5):
                    is_correct = True
                    match_type = "contained-in"
                    matched_answer = original_correct_answers[i]
                    print(f"MATCH: Contained-in match found with answer option {i+1}")
                    break
            
            # Check if the correct answer is completely contained in the provided answer
            # (useful when the user gives more detail than needed)
            elif len(correct) >= 3 and correct in provided_normalized:
                # Check that it's at least 70% the length of the provided answer or at least 5 chars
                if len(correct) >= max(5, len(provided_normalized) * 0.7):
                    is_correct = True
                    match_type = "contains"
                    matched_answer = original_correct_answers[i]
                    print(f"MATCH: Contains match found with answer option {i+1}")
                    break
    
    # Log final result
    if is_correct:
        print(f"FINAL RESULT: CORRECT ✓ - '{original_provided}' matched '{matched_answer}' via {match_type}")
    else:
        print(f"FINAL RESULT: INCORRECT ✗ - '{original_provided}' did not match any answer")
        # Log best fuzzy match for debugging
        if 'best_ratio' in locals() and best_ratio > 0.7:
            print(f"Closest match was with '{original_correct_answers[best_index]}', similarity: {best_ratio:.2f}")
    print("==== END ANSWER VALIDATION ====\n")
    
    # If correct, update the answer object and calculate points
    if is_correct:
        # Calculate points (more points for fewer attempts)
        max_points = question.points
        points_awarded = max(int(max_points * (1 - (attempt_number - 1) * 0.3)), max_points // 3)
        
        # Update answer object
        answer_obj.answered_correctly = True
        answer_obj.points_awarded = points_awarded
        answer_obj.answer_text = provided_answer
        answer_obj.matched_with = matched_answer
        answer_obj.match_type = match_type
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