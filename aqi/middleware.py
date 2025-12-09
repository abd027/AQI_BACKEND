"""
JWT Authentication middleware for WebSocket connections
"""
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from urllib.parse import parse_qs
import jwt

User = get_user_model()


@database_sync_to_async
def get_user_from_token(token_string):
    """Get user from JWT token"""
    try:
        # Validate token
        UntypedToken(token_string)
        
        # Decode token to get user ID
        decoded_data = jwt.decode(token_string, options={"verify_signature": False})
        user_id = decoded_data.get('user_id')
        
        if user_id:
            try:
                return User.objects.get(id=user_id)
            except User.DoesNotExist:
                return AnonymousUser()
    except (InvalidToken, TokenError, jwt.DecodeError, jwt.InvalidTokenError):
        pass
    
    return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom middleware to authenticate WebSocket connections using JWT tokens
    """
    
    async def __call__(self, scope, receive, send):
        # Extract token from query string
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]
        
        if token:
            scope['user'] = await get_user_from_token(token)
        else:
            scope['user'] = AnonymousUser()
        
        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    """Stack JWT auth middleware"""
    return JWTAuthMiddleware(inner)


