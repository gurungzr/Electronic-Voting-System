// Secure Voting System - Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss alerts after 5 seconds (except those with Voter ID info)
    const alerts = document.querySelectorAll('.alert:not(.alert-info):not(.alert-warning)');
    alerts.forEach(function(alert) {
        // Don't auto-dismiss alerts containing Voter ID - user needs time to note it down
        if (alert.textContent.includes('Voter ID')) {
            return;
        }
        setTimeout(function() {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Form validation enhancement
    const forms = document.querySelectorAll('form');
    forms.forEach(function(form) {
        form.addEventListener('submit', function(e) {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn && !form.classList.contains('no-loading')) {
                submitBtn.classList.add('loading');
                submitBtn.disabled = true;
            }
        });
    });

    // Password visibility toggle
    const passwordInputs = document.querySelectorAll('input[type="password"]');
    passwordInputs.forEach(function(input) {
        const wrapper = input.parentElement;
        if (wrapper.classList.contains('input-group')) {
            const toggleBtn = document.createElement('button');
            toggleBtn.type = 'button';
            toggleBtn.className = 'btn btn-outline-secondary';
            toggleBtn.innerHTML = '<i class="bi bi-eye"></i>';
            toggleBtn.addEventListener('click', function() {
                if (input.type === 'password') {
                    input.type = 'text';
                    toggleBtn.innerHTML = '<i class="bi bi-eye-slash"></i>';
                } else {
                    input.type = 'password';
                    toggleBtn.innerHTML = '<i class="bi bi-eye"></i>';
                }
            });
            wrapper.appendChild(toggleBtn);
        }
    });

    // Voter ID auto-formatting
    const voterIdInput = document.getElementById('voter_id');
    if (voterIdInput) {
        voterIdInput.addEventListener('input', function() {
            this.value = this.value.toUpperCase();
        });
    }

    // Citizenship number formatting
    const citizenshipInput = document.getElementById('citizenship_number');
    if (citizenshipInput) {
        citizenshipInput.addEventListener('input', function() {
            this.value = this.value.replace(/[^A-Za-z0-9]/g, '').toUpperCase();
        });
    }

    // Password strength indicator (only on registration page, not admin login)
    const passwordInput = document.getElementById('password');
    const isRegistrationPage = document.getElementById('citizenship_number') !== null;

    if (passwordInput && isRegistrationPage) {
        const strengthIndicator = document.createElement('div');
        strengthIndicator.className = 'password-strength mt-2';
        strengthIndicator.innerHTML = '<div class="progress" style="height: 5px;"><div class="progress-bar" role="progressbar"></div></div><small class="text-muted"></small>';
        passwordInput.parentElement.parentElement.appendChild(strengthIndicator);

        passwordInput.addEventListener('input', function() {
            const strength = calculatePasswordStrength(this.value);
            const progressBar = strengthIndicator.querySelector('.progress-bar');
            const text = strengthIndicator.querySelector('small');

            progressBar.style.width = strength.score + '%';
            progressBar.className = 'progress-bar ' + strength.class;
            text.textContent = strength.text;
        });
    }

    // Confirm password matching
    const confirmPasswordInput = document.getElementById('confirm_password');
    if (confirmPasswordInput && passwordInput) {
        confirmPasswordInput.addEventListener('input', function() {
            if (this.value !== passwordInput.value) {
                this.classList.add('is-invalid');
            } else {
                this.classList.remove('is-invalid');
                this.classList.add('is-valid');
            }
        });
    }

    // Date validation for election creation
    const startDateInput = document.getElementById('start_date');
    const endDateInput = document.getElementById('end_date');
    if (startDateInput && endDateInput) {
        startDateInput.addEventListener('change', function() {
            endDateInput.min = this.value;
            if (endDateInput.value && endDateInput.value < this.value) {
                endDateInput.value = '';
            }
        });
    }

    // Candidate card selection highlight
    const candidateCards = document.querySelectorAll('.candidate-card');
    candidateCards.forEach(function(card) {
        card.addEventListener('click', function() {
            const radio = this.querySelector('input[type="radio"]');
            if (radio) {
                radio.checked = true;
                candidateCards.forEach(c => c.classList.remove('selected'));
                this.classList.add('selected');
            }
        });
    });

    // Confirmation dialog for destructive actions
    const dangerButtons = document.querySelectorAll('[data-confirm]');
    dangerButtons.forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            if (!confirm(this.dataset.confirm || 'Are you sure?')) {
                e.preventDefault();
            }
        });
    });

    // Table row click for details
    const clickableRows = document.querySelectorAll('tr[data-href]');
    clickableRows.forEach(function(row) {
        row.style.cursor = 'pointer';
        row.addEventListener('click', function() {
            window.location.href = this.dataset.href;
        });
    });
});

// Password strength calculator
function calculatePasswordStrength(password) {
    let score = 0;
    let text = 'Very Weak';
    let cssClass = 'bg-danger';

    if (!password) {
        return { score: 0, text: '', class: '' };
    }

    // Length
    if (password.length >= 8) score += 20;
    if (password.length >= 12) score += 10;

    // Lowercase
    if (/[a-z]/.test(password)) score += 15;

    // Uppercase
    if (/[A-Z]/.test(password)) score += 15;

    // Numbers
    if (/\d/.test(password)) score += 15;

    // Special characters
    if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) score += 25;

    if (score >= 80) {
        text = 'Strong';
        cssClass = 'bg-success';
    } else if (score >= 60) {
        text = 'Good';
        cssClass = 'bg-info';
    } else if (score >= 40) {
        text = 'Fair';
        cssClass = 'bg-warning';
    } else if (score >= 20) {
        text = 'Weak';
        cssClass = 'bg-danger';
    }

    return { score: score, text: text, class: cssClass };
}

// Utility function to format dates
function formatDate(date) {
    return new Intl.DateTimeFormat('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    }).format(new Date(date));
}

// Countdown timer for elections
function startCountdown(endDate, elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;

    const timer = setInterval(function() {
        const now = new Date().getTime();
        const end = new Date(endDate).getTime();
        const distance = end - now;

        if (distance < 0) {
            clearInterval(timer);
            element.innerHTML = 'Election has ended';
            return;
        }

        const days = Math.floor(distance / (1000 * 60 * 60 * 24));
        const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((distance % (1000 * 60)) / 1000);

        element.innerHTML = days + 'd ' + hours + 'h ' + minutes + 'm ' + seconds + 's';
    }, 1000);
}
