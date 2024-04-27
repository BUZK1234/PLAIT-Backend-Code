from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from .models import AnalysisRequest
from subprocess import Popen, PIPE
from rest_framework import status
from rest_framework import viewsets
import json
from .serializers import AnalysisRequestSerializer
from django.http import FileResponse
from json.decoder import JSONDecodeError
from celery import shared_task
from django.conf import settings
import os
from django.core.mail import EmailMessage
import threading
import time
from rest_framework.pagination import PageNumberPagination

class TicketView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    parser_classes = [MultiPartParser]
    monitoring_started = False  # Class-level variable to track if monitoring has started

    def __init__(self):
        self.running_threads = {}
        self.running_threads_lock = threading.Lock()  # Lock for thread-safe access
        self.start_monitoring()

    def start_monitoring(self):
        try:
            if not TicketView.monitoring_started:  # Check if monitoring has already started
                # Start the thread monitoring function
                thread = threading.Thread(target=self.monitor_threads)
                thread.daemon = True  # Terminate when main thread exits
                thread.start()
                TicketView.monitoring_started = True  # Set monitoring flag to True
        except Exception as e:
            print(f"Error occurred while starting monitoring: {str(e)}")

    def create_ticket(self, request, format=None):
        try:
            uploaded_file = request.FILES.get('file')
            name = request.data.get('name')
            description = request.data.get("description")

            if not uploaded_file:
                return Response({"error": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

            user = request.user

            if AnalysisRequest.objects.filter(status='progress').count() >= 3:
                AnalysisRequest.objects.create(
                    user=user,
                    name=name,
                    file=uploaded_file,
                    description=description,
                    status='queue'
                )
                return Response({
                    "statusMessage": "Another process is currently in progress. This upload is queued.",
                    "errorStatus": False,
                    "data": [],
                    "statusCode": status.HTTP_200_OK,
                })

            # If no ticket is in progress, create the ticket with status 'progress'
            analysis_request_obj = AnalysisRequest.objects.create(user=user, name=name, file=uploaded_file,
                                                                  description=description, status='progress')

            # Start a thread for R script execution
            thread = threading.Thread(target=self.execute_r_script, args=(analysis_request_obj,))
            thread.start()

            # Track the thread by ticket ID
            with self.running_threads_lock:
                self.running_threads[analysis_request_obj.id] = thread

            return Response({
                "statusMessage": "R code execution started",
                "errorStatus": False,
                "data": [],
                "statusCode": status.HTTP_200_OK,
            })

        except Exception as e:
            print(f"Error occurred while creating ticket: {str(e)}")
            return Response({
                "statusMessage": str(e),
                "errorStatus": True,
                "data": [],
                "statusCode": status.HTTP_500_INTERNAL_SERVER_ERROR,
            })

    def execute_r_script(self, analysis_request_obj):
        try:
            r_script_path = os.path.join(settings.BASE_DIR, 'Server', 'DBS_Call.R')
            print(r_script_path)
            time.sleep(30)
            process = Popen(
                ['Rscript', r_script_path, analysis_request_obj.file.path, str(analysis_request_obj.id)],
                stdout=PIPE, stderr=PIPE)
            stdout, stderr = process.communicate()
            if process.returncode != 0:
                print(f"R script execution failed with error: {stderr.decode()}")
                analysis_request_obj.status = 'failed'
                analysis_request_obj.save()
                del self.running_threads[analysis_request_obj.id]
        except Exception as e:
            print(f"Error occurred while executing R script: {str(e)}")

    def monitor_threads(self):
        try:
            # Check running threads periodically and terminate if exceeds time limit
            while True:
                num_threads = len(self.running_threads)
                print(f"Number of running threads: {num_threads}")
                for ticket_id, thread in list(self.running_threads.items()):
                    if thread.is_alive():
                        # Check if the ticket has exceeded the time limit
                        analysis_request_obj = AnalysisRequest.objects.get(id=ticket_id)
                        if analysis_request_obj.status != 'killed':
                            elapsed_time = time.time() - analysis_request_obj.created_at.timestamp()
                            if elapsed_time > 60:  # If more than 60 seconds, mark ticket as killed
                                analysis_request_obj.status = 'killed'
                                analysis_request_obj.save()
                                message = f"Ticket {ticket_id} has been killed due to exceeding the time limit."
                                print(message)
                                with self.running_threads_lock:
                                    del self.running_threads[ticket_id]
                time.sleep(10)  # Check every 10 seconds
        except Exception as e:
            print(f"Error occurred in thread monitoring: {str(e)}")

    def get_tickets(self, request):
        try:
            user = request.user

            if user.is_superuser:
                analysis_requests = AnalysisRequest.objects.all().order_by('-created_at')
            else:
                analysis_requests = AnalysisRequest.objects.filter(user=user).order_by('-created_at')

            paginator = PageNumberPagination()
            paginator.page_size = 10  # Adjust the page size as needed

            result_page = paginator.paginate_queryset(analysis_requests, request)

            # Now result_page contains the objects for the current page determined by the request

            total_tickets = analysis_requests.count()
            in_progress_count = analysis_requests.filter(status='progress').count()
            queue_count = analysis_requests.filter(status='queue').count()
            completed_count = analysis_requests.filter(status='completed').count()
            failed_count = analysis_requests.filter(status='failed').count()

            custom_response = {
                "statusMessage": "Success",
                "errorStatus": False,
                "total_tickets": total_tickets,
                "in_progress_count": in_progress_count,
                "queue_count": queue_count,
                "completed_count": completed_count,
                "failed_count": failed_count,
                "data": AnalysisRequestSerializer(result_page, many=True, context={'request': request}).data,
                "next_page": paginator.get_next_link(),
                "previous_page": paginator.get_previous_link(),
                "total_pages": paginator.page.paginator.num_pages,
                "current_page": paginator.page.number,
                "statusCode": status.HTTP_200_OK,
            }

            return Response(custom_response)

        except Exception as e:
            custom_response = {
                "statusMessage": str(e),
                "errorStatus": True,
                "data": [],
                "statusCode": status.HTTP_500_INTERNAL_SERVER_ERROR,
            }
            return Response(custom_response)

    def download_file(self, request, id):
        try:
            analysis_request = AnalysisRequest.objects.get(id=id)
            file_path = analysis_request.file.path
            response = FileResponse(open(file_path, 'rb'))
            response['Content-Disposition'] = f'attachment; filename="{analysis_request.file.name}"'
            return response
        except AnalysisRequest.DoesNotExist:
            return Response({"error": "Analysis request not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TicketResultsView(viewsets.ViewSet):

    def upload_results(self, request):
        try:
            ticket_id = request.POST.get('ticket_id')
            file = request.FILES.get('file')

            analysis_request = AnalysisRequest.objects.get(id=ticket_id)
            user_email = analysis_request.user.email

            # Email the file to the user
            email_subject = 'Analysis Result'
            email_body = 'Please find attached the result of your analysis.'
            email = EmailMessage(email_subject, email_body, to=[user_email])
            email.attach(file.name, file.read(), file.content_type)
            email.send()
            analysis_request.status = 'completed'
            analysis_request.result.save(file.name, file, save=True)
            analysis_request.email_sent = True
            analysis_request.save()
            del self.running_threads[ticket_id]
            analysis_request_obj = AnalysisRequest.objects.filter(status='queue').order_by('created_at').first()
            if analysis_request_obj:
                # Set the status of the ticket to 'progress'
                analysis_request_obj.status = 'progress'
                analysis_request_obj.save()
                thread = threading.Thread(target=TicketView.execute_r_script, args=(analysis_request_obj,))
                thread.start()

            custom_response = {
                "statusMessage": "File uploaded successfully",
                "errorStatus": False,
                "data": [],
                "statusCode": status.HTTP_200_OK,
            }
            return Response(custom_response)
        except AnalysisRequest.DoesNotExist:
            custom_response = {
                "statusMessage": "AnalysisRequest with provided ticket_id not found",
                "errorStatus": True,
                "data": [],
                "statusCode": status.HTTP_404_NOT_FOUND,
            }
            return Response(custom_response)
        except Exception as e:
            custom_response = {
                "statusMessage": str(e),
                "errorStatus": True,
                "data": [],
                "statusCode": status.HTTP_500_INTERNAL_SERVER_ERROR,
            }
            return Response(custom_response)
