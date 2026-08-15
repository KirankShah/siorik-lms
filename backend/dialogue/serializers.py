from rest_framework import serializers

from .models import Character, Scene


class CharacterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Character
        fields = ['id', 'name', 'role', 'avatar_image']


class SceneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scene
        fields = ['id', 'name', 'scene_type', 'background_image']
