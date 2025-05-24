document.addEventListener('DOMContentLoaded', function() {
    const confirmationModalEl = document.getElementById('confirmationSection');
    const confirmPurchaseButton = document.getElementById('confirmPurchase');
    const modalEventNameEl = document.getElementById('modalEventName');
    const chargeAmountEl = document.getElementById('chargeAmount');
    const modalCurrentBalanceEl = document.getElementById('currentBalance'); // In modal
    const pageAccountBalanceEl = document.getElementById('accountBalance'); // On page
    const insufficientFundsAlertEl = document.getElementById('insufficientFundsAlert');

    // Toast elements
    const purchaseToastEl = document.getElementById('purchaseToast');
    const errorToastEl = document.getElementById('errorToast');
    const errorToastMessageEl = document.getElementById('errorMessage'); // Inside error toast

    const purchaseToastInstance = purchaseToastEl ? new bootstrap.Toast(purchaseToastEl) : null;
    const errorToastInstance = errorToastEl ? new bootstrap.Toast(errorToastEl) : null;

    let eventIdToPurchase = null; // To store the event ID for the confirm button
    let originalConfirmButtonText = confirmPurchaseButton ? confirmPurchaseButton.innerHTML : "Confirm Purchase";

    const confirmationModalInstance = confirmationModalEl ? new bootstrap.Modal(confirmationModalEl) : null;

    // Event listener for all "Buy Ticket" buttons that trigger the modal
    document.querySelectorAll('.buy-ticket-btn[data-bs-toggle="modal"]').forEach(button => {
        button.addEventListener('click', function() {
            eventIdToPurchase = this.dataset.eventId;
            const eventName = this.dataset.eventName;
            const eventPrice = parseFloat(this.dataset.eventPrice);
            const currentAccountBalance = parseFloat(pageAccountBalanceEl.textContent.replace('$', ''));

            if (modalEventNameEl) modalEventNameEl.textContent = eventName;
            if (chargeAmountEl) chargeAmountEl.textContent = eventPrice.toFixed(2);
            if (modalCurrentBalanceEl) modalCurrentBalanceEl.textContent = currentAccountBalance.toFixed(2);

            if (currentAccountBalance < eventPrice) {
                if (insufficientFundsAlertEl) insufficientFundsAlertEl.classList.remove('d-none');
                if (confirmPurchaseButton) {
                    confirmPurchaseButton.disabled = true;
                    confirmPurchaseButton.innerHTML = "Insufficient Credits";
                }
            } else {
                if (insufficientFundsAlertEl) insufficientFundsAlertEl.classList.add('d-none');
                if (confirmPurchaseButton) {
                    confirmPurchaseButton.disabled = false;
                    confirmPurchaseButton.innerHTML = originalConfirmButtonText;
                }
            }
        });
    });

    // Event listener for the actual "Confirm Purchase" button in the modal
    if (confirmPurchaseButton) {
        confirmPurchaseButton.addEventListener('click', function() {
            if (!eventIdToPurchase) {
                console.error('Event ID not found for purchase.');
                showAlert('danger', 'Could not process purchase. Event ID missing.');
                return;
            }

            this.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
            this.disabled = true;

            fetch(`/purchase_ticket/${eventIdToPurchase}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({}),
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => {
                        throw new Error(err.error || 'Failed to purchase ticket');
                    });
                }
                return response.json();
            })
            .then(data => {
                if (confirmationModalInstance) confirmationModalInstance.hide();
                showAlert('success', data.message || 'Ticket purchased successfully!');
                if (pageAccountBalanceEl && data.new_balance !== undefined) {
                    pageAccountBalanceEl.textContent = `$${parseFloat(data.new_balance).toFixed(2)}`;
                }
                setTimeout(() => window.location.reload(), 1500);
            })
            .catch(error => {
                if (confirmationModalInstance) confirmationModalInstance.hide();
                console.error('Purchase Error:', error);
                showAlert('danger', error.message || 'An error occurred during purchase.');
                 // Reset button state on error, allowing user to try again if it's a recoverable error
                this.innerHTML = originalConfirmButtonText;
                // Re-check funds if modal were to be re-shown without re-clicking 'buy'
                // For now, modal hide is enough.
            });
        });
    }

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

    function showAlert(type, message) {
        if (type === 'success' && purchaseToastInstance) {
            // If toast has a body for message, set it here, e.g.,
            // purchaseToastEl.querySelector('.toast-body').textContent = message;
            purchaseToastInstance.show();
        } else if (type === 'danger' && errorToastInstance) {
            if (errorToastMessageEl) errorToastMessageEl.textContent = message;
            errorToastInstance.show();
        } else {
            // Fallback to basic alert if toasts are not available
            console.warn('Toast elements not found, using fallback alert.');
            const alertDiv = document.createElement('div');
            alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x m-3`;
            alertDiv.style.zIndex = "2000"; // Ensure it's on top
            alertDiv.role = 'alert';
            alertDiv.innerHTML = `${message}<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>`;
            document.body.appendChild(alertDiv);
            setTimeout(() => alertDiv.remove(), 5000);
        }
    }
});