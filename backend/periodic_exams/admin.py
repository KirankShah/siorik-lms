from django.contrib import admin

from .models import (
    PeriodicExamAttempt,
    PeriodicExamAttemptQuestion,
    PeriodicExamCycle,
    PeriodicExamCycleQuestion,
    PeriodicExamParticipant,
    PeriodicExamQuestionUsage,
    PeriodicExamSettings,
)

admin.site.register(PeriodicExamSettings)
admin.site.register(PeriodicExamCycle)
admin.site.register(PeriodicExamCycleQuestion)
admin.site.register(PeriodicExamParticipant)
admin.site.register(PeriodicExamAttempt)
admin.site.register(PeriodicExamAttemptQuestion)
admin.site.register(PeriodicExamQuestionUsage)
