import ast
import json
from rest_framework import permissions, status
import gzip
from io import BytesIO
from django.http import HttpResponse
from django.http import FileResponse

class ResponseFormatMiddleware:
    """
    Custom middleware for changing response
    """
    admin_panel_check = None
    rendered_content = None

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self.admin_panel_check = None
        response = self.get_response(request)

        if isinstance(response, FileResponse):
            # Handle FileResponse instances appropriately
            return response

        if response.has_header('Content-Encoding') and response['Content-Encoding'] == 'gzip':
            compressed_data = response.content
            decompressed_data = gzip.decompress(compressed_data)
            my_response = decompressed_data.decode('utf-8')
        else:
            my_response = response.content.decode('utf-8')

        try:
            self.rendered_content = response.rendered_content
        except Exception as e:
            print("Exception in ResponseFormatMiddleware/__call__", str(e))
            self.rendered_content = None

        try:
            self.admin_panel_check = response.accepted_renderer
        except Exception as e:
            print("Exception in ResponseFormatMiddleware/__call__:", str(e))
            self.admin_panel_check = None
        if self.admin_panel_check is not None:
            my_data = json.loads(my_response)

            if my_data.get("code", "") == 'token_not_valid':
                try:
                    json_response = {"statusMessage": "Ticket not valid or expired", "data": [], "statusCode": status.HTTP_401_UNAUTHORIZED, "errorStatus": "True"}
                    json_to_string = json.dumps(json_response)
                    string_to_bytes = json_to_string.encode()
                    response.content = string_to_bytes
                    response.status_code = 200
                except AttributeError:
                    pass

            if my_data.get("access", None) and my_data.get("refresh", None):
                access_token = my_data.get("access", None)
                refresh_token = my_data.get("refresh", None)
                json_response = {"statusMessage": "Ticket refreshed successfully", "data": {"access_token": access_token, "refresh_token": refresh_token}, "statusCode": status.HTTP_200_OK, "errorStatus": "False"}
                json_to_string = json.dumps(json_response)
                string_to_bytes = json_to_string.encode()
                response.content = string_to_bytes
                response.status_code = 200

        return response


class XSSProtectionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['X-XSS-Protection'] = '1; mode=block'
        return response