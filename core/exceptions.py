"""
Custom exception handlers for DRF
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """
    Custom exception handler that formats errors consistently
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    # If response is None, it means DRF couldn't handle the exception
    # We'll create a generic error response
    if response is None:
        response = Response(
            {'error': True, 'detail': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    else:
        # Customize the response data structure
        custom_response_data = {
            'error': True,
            'detail': response.data
        }
        
        # If it's a validation error, format it nicely
        if isinstance(response.data, dict):
            if 'detail' in response.data:
                custom_response_data['detail'] = response.data['detail']
            elif 'non_field_errors' in response.data:
                custom_response_data['detail'] = response.data['non_field_errors']
            else:
                custom_response_data['detail'] = response.data
        else:
            custom_response_data['detail'] = response.data
        
        response.data = custom_response_data

    return response

