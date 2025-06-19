document.addEventListener('DOMContentLoaded', function() {
    // Toggle sidebar on mobile
    const toggleSidebar = document.getElementById('toggleSidebar');
    const closeSidebar = document.getElementById('closeSidebar');
    const sidebar = document.querySelector('.sidebar');
    
    if (toggleSidebar) {
        toggleSidebar.addEventListener('click', function() {
            sidebar.classList.add('active');
        });
    }
    
    if (closeSidebar) {
        closeSidebar.addEventListener('click', function() {
            sidebar.classList.remove('active');
        });
    }
    
    // Auto-hide flash messages after 5 seconds
    const flashMessages = document.querySelectorAll('.alert');
    flashMessages.forEach(message => {
        setTimeout(() => {
            message.style.opacity = '0';
            setTimeout(() => {
                message.style.display = 'none';
            }, 300);
        }, 5000);
    });
    
    // Close flash message when X is clicked
    document.querySelectorAll('.alert button').forEach(button => {
        button.addEventListener('click', function() {
            this.parentElement.style.opacity = '0';
            setTimeout(() => {
                this.parentElement.style.display = 'none';
            }, 300);
        });
    });
        const searchForm = document.querySelector('form[action*="/search"]');
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            const searchInput = this.querySelector('input[name="q"]');
            const value = searchInput.value.trim();
            
            // Validate input
            const regex = /^[a-zA-Z0-9\s\-\@\.\#]+$/;
            
            if (!value) {
                e.preventDefault();
                alert('Please enter a search term');
                return false;
            }
            
            if (!regex.test(value)) {
                e.preventDefault();
                alert('Only letters, numbers, spaces, and - . @ # are allowed');
                return false;
            }
            
            if (value.length > 100) {
                searchInput.value = value.substring(0, 100);
                alert('Search term was truncated to 100 characters');
            }
        });
    }
});
