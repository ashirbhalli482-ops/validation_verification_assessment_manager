document.addEventListener('DOMContentLoaded', function() {
    const qualitySelect = document.getElementById('quality-select');
    const closeDateInput = document.getElementById('close-date-input');
    const previewDiv = document.getElementById('evaluation-preview');
    const previewContent = document.getElementById('preview-content');
    
    if (!qualitySelect || !closeDateInput || !previewDiv || !previewContent) {
        return; // Elements not found, exit
    }
    
    // Get data from data attributes
    const taskPriority = {
        name: qualitySelect.dataset.priorityName || '',
        multiplier: parseFloat(qualitySelect.dataset.priorityMultiplier) || 1.0,
        code: qualitySelect.dataset.priorityCode || ''
    };
    
    const targetDate = qualitySelect.dataset.targetDate || '';
    
    function updatePreview() {
        const qualityValue = qualitySelect.value;
        const closeDateValue = closeDateInput.value;
        
        if (!qualityValue || !closeDateValue) {
            previewDiv.style.display = 'none';
            return;
        }
        
        // Get quality percentage from the selected option
        const qualityOption = qualitySelect.options[qualitySelect.selectedIndex];
        const qualityText = qualityOption.text;
        const qualityPercentage = parseFloat(qualityText.match(/\((\d+(?:\.\d+)?)%\)/)?.[1] || 0);
        
        // Calculate time difference
        const target = new Date(targetDate);
        const close = new Date(closeDateValue);
        const timeDiff = target.getTime() - close.getTime();
        const daysDiff = Math.ceil(timeDiff / (1000 * 3600 * 24));
        
        // Calculate evaluation
        let baseScore = qualityPercentage;
        let priorityBonus = 0;
        let timeBonus = 0;
        let finalScore = baseScore;
        
        // Priority multiplier
        if (taskPriority.multiplier > 1) {
            priorityBonus = (taskPriority.multiplier - 1) * 100;
            baseScore = qualityPercentage * taskPriority.multiplier;
            finalScore = baseScore;
        }
        
        // Time bonus/penalty (simplified calculation)
        if (daysDiff > 0) {
            timeBonus = Math.min(daysDiff * 1, 5); // 1% per day, max 5%
            finalScore += timeBonus;
        } else if (daysDiff < 0) {
            timeBonus = Math.max(daysDiff * 2, -20); // -2% per day, max -20%
            finalScore += timeBonus;
        }
        
        // Ensure score is within 0-100 range
        finalScore = Math.max(0, Math.min(100, finalScore));
        
        // Generate preview HTML
        let previewHTML = `
            <div class="table-responsive">
                <table class="table table-sm table-borderless">
                    <tbody>
                        <tr>
                            <td width="30%"><strong>Quality:</strong></td>
                            <td>${qualityText}</td>
                        </tr>
        `;
        
        if (taskPriority.multiplier > 1) {
            previewHTML += `
                        <tr>
                            <td><strong>Priority:</strong></td>
                            <td>${taskPriority.name} → +${priorityBonus.toFixed(0)}% → ${qualityPercentage.toFixed(1)} × ${taskPriority.multiplier.toFixed(2)} = <strong>${baseScore.toFixed(1)}</strong></td>
                        </tr>
            `;
        }
        
        if (timeBonus !== 0) {
            const timeText = daysDiff > 0 ? 
                `Finished ${daysDiff} day${daysDiff > 1 ? 's' : ''} early → +${timeBonus.toFixed(1)}%` :
                `Finished ${Math.abs(daysDiff)} day${Math.abs(daysDiff) > 1 ? 's' : ''} late → ${timeBonus.toFixed(1)}%`;
            const timeClass = timeBonus > 0 ? 'text-success' : 'text-danger';
            
            previewHTML += `
                        <tr>
                            <td><strong>Time Adjustment:</strong></td>
                            <td><span class="${timeClass}">${timeText}</span></td>
                        </tr>
            `;
        }
        
        previewHTML += `
                        <tr class="table-active">
                            <td><strong>Final Score:</strong></td>
                            <td><strong>${finalScore.toFixed(1)}%</strong></td>
                        </tr>
                    </tbody>
                </table>
            </div>
        `;
        
        previewContent.innerHTML = previewHTML;
        previewDiv.style.display = 'block';
    }
    
    // Add event listeners
    qualitySelect.addEventListener('change', updatePreview);
    closeDateInput.addEventListener('change', updatePreview);
    
    // Initial preview if values are already set
    if (qualitySelect.value && closeDateInput.value) {
        updatePreview();
    }
}); 