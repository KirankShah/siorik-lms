from rest_framework import serializers

from .models import Organization, User


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'slug', 'logo', 'is_active']


class UserSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'role',
            'organization',
            'phone_number',
            'is_active',
        ]
        read_only_fields = fields
