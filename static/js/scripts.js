// Mobile detection
const isMobile = () => window.innerWidth <= 768;
const isTablet = () => window.innerWidth > 768 && window.innerWidth <= 1024;

// Sidebar functionality
document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const toggleSidebarBtn = document.getElementById('toggleSidebar');
    const closeSidebarBtn = document.getElementById('closeSidebar');

    if (toggleSidebarBtn) {
        toggleSidebarBtn.addEventListener('click', function() {
            sidebar.classList.add('open');
            sidebarOverlay.classList.remove('hidden');
            sidebarOverlay.classList.add('show');
            document.body.style.overflow = 'hidden';
        });
    }

    if (closeSidebarBtn) {
        closeSidebarBtn.addEventListener('click', closeSidebar);
    }

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', closeSidebar);
    }

    function closeSidebar() {
        sidebar.classList.remove('open');
        sidebarOverlay.classList.add('hidden');
        sidebarOverlay.classList.remove('show');
        document.body.style.overflow = '';
    }

    // Close sidebar when clicking on a link (mobile)
    if (isMobile()) {
        const sidebarLinks = sidebar.querySelectorAll('a');
        sidebarLinks.forEach(link => {
            link.addEventListener('click', () => {
                setTimeout(closeSidebar, 100);
            });
        });
    }

    // Handle window resize
    window.addEventListener('resize', function() {
        if (window.innerWidth > 768) {
            closeSidebar();
        }
    });
});

// Profile dropdown
document.addEventListener('DOMContentLoaded', function() {
    const profileButton = document.getElementById('profileButton');
    const profileMenu = document.getElementById('profileMenu');
    const profileChevron = document.getElementById('profileChevron');

    if (profileButton && profileMenu) {
        profileButton.addEventListener('click', function(e) {
            e.stopPropagation();
            profileMenu.classList.toggle('hidden');
            profileChevron.style.transform = profileMenu.classList.contains('hidden') ? '' : 'rotate(180deg)';
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', function(e) {
            if (!profileButton.contains(e.target) && !profileMenu.contains(e.target)) {
                profileMenu.classList.add('hidden');
                profileChevron.style.transform = '';
            }
        });
    }
});

// Smart refresh button functionality
document.addEventListener('DOMContentLoaded', function() {
    const smartRefreshBtn = document.getElementById('smart-refresh-btn');
    const refreshContextMenu = document.getElementById('refresh-context-menu');
    const refreshNowBtn = document.getElementById('refresh-now-btn');
    const toggleAutoRefreshBtn = document.getElementById('toggle-auto-refresh-btn');
    const autoRefreshText = document.getElementById('auto-refresh-text');
    const autoRefreshIndicator = document.getElementById('auto-refresh-indicator');
    const refreshIcon = document.getElementById('refresh-icon');

    let autoRefreshInterval = null;
    let autoRefreshEnabled = false;
    let currentInterval = 30; // Default 30 seconds

    if (smartRefreshBtn) {
        // Left click - manual refresh
        smartRefreshBtn.addEventListener('click', function(e) {
            e.preventDefault();
            refreshAlerts();
            
            // Pause auto-refresh briefly on manual refresh
            if (autoRefreshEnabled) {
                pauseAutoRefresh(5000); // Pause for 5 seconds
            }
        });

        // Right click or long press - show context menu
        smartRefreshBtn.addEventListener('contextmenu', function(e) {
            e.preventDefault();
            toggleContextMenu();
        });

        // Touch events for mobile
        let touchTimer = null;
        smartRefreshBtn.addEventListener('touchstart', function(e) {
            touchTimer = setTimeout(() => {
                toggleContextMenu();
            }, 500); // Long press threshold
        });

        smartRefreshBtn.addEventListener('touchend', function() {
            if (touchTimer) {
                clearTimeout(touchTimer);
                touchTimer = null;
            }
        });

        smartRefreshBtn.addEventListener('touchmove', function() {
            if (touchTimer) {
                clearTimeout(touchTimer);
                touchTimer = null;
            }
        });
    }

    if (refreshNowBtn) {
        refreshNowBtn.addEventListener('click', function() {
            refreshAlerts();
            hideContextMenu();
        });
    }

    if (toggleAutoRefreshBtn) {
        toggleAutoRefreshBtn.addEventListener('click', function() {
            toggleAutoRefresh();
            hideContextMenu();
        });
    }

    // Interval selection
    document.querySelectorAll('input[name="refresh-interval"]').forEach(radio => {
        radio.addEventListener('change', function() {
            currentInterval = parseInt(this.value);
            if (autoRefreshEnabled) {
                restartAutoRefresh();
            }
        });
    });

    function toggleContextMenu() {
        refreshContextMenu.classList.toggle('hidden');
        
        // Position menu properly on mobile
        if (isMobile()) {
            const rect = smartRefreshBtn.getBoundingClientRect();
            refreshContextMenu.style.right = '0';
            refreshContextMenu.style.left = 'auto';
        }
    }

    function hideContextMenu() {
        refreshContextMenu.classList.add('hidden');
    }

    function toggleAutoRefresh() {
        if (autoRefreshEnabled) {
            stopAutoRefresh();
        } else {
            startAutoRefresh();
        }
    }

    function startAutoRefresh() {
        autoRefreshEnabled = true;
        autoRefreshText.textContent = 'Turn Auto-Refresh Off';
        autoRefreshIndicator.style.opacity = '1';
        refreshIcon.classList.add('animate-spin');
        startAutoRefreshInterval();
        
        // Show notification
        showNotification('Auto-refresh enabled', 'success');
    }

    function stopAutoRefresh() {
        autoRefreshEnabled = false;
        autoRefreshText.textContent = 'Turn Auto-Refresh On';
        autoRefreshIndicator.style.opacity = '0';
        refreshIcon.classList.remove('animate-spin');
        stopAutoRefreshInterval();
        
        // Show notification
        showNotification('Auto-refresh disabled', 'info');
    }

    function pauseAutoRefresh(duration) {
        stopAutoRefreshInterval();
        setTimeout(() => {
            if (autoRefreshEnabled) {
                startAutoRefreshInterval();
            }
        }, duration);
    }

    function startAutoRefreshInterval() {
        stopAutoRefreshInterval();
        autoRefreshInterval = setInterval(() => {
            refreshAlerts();
        }, currentInterval * 1000);
    }

    function stopAutoRefreshInterval() {
        if (autoRefreshInterval) {
            clearInterval(autoRefreshInterval);
            autoRefreshInterval = null;
        }
    }

    function restartAutoRefresh() {
        if (autoRefreshEnabled) {
            stopAutoRefreshInterval();
            startAutoRefreshInterval();
        }
    }

    // Close context menu when clicking outside
    document.addEventListener('click', function(e) {
        if (!smartRefreshBtn.contains(e.target) && !refreshContextMenu.contains(e.target)) {
            hideContextMenu();
        }
    });

    // Handle escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            hideContextMenu();
        }
    });
});

// Enhanced alerts refresh functionality
function refreshAlerts() {
    const alertsContainer = document.getElementById('alerts-container');
    const alertsLoading = document.getElementById('alerts-loading');
    const lastUpdatedTime = document.getElementById('last-updated-time');

    if (!alertsContainer) return;

    // Show loading state
    alertsLoading.classList.remove('hidden');
    alertsContainer.style.opacity = '0.5';

    fetch('/alerts/refresh', {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update alerts container
            alertsContainer.innerHTML = data.html;
            
            // Update timestamp
            if (lastUpdatedTime) {
                lastUpdatedTime.textContent = 'Just now';
            }

            // Show notification if there are new alerts
            if (data.new_alerts_count > 0) {
                showNotification(`${data.new_alerts_count} new alert(s)`, 'info');
            }

            // Re-attach event listeners to new alert items
            attachAlertEventListeners();
        } else {
            showNotification('Failed to refresh alerts', 'error');
        }
    })
    .catch(error => {
        console.error('Error refreshing alerts:', error);
        showNotification('Error refreshing alerts', 'error');
    })
    .finally(() => {
        // Hide loading state
        alertsLoading.classList.add('hidden');
        alertsContainer.style.opacity = '1';
    });
}

// Attach event listeners to alert items
function attachAlertEventListeners() {
    const alertItems = document.querySelectorAll('.alert-item');
    
    alertItems.forEach(item => {
        item.addEventListener('click', function() {
            const type = this.dataset.type;
            const manufacturer = this.dataset.manufacturer;
            const model = this.dataset.model;
            const days = this.dataset.days;
            
            // Show alert details modal
            showAlertModal(type, manufacturer, model, days);
        });

        // Add touch feedback for mobile
        if (isMobile()) {
            item.addEventListener('touchstart', function() {
                this.style.transform = 'scale(0.98)';
            });

            item.addEventListener('touchend', function() {
                this.style.transform = '';
            });
        }
    });
}

// Show alert modal
function showAlertModal(type, manufacturer, model, days) {
    const modal = document.getElementById('assetModal');
    if (!modal) return;

    // Create modal content
    const modalContent = `
        <div class="relative bg-white rounded-lg shadow-xl max-w-md mx-auto mt-20 p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-lg font-semibold text-gray-900">Alert Details</h3>
                <button onclick="closeAlertModal()" class="text-gray-400 hover:text-gray-600 p-2 touch-manipulation">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="space-y-3">
                <div>
                    <span class="text-sm font-medium text-gray-500">Type:</span>
                    <span class="ml-2 px-2 py-1 text-xs rounded-full ${
                        type === 'warning' ? 'bg-yellow-100 text-yellow-800' :
                        type === 'danger' ? 'bg-red-100 text-red-800' :
                        'bg-blue-100 text-blue-800'
                    }">${type}</span>
                </div>
                <div>
                    <span class="text-sm font-medium text-gray-500">Manufacturer:</span>
                    <span class="ml-2 text-gray-900">${manufacturer}</span>
                </div>
                ${model ? `<div>
                    <span class="text-sm font-medium text-gray-500">Model:</span>
                    <span class="ml-2 text-gray-900">${model}</span>
                </div>` : ''}
                <div>
                    <span class="text-sm font-medium text-gray-500">Days:</span>
                    <span class="ml-2 text-gray-900">${days}</span>
                </div>
            </div>
            <div class="mt-6 flex justify-end">
                <button onclick="closeAlertModal()" class="bg-primary text-white px-4 py-2 rounded-md hover:bg-opacity-90 transition duration-200 touch-manipulation">
                    Close
                </button>
            </div>
        </div>
    `;

    modal.innerHTML = modalContent;
    modal.classList.remove('hidden');

    // Close modal when clicking outside
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeAlertModal();
        }
    });

    // Close modal with escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeAlertModal();
        }
    });
}

function closeAlertModal() {
    const modal = document.getElementById('assetModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// Notification system
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 z-50 p-4 rounded-lg shadow-lg max-w-sm transform transition-all duration-300 translate-x-full ${
        type === 'success' ? 'bg-green-500 text-white' :
        type === 'error' ? 'bg-red-500 text-white' :
        type === 'warning' ? 'bg-yellow-500 text-white' :
        'bg-blue-500 text-white'
    }`;
    
    notification.innerHTML = `
        <div class="flex items-center justify-between">
            <span class="text-sm font-medium">${message}</span>
            <button onclick="this.parentElement.parentElement.remove()" class="ml-4 text-white hover:text-gray-200 touch-manipulation">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(() => {
        notification.classList.remove('translate-x-full');
    }, 100);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        notification.classList.add('translate-x-full');
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 300);
    }, 5000);
}

// Enhanced file upload functionality
document.addEventListener('DOMContentLoaded', function() {
    const dropArea = document.getElementById('drop-area');
    const fileInput = document.getElementById('csv_file');
    const fileInfo = document.getElementById('file-info');
    const fileName = document.getElementById('file-name');
    const fileSize = document.getElementById('file-size');
    const removeFileBtn = document.getElementById('remove-file');
    const submitBtn = document.getElementById('submit-btn');
    const uploadOptions = document.querySelectorAll('.upload-option');
    const syncWarning = document.getElementById('sync-warning');

    if (dropArea && fileInput) {
        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, preventDefaults, false);
            document.body.addEventListener(eventName, preventDefaults, false);
        });

        // Highlight drop area when item is dragged over it
        ['dragenter', 'dragover'].forEach(eventName => {
            dropArea.addEventListener(eventName, highlight, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, unhighlight, false);
        });

        // Handle dropped files
        dropArea.addEventListener('drop', handleDrop, false);

        // Handle file input change
        fileInput.addEventListener('change', handleFiles);

        // Handle click on drop area
        dropArea.addEventListener('click', () => fileInput.click());
    }

    if (removeFileBtn) {
        removeFileBtn.addEventListener('click', removeFile);
    }

    if (uploadOptions.length > 0) {
        uploadOptions.forEach(option => {
            option.addEventListener('click', function() {
                // Remove selected class from all options
                uploadOptions.forEach(opt => {
                    opt.classList.remove('border-primary', 'bg-blue-50');
                    opt.classList.add('border-gray-200');
                });
                
                // Add selected class to clicked option
                this.classList.remove('border-gray-200');
                this.classList.add('border-primary', 'bg-blue-50');
                
                // Check radio button
                const radio = this.querySelector('input[type="radio"]');
                if (radio) {
                    radio.checked = true;
                }
                
                // Show/hide sync warning
                const value = this.dataset.value;
                if (value === 'sync') {
                    syncWarning.classList.remove('hidden');
                } else {
                    syncWarning.classList.add('hidden');
                }
            });
        });
    }

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function highlight(e) {
        dropArea.classList.add('border-primary', 'bg-blue-50');
    }

    function unhighlight(e) {
        dropArea.classList.remove('border-primary', 'bg-blue-50');
    }

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles({ target: { files } });
    }

    function handleFiles(e) {
        const files = e.target.files;
        if (files.length > 0) {
            const file = files[0];
            
            // Validate file type
            if (!file.name.toLowerCase().endsWith('.csv')) {
                showNotification('Please select a CSV file', 'error');
                return;
            }
            
            // Validate file size (5MB limit)
            if (file.size > 5 * 1024 * 1024) {
                showNotification('File size must be less than 5MB', 'error');
                return;
            }
            
            displayFileInfo(file);
            enableSubmitButton();
        }
    }

    function displayFileInfo(file) {
        fileName.textContent = file.name;
        fileSize.textContent = formatFileSize(file.size);
        fileInfo.classList.remove('hidden');
        dropArea.classList.add('hidden');
    }

    function removeFile() {
        fileInput.value = '';
        fileInfo.classList.add('hidden');
        dropArea.classList.remove('hidden');
        disableSubmitButton();
    }

    function enableSubmitButton() {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        }
    }

    function disableSubmitButton() {
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.classList.add('opacity-50', 'cursor-not-allowed');
        }
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
});

// Enhanced asset table functionality
document.addEventListener('DOMContentLoaded', function() {
    // Handle asset row clicks
    const assetRows = document.querySelectorAll('tr[data-id]');
    assetRows.forEach(row => {
        row.addEventListener('click', function() {
            const assetId = this.dataset.id;
            showAssetDetails(assetId);
        });
    });

    // Handle delete buttons
    const deleteButtons = document.querySelectorAll('.delete-btn');
    deleteButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const assetId = this.dataset.id;
            confirmDeleteAsset(assetId);
        });
    });

    // Handle mobile card clicks
    const assetCards = document.querySelectorAll('[data-id]');
    assetCards.forEach(card => {
        card.addEventListener('click', function() {
            const assetId = this.dataset.id;
            showAssetDetails(assetId);
        });
    });
});

function showAssetDetails(assetId) {
    // Implement asset details modal
    console.log('Show asset details for ID:', assetId);
}

function confirmDeleteAsset(assetId) {
    if (confirm('Are you sure you want to delete this asset? This action cannot be undone.')) {
        // Implement delete functionality
        console.log('Delete asset with ID:', assetId);
    }
}

// Mobile-specific enhancements
document.addEventListener('DOMContentLoaded', function() {
    // Improve mobile scrolling
    if (isMobile()) {
        // Add smooth scrolling to all scrollable elements
        const scrollableElements = document.querySelectorAll('.overflow-y-auto, .overflow-x-auto');
        scrollableElements.forEach(element => {
            element.style.webkitOverflowScrolling = 'touch';
        });
    }

    // Handle mobile keyboard events
    if (isMobile()) {
        // Prevent zoom on input focus
        const inputs = document.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            input.addEventListener('focus', function() {
                this.style.fontSize = '16px';
            });
        });
    }

    // Improve mobile touch interactions
    if (isMobile()) {
        // Add touch feedback to buttons
        const buttons = document.querySelectorAll('button, a');
        buttons.forEach(button => {
            button.addEventListener('touchstart', function() {
                this.style.transform = 'scale(0.98)';
            });
            
            button.addEventListener('touchend', function() {
                this.style.transform = '';
            });
        });
    }
});

// Initialize all functionality when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Attach alert event listeners
    attachAlertEventListeners();
    
    // Initialize mobile-specific features
    if (isMobile()) {
        // Add mobile-specific classes
        document.body.classList.add('mobile');
        
        // Optimize for mobile performance
        const images = document.querySelectorAll('img');
        images.forEach(img => {
            img.loading = 'lazy';
        });
    }
});

// Handle window resize events
window.addEventListener('resize', function() {
    // Re-initialize mobile features if needed
    if (isMobile()) {
        document.body.classList.add('mobile');
    } else {
        document.body.classList.remove('mobile');
    }
});
