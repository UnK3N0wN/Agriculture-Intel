from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import update_last_login
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from config.exceptions import human_wait

from . import lockout
from .serializers import (
    LoginSerializer,
    LogoutSerializer,
    MeSerializer,
    MeUpdateSerializer,
    RegisterSerializer,
)

from .throttles import RegisterRateThrottle

User = get_user_model()


def issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}

def locked_response(retry_after_seconds):
    response = Response(
        {
            "code": "login_locked",
            "detail": (
                "Too many failed login attempts. "
                f"Please try again in {human_wait(retry_after_seconds)}."
            ),
            "retry_after_seconds": retry_after_seconds,
        },
        status=status.HTTP_429_TOO_MANY_REQUESTS,
    )
    response["Retry-After"] = str(retry_after_seconds)
    return response

class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AnonRateThrottle, RegisterRateThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        body = {"user": MeSerializer(user).data, **issue_tokens(user)}
        return Response(body, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"].strip()
        password = serializer.validated_data["password"]
        ip = lockout.get_client_ip(request)

        state = lockout.check_locked(username, ip)
        if state.locked:
            return locked_response(state.retry_after_seconds)

        # Usernames are matched case-insensitively. We always call authenticate()
        # (even for unknown names) so response time doesn't reveal which names exist.
        found = User.objects.filter(username__iexact=username).first()
        user = authenticate(
            request,
            username=found.username if found else username,
            password=password,
        )
        if user is None:
            state, remaining = lockout.register_failure(username, ip)
            if state.locked:
                return locked_response(state.retry_after_seconds)
            return Response(
                {"code": "invalid_credentials", "detail": "Invalid username or password.", "attempts_remaining": remaining,},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        lockout.reset(username, ip)
        update_last_login(None, user)
        return Response({"user": MeSerializer(user).data, **issue_tokens(user)})


class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            return Response(
                {"code": "invalid_token", "detail": "This session token is invalid or already ended."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data)

    def patch(self, request):
        serializer = MeUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(MeSerializer(user).data)