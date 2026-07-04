// Notification Management JavaScript
$(document).ready(function() {
    // Mark notification as read
    $('.mark-read-btn').click(function() {
        var notificationId = $(this).data('notification-id');
        var row = $(this).closest('tr');
        var btn = $(this);
        
        $.ajax({
            url: '/notifications/' + notificationId + '/mark-read/',
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            },
            success: function(response) {
                if (response.success) {
                    // Update row appearance
                    row.removeClass('table-warning');
                    row.find('.fa-circle').removeClass('fa-circle text-warning').addClass('fa-check-circle text-success');
                    btn.remove();
                    
                    // Update unread count in header and sidebar
                    updateUnreadCount();
                    
                    // Show success message
                    showToast('Notification marked as read', 'success');
                }
            },
            error: function() {
                showToast('Error marking notification as read', 'error');
            }
        });
    });

    // Delete notification
    $('.delete-notification-btn').click(function() {
        var notificationId = $(this).data('notification-id');
        var row = $(this).closest('tr');
        
        if (confirm('Are you sure you want to delete this notification?')) {
            $.ajax({
                url: '/notifications/' + notificationId + '/delete/',
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                },
                success: function(response) {
                    if (response.success) {
                        row.fadeOut(function() {
                            row.remove();
                            updateUnreadCount();
                            
                            // Reload if no notifications left
                            if ($('tbody tr').length === 0) {
                                location.reload();
                            }
                        });
                        showToast('Notification deleted', 'success');
                    }
                },
                error: function() {
                    showToast('Error deleting notification', 'error');
                }
            });
        }
    });

    // Mark all notifications as read
    $('.mark-all-read-btn').click(function() {
        var btn = $(this);
        var originalText = btn.html();
        
        btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Processing...');
        
        $.ajax({
            url: '/notifications/mark-all-read/',
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCookie('csrftoken')
            },
            success: function(response) {
                if (response.success) {
                    // Update all unread notifications
                    $('.table-warning').removeClass('table-warning');
                    $('.fa-circle.text-warning').removeClass('fa-circle text-warning').addClass('fa-check-circle text-success');
                    $('.mark-read-btn').remove();
                    
                    updateUnreadCount();
                    showToast(response.updated_count + ' notifications marked as read', 'success');
                }
            },
            error: function() {
                showToast('Error marking notifications as read', 'error');
            },
            complete: function() {
                btn.prop('disabled', false).html(originalText);
            }
        });
    });

    // Update unread count in header and sidebar
    function updateUnreadCount() {
        var unreadCount = $('.table-warning').length;
        
        // Update header badge
        var headerBadge = $('.navbar .fa-bell').siblings('.badge');
        if (unreadCount > 0) {
            if (headerBadge.length === 0) {
                $('.navbar .fa-bell').after('<span class="badge badge-danger">' + unreadCount + '</span>');
            } else {
                headerBadge.text(unreadCount);
            }
        } else {
            headerBadge.remove();
        }
        
        // Update sidebar badge
        var sidebarBadge = $('.sidebar .fa-bell').siblings('.badge');
        if (unreadCount > 0) {
            if (sidebarBadge.length === 0) {
                $('.sidebar .fa-bell').after('<span class="badge badge-danger ml-2">' + unreadCount + '</span>');
            } else {
                sidebarBadge.text(unreadCount);
            }
        } else {
            sidebarBadge.remove();
        }
    }

    // Get CSRF token from cookies
    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Show toast notification
    function showToast(message, type) {
        var toastClass = type === 'success' ? 'alert-success' : 'alert-danger';
        var toast = $('<div class="alert ' + toastClass + ' alert-dismissible fade show position-fixed" style="top: 20px; right: 20px; z-index: 9999;">' +
                     '<button type="button" class="close" data-dismiss="alert">&times;</button>' +
                     message +
                     '</div>');
        
        $('body').append(toast);
        
        // Auto-dismiss after 3 seconds
        setTimeout(function() {
            toast.alert('close');
        }, 3000);
    }

    // Auto-refresh notifications every 30 seconds (optional)
    setInterval(function() {
        if ($('.notifications-list').length > 0) {
            // Only refresh if we're on the notifications page
            location.reload();
        }
    }, 30000);
}); 