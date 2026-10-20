from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Sum, Avg, Count
from datetime import timedelta

from apps.members.models import Membership, CheckIn
from apps.workouts.models import Workout, WorkoutSet, PersonalRecord, Exercise
from apps.notifications.models import Notification
from apps.facilities.models import Facility


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard(request):
    """
    GET /api/dashboard/
    One endpoint, everything the Dashboard needs.
    """
    user = request.user
    now = timezone.now()
    today = timezone.localdate()
    thirty_days_ago = now - timedelta(days=30)

    # ============================================
    # WORKOUT STATS
    # ============================================
    workouts_qs = Workout.objects.filter(member=user)
    completed_workouts = workouts_qs.filter(status='completed')
    recent_workouts = completed_workouts.filter(completed_at__gte=thirty_days_ago)

    # Streak
    streak = 0
    check_date = today
    while completed_workouts.filter(completed_at__date=check_date).exists():
        streak += 1
        check_date -= timedelta(days=1)

    # Total tonnage
    total_tonnage = completed_workouts.aggregate(
        t=Sum('total_tonnage_kg')
    )['t'] or 0

    recent_tonnage = recent_workouts.aggregate(
        t=Sum('total_tonnage_kg')
    )['t'] or 0

    # Avg velocity
    avg_velocity = (
        recent_workouts
        .filter(avg_velocity__isnull=False)
        .aggregate(a=Avg('avg_velocity'))['a'] or 0
    )

    # ============================================
    # RECENT WORKOUTS (for logs)
    # ============================================
    workouts_list = []
    for w in completed_workouts.order_by('-completed_at')[:5]:
        workouts_list.append({
            'id': w.id,
            'name': w.name,
            'status': w.status,
            'type': 'strength',  # inferred from category
            'started_at': w.started_at.isoformat() if w.started_at else None,
            'completed_at': w.completed_at.isoformat() if w.completed_at else None,
            'duration_minutes': w.duration_minutes,
            'total_exercises': w.total_exercises,
            'total_sets': w.total_sets,
            'total_tonnage_kg': float(w.total_tonnage_kg or 0),
            'is_pr': False,
        })

    # ============================================
    # MEMBERSHIP
    # ============================================
    membership_data = None
    try:
        m = Membership.objects.select_related('plan').get(member=user)
        membership_data = {
            'id': m.id,
            'plan': {
                'name': m.plan.display_name,
                'tier': m.plan.name,
            },
            'status': m.status,
            'start_date': m.start_date.isoformat(),   # = the day the registration was approved
            'expiry_date': m.expiry_date.isoformat(),
            'days_remaining': m.days_remaining,
            'time_remaining': m.time_remaining,       # months + days left, % of plan used
            'auto_renew': m.auto_renew,
        }
    except Membership.DoesNotExist:
        pass

    # ============================================
    # NOTIFICATIONS
    # ============================================
    unread_count = Notification.objects.filter(
        recipient=user, is_read=False
    ).count()

    # ============================================
    # TODAY'S WORKOUT (in progress or last completed)
    # ============================================
    in_progress = workouts_qs.filter(status='in_progress').order_by('-started_at').first()
    today_workout = None
    if in_progress:
        # Build with exercises and sets
        exercises = []
        for we in in_progress.exercises.all()[:3]:
            sets_data = [{
                'set_number': s.set_number,
                'reps': s.reps,
                'weight_kg': float(s.weight_kg),
                'is_pr': s.is_pr,
                'is_warmup': s.is_warmup,
            } for s in we.sets.all()]

            exercises.append({
                'id': we.id,
                'name': we.exercise.name,
                'muscle': we.exercise.primary_muscle,
                'sets': sets_data,
                'total_sets': we.sets.count(),
            })

        today_workout = {
            'id': in_progress.id,
            'name': in_progress.name,
            'status': 'in_progress',
            'started_at': in_progress.started_at.isoformat(),
            'total_exercises': in_progress.total_exercises or len(exercises),
            'total_sets': in_progress.total_sets or sum(e['total_sets'] for e in exercises),
            'rpe_avg': float(in_progress.rpe_avg) if in_progress.rpe_avg else None,
            'exercises': exercises,
        }

    # ============================================
    # BIOMETRIC DATA (from latest workout)
    # ============================================
    latest_workout = completed_workouts.order_by('-completed_at').first()
    biometric = {
        'calories': latest_workout.calories_burned if latest_workout else 0,
        'avg_velocity': float(latest_workout.avg_velocity) if latest_workout and latest_workout.avg_velocity else 0,
        'heart_rate': 178,         # would come from wearables (future)
        'heart_zone': 'Zone 4 (Threshold Hypertrophy)',
        'velocity_delta': '+0.12',
        'hrv_delta': '+14ms via Sleep Matrix',
        'recovery_score': 91,
    }

    # ============================================
    # AI DIRECTIVES (rule-based insights)
    # ============================================
    directives = []
    # If streak is 15+
    if streak >= 15:
        directives.append({
            'tag': 'Milestone',
            'tag_color': 'primary',
            'icon': 'emoji_events',
            'title': f'{streak}-Day Streak Milestone',
            'body': 'You are on a strong consistency run. Consider a deload to prevent overtraining.',
            'footer': 'Suggested Recovery',
            'cta': 'View Options',
        })

    # If no workouts in 3 days
    last_workout_date = (
        completed_workouts.order_by('-completed_at')
        .values_list('completed_at__date', flat=True)
        .first()
    )
    if last_workout_date and (today - last_workout_date).days >= 3:
        directives.append({
            'tag': 'Recovery Alert',
            'tag_color': 'primary',
            'icon': 'ac_unit',
            'title': '15-Min Cryo Chamber Pod',
            'body': f'Your last session was {(today - last_workout_date).days} days ago. A recovery pod session will reset your HRV.',
            'footer': 'Cryo Pod Available',
            'cta': 'Book Slot',
        })

    # Always show a course/recovery recommendation
    directives.append({
        'tag': 'New Masterclass',
        'tag_color': 'accent',
        'icon': 'school',
        'title': 'VBT Bar Speed: Kinetic Force',
        'body': 'Led by Dr. Elias Vance. Master velocity loss thresholds for explosive output.',
        'footer': '28 MIN · VIDEO',
        'cta': 'Watch Now',
    })

    # ============================================
    # FLOOR DENSITY (from facilities)
    # ============================================
    facilities = Facility.objects.filter(is_active=True)[:3]
    floor_density = {
        'overall_percent': 68,
        'label': 'Moderate Peak',
        'facility': 'District 01 HQ Status',
        'location': 'Metro Station Sub-Level Alpha',
        'zones': [
            {
                'label': f.name,
                'percent': f.utilization,
                'accent': f.utilization >= 80,
            }
            for f in facilities
        ],
    }

    # ============================================
    # RESPONSE
    # ============================================
    return Response({
        'user': {
            'id': user.id,
            'full_name': user.full_name,
            'first_name': user.first_name,
            'avatar': user.avatar.url if user.avatar else None,
        },
        'stats': {
            'total_workouts': completed_workouts.count(),
            'recent_30d': {
                'workouts': recent_workouts.count(),
                'total_tonnage_kg': float(recent_tonnage),
            },
            'total_tonnage_all_time': float(total_tonnage),
            'current_streak_days': streak,
            'total_prs': PersonalRecord.objects.filter(member=user).count(),
            'avg_velocity': float(avg_velocity),
        },
        'membership': membership_data,
        'unread_notifications': unread_count,
        'recent_workouts': workouts_list,
        'today_workout': today_workout,
        'biometric': biometric,
        'directives': directives,
        'floor_density': floor_density,
    })