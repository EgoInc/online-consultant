from django.urls import path

from .views import DialogMessageView, ProductSearchView, StoreCreateView, StoreStatusView

urlpatterns = [
    path("stores", StoreCreateView.as_view()),
    path("stores/<str:store_id>/status", StoreStatusView.as_view()),
    path("stores/<str:store_id>/search", ProductSearchView.as_view()),
    path("stores/<str:store_id>/dialog/messages", DialogMessageView.as_view()),
]
