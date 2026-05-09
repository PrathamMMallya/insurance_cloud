# insurance/urls.py
from django.urls import path
from . import views
from .views import InsuranceQueryView, UserDocumentSummaryView

app_name = 'insurance'

urlpatterns = [
    # Main views (template-based, kept for backwards compat)
    path('', views.InsuranceIndexView.as_view(), name='index'),
    
    # Document management (knowledge base)
    path('upload/', views.DocumentUploadView.as_view(), name='upload_document'),
    path('document/<int:document_id>/', views.document_detail, name='document_detail'),
    path('document/<int:document_id>/delete/', views.delete_document, name='delete_document'),
    path('document/<int:document_id>/reprocess/', views.reprocess_document, name='reprocess_document'),
    path('document/<int:document_id>/export/', views.export_chunks, name='export_chunks'),
    
    # User document summary
    path('summarize-user-doc/', UserDocumentSummaryView.as_view(), name='summarize_user_doc'),

    # Query management
    path('query/', views.InsuranceQueryView.as_view(), name='query'),
    path('query-history/', views.query_history, name='query_history'),
    
    # System management
    path('clear-database/', views.clear_database, name='clear_database'),
    path('system-status/', views.system_status, name='system_status'),

    # JSON API endpoints for React frontend
    path('api/stats/', views.api_stats, name='api_stats'),
    path('api/documents/', views.api_documents, name='api_documents'),
    path('api/queries/', views.api_queries, name='api_queries'),
    path('api/system-status/', views.api_system_status, name='api_system_status'),

    # S3 data logs API
    path('api/s3-logs/', views.api_s3_logs, name='api_s3_logs'),
    path('api/s3-detail/', views.api_s3_detail, name='api_s3_detail'),
]