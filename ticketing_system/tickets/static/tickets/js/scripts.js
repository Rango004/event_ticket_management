// Theme Management
function initializeTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.body.setAttribute('data-bs-theme', savedTheme);
    updateThemeToggleIcon(savedTheme);
}

function updateThemeToggleIcon(theme) {
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.innerHTML = theme === 'dark' ? 
            '<i class="bi bi-sun"></i>' : 
            '<i class="bi bi-moon-stars"></i>';
    }
}

document.getElementById('theme-toggle')?.addEventListener('click', () => {
    const newTheme = document.body.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
    document.body.setAttribute('data-bs-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeToggleIcon(newTheme);
});

// QR Scanner Initialization
let qrScanner = null;
function initializeQRScanner() {
    const qrReaderElement = document.getElementById('qr-reader');
    if (!qrReaderElement) {
        // console.log('QR Reader element not found on this page. Skipping QR Scanner initialization.');
        return; // Exit if the QR reader element isn't on the page
    }
    // Check if the Html5QrcodeScanner library is loaded
    if (typeof Html5QrcodeScanner === 'undefined') {
        console.error('Html5QrcodeScanner library is not loaded, but #qr-reader element is present. Please include the html5-qrcode.min.js script before scripts.js on this page.');
        if(qrReaderElement) qrReaderElement.innerHTML = `<div class="alert alert-warning">QR Scanner library not loaded. Please ensure it's included on this page.</div>`;
        return;
    }

    try {
        qrScanner = new Html5QrcodeScanner('qr-reader', { 
            fps: 10, 
            qrbox: 250,
            showTorchButtonIfSupported: true
        });

        qrScanner.render((data, result) => {
            handleQRScan(data);
        });
    } catch (error) {
        console.error('QR Scanner initialization failed:', error);
        document.getElementById('qr-reader').innerHTML = `
            <div class="alert alert-danger">
                QR Scanner initialization failed: ${error.message}
            </div>
        `;
    }
}

async function handleQRScan(data) {
    const resultDiv = document.getElementById('qr-result');
    try {
        const response = await fetch(`/api/validate/${encodeURIComponent(data)}/`);
        if (!response.ok) throw new Error('Validation failed');
        
        const result = await response.json();
        resultDiv.className = `alert alert-${result.valid ? 'success' : 'danger'}`;
        resultDiv.textContent = result.valid ? '✅ Valid Ticket!' : '❌ Invalid Ticket';
        resultDiv.style.display = 'block';
        
        if (result.valid) {
            setTimeout(() => resultDiv.style.display = 'none', 3000);
        }
    } catch (error) {
        resultDiv.className = 'alert alert-danger';
        resultDiv.textContent = 'Error validating ticket';
        resultDiv.style.display = 'block';
    }
}

// Form Handling Utilities
function showLoading(button) {
    button.disabled = true;
    button.querySelector('.spinner-border')?.classList.remove('d-none');
}

function hideLoading(button) {
    button.disabled = false;
    button.querySelector('.spinner-border')?.classList.add('d-none');
}

function showFormErrors(form, errors) {
    Object.entries(errors).forEach(([fieldName, messages]) => {
        const input = form.querySelector(`[name="${fieldName}"]`);
        const feedback = form.querySelector(`.${fieldName}-feedback`);
        if (input) {
            input.classList.add('is-invalid');
            if (feedback) feedback.textContent = messages.join(', ');
        }
    });
}

// Ticket Creation
document.getElementById('ticket-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    const submitButton = form.querySelector('button[type="submit"]');
    const qrCodeDiv = document.getElementById('qr-code');

    showLoading(submitButton);
    
    try {
        const response = await fetch('/api/create/', {
            method: 'POST',
            body: new FormData(form),
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });

        const data = await response.json();
        if (!response.ok) throw data;

        qrCodeDiv.innerHTML = `
            <div class="alert alert-success">
                <img src="${data.qr_code_url}" class="img-fluid mt-3">
                <p class="mt-2">Ticket for: ${data.event}</p>
            </div>
        `;
    } catch (error) {
        qrCodeDiv.innerHTML = `
            <div class="alert alert-danger">
                ${error.message || 'Ticket creation failed'}
            </div>
        `;
        if (error.errors) showFormErrors(form, error.errors);
    } finally {
        hideLoading(submitButton);
    }
});

// AI Chatbot System (HTTP)
const chatWidget = document.getElementById('chat-widget');
const chatToggleBtn = document.getElementById('chat-toggle-btn');
const closeChatBtn = document.getElementById('close-chat');
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendMessageBtn = document.getElementById('send-message');

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
const csrftoken = getCookie('my_csrftoken') || document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    

function appendMessage(message, sender) { // sender can be 'User' or 'Bot'
    if (!chatMessages) return;
    const messageDiv = document.createElement('div');
    messageDiv.className = `mb-2 p-2 rounded ${sender === 'User' ? 'bg-primary text-white ms-auto' : 'bg-light text-dark me-auto'}`;
    messageDiv.style.maxWidth = '75%';
    messageDiv.style.wordWrap = 'break-word';
    messageDiv.textContent = message;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

chatToggleBtn?.addEventListener('click', () => {
    chatWidget?.classList.toggle('d-none');
    chatToggleBtn?.classList.toggle('d-none'); // Hide toggle button when widget is open
});

closeChatBtn?.addEventListener('click', () => {
    chatWidget?.classList.add('d-none');
    chatToggleBtn?.classList.remove('d-none'); // Show toggle button when widget is closed
});

async function handleSendMessage() {
    
    if (!userInput || !sendMessageBtn) {
        console.error('[Chat] userInput or sendMessageBtn not found');
        return;
    }
    
    // Check if user is authenticated
    const isAuthenticated = document.body.getAttribute('data-is-authenticated') === 'true';
    if (!isAuthenticated) {
        appendMessage('Please log in to use the chat feature.', 'Bot');
        window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname);
        return;
    }
    
    const message = userInput.value.trim();
    
    if (!message) {
        
        return;
    }

    appendMessage(message, 'User');
    
    userInput.value = '';
    
    showLoading(sendMessageBtn);
    
    
    
    try {
        
        const response = await fetch('/chatbot/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            credentials: 'same-origin',
            body: JSON.stringify({ message: message })
        });

        
        
        if (response.status === 403) {
            // Handle unauthorized access
            appendMessage('Your session has expired. Please log in again.', 'Bot');
            window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname);
            return;
        }
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.reply || `Error: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();
        
        appendMessage(data.reply, 'Bot');
        

    } catch (error) {
        console.error('[Chat] Error in handleSendMessage:', error);
        if (error.message.includes('Failed to fetch')) {
            appendMessage('Unable to connect to the server. Please check your internet connection.', 'Bot');
        } else {
            appendMessage(`Sorry, an error occurred: ${error.message}`, 'Bot');
        }
    } finally {
        
        hideLoading(sendMessageBtn);
        userInput.focus();
    }
}

sendMessageBtn?.addEventListener('click', handleSendMessage);
userInput?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault(); // Prevents newline in input, if it's a textarea, or form submission
        handleSendMessage();
    }
});

// Initialize all components
document.addEventListener('DOMContentLoaded', () => {
    initializeTheme();
    // Call initializeQRScanner only if the specific element might exist.
    // The function itself will do the final check.
    if (document.getElementById('qr-reader')) { 
        initializeQRScanner();
    }
    // initializeChat(); // WebSocket chat initialization commented out for now
    
    // Initial state for chat widget and toggle button
    if (chatWidget?.classList.contains('d-none')) {
        chatToggleBtn?.classList.remove('d-none');
    } else {
        chatToggleBtn?.classList.add('d-none');
    }
});