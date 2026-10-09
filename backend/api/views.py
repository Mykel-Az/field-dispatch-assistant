from django.shortcuts import render

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
# Create your views here.

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint to verify the API is running.
    """
    return Response({"status": "ok"}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def skills(request):
    """
    Endpoint to retrieve a list of skills.
    """
    skills_list = ["Skill 1", "Skill 2", "Skill 3"]  # Replace with actual skill retrieval logic
    return Response({"skills": skills_list}, status=status.HTTP_200_OK)