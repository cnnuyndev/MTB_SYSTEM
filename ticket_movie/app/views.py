from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import requests, os, polib
from ticket_movie.app.serializers import MovieSerializer
from ticket_movie.models import Movie

class TranslateView(APIView):
    def get(self, request):
        try:
            TRANSLATION_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'translations'))
            lang = request.query_params.get("lang")
            if not lang:
                return Response({"error": "Missing 'lang' query parameter"}, status=status.HTTP_400_BAD_REQUEST)

            filepath = os.path.join(TRANSLATION_DIR, f"{lang}.po")
            if not os.path.exists(filepath):
                return Response({"error": "Translation file not found"}, status=status.HTTP_404_NOT_FOUND)

            po = polib.pofile(filepath)
            translations = {entry.msgid: entry.msgstr for entry in po if entry.msgstr}
            return Response(translations)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
class MainView(APIView):
    
    def get(self, request):
        movies = Movie.objects.all().order_by('-id')
        serializer = MovieSerializer(movies, many=True)
        return Response(serializer.data)