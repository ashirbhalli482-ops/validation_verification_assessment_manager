$(document).ready(function() {
    'use strict';
    
    // Handle dynamic task filtering based on assigned employee
    $('#id_assigned_to').on('change', function() {
        var employeeId = $(this).val();
        var relatedTaskSelect = $('#id_related_task');
        
        // Clear the related task dropdown
        relatedTaskSelect.empty();
        relatedTaskSelect.append('<option value="">---------</option>');
        
        if (!employeeId) {
            // No employee selected, keep dropdown empty
            return;
        }
        
        // Show loading state
        relatedTaskSelect.prop('disabled', true);
        relatedTaskSelect.append('<option value="">Loading tasks...</option>');
        $('#task-loading-indicator').show();
        
        // Make AJAX request to get tasks for the selected employee
        $.ajax({
            url: '/ajax/employee/' + employeeId + '/tasks/',
            type: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            },
            success: function(response) {
                // Clear loading state
                relatedTaskSelect.empty();
                relatedTaskSelect.append('<option value="">---------</option>');
                
                if (response.tasks && response.tasks.length > 0) {
                    // Add tasks to dropdown
                    $.each(response.tasks, function(index, task) {
                        var optionText = task.title;
                        if (task.target_date) {
                            optionText += ' (Due: ' + task.target_date + ')';
                        }
                        if (task.status) {
                            optionText += ' [' + task.status.charAt(0).toUpperCase() + task.status.slice(1) + ']';
                        }
                        
                        relatedTaskSelect.append(
                            '<option value="' + task.id + '">' + optionText + '</option>'
                        );
                    });
                } else {
                    // No tasks found for this employee
                    relatedTaskSelect.append('<option value="">No tasks found for this employee</option>');
                }
                
                // Re-enable the dropdown
                relatedTaskSelect.prop('disabled', false);
                $('#task-loading-indicator').hide();
            },
            error: function(xhr, status, error) {
                // Handle error
                relatedTaskSelect.empty();
                relatedTaskSelect.append('<option value="">---------</option>');
                
                var errorMessage = 'Error loading tasks';
                if (xhr.status === 403) {
                    errorMessage = 'Permission denied';
                } else if (xhr.status === 404) {
                    errorMessage = 'Employee not found';
                }
                
                relatedTaskSelect.append('<option value="">' + errorMessage + '</option>');
                relatedTaskSelect.prop('disabled', false);
                $('#task-loading-indicator').hide();
                
                console.error('Error loading tasks for employee ' + employeeId + ':', error);
            }
        });
    });
    
    // Initialize task dropdown if an employee is already selected (for edit forms)
    var initialEmployeeId = $('#id_assigned_to').val();
    if (initialEmployeeId) {
        // Trigger change event to load tasks for pre-selected employee
        $('#id_assigned_to').trigger('change');
    }
});
