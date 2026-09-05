from rest_framework import serializers

from .models import SlideNarration


class SlideNarrationSerializer(serializers.ModelSerializer):
    """
    Entirely system-generated — there is no manual create/update endpoint,
    only the generate action (narration.views.SlideNarrationViewSet.generate),
    so every field here is read-only.
    """

    generated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SlideNarration
        fields = [
            'id',
            'slide',
            'language',
            'script_text',
            'audio_file',
            'voice_name',
            'generated_by',
            'generated_by_name',
            'generated_at',
        ]
        read_only_fields = fields

    def get_generated_by_name(self, obj):
        if not obj.generated_by:
            return None
        full_name = f'{obj.generated_by.first_name} {obj.generated_by.last_name}'.strip()
        return full_name or obj.generated_by.email
