from django.contrib import admin

from .models import PeriodicExamCycle, PeriodicExamSettings

admin.site.register(PeriodicExamSettings)
admin.site.register(PeriodicExamCycle)
