from rest_framework import serializers

from accounts.models import User
from courses.models import Slide

from .models import ScenarioAttempt, ScenarioChoice, ScenarioNode

PRIVILEGED_ROLES = (User.Role.INSTRUCTOR, User.Role.ORG_ADMIN, User.Role.PLATFORM_ADMIN)


class ScenarioChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScenarioChoice
        fields = ['id', 'node', 'choice_text', 'next_node', 'feedback_text', 'is_recommended', 'order']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request is None or request.user.role not in PRIVILEGED_ROLES:
            # is_recommended flags the "best" path through the tree — same
            # answer-key treatment as Choice.is_correct elsewhere. It isn't
            # needed to render or navigate the scenario (the server computes
            # reached_recommended_ending itself once an attempt is submitted),
            # so stripping it costs the learner nothing.
            data.pop('is_recommended', None)
        return data


class ScenarioNodeSerializer(serializers.ModelSerializer):
    choices = ScenarioChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = ScenarioNode
        fields = ['id', 'slide', 'node_key', 'prompt', 'prompt_image', 'is_start', 'choices']


class ScenarioNodeWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScenarioNode
        fields = ['id', 'slide', 'node_key', 'prompt', 'prompt_image', 'is_start']


class ScenarioChoiceWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScenarioChoice
        fields = ['id', 'node', 'choice_text', 'next_node', 'feedback_text', 'is_recommended', 'order']

    def validate(self, attrs):
        node = attrs.get('node') or getattr(self.instance, 'node', None)
        next_node = attrs.get('next_node')
        if next_node and node and next_node.slide_id != node.slide_id:
            raise serializers.ValidationError({'next_node': 'Must be a node on the same slide.'})
        return attrs


class ScenarioAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScenarioAttempt
        fields = ['id', 'enrollment', 'slide', 'path_taken', 'reached_recommended_ending', 'completed_at']
        read_only_fields = fields


class ScenarioAttemptInputSerializer(serializers.Serializer):
    slide = serializers.PrimaryKeyRelatedField(queryset=Slide.objects.all())
    path_taken = serializers.PrimaryKeyRelatedField(queryset=ScenarioChoice.objects.all(), many=True)

    def validate(self, attrs):
        slide = attrs['slide']
        if slide.slide_type != Slide.SlideType.SCENARIO:
            raise serializers.ValidationError({'slide': 'Not a scenario slide.'})
        path_taken = attrs['path_taken']
        if not path_taken:
            raise serializers.ValidationError({'path_taken': 'Path must not be empty.'})
        for choice in path_taken:
            if choice.node.slide_id != slide.id:
                raise serializers.ValidationError({'path_taken': 'Choice does not belong to this scenario.'})
        if path_taken[-1].next_node_id is not None:
            raise serializers.ValidationError({'path_taken': 'Path must end at a choice that ends the scenario.'})
        return attrs
