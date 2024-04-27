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
from django.conf import settings
import os
from django.core.mail import EmailMessage
import threading
import time
from rest_framework.pagination import PageNumberPagination


class TicketView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def __init__(self):
        self.running_threads = {}
        self.running_threads_lock = threading.Lock()
        self.start_monitoring()

    def start_monitoring(self):
        try:
            if not hasattr(self, 'monitoring_thread') or not self.monitoring_thread.is_alive():
                print("Starting monitoring thread...")
                self.monitoring_thread = threading.Thread(target=self.monitor_threads)
                self.monitoring_thread.daemon = True
                self.monitoring_thread.start()
                print("Monitoring thread started.")
        except Exception as e:
            print(f"Error occurred while starting monitoring: {str(e)}")

    def create_ticket(self, request, format=None):
        try:
            print("Creating ticket...")
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

            analysis_request_obj = AnalysisRequest.objects.create(
                user=user,
                name=name,
                file=uploaded_file,
                description=description,
                status='progress'
            )

            thread = threading.Thread(target=self.execute_r_script, args=(analysis_request_obj,))
            start_time = time.time()  # Set start time here
            thread.start()

            with self.running_threads_lock:
                self.running_threads[analysis_request_obj.id] = {
                    'thread': thread,
                    'start_time': start_time,  # Pass start time to running_threads
                    'process': None  # Placeholder for subprocess
                }
                print(f"Ticket created: {analysis_request_obj.id}")

            print("Ticket created successfully.")
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
            print("Executing R script...")
            time.sleep(40)
            r_script_path = os.path.join(settings.BASE_DIR, 'Server', 'DBS_Call.R')
            process = Popen(
                ['Rscript', r_script_path, analysis_request_obj.file.path, str(analysis_request_obj.id)],
                stdout=PIPE, stderr=PIPE)

            with self.running_threads_lock:
                self.running_threads[analysis_request_obj.id]['process'] = process

            stdout, stderr = process.communicate()
            if process.returncode != 0:
                print(f"R script execution failed with error: {stderr.decode()}")
                analysis_request_obj.status = 'failed'
                analysis_request_obj.save()
                with self.running_threads_lock:
                    del self.running_threads[analysis_request_obj.id]
                self.start_queued_tickets_execution()
        except Exception as e:
            print(f"Error occurred while executing R script: {str(e)}")

    def monitor_threads(self):
        try:
            print("Monitoring threads...")
            while True:
                with self.running_threads_lock:
                    for ticket_id, thread_info in list(self.running_threads.items()):
                        thread = thread_info['thread']
                        start_time = thread_info['start_time']
                        if thread.is_alive():
                            elapsed_time = time.time() - start_time
                            if elapsed_time > 60:
                                analysis_request_obj = AnalysisRequest.objects.get(id=ticket_id)
                                if analysis_request_obj.status != 'killed':
                                    analysis_request_obj.status = 'killed'
                                    analysis_request_obj.save()
                                    print(f"Ticket {ticket_id} has been killed due to exceeding the time limit.")
                                    del self.running_threads[ticket_id]
                time.sleep(10)
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

    def start_queued_tickets_execution(self):
        try:
            analysis_request_obj = AnalysisRequest.objects.filter(status='queue').order_by('created_at').first()
            if analysis_request_obj:
                analysis_request_obj.status = 'progress'
                analysis_request_obj.save()
                thread = threading.Thread(target=self.execute_r_script, args=(analysis_request_obj,))
                start_time = time.time()  # Set start time here
                thread.start()

                with self.running_threads_lock:
                    self.running_threads[analysis_request_obj.id] = {
                        'thread': thread,
                        'start_time': start_time,  # Pass start time to running_threads
                        'process': None  # Placeholder for subprocess
                    }
                    print(f"Ticket created: {analysis_request_obj.id}")
        except Exception as e:
            print(f"Error occurred while starting queued tickets execution: {str(e)}")

class TicketResultsView(viewsets.ViewSet):

    def upload_results(self, request):
        try:
            ticket_id = request.POST.get('ticket_id')
            file = request.FILES.get('file')

            analysis_request = AnalysisRequest.objects.get(id=ticket_id)
            user_email = analysis_request.user.email

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

            # Start executing queued tickets
            TicketView().start_queued_tickets_execution()

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



