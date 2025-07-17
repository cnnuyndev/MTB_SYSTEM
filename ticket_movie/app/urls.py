from django.urls import path
from .views import MainView, TranslateView

urlpatterns = [
    path('translate/', TranslateView.as_view(), name='translate'),
    path('main/data/', MainView.as_view(), name='get_data'),
]
