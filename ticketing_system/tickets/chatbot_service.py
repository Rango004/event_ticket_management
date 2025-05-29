import os
import logging
import traceback
import logging
import json
import time
import random
from datetime import datetime, timedelta
from openai import OpenAI, APIError, APIConnectionError, RateLimitError
from django.conf import settings
from django.utils import timezone
from dotenv import load_dotenv
from functools import wraps
from .languages import LANGUAGE_PROMPTS

def detect_language(text):
    """
    Detect the language of the input text.
    Returns 'am' for Amharic, 'kri' for Krio, or 'en' for English (default).
    """
    if not text or not isinstance(text, str):
        return 'en'
        
    text_lower = text.lower().strip()
    
    # Define language indicators for Sierra Leonean Krio
    krio_indicators = [
        'kushe', 'aw di go', 'aw di bɔdi', 'aw di tɛm', 'aw yu du', 'aw yu de',
        'a de', 'i de', 'u de', 'wi de', 'una de', 'na', 'sabi', 'pikin',
        'chop', 'boku', 'abeg', 'wetin', 'ehn', 'dem', 'wetin na', 'mek',
        'wan', 'tink', 'nɔ', 'get', 'go', 'kam', 'si', 'tu', 'tri',
        'aw yu de du', 'aw u de', 'tenki', 'tɛnki', 'a bɛg'
    ]
    
    amharic_indicators = [
        'ሰላም', 'እንዴት ነህ', 'እንዴት ነሽ', 'እርዳት', 'አመሰግናለሁ', 'አይነት', 'ቲኬት',
        'ክስተት', 'ቀን', 'ስም', 'አድራሻ', 'ዋጋ', 'ገንዘብ', 'ቦታ', 'ጊዜ', 'ስለዚህ'
    ]
    
    # Check for Krio
    krio_word_count = sum(1 for word in krio_indicators if word in text_lower)
    if krio_word_count > 0:
        return 'kri'
        
    # Check for Amharic
    amharic_word_count = sum(1 for word in amharic_indicators if word in text_lower)
    if amharic_word_count > 0:
        return 'am'
    
    # Default to English
    return 'en'

def retry_on_exception(max_retries=3, initial_delay=1, backoff=2, exceptions=(APIError, APIConnectionError, RateLimitError)):
    """
    Retry decorator with exponential backoff.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            delay = initial_delay
            
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    retries += 1
                    if retries > max_retries:
                        logger_service.error(f'Max retries ({max_retries}) reached. Giving up.')
                        raise
                    
                    # Calculate delay with jitter
                    sleep_time = delay * (2 ** (retries - 1)) + random.uniform(0, 1)
                    logger_service.warning(f'Attempt {retries}/{max_retries} failed. Retrying in {sleep_time:.2f}s. Error: {str(e)}')
                    time.sleep(sleep_time)
        return wrapper
    return decorator

# Set up logging
logger_service = logging.getLogger('tickets.chatbot_service')
logger_service.setLevel(logging.DEBUG)  # Set to DEBUG for more detailed logs

# Add a console handler if not already configured
if not logger_service.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger_service.addHandler(console_handler)

# Debug environment variables
logger_service.debug('=' * 80)
logger_service.debug('Environment Variables Debug:')
logger_service.debug(f'Current working directory: {os.getcwd()}')
logger_service.debug(f'Environment file exists: {os.path.exists(".env")}')

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client
api_key = os.getenv('OPENAI_API_KEY', getattr(settings, 'OPENAI_API_KEY', ''))

# Debug API key
if not api_key:
    logger_service.error('❌ OPENAI_API_KEY not found in environment variables or settings.')
    logger_service.error('Please make sure you have a .env file with OPENAI_API_KEY in the project root.')
else:
    logger_service.info('✅ OPENAI_API_KEY found in environment variables')
    logger_service.debug(f'API Key: {api_key[:5]}...{api_key[-5:]}' if api_key else 'No API key')

# Initialize the OpenAI client
client = None
if api_key:
    try:
        client = OpenAI(api_key=api_key)
        logger_service.info('✅ OpenAI client initialized successfully')
    except Exception as e:
        logger_service.error(f'❌ Failed to initialize OpenAI client: {str(e)}')
        logger_service.debug(traceback.format_exc())
else:
    logger_service.error('❌ Cannot initialize OpenAI client: No API key available')

# Get model from settings or use default
OPENAI_MODEL = getattr(settings, 'OPENAI_MODEL', 'gpt-3.5-turbo')
DEFAULT_LANGUAGE = getattr(settings, 'DEFAULT_LANGUAGE', 'en')

# Default system prompt (can be overridden in settings)
DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant for a ticketing system. "
    "You help users with ticket purchases, event information, and support. "
    "Be concise and helpful in your responses."
)

# Get system prompt from settings or use default
SYSTEM_PROMPT = getattr(settings, 'CHATBOT_SYSTEM_PROMPT', DEFAULT_SYSTEM_PROMPT)

def generate_reply(user_message, conversation_history=None, language=None, request=None, **kwargs):
    """
    Generate a response to the user's message using the OpenAI API with multilingual support.
    
    Args:
        user_message (str): The user's message
        conversation_history (list, optional): List of previous messages in the conversation
        language (str, optional): Language code ('en', 'am', or 'kri'). If None, auto-detect.
        request: The HTTP request object for user context
        **kwargs: Additional keyword arguments
        
    Returns:
        tuple: (response_text, language_code) - The generated response and detected language
    """
    # Track conversation context
    context = kwargs.get('context', {})
    # Log the start of the function
    logger_service.info('=' * 80)
    logger_service.info('🔄 [ChatService] generate_reply called')
    logger_service.info(f'📩 Message: "{user_message[:200]}" (length: {len(user_message)})')
    
    # Validate input
    if not user_message or not isinstance(user_message, str):
        logger_service.error('❌ Invalid user message')
        return "I'm sorry, I didn't receive a valid message. Please try again.", 'en'
    
    # Detect language if not provided
    if language is None:
        language = detect_language(user_message)
        logger_service.info(f'🔍 Detected language: {language}')
    
    # Ensure language is valid, default to English if not
    if language not in LANGUAGE_PROMPTS:
        logger_service.warning(f'⚠️ Unsupported language: {language}. Defaulting to English.')
        language = 'en'
    
    # Store detected language in context
    context['detected_language'] = language
    
    # Update context with detected language
    context['language'] = language
    logger_service.info(f'🌐 Language set to: {language}')
    
    # Get language-specific prompts and responses
    lang_data = LANGUAGE_PROMPTS[language]
    system_prompt = lang_data['system']
    
    # Add context to system prompt
    context_info = []
    if 'last_topic' in context:
        context_info.append(f"The user was previously asking about {context['last_topic']}.")
    if 'last_action' in context:
        context_info.append(f"The last action was: {context['last_action']}.")
    
    if context_info:
        system_prompt += " " + " ".join(context_info)
    
    # Add user context if available
    user_context = ""
    if request and hasattr(request, 'user') and request.user.is_authenticated:
        user = request.user
        user_context = f" The user's name is {user.get_full_name() or user.username}. "
        
        # Add user's tickets information if available
        try:
            from .models import Ticket
            user_tickets = Ticket.objects.filter(user=user, status='PURCHASED')
            if user_tickets.exists():
                user_context += f"The user has {user_tickets.count()} active ticket(s). "
        except Exception as e:
            logger_service.warning(f'Could not fetch user tickets: {str(e)}')
    
    # Enhance system prompt with user context
    system_prompt = f"{system_prompt}{user_context}"
    
    # Common responses in the detected language
    common_responses = {
        'greeting': lang_data.get('greeting', 'Hello! How can I assist you today?'),
        'error': lang_data.get('error', 'I encountered an error processing your request.'),
        'fallback': lang_data.get('fallback', 'I\'m not sure how to respond to that.')
    }
    
    # Log language information
    logger_service.info(f'🌐 Language: {language} ({lang_data.get("name", "Unknown")})')
    logger_service.debug(f'System prompt: {system_prompt[:200]}...')
    
    # Check if client is properly initialized
    if not client:
        error_msg = '❌ OpenAI client not initialized. Chat functionality is disabled.'
        logger_service.error(error_msg)
        
        # Return error in the detected language with language code
        return common_responses['error'] + ' ' + \
               'The chatbot is not properly configured. Please try again later.', language
    
    # Handle common queries without API call when possible
    user_msg_lower = user_message.lower().strip()
    
    # Update context based on user message
    if any(word in user_msg_lower for word in ['ticket', 'tickets']):
        context['last_topic'] = 'tickets'
    elif any(word in user_msg_lower for word in ['event', 'events']):
        context['last_topic'] = 'events'
    elif any(word in user_msg_lower for word in ['help', 'support']):
        context['last_topic'] = 'help'
    
    # Track if this is a follow-up question
    is_follow_up = any(word in user_msg_lower for word in ['that', 'it', 'they', 'them', 'this', 'those', 'these'])
    if is_follow_up and 'last_topic' in context:
        user_message = f"{context['last_topic']} - {user_message}"
        logger_service.info(f'🔍 Detected follow-up about: {context["last_topic"]}')
    
    # Get user's active tickets if available
    user_tickets = []
    if request and hasattr(request, 'user') and request.user.is_authenticated:
        try:
            from .models import Ticket
            user_tickets = list(Ticket.objects.filter(
                user=request.user,
                status='PURCHASED',
                event__date__gte=timezone.now()
            ).select_related('event').order_by('event__date'))
        except Exception as e:
            logger_service.warning(f'Could not fetch user tickets: {str(e)}')
    
    # Get all available events
    try:
        from .models import Event
        available_events = list(Event.objects.filter(
            date__gte=timezone.now()
        ).order_by('date'))
    except Exception as e:
        available_events = []
        logger_service.warning(f'Could not fetch available events: {str(e)}')
    
    # Greeting responses
    if any(word in user_msg_lower for word in ['hello', 'hi', 'hey', 'hola', 'salam', 'selam', 'kushe', 'sannu']):
        if language == 'am':
            if user_tickets:
                return f"ሰላም! እርስዎ {len(user_tickets)} አይነት ቲኬቶች አሉዎት። እንዴት ልትረዱኝ እችላለሁ?", language
            return "ሰላም! በቲኬቶች እና ክስተቶች ላይ እርዳት እችላለሁ። እባክዎ ጥያቄዎን ይግለጹ።", language
        elif language == 'kri':
            if user_tickets:
                return f"Kushe! Yu gɛt {len(user_tickets)} tikit dɛn. Aw a go ɛp yu?", language
            return "Kushe! A kin ɛp yu wit tikit ɛn ivɛnt. Wetin yu want?", language
        else:
            if user_tickets:
                return f"Hello! You have {len(user_tickets)} active tickets. How can I assist you today?", language
            return "Hello! I can help you with tickets and events. What would you like to know?", language
    
    # Ticket expiration queries
    if any(word in user_msg_lower for word in ['when my ticket expire', 'when ticket expire', 'ticket expiry', 'ticket expir']):
        if user_tickets:
            next_ticket = user_tickets[0]  # Get the soonest ticket
            event = next_ticket.event
            days_left = (event.date - timezone.now()).days
            
            if language == 'am':
                return f"የእርስዎ ቲኬት ለ '{event.name}' በ {event.date.strftime('%B %d, %Y')} ይዘጋል። {'ቀናት' if days_left > 1 else 'ቀን'} {days_left} ብቻ ቀርቷል!", language
            elif language == 'kri':
                return f"Yu tikit fɔ '{event.name}' go don na {event.date.strftime('%B %d, %Y')}. I rɛmɛn jɔs {days_left} {'dɛn' if days_left > 1 else 'dey'}!", language
            else:
                return f"Your ticket for '{event.name}' expires on {event.date.strftime('%B %d, %Y')}. Only {days_left} {'days' if days_left > 1 else 'day'} left!", language
        else:
            if language == 'am':
                return "ምንም አይነት ተገቢ ያልሆኑ ቲኬቶች አልተገኙም።", language
            elif language == 'kri':
                return "A nɔ si ɛni valid tikit we yu gɛt.", language
            return "You don't have any valid tickets at the moment.", language
    
    # Event-related queries
    if any(word in user_msg_lower for word in ['event', 'events', 'ticket', 'tickets', 'upcoming', 'available']):
        if available_events:
            next_event = available_events[0]
            if language == 'am':
                response = f"የሚቀጥለው ክስተት '{next_event.name}' በ {next_event.date.strftime('%B %d, %Y')} በ {next_event.location} ነው።"
                if len(available_events) > 1:
                    response += f" አጠቃላይ {len(available_events)} ክስተቶች አሉ። ለበለጠ መረጃ ይጠይቁኝ።"
                return response, language
            elif language == 'kri':
                response = f"Di nɛks ivɛnt na '{next_event.name}' na {next_event.date.strftime('%B %d, %Y')} na {next_event.location}."
                if len(available_events) > 1:
                    response += f" Wi gɛt {len(available_events)} difrɛn ivɛnt. Aks mi if yu want no mɔ."
                return response, language
            else:
                response = f"The next event is '{next_event.name}' on {next_event.date.strftime('%B %d, %Y')} at {next_event.location}."
                if len(available_events) > 1:
                    response += f" There are {len(available_events)} total events available. Ask me for more details."
                return response, language
        else:
            if language == 'am':
                return "በአሁኑ ጊዜ ምንም ክስተቶች የሉም። በቅርቡ እንደገና ይመልከቱ።", language
            elif language == 'kri':
                return "Nɔ ivɛnt de na in de now. Chɛk bak lɛta.", language
            return "There are no events available at the moment. Please check back later.", language
    
    # Help request - handle variations
    help_phrases = {
        'en': ['help', 'support', 'assist', 'aid'],
        'am': ['እርዳት', 'ድጋፍ', 'እንዴት', 'ምን ማድረግ አለብኝ'],
        'kri': ['hep', 'sapot', 'aw', 'aw fo', 'wetin fo du']
    }
    
    if any(phrase in user_msg_lower for phrase in help_phrases.get(language, [])) or \
       any(phrase in user_msg_lower for phrases in help_phrases.values() for phrase in phrases):
        responses = {
            'am': "እባክዎ የተወሰነውን ጥያቄዎን ይግለጹ። በቲኬቶች፣ ክስተቶች ወይም ደረሰኞች ላይ እርዳት እችላለሁ። ምን ማድረግ ትፈልጋለህ?",
            'kri': "Padi, wetin na ya palava? A kin ɛp yu wit tikit, ivɛnt, ɛn ɛni oda tin we yu nid. Wetin yu want?",
            'en': "How can I assist you today? I can help with tickets, events, or any other questions you might have. What would you like to know?"
        }
        return responses.get(language, responses['en']), language
    
    # Thank you responses - handle variations in all languages
    thank_phrases = {
        'en': ['thank', 'thanks', 'appreciate', 'grateful'],
        'am': ['አመሰግናለሁ', 'አመሰግናለሁ', 'የተዋወርኩ'],
        'kri': ['tenki', 'a de kam', 'a de tank', 'tank yu']
    }
    
    # Check for thank you in any language
    if any(phrase in user_msg_lower for phrase in thank_phrases.get(language, [])) or \
       any(phrase in user_msg_lower for phrases in thank_phrases.values() for phrase in phrases):
        responses = {
            'am': "እናመሰግናለን! ሌላ ማድረግ የሚፈልጉት ነገር አለ?",
            'kri': "A de kam! A glad se a bin kin ɛp. Yu gɛt ɛni oda kɛsƐn?",
            'en': "You're welcome! Is there anything else I can assist you with?"
        }
        return responses.get(language, responses['en']), language
    
    @retry_on_exception(max_retries=3, initial_delay=1, backoff=2)
    def call_openai_api(messages):
        """Helper function to call OpenAI API with retry logic"""
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                max_tokens=500,
                temperature=0.7,
                timeout=10  # Add timeout to prevent hanging
            )
            return response
        except Exception as e:
            logger_service.error(f'❌ Error calling OpenAI API: {str(e)}')
            return None

    try:
        # Log the API key status
        logger_service.info(f'[ChatService] Using model: {OPENAI_MODEL}')
        logger_service.info(f'[ChatService] System prompt: {SYSTEM_PROMPT[:100]}...')
        
        # Prepare the messages list with system prompt and conversation history
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history if provided (limit to last 5 messages for context)
        if conversation_history:
            messages.extend(conversation_history[-5:])  # Only keep last 5 messages for context
        
        # Add context about previous interactions if available
        if 'last_action' in context:
            messages.append({
                "role": "system", 
                "content": f"User's last action was: {context['last_action']}"
            })
                
        # Add the current user message with language context
        messages.append({
            "role": "user", 
            "content": f"[{language.upper()}] {user_message}"
        })
            
        logger_service.info('[ChatService] Messages prepared for API:')
        for msg in messages:
            role = msg['role']
            content_preview = msg['content'][:50] + ('...' if len(msg['content']) > 50 else '')
            logger_service.info(f'  {role}: {content_preview}')
            
        logger_service.info('[ChatService] Sending request to OpenAI API...')
        
        try:
            # Make the API call with retry logic
            start_time = time.time()
            response = call_openai_api(messages)
            elapsed = time.time() - start_time
            
            # Extract the response text and clean it
            bot_response = response.choices[0].message.content.strip()
            
            # Remove any language tags if present
            for lang in ['[EN]', '[AM]', '[KRI]']:
                if bot_response.startswith(lang):
                    bot_response = bot_response[len(lang):].strip()
            
            # Update context based on response
            if 'ticket' in bot_response.lower() and 'event' in bot_response.lower():
                context['last_topic'] = 'tickets and events'
            elif 'ticket' in bot_response.lower():
                context['last_topic'] = 'tickets'
            elif 'event' in bot_response.lower():
                context['last_topic'] = 'events'
                
            # Log the response
            logger_service.info(f'✅ [ChatService] Successfully received response in {elapsed:.2f}s')
            logger_service.debug(f'[ChatService] Response: {bot_response[:200]}...')
            
            # Add context to the response if this is a follow-up
            if is_follow_up and 'last_topic' in context:
                follow_up_phrases = {
                    'en': "Continuing about %s... ",
                    'am': "በ%s ላይ በመቀጠል... ",
                    'kri': "A de kam wit %s... "
                }
                bot_response = follow_up_phrases.get(language, follow_up_phrases['en']) % context['last_topic'] + bot_response
            
            return bot_response, language
            
        except AuthenticationError as auth_err:
            error_msg = f'❌ [ChatService] Authentication error with OpenAI API. Please check your API key.'
            logger_service.error(error_msg)
            logger_service.error(f'API Key: {api_key[:5]}...{api_key[-5:]}')
            return lang_prompts.get('error', "I'm sorry, there was an error with the chat service. Please try again later."), language
            
        except APIConnectionError as conn_err:
            error_msg = f'❌ [ChatService] Connection error with OpenAI API: {str(conn_err)}'
            logger_service.error(error_msg)
            return "I'm having trouble connecting to the chat service. Please check your internet connection and try again.", language
            
        except RateLimitError as rate_err:
            error_msg = f'❌ [ChatService] Rate limit exceeded for OpenAI API: {str(rate_err)}'
            logger_service.error(error_msg)
            return "The chat service is currently experiencing high traffic. Please wait a moment and try again.", language
            
        except APIError as api_err:
            error_msg = f'❌ [ChatService] OpenAI API error: {str(api_err)}'
            logger_service.error(error_msg)
            return "I'm sorry, there was an error processing your request. Please try again in a moment.", language
        
    except Exception as e:
        error_msg = f'❌ [ChatService] Unexpected error: {str(e)}'
        logger_service.error(error_msg, exc_info=True)
        logger_service.error(f'Error type: {type(e).__name__}')
        logger_service.error(f'Error details: {str(e)}')
        return "I'm sorry, an unexpected error occurred. The administrator has been notified.", language

# Example usage (for testing this module directly, not used by Django view directly):
# if __name__ == '__main__':
#     if model and tokenizer:
#         print("Chatbot is ready. Type 'quit' to exit.")
#         while True:
#             message = input("You: ")
#             if message.lower() == 'quit':
#                 break
#             response = generate_reply(message)
#             print(f"Bot: {response}")
#     else:
#         print("Chatbot could not be initialized.")
