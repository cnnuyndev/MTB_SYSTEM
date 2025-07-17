from rest_framework import serializers
from ticket_movie.models import Movie
from datetime import date

class MovieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movie
        fields = [
            'id',
            'title',
            'description',
            'duration',
            'release_date',
            'genre',
            'director',
            'movie_cast',
            'poster_url',
            'trailer_url',
            'rating',
            'status',
        ]
        extra_kwargs = {
            'rating': {'read_only': True},
            'status': {'read_only': True}, 
        }

    def validate_duration(self, value):
        if value <= 0:
            raise serializers.ValidationError("Thời lượng phim phải lớn hơn 0 phút.")
        return value

    def validate_release_date(self, value):
        if value < date(1900, 1, 1):
            raise serializers.ValidationError("Ngày phát hành không hợp lệ.")
        return value