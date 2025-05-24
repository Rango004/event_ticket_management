from django.urls import path
from .views import (
    delete_event,
    edit_event,
    home,
    register,
    CustomLoginView,
    dashboard,
    create_event,
    bulk_create_tickets,
    create_ticket,
    revoke_token,
    token_dashboard,
    validate_ticket,
    validate_ticket_api,
    ticket_validator,
    send_message,
    purchase_ticket,
    claim_ticket, 
    purchase_token,
    redeem_token,
    token_management,
    transaction_history,
    add_credits_placeholder_view,
    create_announcement,
    edit_announcement,
    delete_announcement,
    manage_announcements
)
from django.contrib.auth.views import LogoutView

urlpatterns = [
    # Authentication URLs
    path('', home, name='home'),
    path('register/', register, name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='home'), name='logout'),  # Explicit redirect
    
    # Dashboard URLs
    path('dashboard/', dashboard, name='dashboard'),
    path('create-event/', create_event, name='create_event'),
    path('bulk-tickets/', bulk_create_tickets, name='bulk_create_tickets'),
    path('purchase_ticket/<int:event_id>/', purchase_ticket, name='purchase_ticket'),
    path('claim-ticket/', claim_ticket, name='claim_ticket'),
    path('purchase-token/', purchase_token, name='purchase_token'),
    path('redeem-token/', redeem_token, name='redeem_token'),
    path('token-management/', token_management, name='token_management'),
    path('transaction-history/', transaction_history, name='transaction_history'),
    path('token-dashboard/', token_dashboard, name='token_dashboard'),
    path('add-credits/', add_credits_placeholder_view, name='add_credits_placeholder'),
    path('tokens/<int:token_id>/revoke/', revoke_token, name='revoke_token'),
    path('edit-event/<int:event_id>/', edit_event, name='edit_event'),
    path('delete-event/<int:event_id>/', delete_event, name='delete_event'),
   
    # Ticket Validation
    path('ticket-validator/', ticket_validator, name='ticket_validator'),
    
    # Announcement URLs
    path('announcements/', manage_announcements, name='manage_announcements'),
    path('announcements/create/', create_announcement, name='create_announcement'),
    path('announcements/<int:announcement_id>/edit/', edit_announcement, name='edit_announcement'),
    path('announcements/<int:announcement_id>/delete/', delete_announcement, name='delete_announcement'),
    
    # API Endpoints
    path('create/<int:event_id>/', create_ticket, name='create_ticket'),
    path('validate/<str:qr_data>/', validate_ticket, name='validate_ticket'),
    path('api/validate-ticket/', validate_ticket_api, name='validate_ticket_api'),
    path('chatbot/', send_message, name='send_message'),
]