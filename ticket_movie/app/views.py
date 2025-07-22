from datetime import datetime
from decimal import Decimal
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser
import os, polib
from ticket_movie.app.serializers import CinemaSerializer, CitiesSerializer, MovieSerializer
from ticket_movie.models import Booking, BookingSeat, Cinema, City, Movie, Seat, Showtime, User
from django.db.models import Max, Count
from django.utils.crypto import get_random_string
from django.db import transaction
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
        
        cities = City.objects.all().order_by('id')
        cities_serializer = CitiesSerializer(cities, many=True)
        cinemas = Cinema.objects.all().order_by('id')
        cinemas_serializer = CinemaSerializer(cinemas, many=True)
        return Response({ 
                            "movies": serializer.data , 
                            "cities": cities_serializer.data,
                            "cinemas": cinemas_serializer.data,
                        })
        
class MoviesSchedule(APIView):
    def post(self, request):
        cinema_id = request.data.get("cinema_id", 1)
        day_str = request.data.get("day")
        if day_str:
            day = datetime.strptime(day_str, '%Y-%m-%d').date()
            
        start_datetime = datetime.combine(day, datetime.min.time())
        end_datetime = datetime.combine(day, datetime.max.time())

        showtimes = Showtime.objects.select_related('movie', 'screen') \
            .filter(status='scheduled', screen__cinema_id=cinema_id
                    , start_time__gt=timezone.now()
                    , start_time__gte=start_datetime
                    , start_time__lte=end_datetime) \
            .order_by('id')

        data = []
        for st in showtimes:
            data.append({
                "showtime_id": st.id,
                "movie_id": st.movie.id,
                "movie_poster_url": st.movie.poster_url,
                "movie_title": st.movie.title,
                "movie_genre": st.movie.genre,
                "duration": st.movie.duration,
                "start_time": st.start_time,
                "end_time": st.end_time,
                "base_price": float(st.base_price),
                "screen_id": st.screen.id,
                "screen_name": st.screen.name,
                "screen_type": st.screen.type,
            })

        return Response(data)
    
class SeatsScreen(APIView):
    def post(self, request):
        screen_id = request.data.get("screen_id", 1)
        max_number = Seat.objects.filter(screen_id=screen_id).aggregate(Max('number'))['number__max']
        max_row = Seat.objects.filter(screen_id=screen_id).values('row').distinct().count()

        queryset = Seat.objects.raw(f"""
            SELECT 
                s.*,
                s.row || seat_index AS seat_name,
                CASE 
                    WHEN s.type = 'couple' THEN s.row || (seat_index + 1)
                    ELSE NULL
                END AS seat_name_couple
            FROM (
                SELECT 
                    s.*,
                    SUM(
                        CASE 
                            WHEN s.type = 'couple' THEN 2
                            ELSE 1
                        END
                    ) OVER (
                        PARTITION BY s.row 
                        ORDER BY s.number 
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ) - 
                    CASE 
                        WHEN s.type = 'couple' THEN 1
                        ELSE 0
                    END AS seat_index
                FROM public.seats s
                WHERE s.screen_id = %s
            ) s
            ORDER BY s.row, s.number
        """, [screen_id])

        data = [
            {
                "id": seat.id,
                "screen_id": seat.screen_id,
                "row": seat.row,
                "number": seat.number,
                "type": seat.type,
                "is_active": seat.is_active,
                "seat_name": seat.seat_name,
                "seat_name_couple": seat.seat_name_couple,
            }
            for seat in queryset
        ]
        
        new_data = []

        rows = {}
        for seat in data:
            row = seat["row"] 
            if row not in rows:
                rows[row] = {} # rows{"A"}
            rows[row][seat["number"]] = seat # rows{"A": ""}

        for row_label in sorted(rows.keys()):
            row_data = []
            seat_couple = False
            for num in range(1, max_number + 1):
                if num in rows[row_label]:
                    seat_temp = rows[row_label][num]
                    
                    if seat_temp['type'] == "couple":
                        seat_couple = True
                        
                    row_data.append(seat_temp)
                else:
                    if seat_couple:
                        seat_couple = False
                    else:
                        row_data.append(False)
            new_data.append(row_data)

        return Response({
            "data": new_data,
            "max_number": max_number,
            "max_row": max_row,
        })
        
class SeatsScreenBooking(APIView):
    def post(self, request):
        data = request.data
        user_id = data.get('user_id')
        showtime_id = data.get('showtime_id')
        total_amount = data.get('total_amount')
        seats_id = data.get('seats_id')
        
        user = User.objects.get(id=user_id)
        showtime = Showtime.objects.get(id=showtime_id)
        booking = Booking.objects.create(
            user=user,
            showtime=showtime,
            booking_code=get_random_string(10).upper(),  # hoặc bạn tự sinh code khác
            total_amount=Decimal(total_amount),
            status=Booking.BookingStatus.PENDING
        )
        
        for id in seats_id:
            seat_temp = Seat.objects.get(id = id)
            price = showtime.base_price * 2 if seat_temp.type == "couple" else showtime.base_price
            booking_seat = BookingSeat.objects.create(
                booking=booking,
                seat=seat_temp,
                price = price,  # hoặc bạn tự sinh code khác
            )
            
            seat_temp.is_active = False
            seat_temp.save()
            
        return Response({"message": "OK"})
class CinemaCreateView(APIView):
    permission_classes = [IsAdminUser]
    @transaction.atomic
    def post(self, request):
        try:
            serializer = CinemaSerializer(data=request.data, context={'request': request})
            
            if not serializer.is_valid():
                return Response({
                    'success': False,
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            serializer.save()
            
            return Response({
                'success': True,
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)