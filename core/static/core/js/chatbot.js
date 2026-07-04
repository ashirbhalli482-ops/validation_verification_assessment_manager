// Chatbot JavaScript functionality

$(document).ready(function() {
    let currentSessionId = $('#current-session-id').val();
    let isTyping = false;
    let timeUpdateInterval;
    
    // Initialize
    initializeChatbot();
    
    function initializeChatbot() {
        // Auto-resize textarea
        autoResizeTextarea();
        
        // Bind events
        bindEvents();
        
        // Load messages for current session (but only within the chat area)
        loadCurrentSessionMessages();
        
        // Focus on message input
        $('#message-input').focus();
    }
    
    function bindEvents() {
        // Send message form
        $('#chat-form').on('submit', handleSendMessage);
        
        // New chat button
        $('#new-chat-btn').on('click', showNewChatModal);
        
        // Create session button
        $('#create-session-btn').on('click', createNewSession);
        
        // Chat session selection
        $(document).on('click', '.chat-session-item', selectChatSession);
        
        // Delete session buttons
        $(document).on('click', '.delete-session-btn', deleteSession);
        $('#delete-current-session-btn').on('click', deleteCurrentSession);
        
        // Rename session
        $('#rename-session-btn').on('click', showRenameModal);
        $('#save-rename-btn').on('click', renameCurrentSession);
        
        // Delete session confirmation
        $('#confirm-delete-session-btn').on('click', function() {
            const sessionId = $(this).data('session-id');
            performSessionDeletion(sessionId);
        });
        
        // Enter key handling for textarea
        $('#message-input').on('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                $('#chat-form').submit();
            }
        });
        
        // Auto-resize textarea on input
        $('#message-input').on('input', autoResizeTextarea);
    }
    
    function handleSendMessage(e) {
        e.preventDefault();
        
        const message = $('#message-input').val().trim();
        if (!message || isTyping) return;
        
        // Add user message to chat
        addMessageToChat('user', message);
        
        // Clear input
        $('#message-input').val('');
        autoResizeTextarea();
        
        // Show typing indicator
        showTypingIndicator();
        
        // Send to server
        sendMessageToServer(message);
    }
    
    function addMessageToChat(type, content, timestamp = null, tokensUsed = 0) {
        // Hide welcome message when adding a message
        $('#welcome-message').hide();
        
        const messageHtml = createMessageHtml(type, content, timestamp, tokensUsed);
        $('#chat-messages').append(messageHtml);
        scrollToBottom();
    }
    
    function createMessageHtml(type, content, timestamp, tokensUsed) {
        const isUser = type === 'user';
        // Format time in Muscat timezone (Asia/Muscat)
        const timeStr = timestamp ? 
            new Date(timestamp).toLocaleString('en-US', { 
                timeZone: 'Asia/Muscat',
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: true
            }) : 
            new Date().toLocaleString('en-US', { 
                timeZone: 'Asia/Muscat',
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: true
            });
        
        return `
            <div class="message ${isUser ? 'user-message' : 'assistant-message'} mb-3">
                <div class="d-flex ${isUser ? 'justify-content-end' : 'justify-content-start'}">
                    <div class="message-bubble ${isUser ? 'bg-primary text-white' : 'bg-light'} p-3 rounded" style="max-width: 70%;">
                        <div class="message-content">${content.replace(/\n/g, '<br>')}</div>
                        <small class="message-time text-muted d-block mt-2">
                            ${timeStr}
                        </small>
                    </div>
                </div>
            </div>
        `;
    }
    
    function showTypingIndicator() {
        isTyping = true;
        $('#typing-indicator').show();
        scrollToBottom();
    }
    
    function hideTypingIndicator() {
        isTyping = false;
        $('#typing-indicator').hide();
    }
    
    function sendMessageToServer(message) {
        $.ajax({
            url: `/chatbot/session/${currentSessionId}/send/`,
            type: 'POST',
            data: {
                'message': message,
                'csrfmiddlewaretoken': $('[name=csrfmiddlewaretoken]').val()
            },
            success: function(response) {
                hideTypingIndicator();
                
                if (response.success) {
                    addMessageToChat('assistant', response.message, null, response.tokens_used);
                } else {
                    showError('Failed to get response: ' + (response.error || 'Unknown error'));
                }
            },
            error: function(xhr) {
                hideTypingIndicator();
                let errorMsg = 'Failed to send message';
                
                try {
                    const response = JSON.parse(xhr.responseText);
                    errorMsg = response.error || errorMsg;
                } catch (e) {
                    errorMsg = `Server error: ${xhr.status}`;
                }
                
                showError(errorMsg);
            }
        });
    }
    
    function showNewChatModal() {
        $('#session-name').val('New Chat');
        $('#newChatModal').modal('show');
    }
    
    function createNewSession() {
        const sessionName = $('#session-name').val().trim() || 'New Chat';
        
        $.ajax({
            url: '/chatbot/session/create/',
            type: 'POST',
            data: {
                'session_name': sessionName,
                'csrfmiddlewaretoken': $('[name=csrfmiddlewaretoken]').val()
            },
            success: function(response) {
                if (response.success) {
                    $('#newChatModal').modal('hide');
                    // Reload page to show new session
                    window.location.href = `/chatbot/`;
                } else {
                    showError('Failed to create session: ' + (response.error || 'Unknown error'));
                }
            },
            error: function(xhr) {
                let errorMsg = 'Failed to create session';
                try {
                    const response = JSON.parse(xhr.responseText);
                    errorMsg = response.error || errorMsg;
                } catch (e) {
                    errorMsg = `Server error: ${xhr.status}`;
                }
                showError(errorMsg);
            }
        });
    }
    
    function selectChatSession(e) {
        e.preventDefault();
        const sessionId = $(this).data('session-id');
        
        if (sessionId !== currentSessionId) {
            // Load chat history for selected session
            loadChatHistory(sessionId);
        }
    }
    
    function loadChatHistory(sessionId) {
        $.ajax({
            url: `/chatbot/session/${sessionId}/history/`,
            type: 'GET',
            success: function(response) {
                if (response.success) {
                    // Update current session
                    currentSessionId = sessionId;
                    $('#current-session-id').val(sessionId);
                    $('#current-session-name').text(response.session_name);
                    
                    // Clear current messages and hide welcome message
                    $('#chat-messages').empty();
                    $('#welcome-message').hide();
                    
                    // Add messages
                    if (response.messages.length > 0) {
                        response.messages.forEach(function(msg) {
                            addMessageToChat(msg.type, msg.content, msg.timestamp, msg.tokens_used);
                        });
                        scrollToBottom();
                    } else {
                        // Show welcome message if no messages
                        $('#welcome-message').show();
                    }
                    
                    // Update active session in sidebar
                    $('.chat-session-item').removeClass('active');
                    $(`.chat-session-item[data-session-id="${sessionId}"]`).addClass('active');
                } else {
                    showError('Failed to load chat history: ' + (response.error || 'Unknown error'));
                }
            },
            error: function(xhr) {
                let errorMsg = 'Failed to load chat history';
                try {
                    const response = JSON.parse(xhr.responseText);
                    errorMsg = response.error || errorMsg;
                } catch (e) {
                    errorMsg = `Server error: ${xhr.status}`;
                }
                showError(errorMsg);
            }
        });
    }
    
    function deleteSession(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const sessionId = $(this).data('session-id');
        const sessionName = $(this).closest('.chat-session-item').find('h6').text();
        
        // Show beautiful confirmation modal
        showDeleteConfirmationModal(sessionId, sessionName);
    }
    
    function deleteCurrentSession() {
        const sessionName = $('#current-session-name').text();
        showDeleteConfirmationModal(currentSessionId, sessionName);
    }
    
    function showDeleteConfirmationModal(sessionId, sessionName) {
        // Update modal content with session name
        $('#delete-session-name').text(sessionName);
        
        // Store session ID for deletion
        $('#confirm-delete-session-btn').data('session-id', sessionId);
        
        // Show the modal
        $('#deleteChatSessionModal').modal('show');
    }
    
    function performSessionDeletion(sessionId) {
        $.ajax({
            url: `/chatbot/session/${sessionId}/delete/`,
            type: 'POST',
            data: {
                'csrfmiddlewaretoken': $('[name=csrfmiddlewaretoken]').val()
            },
            success: function(response) {
                if (response.success) {
                    // Hide modal
                    $('#deleteChatSessionModal').modal('hide');
                    
                    // Remove from sidebar
                    $(`.chat-session-item[data-session-id="${sessionId}"]`).remove();
                    
                    // If this was the current session, redirect to chatbot home
                    if (sessionId == currentSessionId) {
                        window.location.href = '/chatbot/';
                    }
                    
                    // Show success message
                    showSuccess('Chat session deleted successfully');
                } else {
                    showError('Failed to delete session: ' + (response.error || 'Unknown error'));
                }
            },
            error: function(xhr) {
                let errorMsg = 'Failed to delete session';
                try {
                    const response = JSON.parse(xhr.responseText);
                    errorMsg = response.error || errorMsg;
                } catch (e) {
                    errorMsg = `Server error: ${xhr.status}`;
                }
                showError(errorMsg);
            }
        });
    }
    
    function showRenameModal() {
        const currentName = $('#current-session-name').text();
        $('#new-session-name').val(currentName);
        $('#renameSessionModal').modal('show');
    }
    
    function renameCurrentSession() {
        const newName = $('#new-session-name').val().trim();
        if (!newName) {
            showError('Session name cannot be empty');
            return;
        }
        
        // Update the session name in the UI
        $('#current-session-name').text(newName);
        $(`.chat-session-item[data-session-id="${currentSessionId}"] h6`).text(newName);
        
        $('#renameSessionModal').modal('hide');
        showSuccess('Session renamed successfully');
    }
    
    function autoResizeTextarea() {
        const textarea = $('#message-input');
        textarea.css('height', 'auto');
        const newHeight = Math.min(textarea[0].scrollHeight, 120);
        textarea.css('height', newHeight + 'px');
    }
    
    function scrollToBottom() {
        const chatMessages = $('#chat-messages');
        chatMessages.scrollTop(chatMessages[0].scrollHeight);
    }
    
    function loadCurrentSessionMessages() {
        // Load messages for the current session only within the chat area
        const sessionId = $('#current-session-id').val();
        if (sessionId) {
            loadChatHistory(sessionId);
        }
    }
    
    function showError(message) {
        // Hide any existing toasts
        $('.toast').toast('hide');
        
        // Set the error message
        $('#error-toast-body').text(message);
        
        // Show the beautiful error toast
        $('#error-toast').toast({
            autohide: true,
            delay: 5000
        }).toast('show');
    }
    
    function showSuccess(message) {
        // Hide any existing toasts
        $('.toast').toast('hide');
        
        // Set the success message
        $('#success-toast-body').text(message);
        
        // Show the beautiful success toast
        $('#success-toast').toast({
            autohide: true,
            delay: 4000
        }).toast('show');
    }
    
    // Handle session hover effects
    $(document).on('mouseenter', '.chat-session-item', function() {
        $(this).find('.delete-session-btn').show();
    });
    
    $(document).on('mouseleave', '.chat-session-item', function() {
        $(this).find('.delete-session-btn').hide();
    });
    
    // Handle modal events
    $('#newChatModal').on('shown.bs.modal', function() {
        $('#session-name').focus();
    });
    
    $('#renameSessionModal').on('shown.bs.modal', function() {
        $('#new-session-name').focus();
    });
    
    // Handle Enter key in modals
    $('#session-name').on('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            $('#create-session-btn').click();
        }
    });
    
    $('#new-session-name').on('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            $('#save-rename-btn').click();
        }
    });
});
