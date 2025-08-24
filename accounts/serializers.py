# accounts/serializers.py
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class EmailOrUsernameTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Allow login with username OR email."""

    @classmethod
    def get_token(cls, user):
        tok = super().get_token(user)
        tok["username"] = user.get_username()
        tok["email"] = user.email or ""
        return tok

    def validate(self, attrs):
        supplied = (attrs.get("username") or "").strip()
        if "@" in supplied:
            try:
                user = User.objects.get(email__iexact=supplied)
                attrs["username"] = getattr(user, User.USERNAME_FIELD)
            except User.DoesNotExist:
                pass
        else:
            try:
                user = User.objects.get(**{f"{User.USERNAME_FIELD}__iexact": supplied})
                attrs["username"] = getattr(user, User.USERNAME_FIELD)
            except User.DoesNotExist:
                pass

        data = super().validate(attrs)
        data["user"] = {
            "id": self.user.id,
            "username": self.user.get_username(),
            "email": self.user.email or "",
            "first_name": getattr(self.user, "first_name", "") or "",
            "last_name": getattr(self.user, "last_name", "") or "",
        }
        return data


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "password")

    def validate_username(self, v):
        if User.objects.filter(username__iexact=v).exists():
            raise serializers.ValidationError("Username already taken.")
        return v

    def validate_email(self, v):
        if v and User.objects.filter(email__iexact=v).exists():
            raise serializers.ValidationError("Email already registered.")
        return v

    def create(self, validated_data):
        pwd = validated_data.pop("password")
        user = User.objects.create_user(**validated_data)
        user.set_password(pwd)
        user.save()
        return user

    def to_representation(self, instance):
        ref = RefreshToken.for_user(instance)
        return {
            "user": {
                "id": instance.id,
                "username": instance.get_username(),
                "email": instance.email or "",
                "first_name": getattr(instance, "first_name", "") or "",
                "last_name": getattr(instance, "last_name", "") or "",
            },
            "access": str(ref.access_token),
            "refresh": str(ref),
        }
