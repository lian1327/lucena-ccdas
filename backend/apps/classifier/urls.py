from django.urls import path

from . import views as v

urlpatterns = [
    path("", v.MLOverviewView.as_view(), name="ml-overview"),
    path("train/", v.MLTrainView.as_view(), name="ml-train"),
    path("versions/<int:pk>/activate/", v.MLActivateView.as_view(), name="ml-activate"),
]
