from rest_framework import serializers

from .models import Resource


class ResourceSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    # Tells the frontend whether *this* request's user may delete this row,
    # so the UI doesn't have to re-derive the "own upload, or platform admin"
    # rule itself — the real enforcement is still server-side, in
    # resources.views.ResourceViewSet.perform_destroy.
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            'id', 'organization', 'title', 'description', 'file',
            'uploaded_by', 'uploaded_by_name', 'uploaded_at', 'can_delete',
        ]
        read_only_fields = ['organization', 'uploaded_by', 'uploaded_at']
        extra_kwargs = {
            # Accepted on upload but never echoed back: the raw storage path
            # is never handed to a client. The protected viewer gets PDF
            # bytes exclusively through the authenticated
            # ResourceViewSet.stream action instead — see its docstring.
            # Unlike course/narration media, there's deliberately no
            # unauthenticated way to reach a resource's file at all.
            'file': {'write_only': True},
        }

    def get_uploaded_by_name(self, obj):
        if not obj.uploaded_by:
            return None
        full_name = f'{obj.uploaded_by.first_name} {obj.uploaded_by.last_name}'.strip()
        return full_name or obj.uploaded_by.email

    def get_can_delete(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return False
        user = request.user
        if user.role == user.Role.PLATFORM_ADMIN:
            return True
        return user.role == user.Role.ORG_ADMIN and obj.uploaded_by_id == user.id
