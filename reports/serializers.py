from rest_framework import serializers
from .models import DailySales, ShiftReport

class DailySalesSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source='location.name', read_only=True)
    
    class Meta:
        model = DailySales
        fields = '__all__'

class ShiftReportSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source='location.name', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = ShiftReport
        fields = '__all__'