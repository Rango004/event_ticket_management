"""
Language configurations for the ticketing system.
"""

# System prompts for different languages
LANGUAGE_PROMPTS = {
    'en': {
        'system': (
            "You are a helpful assistant for an event ticketing system. "
            "You help users with ticket purchases, event information, and support. "
            "Be polite, concise, and professional in your responses."
        ),
        'greeting': "Hello! How can I assist you with your ticketing needs today?",
        'error': "I'm sorry, I encountered an error processing your request. Please try again later.",
        'fallback': "I'm not sure how to respond to that. Could you rephrase or ask about something else?"
    },
    'am': {
        'system': (
            "እርስዎ የቲኬት ስርዓት ረዳት ነዎት። ተጠቃሚዎችን በቲኬት ግዢ፣ በክስተት መረጃ እና በድጋፍ ይርዳሉ። "
            "በክብር እና በጥሞና መልስ መስጠት ይጠበቅብዎታል።"
        ),
        'greeting': "ሰላም! ስለ ቲኬቶች እንዴት ልርዱዎ?",
        'error': "ይቅርታ፣ ጥያቄዎን በሚያስተናግዱበት ጊዜ ስህተት ተከስቷል። እባክዎ ቆይተው ይሞክሩ።",
        'fallback': "ለዚህ ጥያቄ መልስ ማግኘት አልቻልኩም። እባክዎ ይልቁን ይጨምሩ ወይም ሌላ ነገር ይጠይቁ።"
    },
    'kri': {
        'system': (
            "Yu na wan gud yonman we de help pan di tikiting sistem. Yu de help pipul fo bai tikit, "
            "fo get infomeshon bout ivent, en fo get help. Mek yu ansa gud en na gud maner."
        ),
        'greeting': "Kushe! Ow na? Awan mek a help yu wit yu tikit tin dem?",
        'error': "A beg yu padi, someting bad don hapun. Try back small time.",
        'fallback': "A no kin andastand wetin yu de tok. Try tok am anoda way."
    }
}

def detect_language(text):
    """
    Detect the language of the input text.
    Returns 'am' for Amharic, 'kri' for Krio, or 'en' for English (default).
    """
    # Amharic Unicode range
    if any('\u1200' <= char <= '\u137F' for char in text):
        return 'am'
    
    # Common Krio words and phrases
    krio_indicators = [
        'una', 'sabi', 'pikin', 'chop', 'boku', 'abeg', 'wetin', 'na', 'ehn', 
        'dem', 'una', 'waytin', 'mek', 'wan', 'tink', 'dey', 'no', 'get', 
        'mek', 'go', 'come', 'see', 'wan', 'two', 'tree'
    ]
    
    text_lower = text.lower()
    krio_word_count = sum(1 for word in krio_indicators if word in text_lower)
    
    # If we find multiple Krio words, it's likely Krio
    if krio_word_count >= 2:
        return 'kri'
    
    # Default to English
    return 'en'
