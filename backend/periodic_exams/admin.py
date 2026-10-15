from django.contrib import admin

from .models import (
    PeriodicExamCycle,
    PeriodicExamCycleQuestion,
    PeriodicExamParticipant,
    PeriodicExamSettings,
)

admin.site.register(PeriodicExamSettings)
admin.site.register(PeriodicExamCycle)
admin.site.register(PeriodicExamCycleQuestion)
admin.site.register(PeriodicExamParticipant)
