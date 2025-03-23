// Main JavaScript for the Sales Meeting Preparation Agent

document.addEventListener('DOMContentLoaded', function() {
    // Add hover effect to meeting cards
    const meetingCards = document.querySelectorAll('.card');
    
    meetingCards.forEach(card => {
        card.classList.add('meeting-card');
    });
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Handle feedback form submission
    const feedbackForms = document.querySelectorAll('form[action="/feedback"]');
    
    feedbackForms.forEach(form => {
        form.addEventListener('submit', function(event) {
            // Check if a rating is selected
            const selectedRating = form.querySelector('input[name="rating"]:checked');
            
            if (!selectedRating) {
                event.preventDefault();
                alert('Please select a rating before submitting feedback.');
            }
        });
    });
});