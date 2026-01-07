// auth.js - Authentication specific functionality
document.addEventListener('DOMContentLoaded', function() {
    
    // Auth Page Panel Toggle
    const signUpButton = document.getElementById('signUp');
    const signInButton = document.getElementById('signIn');
    const authContainer = document.getElementById('authContainer');
    
    if (signUpButton && signInButton && authContainer) {
        signUpButton.addEventListener('click', () => {
            authContainer.classList.add('right-panel-active');
        });
        
        signInButton.addEventListener('click', () => {
            authContainer.classList.remove('right-panel-active');
        });
    }
    
    // Password Toggle Visibility
    const passwordToggles = document.querySelectorAll('.password-toggle');
    
    passwordToggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            const passwordInput = this.previousElementSibling;
            const icon = this.querySelector('i');
            
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                icon.classList.remove('fa-eye');
                icon.classList.add('fa-eye-slash');
            } else {
                passwordInput.type = 'password';
                icon.classList.remove('fa-eye-slash');
                icon.classList.add('fa-eye');
            }
        });
    });

});