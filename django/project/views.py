# project/views.py
from django.http import JsonResponse
from django.db import connection

def health_check(request):
    try:
        connection.ensure_connection()
        return JsonResponse({"status": "ok"}, status=200)
    except Exception:
        return JsonResponse({"status": "error"}, status=503)