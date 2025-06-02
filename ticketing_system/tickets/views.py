# views.py
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.dateparse import parse_datetime  # Add this import
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login, authenticate
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.contrib import messages
from django.views.decorators.http import require_POST, require_http_methods
from django.db import transaction, IntegrityError, models
from django.core.mail import send_mail
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Count, Q
import json
import uuid
import binascii
import os
import random
import pyotp
import base64
from django.db.models import F 
from django.db import transaction
from decimal import Decimal
from .models import Token, Transaction, Announcement
from .models import Ticket, Event, Profile, ChatMessage
from .forms import RegisterForm, SecurePurchaseForm, AnnouncementForm
from . import chatbot_service  # Import the new service

# ========== Helper Functions ==========
def is_staff(user):
    return hasattr(user, 'profile') and user.profile.role == 'staff'

def generate_otp(user):
    if not user.profile.otp_secret:
        user.profile.otp_secret = pyotp.random_base32()
        user.profile.save()
        
    totp = pyotp.TOTP(user.profile.otp_secret, interval=300)
    otp = totp.now()
    user.profile.last_otp = otp
    user.profile.otp_expiry = timezone.now() + timedelta(minutes=5)
    user.profile.save()
    return otp

def handle_success_response(request, ticket):
    response_data = {
        'status': 'success',
        'ticket_id': ticket.id,
        'event_name': ticket.event.name,
        'qr_url': ticket.qr_code.url if ticket.qr_code else None
    }
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(response_data)
    messages.success(request, f"Successfully processed ticket for {ticket.event.name}!")
    return redirect('dashboard')

def handle_error_response(request, error_message, status=400):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'error', 'message': error_message}, status=status)
    messages.error(request, error_message)
    return redirect('dashboard')

def send_otp_email(user, otp):
    subject = 'Your Ticket Purchase OTP'
    message = f'Your OTP for ticket purchase is: {otp}'
    send_mail(subject, message, 'noreply@tickethub.com', [user.email])

def send_pin_email(user, pin):
    subject = 'Your Event Ticket Management Security PIN'
    message = f'Your new security PIN is: {pin}\nKeep it secret!'
    send_mail(subject, message, 'security@eventticketmanagement.com', [user.email])

# ========== Ticket Validation Views ==========
@require_http_methods(["GET", "POST"])
@csrf_exempt
def validate_ticket_api(request):
    """
    API endpoint to validate a ticket by its unique code
    Returns JSON response with validation result and plays appropriate audio feedback
    """
    if request.method == 'GET':
        qr_data = request.GET.get('code')
    else:
        try:
            data = json.loads(request.body)
            qr_data = data.get('code')
        except (json.JSONDecodeError, AttributeError):
            return JsonResponse({'status': 'error', 'message': 'Invalid request data'}, status=400)
    
    if not qr_data:
        return JsonResponse({'status': 'error', 'message': 'No ticket code provided'}, status=400)
    
    try:
        ticket = Ticket.objects.select_related('event', 'user').get(unique_code=qr_data)
        now = timezone.now()
        
        response_data = {
            'status': 'success',
            'ticket': {
                'code': ticket.unique_code,
                'event': ticket.event.name,
                'event_date': ticket.event.date.strftime('%Y-%m-%d %H:%M'),
                'user': ticket.user.get_full_name() or ticket.user.username,
                'status': ticket.status,
                'is_valid': False,
                'message': '',
                'audio_feedback': 'error'  # Default to error sound
            }
        }
        
        # Check ticket status
        if ticket.status == 'USED':
            response_data['ticket']['message'] = 'This ticket has already been used.'
        elif ticket.status == 'EXPIRED':
            response_data['ticket']['message'] = 'This ticket has expired.'
        elif ticket.status == 'AVAILABLE':
            response_data['ticket']['message'] = 'This ticket has not been purchased.'
        elif ticket.status == 'PURCHASED':
            # Mark as used if valid
            ticket.status = 'USED'
            ticket.save(update_fields=['status', 'last_modified'])
            response_data['ticket']['status'] = 'USED'
            response_data['ticket']['is_valid'] = True
            response_data['ticket']['message'] = 'Ticket is valid. Access granted!'
            response_data['ticket']['audio_feedback'] = 'success'
            
        return JsonResponse(response_data)
        
    except Ticket.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Ticket not found',
            'audio_feedback': 'error'
        }, status=404)

# ========== Ticket Validator View ==========
def ticket_validator(request):
    """
    View for the ticket validation interface
    """
    return render(request, 'ticket_validator.html')

# ========== Core Views ==========
@login_required
def dashboard(request):
    try:
        profile = request.user.profile
        context = {
            'credits': profile.credits,
            'events': Event.objects.filter(date__gte=timezone.now()).annotate(
                available_tickets=F('ticket_count') - Count('tickets', 
                                                            filter=Q(tickets__status='PURCHASED'))
            ).prefetch_related('tickets'),
            'tickets': request.user.ticket_set.filter(status='PURCHASED')
                .select_related('event')
                .order_by('-purchased_at'),
            'active_tokens_count': Token.objects.filter(
                used=False, 
                expiry_date__gt=timezone.now()
            ).count(),
            'announcements': get_active_announcements()
        }
        template = 'staff_dashboard.html' if is_staff(request.user) else 'customer_dashboard.html'
        return render(request, template, context)

    except Profile.DoesNotExist:
        messages.error(request, "User profile missing. Please contact support.")
        return redirect('home')

@login_required
@require_http_methods(["POST"])
@csrf_exempt # Kept for consistency, review for security implications
def purchase_ticket(request, event_id): # Changed ticket_id to event_id
    try:
        from .models import Ticket, Event, Transaction # Model imports
        from django.contrib.auth.models import User
        from decimal import Decimal
        from django.utils import timezone
        from django.db import transaction

        logger.info(f"Purchase attempt for Event ID: {event_id} by User: {request.user.id}")

        with transaction.atomic(): # Wrap the core logic in a transaction
            try:
                # Get the event first to ensure it exists
                event = Event.objects.get(id=event_id)
            except Event.DoesNotExist:
                logger.error(f"Event not found during purchase attempt - Event ID: {event_id}")
                return JsonResponse({'success': False, 'error': 'Event not found.'}, status=404)

            # Check if the event has already passed
            if event.date < timezone.now():
                logger.warning(f"Attempt to purchase ticket for past event - Event ID: {event_id}, Event Date: {event.date}")
                return JsonResponse({'success': False, 'error': 'This event has already passed and tickets can no longer be purchased.'}, status=400)

            # Find an available ticket for this event.
            # select_for_update() locks the selected rows until the end of the transaction to prevent race conditions.
            ticket_to_purchase = Ticket.objects.select_for_update().filter(event=event, status='AVAILABLE').first()

            if not ticket_to_purchase:
                logger.warning(f"No available tickets for Event ID: {event_id} at time of purchase attempt by User: {request.user.id}")
                return JsonResponse({'success': False, 'error': 'Sorry, tickets for this event are currently sold out or unavailable.'}, status=404)
            
            # At this point, ticket_to_purchase is the specific ticket instance we intend to sell.
            ticket_price = event.price # Price is on the Event model
            user = request.user
            profile = user.profile

            if profile.credits < ticket_price:
                logger.warning(f"Insufficient credits - User: {user.id}, Event ID: {event_id}, Available Credits: {profile.credits}, Required: {ticket_price}")
                return JsonResponse({'success': False, 'error': 'Insufficient credits to purchase this ticket.'}, status=400)

            # 1. Deduct credits from user's profile
            profile.credits -= Decimal(str(ticket_price))
            profile.save()

            # 2. Update ticket status, assign user, set purchase time
            ticket_to_purchase.user = user
            ticket_to_purchase.status = 'PURCHASED'
            ticket_to_purchase.purchased_at = timezone.now()
            ticket_to_purchase.save() # This will also run the Ticket's save() method for QR, etc.

            # 3. Create a transaction record for auditing
            Transaction.objects.create(
                user=user,
                amount=ticket_price,
                transaction_type='TICKET_PURCHASE'
                # Consider adding a description or linking to the ticket/event if needed for detailed auditing
            )

            logger.info(f"Purchase successful - User: {user.id}, Purchased Ticket ID: {ticket_to_purchase.id} for Event: {event.name}, New Balance: {profile.credits}")

            return JsonResponse({
                'success': True,
                'message': 'Ticket purchased successfully!',
                'new_balance': float(profile.credits) # Convert Decimal to float for JSON
            })

    except ImportError as e: # Specific error catching for import issues
        logger.error(f"ImportError in purchase_ticket: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': f'Server configuration error prevented purchase: {str(e)}'}, status=500)
    except Exception as e: # Generic error catching for unexpected issues
        # Log the event_id if available, otherwise note it's unknown at this stage of error.
        current_event_id = event_id if 'event_id' in locals() else 'unknown'
        logger.error(f"Unexpected error in purchase_ticket (Event ID: {current_event_id}): {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'An unexpected server error occurred. Our team has been notified.'
        }, status=500)

logger = logging.getLogger(__name__)

# ========== Ticket Management Views ==========
@login_required
@require_POST
def claim_ticket(request):
    code = request.POST.get('code', '').strip().upper()
    
    if not code or len(code) != 17 or not code.isalnum():
        return handle_error_response(request, "Invalid code format")

    try:
        with transaction.atomic():
            ticket = Ticket.objects.select_for_update().get(
                unique_code=code, 
                user__isnull=True
            )
            ticket.user = request.user
            ticket.status = 'PURCHASED'
            ticket.generate_qr_code()
            ticket.save()
            return handle_success_response(request, ticket)

    except Ticket.DoesNotExist:
        return handle_error_response(request, "Invalid or already claimed ticket code")
    except Exception as e:
        return handle_error_response(request, f"Ticket claim error: {str(e)}")

@login_required
def validate_ticket(request, qr_data):
    try:
        ticket_id = int(qr_data.split("Ticket ID: ")[1].split(",")[0])
        ticket = Ticket.objects.get(id=ticket_id)
        
        if ticket.status == 'USED':
            return JsonResponse({'valid': False, 'message': 'Ticket already used'})
        
        ticket.status = 'USED'
        ticket.save()
        return JsonResponse({
            'valid': True, 
            'event': ticket.event.name,
            'user': ticket.user.username
        })
        
    except (ValueError, IndexError, Ticket.DoesNotExist):
        return JsonResponse({'valid': False, 'message': 'Invalid ticket'})

@login_required
@user_passes_test(is_staff)
def bulk_create_tickets(request):
    if request.method == 'POST':
        event_id = request.POST.get('event')
        quantity = int(request.POST.get('quantity'))
        event = get_object_or_404(Event, id=event_id)

        if quantity > event.ticket_count:
            return handle_error_response(request, 
                f"Cannot create more tickets than available ({event.ticket_count})")

        created_count = 0
        with transaction.atomic():
            event = Event.objects.select_for_update().get(id=event_id)
            for _ in range(quantity):
                try:
                    # Create a new Ticket instance
                    new_ticket = Ticket(
                        event=event,
                        # unique_code will be generated by the Ticket's save() method if not provided,
                        # or we can continue to generate it here if preferred.
                        # For consistency with previous behavior, let's keep generating it here for now.
                        unique_code=uuid.uuid4().hex[:17].upper()
                        # Status will default to 'AVAILABLE' as per model definition
                    )
                    # Call the save method, which includes QR code generation and other logic
                    new_ticket.save()
                    logger.info(f"Successfully created Ticket ID: {new_ticket.id}, Status: {new_ticket.status}, Event ID: {event.id}, QR: {new_ticket.qr_code.name if new_ticket.qr_code else 'No QR'}")
                    created_count += 1
                except IntegrityError as e:
                    logger.error(f"IntegrityError while creating ticket for event {event.id}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error while creating ticket for event {event.id}: {e}", exc_info=True)
                    continue

        messages.success(request, f"Created {created_count} tickets!")
        return redirect('dashboard')

    return render(request, 'bulk_create.html', {'events': Event.objects.all()})

# ========== Chat Functionality ==========
@login_required
def chat_history(request):
    messages = ChatMessage.objects.filter(user=request.user).order_by('-timestamp')[:50]
    return JsonResponse({
        'messages': [
            {
                'text': msg.message,
                'timestamp': msg.timestamp.strftime("%Y-%m-%d %H:%M"),
                'response': msg.response
            } for msg in messages
        ]
    })

@csrf_exempt
@login_required
@require_POST
def send_message(request):
    logger.info('=' * 50)
    logger.info('[Chat] Received send_message request')
    logger.info(f'[Chat] Request method: {request.method}')
    logger.info(f'[Chat] Request headers: {dict(request.headers)}')
    
    try:
        # Log raw request body for debugging
        body = request.body.decode('utf-8')
        logger.info(f'[Chat] Request body: {body}')
        
        data = json.loads(body)
        message = data.get('message', '').strip()
        language = data.get('language')  # Get language from request
        
        # Log the detected language
        if language:
            logger.info(f'[Chat] Language specified: {language}')
        
        logger.info(f'[Chat] Extracted message: "{message}"')
        
        if not message:
            logger.warning('[Chat] No message found in JSON data.')
            return JsonResponse({'status': 'error', 'message': 'Message is required'}, status=400)
        
        # Get bot response with language context and user info
        logger.info('[Chat] Calling chatbot_service.generate_reply()')
        bot_response, detected_language = chatbot_service.generate_reply(
            user_message=message,
            language=language,  # Pass the language to the chatbot
            request=request    # Pass the request object for user context
        )
        logger.info(f'[Chat] Received bot response: {bot_response[:200]}...')
        logger.info(f'[Chat] Detected language: {detected_language}')
        
        # Save the message and response with language context
        logger.info('[Chat] Saving message to database')
        from .models import ChatMessage
        chat_message = ChatMessage.objects.create(
            user=request.user,
            message=message,
            response=bot_response,
            language=detected_language or language or 'en'  # Store the detected language or fallback to provided or English
        )
        logger.info(f'[Chat] Message saved with ID: {chat_message.id}')
        
        response_data = {
            'status': 'success',
            'reply': bot_response,
            'timestamp': chat_message.timestamp.strftime("%Y-%m-%d %H:%M"),
            'language': detected_language or language or 'en',  # Use detected language with fallback
            'detected_language': detected_language  # Always include the detected language
        }
        logger.info(f'[Chat] Sending response: {json.dumps(response_data)[:200]}...')
        
        return JsonResponse(response_data)
        
    except json.JSONDecodeError as e:
        logger.error(f'[Chat] JSON decode error: {str(e)}')
        logger.error(f'[Chat] Request body that caused error: {request.body}')
        return JsonResponse(
            {'status': 'error', 'message': 'Invalid JSON'}, 
            status=400
        )
    except Exception as e:
        error_msg = f'[Chat] Error in send_message: {str(e)}'
        logger.error(error_msg, exc_info=True)
        return JsonResponse(
            {
                'status': 'error', 
                'message': 'An error occurred while processing your message.',
                'debug': str(e)
            }, 
            status=500
        )
    finally:
        logger.info('[Chat] Request processing complete')
        logger.info('=' * 50)

# ========== Authentication Views ==========
class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        # Ensure profile exists or create one
        # This assumes 'staff' role if user.is_staff, otherwise 'customer'
        Profile.objects.get_or_create(user=user, defaults={'role': 'staff' if user.is_staff else 'customer'})
        return reverse_lazy('dashboard')

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False) # Don't save yet to handle profile
            # If your RegisterForm doesn't handle profile creation or if Profile is separate
            user.save() # Save the user first
            
            # Ensure profile is created. If you have a signal, this might be redundant.
            # Otherwise, create profile here explicitly.
            profile, created = Profile.objects.get_or_create(user=user)
            if created:
                # Set default role or other attributes if needed, e.g., from form
                profile.role = 'customer' # Default role
            
            # Handle phone number if it's part of RegisterForm and stored in Profile
            if 'phone' in form.cleaned_data and hasattr(profile, 'phone'):
                profile.phone = form.cleaned_data.get('phone')
                profile.save()
            
            # Login the user
            # Note: Django's form.save() for UserCreationForm doesn't log in the user.
            # You need to authenticate and login manually.
            raw_password = form.cleaned_data.get('password2') # Or password1, depends on your form field for confirmation
            # It's generally better to use cleaned_data['password2'] (or whatever the field is) 
            # from a UserCreationForm after validation for the password to use for authenticate.
            # However, UserCreationForm itself doesn't store the raw password after clean.
            # A common pattern is to authenticate with username and password1 (the first password field).
            authenticated_user = authenticate(username=user.username, password=form.cleaned_data.get('password1'))
            if authenticated_user is not None:
                login(request, authenticated_user)
                messages.success(request, f"Registration successful. Welcome, {user.username}!")
                return redirect('home')  # Or 'dashboard'
            else:
                # This case should ideally not happen if form validation is correct
                # and user is active by default.
                messages.error(request, "Registration successful, but automatic login failed. Please try logging in manually.")
                return redirect('login')
        else:
            # Form is not valid, pass it back to the template to show errors
            pass # Fall through to render form with errors
    else:
        form = RegisterForm()
    return render(request, 'registration/register.html', {'form': form})

# ========== Event Management ==========
@login_required
@user_passes_test(is_staff)
def create_event(request):
    if request.method == 'POST':
        try:
            date_str = request.POST.get('date')
            # Ensure parse_datetime and timezone are imported at the top of views.py
            naive_datetime = parse_datetime(date_str)
            aware_datetime = None

            if naive_datetime:
                aware_datetime = timezone.make_aware(naive_datetime)
            else:
                messages.error(request, f"Invalid date format for '{date_str}'. Please use YYYY-MM-DD HH:MM[:SS] or YYYY-MM-DDTHH:MM[:SS].")
                # Consider re-rendering the form with user's previous input if you have a Django form
                return render(request, 'create_event.html') 

            Event.objects.create(
                name=request.POST.get('name'),
                date=aware_datetime,
                location=request.POST.get('location'),
                price=Decimal(request.POST.get('price')), # Convert to Decimal
                ticket_count=int(request.POST.get('ticket_count')), # Convert to int
                max_purchase_per_user=int(request.POST.get('max_purchase_per_user', 5))
            )
            messages.success(request, "Event created successfully!")
            return redirect('dashboard')
        except ValueError as e: 
            messages.error(request, f"Invalid input for price, ticket count, or max purchase: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating event: {str(e)}", exc_info=True)
            messages.error(request, f"An unexpected error occurred: {str(e)}")
    # For GET request or if POST fails and form needs to be re-rendered with errors
    # If using a Django Form for create_event, you'd instantiate it here for GET
    # and pass it to the template.
    return render(request, 'create_event.html')

# ========== Miscellaneous Views ==========
def home(request):
    # Add any context data the home.html template might need
    # For example, upcoming events:
    # upcoming_events = Event.objects.filter(date__gte=timezone.now()).order_by('date')[:5]
    # context = {'upcoming_events': upcoming_events}
    # return render(request, 'home.html', context)
    return render(request, 'home.html')


@csrf_exempt
@login_required
def chatbot_webhook(request):
    logger.info(f'[chatbot_webhook] VIEW ENTERED. Method: {request.method}. Headers: {dict(request.headers)}') # Using .info for higher visibility for now
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            
            if not user_message:
                return JsonResponse({'reply': 'No message provided.'}, status=400)
            
            # Get reply from the chatbot service
            logger.info(f'[chatbot_webhook] Calling chatbot_service with message: "{user_message[:100]}..."')
            bot_reply = chatbot_service.generate_reply(user_message)
            logger.info(f'[chatbot_webhook] Reply from service: "{bot_reply[:100]}..."')
            
            return JsonResponse({'reply': bot_reply})
        except json.JSONDecodeError as e:
            logger.error(f'[chatbot_webhook] JSONDecodeError: {e}. Body was: {request.body[:500]}...', exc_info=True)
            return JsonResponse({'reply': 'Invalid request format'}, status=400)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)
@login_required
def create_ticket(request, event_id):
    """API endpoint for programmatic ticket creation"""
    try:
        event = get_object_or_404(Event, id=event_id)
        ticket = Ticket.objects.create(
            user=request.user,
            event=event,
            unique_code=uuid.uuid4().hex[:17].upper()
        )
        ticket.generate_qr_code()
        ticket.save()
        return JsonResponse({
            'ticket_id': ticket.id,
            'qr_code_url': ticket.qr_code.url,
            'event': ticket.event.name
        })
    
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Ticket creation failed: {str(e)}'
        }, status=400)

@login_required
def add_credits_placeholder_view(request):
    return render(request, 'add_credits_placeholder.html')

@login_required
def purchase_token(request):
    return render(request, 'purchase_token.html')

@login_required
@require_POST
def redeem_token(request):
    code = request.POST.get('token_code', '').strip()
    
    try:
        with transaction.atomic():
            token = Token.objects.select_for_update().get(
                code=code,
                used=False,
                expiry_date__gt=timezone.now()  # Check expiration
            )
            profile = request.user.profile
            profile.credits += token.amount
            profile.save()
            
            # Create transaction record
            Transaction.objects.create(
                user=request.user,
                amount=token.amount,
                transaction_type='REDEMPTION'
            )
            
            token.used = True
            token.used_by = request.user
            token.used_at = timezone.now()
            token.save()
            
            messages.success(request, f"Added ${token.amount} to your account!")
    except Token.DoesNotExist:
        messages.error(request, "Invalid, expired, or already used token")
    except Exception as e:
        messages.error(request, f"Error redeeming token: {str(e)}")
    
    return redirect('dashboard')
@login_required
@user_passes_test(is_staff)
def token_management(request):
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount'))
        expiry_date = timezone.make_aware(
            datetime.strptime(request.POST.get('expiry_date'), '%Y-%m-%dT%H:%M')
        )
        
        token = Token.objects.create(
            amount=amount,
            expiry_date=expiry_date,
            created_by=request.user
        )
        messages.success(request, f"Token {token.code} created!")
        return redirect('token_management')
    
    active_tokens = Token.objects.filter(used=False, expiry_date__gt=timezone.now())
    return render(request, 'token_management.html', {'active_tokens': active_tokens})

@login_required
def transaction_history(request):
    transactions = Transaction.objects.filter(user=request.user).order_by('-timestamp')
    return render(request, 'transaction_history.html', {'transactions': transactions})

from django.utils.dateparse import parse_datetime  # Add this import

@login_required
@user_passes_test(is_staff)
def token_dashboard(request):
    status = request.GET.get('status', 'all')
    
    # Always return a QuerySet
    tokens = Token.objects.annotate(
    is_expired=models.ExpressionWrapper(
        Q(expiry_date__lt=timezone.now()) | Q(used=True),
        output_field=models.BooleanField()
    )
)

    if status == 'active':
        tokens = tokens.filter(expiry_date__gt=timezone.now(), used=False)
    elif status == 'expired':
        tokens = tokens.filter(Q(expiry_date__lt=timezone.now()) | Q(used=True))

    # Handle POST requests
    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount'))
            expiry_date = timezone.make_aware(
                datetime.strptime(request.POST.get('expiry_date'), '%Y-%m-%dT%H:%M')
            )
            
            Token.objects.create(
                amount=amount,
                expiry_date=expiry_date,
                created_by=request.user
            )
            return redirect('token_dashboard')
            
        except Exception as e:
            messages.error(request, f"Error creating token: {str(e)}")
            return redirect('token_dashboard')  # Ensure return

    # Always return HttpResponse for GET
    return render(request, 'token_dashboard.html', {
        'tokens': tokens,
        'current_status': status
    })
@login_required
@user_passes_test(is_staff)
@require_POST
def revoke_token(request, token_id):
    token = get_object_or_404(Token, id=token_id)
    token.expiry_date = timezone.now()
    token.save()
    return JsonResponse({'status': 'success'})

@login_required
@user_passes_test(is_staff)
def edit_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        event.name = request.POST.get('name')
        event.date = request.POST.get('date')
        event.location = request.POST.get('location')
        event.price = request.POST.get('price')
        event.ticket_count = request.POST.get('ticket_count')
        event.max_purchase_per_user = request.POST.get('max_purchase_per_user')
        event.save()
        return redirect('dashboard')
    return render(request, 'edit_event.html', {'event': event})

@login_required
@user_passes_test(is_staff)
def delete_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':  # Require POST for deletion
        event.delete()
        messages.success(request, "Event deleted successfully")
        return redirect('dashboard')  # Use correct URL name
    return render(request, 'delete_event.html', {'event': event})

# ========== Announcement Views ==========

@login_required
@user_passes_test(is_staff)
def create_announcement(request):
    if request.method == 'POST':
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.created_by = request.user
            announcement.save()
            messages.success(request, 'Announcement created successfully.')
            return redirect('manage_announcements')
    else:
        form = AnnouncementForm()
    
    return render(request, 'announcements/announcement_form.html', {
        'form': form,
        'title': 'Create New Announcement'
    })

@login_required
@user_passes_test(is_staff)
def edit_announcement(request, announcement_id):
    announcement = get_object_or_404(Announcement, id=announcement_id)
    
    if request.method == 'POST':
        form = AnnouncementForm(request.POST, instance=announcement)
        if form.is_valid():
            form.save()
            messages.success(request, 'Announcement updated successfully.')
            return redirect('manage_announcements')
    else:
        form = AnnouncementForm(instance=announcement)
    
    return render(request, 'announcements/announcement_form.html', {
        'form': form,
        'title': 'Edit Announcement'
    })

@login_required
@user_passes_test(is_staff)
def delete_announcement(request, announcement_id):
    announcement = get_object_or_404(Announcement, id=announcement_id)
    if request.method == 'POST':
        announcement.delete()
        messages.success(request, 'Announcement deleted successfully.')
        return redirect('manage_announcements')
    
    return render(request, 'announcements/delete_announcement.html', {
        'announcement': announcement
    })

@login_required
@user_passes_test(is_staff)
def manage_announcements(request):
    announcements = Announcement.objects.all().order_by('-created_at')
    return render(request, 'announcements/manage_announcements.html', {
        'announcements': announcements
    })

def get_active_announcements():
    """Helper function to get active announcements"""
    now = timezone.now()
    return Announcement.objects.filter(
        is_active=True,
        valid_until__gt=now
    ).order_by('-priority', '-created_at')