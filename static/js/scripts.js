document.addEventListener('DOMContentLoaded', function() {
    // Responsive sidebar functionality
    const toggleSidebar = document.getElementById('toggleSidebar');
    const closeSidebar = document.getElementById('closeSidebar');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    
    function openSidebar() {
        sidebar.classList.remove('-translate-x-full');
        sidebar.classList.add('translate-x-0');
        sidebarOverlay.classList.remove('hidden');
        document.body.style.overflow = 'hidden'; // Prevent background scrolling
    }
    
    function closeSidebarFunc() {
        sidebar.classList.remove('translate-x-0');
        sidebar.classList.add('-translate-x-full');
        sidebarOverlay.classList.add('hidden');
        document.body.style.overflow = ''; // Restore scrolling
    }
    
    if (toggleSidebar) {
        toggleSidebar.addEventListener('click', openSidebar);
    }
    
    if (closeSidebar) {
        closeSidebar.addEventListener('click', closeSidebarFunc);
    }
    
    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', closeSidebarFunc);
    }
    
    // Close sidebar on escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && !sidebar.classList.contains('-translate-x-full')) {
            closeSidebarFunc();
        }
    });
    
    // Close sidebar when clicking on a link (mobile)
    const sidebarLinks = sidebar.querySelectorAll('a');
    sidebarLinks.forEach(link => {
        link.addEventListener('click', function() {
            if (window.innerWidth < 768) { // Only on mobile
                closeSidebarFunc();
            }
        });
    });
    
    // Handle window resize
    window.addEventListener('resize', function() {
        if (window.innerWidth >= 768) {
            // On desktop, ensure sidebar is visible
            sidebar.classList.remove('-translate-x-full');
            sidebar.classList.add('translate-x-0');
            sidebarOverlay.classList.add('hidden');
            document.body.style.overflow = '';
        } else {
            // On mobile, ensure sidebar is hidden by default
            if (!sidebar.classList.contains('translate-x-0')) {
                sidebar.classList.add('-translate-x-full');
                sidebar.classList.remove('translate-x-0');
            }
        }
    });
    
    // Profile dropdown functionality
    const profileButton = document.getElementById('profileButton');
    const profileMenu = document.getElementById('profileMenu');
    const profileChevron = document.getElementById('profileChevron');
    
    if (profileButton && profileMenu) {
        profileButton.addEventListener('click', function(e) {
            e.stopPropagation();
            const isOpen = !profileMenu.classList.contains('hidden');
            
            if (isOpen) {
                // Close dropdown
                profileMenu.classList.add('hidden');
                profileChevron.style.transform = 'rotate(0deg)';
            } else {
                // Open dropdown
                profileMenu.classList.remove('hidden');
                profileChevron.style.transform = 'rotate(180deg)';
            }
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', function(e) {
            if (!profileButton.contains(e.target) && !profileMenu.contains(e.target)) {
                profileMenu.classList.add('hidden');
                profileChevron.style.transform = 'rotate(0deg)';
            }
        });
        
        // Close dropdown when pressing Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && !profileMenu.classList.contains('hidden')) {
                profileMenu.classList.add('hidden');
                profileChevron.style.transform = 'rotate(0deg)';
            }
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
