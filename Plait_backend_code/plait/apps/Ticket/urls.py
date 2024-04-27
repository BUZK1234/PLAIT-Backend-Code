from django.urls import path
from .views import TicketView, TicketResultsView
# Create an instance of TicketView and start monitoring threads
# ticket_view_instance = TicketView()
# ticket_view_instance.start_monitoring()

urlpatterns = [
    path("create-ticket", TicketView.as_view({"post": "create_ticket"}), name='create_ticket'),
    path("ticket-list", TicketView.as_view({"get": "get_tickets"}), name='get_tickets'),
    path("download-file/<int:id>", TicketView.as_view({"get": "download_file"}), name='download_file'),
    path("upload-results", TicketResultsView.as_view({"post": "upload_results"}), name='upload_results'),
]