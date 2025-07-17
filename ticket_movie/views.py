from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from .serializers import (
    UserCreateSerializer,
    UserSerializer,
    LoginSerializer,
    RefreshTokenSerializer,
    ChangePasswordSerializer,
    LogoutSerializer,
    SocialLoginSerializer
)

import requests, os, polib
from .models import User
from rest_framework_simplejwt.tokens import RefreshToken


class RegisterView(APIView):
    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)
            return Response({
                'error': "",
                'message': "Đăng nhập thành công",
                'statusCode': 201,
                'data': {
                    'user': UserSerializer(user).data,
                    'refresh_token': str(refresh),
                    'access_token': str(refresh.access_token),
                }
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            refresh_token = serializer.validated_data['refresh']
            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(status=status.HTTP_205_RESET_CONTENT)
        except TokenError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class RefreshTokenView(APIView):
    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        if serializer.is_valid():
            try:
                refresh_token = serializer.validated_data['refresh']
                token = RefreshToken(refresh_token)
                access_token = str(token.access_token)
                return Response({'access': access_token})
            except TokenError as e:
                return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user
        new_password = serializer.validated_data['new_password']
        user.set_password(new_password)
        user.save()

        return Response(
            {'message': 'Mật khẩu đã được cập nhật thành công'},
            status=status.HTTP_200_OK
        )


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    # Lấy thông tin user
    def get(self, request):
        try:
            serializer = UserSerializer(
                request.user, context={'request': request})
            return Response({
                'success': True,
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Cập nhật thông tin user
    def put(self, request):
        try:
            user = request.user
            serializer = UserSerializer(
                user,
                data=request.data,
                partial=True,
                context={'request': request}
            )

            if not serializer.is_valid():
                return Response({
                    'success': False,
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

            serializer.save()
            return Response({
                'success': True,
                'data': serializer.data,
                'message': 'Cập nhật thông tin thành công'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SocialLoginView(APIView):
    def post(self, request):
        serializer = SocialLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        provider = serializer.validated_data['provider']
        access_token = serializer.validated_data['access_token']

        if provider == 'google':
            user_info_url = 'https://www.googleapis.com/oauth2/v3/userinfo'
            headers = {'Authorization': f'Bearer {access_token}'}
            resp = requests.get(user_info_url, headers=headers)
            if resp.status_code != 200:
                return Response({'error': 'Invalid Google token'}, status=400)
            data = resp.json()
            email = data.get('email')
            social_id = data.get('sub')
            avatar = data.get('picture')
            full_name = data.get('name')
        elif provider == 'facebook':
            user_info_url = f'https://graph.facebook.com/me?fields=id,name,email,picture&access_token={access_token}'
            resp = requests.get(user_info_url)
            if resp.status_code != 200:
                return Response({'error': 'Invalid Facebook token'}, status=400)
            data = resp.json()
            email = data.get('email')
            social_id = data.get('id')
            avatar = data.get('picture', {}).get('data', {}).get('url')
            full_name = data.get('name')
        else:
            return Response({'error': 'Provider not supported'}, status=400)

        try:
            user = User.objects.get(provider=provider, social_id=social_id)
            # Cập nhật thông tin nếu cần
            user.email = email or user.email
            user.full_name = full_name or user.full_name
            user.avatar = avatar or user.avatar
            user.save()
        except User.DoesNotExist:
            user = User.objects.create_social_user(
                provider=provider,
                social_id=social_id,
                email=email,
                full_name=full_name,
                avatar=avatar,
                is_active=True,
                username=f'{provider}_{social_id}',
            )

        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })