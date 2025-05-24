import os
import django
import sys

# Set up Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ticketing_system.settings')
django.setup()

# Now we can import the chatbot service
from tickets.chatbot_service import generate_reply

def test_chatbot():
    print("Testing chatbot integration...")
    
    # Test message
    test_message = "Hello, can you help me with my ticket?"
    print(f"\nSending message: {test_message}")
    
    try:
        # Call the chatbot service
        response = generate_reply(test_message)
        print(f"\nResponse from chatbot: {response}")
        
        if "error" in response.lower() or "sorry" in response.lower():
            print("\n⚠️  There might be an issue with the API key or connection.")
        else:
            print("\n✅ Chatbot is working correctly!")
            
    except Exception as e:
        print(f"\n❌ Error testing chatbot: {str(e)}")

if __name__ == "__main__":
    test_chatbot()
