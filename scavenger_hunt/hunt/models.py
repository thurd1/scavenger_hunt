from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.conf import settings
import random
import string
from django.utils import timezone

def generate_lobby_code():
    return str(random.randint(100000, 999999))

class Lobby(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=6, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    teams = models.ManyToManyField('Team', related_name='participating_lobbies')
    is_active = models.BooleanField(default=True)
    hunt_started = models.BooleanField(default=False)
    start_time = models.DateTimeField(null=True, blank=True)
    race = models.ForeignKey('Race', on_delete=models.CASCADE, null=True)

    def save(self, *args, **kwargs):
        if not self.code:
            while True:
                code = str(random.randint(100000, 999999))
                if not Lobby.objects.filter(code=code).exists():
                    self.code = code
                    break
        if self.hunt_started and not self.start_time:
            self.start_time = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Lobby {self.code}"
    
class Team(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=6, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.code:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            self.code = code
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
    
class Riddle(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    question = models.TextField()
    answer = models.CharField(max_length=200)
    points = models.IntegerField(default=10)
    sequence = models.IntegerField()

    def __str__(self):
        return f"Riddle {self.sequence}: {self.question[:50]}"

class Clue(models.Model):
    riddle = models.ForeignKey(Riddle, on_delete=models.CASCADE, related_name="clues")
    text = models.TextField()

    def __str__(self):
        return self.text[:50]

class GameSession(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

class CustomUserManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(username, email, password, **extra_fields)

class CustomUser(AbstractUser):
    is_hunt_leader = models.BooleanField(default=False)
    objects = CustomUserManager()

    def __str__(self):
        return self.username

class TeamMember(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='members')
    role = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.role} - {self.team.name}"

class Submission(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="submissions")
    riddle = models.ForeignKey(Riddle, on_delete=models.CASCADE, related_name="submissions")
    attempt = models.IntegerField(default=0)
    is_correct = models.BooleanField(default=False)
    picture = models.ImageField(upload_to='pictures/', blank=True, null=True)

    def __str__(self):
        return f"Submission by {self.user.username} for Riddle {self.riddle.sequence}: {'Correct' if self.is_correct else 'Incorrect'}"

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ROLE_CHOICES = [
        ('hunt_leader', 'Hunt Leader'),
        ('admin', 'Admin'),
    ]
    role = models.CharField(max_length=11, choices=ROLE_CHOICES, default='hunt_leader')

    def __str__(self):
        return self.user.username

class Race(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    start_location = models.CharField(max_length=200, default='Default Location')
    time_limit_minutes = models.IntegerField(default=60)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Zone(models.Model):
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name='zones')
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.race.name}"

    class Meta:
        ordering = ['created_at']

class Question(models.Model):
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    answer = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Question for {self.zone}: {self.question_text[:50]}"
