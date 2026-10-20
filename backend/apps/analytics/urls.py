from django.urls import path

from . import views as v

urlpatterns = [
    path("offices/", v.OfficeScorecardView.as_view(), name="analytics-offices"),
    path("offices.csv", v.OfficeScorecardCSV.as_view(), name="analytics-offices-csv"),
    path("offices/<int:pk>/", v.OfficeDetailView.as_view(), name="analytics-office-detail"),
    # Step 10: accountability / proof of work
    path("accountability/", v.AccountabilityView.as_view(), name="analytics-accountability"),
    path("offices/<int:pk>/people/", v.OfficePeopleView.as_view(), name="analytics-office-people"),
    path("people/<int:pk>/", v.PersonLedgerView.as_view(), name="analytics-person-ledger"),
    # Step 11: executive decision support
    path("executive/", v.ExecutiveView.as_view(), name="analytics-executive"),
    path("executive/barangays.csv", v.ExecutiveBarangayCSV.as_view(), name="analytics-executive-csv"),
]
