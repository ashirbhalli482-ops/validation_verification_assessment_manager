import $ from 'jquery'
import AjaxLoad from './ajax-load'
import AsideMenu from './aside-menu'
import Sidebar from './sidebar'

/**
 * --------------------------------------------------------------------------
 * CoreUI (v2.0.0-beta.0): index.js
 * Licensed under MIT (https://coreui.io/license)
 * --------------------------------------------------------------------------
 */

(($) => {
  if (typeof $ === 'undefined') {
    throw new TypeError('CoreUI\'s JavaScript requires jQuery. jQuery must be included before CoreUI\'s JavaScript.')
  }

  const version = $.fn.jquery.split(' ')[0].split('.')
  const minMajor = 1
  const ltMajor = 2
  const minMinor = 9
  const minPatch = 1
  const maxMajor = 4

  if (version[0] < ltMajor && version[1] < minMinor || version[0] === minMajor && version[1] === minMinor && version[2] < minPatch || version[0] >= maxMajor) {
    throw new Error('CoreUI\'s JavaScript requires at least jQuery v1.9.1 but less than v4.0.0')
  }
})($)

/**
 * Login Page JavaScript
 * Opticor AI Project Management System
 */

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    
    // Initialize login page functionality
    initLoginPage();
    
});

/**
 * Initialize all login page functionality
 */
function initLoginPage() {
    
    // Add loading state to login button
    initLoginForm();
    
    // Add focus effects to form inputs
    initFormFocusEffects();
    
    // Initialize animations
    initAnimations();
    
    // Initialize password visibility toggle (if needed)
    initPasswordToggle();
    
    // Initialize form validation feedback
    initFormValidation();
    
}

/**
 * Initialize login form submission handling
 */
function initLoginForm() {
    const loginForm = document.querySelector('form[action*="login"]');
    
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            const submitBtn = this.querySelector('.btn-login');
            const originalText = submitBtn.innerHTML;
            
            // Show loading state
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Signing In...';
            submitBtn.disabled = true;
            
            // Re-enable button after a delay (in case of errors)
            setTimeout(() => {
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            }, 5000);
        });
    }
}

/**
 * Initialize form input focus effects
 */
function initFormFocusEffects() {
    const formInputs = document.querySelectorAll('.login-form-control');
    
    formInputs.forEach(input => {
        // Add focus class on focus
        input.addEventListener('focus', function() {
            this.parentElement.classList.add('focused');
            this.parentElement.classList.add('input-focused');
        });
        
        // Remove focus class on blur (if no value)
        input.addEventListener('blur', function() {
            if (!this.value.trim()) {
                this.parentElement.classList.remove('focused');
            }
            this.parentElement.classList.remove('input-focused');
        });
        
        // Add filled class if input has value on load
        if (input.value.trim()) {
            input.parentElement.classList.add('filled');
        }
        
        // Add filled class on input
        input.addEventListener('input', function() {
            if (this.value.trim()) {
                this.parentElement.classList.add('filled');
            } else {
                this.parentElement.classList.remove('filled');
            }
        });
    });
}

/**
 * Initialize page animations
 */
function initAnimations() {
    
    // Animate elements on page load
    const animatedElements = document.querySelectorAll('.login-card, .login-form-group, .login-header');
    
    animatedElements.forEach((element, index) => {
        element.style.opacity = '0';
        element.style.transform = 'translateY(30px)';
        
        setTimeout(() => {
            element.style.transition = 'all 0.6s ease-out';
            element.style.opacity = '1';
            element.style.transform = 'translateY(0)';
        }, index * 100);
    });
    
    // Add hover animations to buttons
    const buttons = document.querySelectorAll('.btn-login');
    
    buttons.forEach(button => {
        button.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
        });
        
        button.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
        
        button.addEventListener('mousedown', function() {
            this.style.transform = 'translateY(0) scale(0.98)';
        });
        
        button.addEventListener('mouseup', function() {
            this.style.transform = 'translateY(-2px) scale(1)';
        });
    });
}

/**
 * Initialize password visibility toggle
 */
function initPasswordToggle() {
    const passwordInput = document.querySelector('input[type="password"]');
    
    if (passwordInput) {
        // Create toggle button
        const toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.className = 'password-toggle';
        toggleBtn.innerHTML = '<i class="fas fa-eye"></i>';
        toggleBtn.style.cssText = `
            position: absolute;
            right: 15px;
            top: 50%;
            transform: translateY(-50%);
            background: none;
            border: none;
            color: #6c757d;
            cursor: pointer;
            font-size: 1rem;
            transition: color 0.3s ease;
        `;
        
        // Add toggle button to password field container
        const passwordContainer = passwordInput.parentElement;
        passwordContainer.style.position = 'relative';
        passwordContainer.appendChild(toggleBtn);
        
        // Toggle password visibility
        toggleBtn.addEventListener('click', function() {
            const icon = this.querySelector('i');
            
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                icon.className = 'fas fa-eye-slash';
                this.style.color = '#321fdb';
            } else {
                passwordInput.type = 'password';
                icon.className = 'fas fa-eye';
                this.style.color = '#6c757d';
            }
        });
    }
}

/**
 * Initialize form validation feedback
 */
function initFormValidation() {
    const form = document.querySelector('form[action*="login"]');
    
    if (form) {
        const inputs = form.querySelectorAll('input[required]');
        
        inputs.forEach(input => {
            input.addEventListener('invalid', function(e) {
                e.preventDefault();
                showValidationError(this, 'This field is required');
            });
            
            input.addEventListener('input', function() {
                clearValidationError(this);
            });
        });
    }
}

/**
 * Show validation error message
 */
function showValidationError(input, message) {
    // Remove existing error
    clearValidationError(input);
    
    // Create error element
    const errorDiv = document.createElement('div');
    errorDiv.className = 'validation-error';
    errorDiv.textContent = message;
    errorDiv.style.cssText = `
        color: #e55353;
        font-size: 0.875rem;
        margin-top: 5px;
        animation: fadeIn 0.3s ease;
    `;
    
    // Add error to input container
    const container = input.parentElement;
    container.appendChild(errorDiv);
    
    // Add error styling to input
    input.style.borderColor = '#e55353';
    input.style.boxShadow = '0 0 0 3px rgba(229, 83, 83, 0.1)';
}

/**
 * Clear validation error message
 */
function clearValidationError(input) {
    const container = input.parentElement;
    const existingError = container.querySelector('.validation-error');
    
    if (existingError) {
        existingError.remove();
    }
    
    // Reset input styling
    input.style.borderColor = '#e9ecef';
    input.style.boxShadow = 'none';
}

/**
 * Show success message
 */
function showSuccessMessage(message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = 'login-alert login-alert-success';
    alertDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${message}`;
    
    insertAlert(alertDiv);
}

/**
 * Show error message
 */
function showErrorMessage(message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = 'login-alert login-alert-danger';
    alertDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
    
    insertAlert(alertDiv);
}

/**
 * Insert alert message into form
 */
function insertAlert(alertDiv) {
    const form = document.querySelector('form[action*="login"]');
    
    if (form) {
        // Remove existing alerts
        const existingAlerts = form.querySelectorAll('.login-alert');
        existingAlerts.forEach(alert => alert.remove());
        
        // Insert new alert at the top of the form
        form.insertBefore(alertDiv, form.firstChild);
        
        // Auto-remove alert after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.style.opacity = '0';
                alertDiv.style.transform = 'translateY(-10px)';
                setTimeout(() => {
                    if (alertDiv.parentNode) {
                        alertDiv.remove();
                    }
                }, 300);
            }
        }, 5000);
    }
}

/**
 * Utility function to add CSS animations
 */
function addCSSAnimation() {
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .input-focused .input-icon {
            color: #321fdb;
        }
        
        .filled .input-icon {
            color: #321fdb;
        }
        
        .login-alert {
            transition: all 0.3s ease;
        }
    `;
    document.head.appendChild(style);
}

// Add CSS animations when script loads
addCSSAnimation();

// Export functions for potential external use
window.LoginPage = {
    showSuccessMessage,
    showErrorMessage,
    initLoginPage
};

export {
  AjaxLoad,
  AsideMenu,
  Sidebar
}
