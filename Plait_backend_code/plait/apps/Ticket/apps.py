from django.apps import AppConfig

class TicketConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.Ticket'

    def ready(self):
        try:
            from apps.Ticket.models import AnalysisRequest
            try:
                current_tickets = AnalysisRequest.objects.filter(status='progress')
                for current_ticket in current_tickets:
                    current_ticket.status = 'queue'
                    current_ticket.save()
                    print('Status updated for the ticket in progress.')
            except AnalysisRequest.DoesNotExist:
                print('No ticket in progress found.')
        except:
            print("No table found. Please insure you did migrations correctly.")