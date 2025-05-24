import os
import logging
import traceback
import socket
import time
import random
import requests
from openai import OpenAI, APIError, APIConnectionError, RateLimitError, AuthenticationError
from django.conf import settings
from dotenv import load_dotenv
from functools import wraps

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
SYSTEM_PROMPT = getattr(settings, 'CHATBOT_SYSTEM_PROMPT', 
    "You are a helpful assistant for a ticketing system. "
    "You help users with their support tickets, answer questions, and provide information. "
    "Be concise and helpful in your responses.")

def generate_reply(user_message, conversation_history=None):
    """
    Generate a response to the user's message using the OpenAI API.
    
    Args:
        user_message (str): The user's message
        conversation_history (list, optional): List of previous messages in the conversation
        
    Returns:
        str: The generated response or error message
    """
    logger_service.info('=' * 80)
    logger_service.info('🔄 [ChatService] generate_reply called')
    logger_service.info(f'📩 Message: "{user_message[:200]}" (length: {len(user_message)})')
    
    # Check if client is properly initialized
    if not client:
        error_msg = '❌ OpenAI client not initialized. Chat functionality is disabled.'
        logger_service.error(error_msg)
        
        # Check for API key in environment and settings
        env_key = os.getenv('OPENAI_API_KEY')
        settings_key = getattr(settings, 'OPENAI_API_KEY', None)
        
        logger_service.error('🔍 Debug Info:')
        logger_service.error(f'  - .env file exists: {os.path.exists(".env")}')
        logger_service.error(f'  - OPENAI_API_KEY in os.environ: {"Yes" if env_key else "No"}')
        logger_service.error(f'  - OPENAI_API_KEY in settings: {"Yes" if settings_key else "No"}')
        
        if env_key:
            logger_service.error(f'  - Environment API key length: {len(env_key)} characters')
        if settings_key:
            logger_service.error(f'  - Settings API key length: {len(settings_key)} characters')

        # Check internet connectivity
        try:
            # Test DNS resolution
            socket.gethostbyname('api.openai.com')
            logger_service.info('✅ Internet connectivity: DNS resolution successful')
            
            # Test HTTPS connection to OpenAI
            response = requests.get('https://api.openai.com/v1/models', 
                                 headers={'Authorization': f'Bearer {env_key}'},
                                 timeout=5)
            logger_service.info(f'✅ OpenAI API reachable. Status code: {response.status_code}')
            logger_service.debug(f'Response: {response.text[:200]}...')
            
        except socket.gaierror:
            logger_service.error('❌ Internet connectivity: DNS resolution failed')
        except requests.exceptions.SSLError as e:
            logger_service.error(f'❌ SSL Error connecting to OpenAI: {str(e)}')
        except requests.exceptions.ConnectTimeout:
            logger_service.error('❌ Connection to OpenAI API timed out')
        except requests.exceptions.RequestException as e:
            logger_service.error(f'❌ Error connecting to OpenAI API: {str(e)}')
        except Exception as e:
            logger_service.error(f'❌ Unexpected error checking connectivity: {str(e)}')
            
        return "I'm sorry, the chatbot is not properly configured. The administrator has been notified. Please try again later."
    
    @retry_on_exception(max_retries=3, initial_delay=1, backoff=2)
    def call_openai_api(messages):
        """Helper function to call OpenAI API with retry logic"""
        return client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=500,
            temperature=0.7,
            timeout=10  # Add timeout to prevent hanging
        )

    try:
        # Log the API key status
        logger_service.info(f'[ChatService] Using model: {OPENAI_MODEL}')
        logger_service.info(f'[ChatService] System prompt: {SYSTEM_PROMPT[:100]}...')
        
        # Prepare the messages list with system prompt and conversation history
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history)
            
        # Add the current user message
        messages.append({"role": "user", "content": user_message})
        
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
            
            # Extract the response text
            bot_response = response.choices[0].message.content.strip()
            logger_service.info(f'✅ [ChatService] Successfully received response in {elapsed:.2f}s')
            logger_service.debug(f'[ChatService] Response: {bot_response[:200]}...')
            
            return bot_response
            
        except AuthenticationError as auth_err:
            error_msg = f'❌ [ChatService] Authentication error with OpenAI API. Please check your API key.'
            logger_service.error(error_msg)
            logger_service.error(f'API Key: {api_key[:5]}...{api_key[-5:]}')
            return "I'm sorry, there was an authentication error with the chat service. The administrator has been notified."
            
        except APIConnectionError as conn_err:
            error_msg = f'❌ [ChatService] Connection error with OpenAI API: {str(conn_err)}'
            logger_service.error(error_msg)
            return "I'm having trouble connecting to the chat service. Please check your internet connection and try again."
            
        except RateLimitError as rate_err:
            error_msg = f'❌ [ChatService] Rate limit exceeded for OpenAI API: {str(rate_err)}'
            logger_service.error(error_msg)
            return "The chat service is currently experiencing high traffic. Please wait a moment and try again."
            
        except APIError as api_err:
            error_msg = f'❌ [ChatService] OpenAI API error: {str(api_err)}'
            logger_service.error(error_msg)
            return "I'm sorry, there was an error processing your request. Please try again in a moment."
        
    except Exception as e:
        error_msg = f'❌ [ChatService] Unexpected error: {str(e)}'
        logger_service.error(error_msg, exc_info=True)
        logger_service.error(f'Error type: {type(e).__name__}')
        logger_service.error(f'Error details: {str(e)}')
        return "I'm sorry, an unexpected error occurred. The administrator has been notified."

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
