"""mcp_app URL Configuration"""
from django.urls import path
from . import views

app_name = 'mcp_app'

urlpatterns = [
    path('', views.index, name='index'),
    path('memos/', views.memo_list, name='memo_list'),
]