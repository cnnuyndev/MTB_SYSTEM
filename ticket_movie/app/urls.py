from django.urls import path
from .views import MainView, MoviesSchedule, SeatsScreen, SeatsScreenBooking, TranslateView

urlpatterns = [
    path('translate/', TranslateView.as_view(), name='translate'),
    path('main/data/', MainView.as_view(), name='get_data'),
    path('main/movies/schedule/', MoviesSchedule.as_view(), name='movie_schedule'),
    path('main/screen/seat/', SeatsScreen.as_view(), name='screen_seat'),
    path('main/screen/seat/booking/', SeatsScreenBooking.as_view(), name='screen_seat_booking'),
]
