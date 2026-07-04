// Login page: toggle password visibility when clicking the lock icon
document.addEventListener('DOMContentLoaded', function () {
    var passwordInput = document.getElementById('id_password');
    if (!passwordInput) return;

    var group = passwordInput.parentElement;
    if (!group) return;

    var icon = group.querySelector('i.input-icon');
    if (!icon) return;

    // Make icon interactive and accessible
    icon.style.cursor = 'pointer';
    icon.setAttribute('role', 'button');
    icon.setAttribute('tabindex', '0');
    icon.setAttribute('aria-label', 'Show password');

    function toggleVisibility() {
        var isHidden = passwordInput.type === 'password';
        passwordInput.type = isHidden ? 'text' : 'password';
        // Swap lock/unlock icon to reflect state
        icon.classList.toggle('fa-lock', !isHidden);
        icon.classList.toggle('fa-unlock', isHidden);
        icon.setAttribute('aria-label', isHidden ? 'Hide password' : 'Show password');
    }

    icon.addEventListener('click', function (e) {
        e.preventDefault();
        toggleVisibility();
    });

    icon.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            toggleVisibility();
        }
    });
});


