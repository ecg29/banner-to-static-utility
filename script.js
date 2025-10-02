// Debug mode flag - set to false for production
// Can be enabled by adding ?debug=true to URL or pressing Ctrl+Shift+D
let DEBUG_MODE = false;

// Check for debug mode in URL parameters
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('debug') === 'true') {
    DEBUG_MODE = true;
    document.body.classList.add('debug-mode');
    console.log('🔍 Debug mode enabled via URL parameter');
}

// Debug-aware console logging
const debugLog = (...args) => {
    if (DEBUG_MODE) console.log(...args);
};

// Enable debug mode with Ctrl+Shift+D
document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.shiftKey && e.key === 'D') {
        DEBUG_MODE = !DEBUG_MODE;
        document.body.classList.toggle('debug-mode', DEBUG_MODE);
        console.log(`🔍 Debug mode ${DEBUG_MODE ? 'enabled' : 'disabled'}`);
        if (DEBUG_MODE) {
            console.log('Debug controls are now visible. Debug logging is active.');
        }
    }
});

class BannerToStaticUtility {
    constructor() {
        this.urls = [];
        this.isProcessing = false;
        this.currentProcessIndex = 0;
        this.capturedImages = []; // Store captured images for ZIP download
        
        this.initializeElements();
        this.attachEventListeners();
        this.updateUI();
    }

    initializeElements() {
        // Input elements
        this.bannerUrlInput = document.getElementById('banner-url');
        this.bulkUrlsTextarea = document.getElementById('bulk-urls');
        this.addUrlBtn = document.getElementById('add-url-btn');
        this.addBulkUrlsBtn = document.getElementById('add-bulk-urls-btn');
        
        // URL list elements
        this.urlCountSpan = document.getElementById('url-count');
        this.urlListDiv = document.getElementById('url-list');
        this.clearAllBtn = document.getElementById('clear-all-btn');
        this.generateAllBtn = document.getElementById('generate-all-btn');
        
        // Preview elements
        this.previewContainer = document.getElementById('preview-container');
        this.viewGridBtn = document.getElementById('view-grid-btn');
        this.viewActualBtn = document.getElementById('view-actual-btn');
        this.bannerCountSpan = document.getElementById('banner-count');
        
        // Preview scanning elements
        this.previewUrlInput = document.getElementById('preview-url');
        this.scanPreviewBtn = document.getElementById('scan-preview-btn');
        
        // Settings elements
        this.autoDetectSizeCheckbox = document.getElementById('auto-detect-size');
        this.imageWidthInput = document.getElementById('image-width');
        this.imageHeightInput = document.getElementById('image-height');
        this.imageFormatSelect = document.getElementById('image-format');
        this.waitTimeInput = document.getElementById('wait-time');
        this.fastModeCheckbox = document.getElementById('fast-mode');
        
        // Loading elements
        this.loadingOverlay = document.getElementById('loading-overlay');
        this.loadingText = document.getElementById('loading-text');
        this.progressFill = document.getElementById('progress-fill');
        this.progressText = document.getElementById('progress-text');
        
        // View state
        this.currentView = 'grid'; // 'grid' or 'actual'
    }

    attachEventListeners() {
        // URL input events
        this.addUrlBtn.addEventListener('click', () => this.addSingleUrl());
        this.bannerUrlInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.addSingleUrl();
        });
        
        // Debug button
        this.debugDimensionsBtn = document.getElementById('debug-dimensions-btn');
        this.debugDimensionsBtn.addEventListener('click', () => this.debugDimensions());
        
        // Test Hoxton button
        this.testHoxtonBtn = document.getElementById('test-hoxton-btn');
        this.testHoxtonBtn.addEventListener('click', () => this.testHoxton());
        
        // Check Hoxton Data button
        this.checkHoxtonDataBtn = document.getElementById('check-hoxton-data-btn');
        this.checkHoxtonDataBtn.addEventListener('click', () => this.checkHoxtonData());
        
        // Add a simple test connection button for debugging
        const debugBtn = document.getElementById('debug-dimensions-btn');
        if (debugBtn) {
            // Replace the debug dimensions with connection test for now
            debugBtn.textContent = 'Test Connection';
            debugBtn.addEventListener('click', () => this.testConnection());
        }
        
        // Preview scan button
        this.scanPreviewBtn.addEventListener('click', () => this.scanPreviewPage());
        this.previewUrlInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.scanPreviewPage();
        });
        
        // View toggle buttons
        this.viewGridBtn.addEventListener('click', () => this.setView('grid'));
        this.viewActualBtn.addEventListener('click', () => this.setView('actual'));
        
        this.addBulkUrlsBtn.addEventListener('click', () => this.addBulkUrls());
        
        // Action events
        this.clearAllBtn.addEventListener('click', () => this.clearAllUrls());
        this.generateAllBtn.addEventListener('click', () => this.generateAllImages());
        
        // Settings auto-save
        [this.autoDetectSizeCheckbox, this.imageWidthInput, this.imageHeightInput, this.imageFormatSelect, this.waitTimeInput]
            .forEach(element => {
                element.addEventListener('change', () => {
                    this.saveSettings();
                    this.toggleDimensionInputs();
                });
            });
        
        // Initialize dimension input state
        this.toggleDimensionInputs();
        
        // Load saved settings
        this.loadSettings();
    }

    async scanPreviewPage() {
        const previewUrl = this.previewUrlInput.value.trim();
        if (!this.isValidUrl(previewUrl)) {
            this.showNotification('Please enter a valid preview page URL', 'error');
            return;
        }
        
        try {
            this.showLoadingOverlay();
            this.loadingText.textContent = 'Scanning preview page for banners...';
            
            const response = await fetch('/scan-preview', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url: previewUrl })
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            if (result.totalBanners === 0) {
                this.showNotification('No banners found on the preview page', 'warning');
                return;
            }
            
            // Add all found banners to the URL list
            let addedCount = 0;
            result.banners.forEach(banner => {
                // Skip if URL already exists
                if (!this.urls.some(item => item.url === banner.url)) {
                    this.urls.push({
                        id: Date.now() + Math.random(),
                        url: banner.url,
                        status: 'pending',
                        filename: this.generateFilename(banner.url),
                        imageData: null,
                        error: null,
                        bannerInfo: banner // Store additional banner info
                    });
                    addedCount++;
                }
            });
            
            this.updateUI();
            
            // Show results
            const scanResults = `
🔍 PREVIEW SCAN RESULTS:

📄 Page: ${result.pageTitle}
🔗 URL: ${result.previewUrl}
📊 Total Banners Found: ${result.totalBanners}
✅ Added to Queue: ${addedCount}

📋 Found Banners:
${result.banners.map(banner => 
    `${banner.type.toUpperCase()}: ${banner.title} (${banner.width}×${banner.height}px)`
).join('\n')}

💡 Ready to generate ${addedCount} banner images!
            `;
            
            this.showDetailedNotification('Preview Scan Complete', scanResults);
            this.previewUrlInput.value = ''; // Clear the input
            
        } catch (error) {
            this.showNotification('Preview scan failed: ' + error.message, 'error');
        } finally {
            this.hideLoadingOverlay();
        }
    }

    async debugDimensions() {
        const url = this.bannerUrlInput.value.trim();
        if (!this.isValidUrl(url)) {
            this.showNotification('Please enter a valid URL or file path', 'error');
            return;
        }
        
        try {
            this.showLoadingOverlay();
            this.loadingText.textContent = 'Analyzing banner dimensions...';
            
            const response = await fetch('/debug-dimensions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url: url })
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            // Display debug information
            const debugInfo = `
🔍 DIMENSION DETECTION DEBUG:

📊 Detected Dimensions: ${result.detectedDimensions.width} × ${result.detectedDimensions.height}px
🎯 Detection Method: ${result.detectedDimensions.detectionMethod}
📱 Viewport: ${result.detectedDimensions.viewportWidth} × ${result.detectedDimensions.viewportHeight}px
📄 Body: ${Math.round(result.detectedDimensions.bodyWidth)} × ${Math.round(result.detectedDimensions.bodyHeight)}px

🔍 Found Elements:
${result.detectedDimensions.foundElements.map(el => 
    `${el.selector}: ${Math.round(el.width)}×${Math.round(el.height)}px 
    └─ CSS: ${el.cssWidth}×${el.cssHeight} | ID: ${el.id} | Class: ${el.className}`
).join('\n')}

💡 RECOMMENDATION: 
${result.recommendedWidth} × ${result.recommendedHeight}px

🛠️ If incorrect, look for an element above with the right dimensions
   and we can add its selector to the priority list.
            `;
            
            // Show in a modal-like notification
            this.showDetailedNotification('Debug Results', debugInfo);
            
        } catch (error) {
            this.showNotification('Debug failed: ' + error.message, 'error');
        } finally {
            this.hideLoadingOverlay();
        }
    }

    async testConnection() {
        debugLog("🧪 Testing server connection...");
        try {
            const response = await fetch('/test', {
                method: 'GET'
            });
            debugLog("📡 Test response:", response.status, response.statusText);
            
            if (response.ok) {
                const data = await response.json();
                debugLog("✅ Test data:", data);
                alert(`✅ Server connection works!\nStatus: ${data.status}\nMessage: ${data.message}`);
            } else {
                console.error("❌ Test failed:", response.status);
                alert(`❌ Server connection failed!\nStatus: ${response.status}`);
            }
        } catch (error) {
            console.error("💥 Connection error:", error);
            alert(`💥 Connection error: ${error.message}`);
        }
    }

    async testHoxton() {
        const url = this.bannerUrlInput.value.trim();
        if (!this.isValidUrl(url)) {
            this.showNotification('Please enter a valid URL or file path', 'error');
            return;
        }
        
        try {
            this.showLoadingOverlay();
            this.loadingText.textContent = 'Testing Hoxton element detection...';
            
            const response = await fetch('/test-hoxton', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url: url })
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            // Display test results
            const testInfo = `
🧪 HOXTON ELEMENT TEST RESULTS:

📄 Page Title: ${result.test_result.pageTitle}
🔍 Page contains 'hoxton': ${result.test_result.pageContainsHoxton ? '✅ YES' : '❌ NO'}
🏷️ Page contains 'reportingLabel': ${result.test_result.pageContainsReportingLabel ? '✅ YES' : '❌ NO'}

� Raw HTML Search Results:
📋 Hoxton tags in HTML: ${result.test_result.rawHTMLSearch.hoxtonMatches.length}
${result.test_result.rawHTMLSearch.hoxtonMatches.map((match, i) => `${i+1}. ${match}`).join('\n')}

�📊 ReportingLabel mentions: ${result.test_result.rawHTMLSearch.reportingLabelMatches.length}
${result.test_result.rawHTMLSearch.reportingLabelMatches.map((match, i) => `${i+1}. ${match}`).join('\n')}

📊 Hoxton Elements Found by DOM: ${result.test_result.hoxtonElements.length}
${result.test_result.hoxtonElements.map((el, i) => 
    `${i+1}. <${el.tagName.toLowerCase()}> 
    └─ Has data attribute: ${el.hasDataAttr ? '✅ YES' : '❌ NO'}
    └─ Data length: ${el.dataLength} characters
    └─ Data preview: ${el.dataPreview.substring(0, 200)}...
    ${el.parsedName !== 'no parsed name' ? `└─ Parsed name: ${el.parsedName}` : ''}
    ${el.parsedReportingLabel !== 'no parsed reportingLabel' ? `└─ Parsed reportingLabel: ${el.parsedReportingLabel}` : ''}`
).join('\n')}

🏗️ Body Structure (first 15 elements):
${result.test_result.bodyStructure.map((el, i) => 
    `${i}. <${el.tagName.toLowerCase()}> ${el.className ? '.' + el.className : ''} ${el.id ? '#' + el.id : ''} ${el.isHoxton ? '🎯 HOXTON!' : ''} data=${el.hasDataAttr ? '✅' : '❌'}(${el.dataLength})`
).join('\n')}

📋 Elements with Data (name/reporting): ${result.test_result.allElementsWithData.length}
${result.test_result.allElementsWithData.slice(0, 3).map((el, i) => 
    `${i+1}. <${el.tagName.toLowerCase()}> ${el.className ? '.' + el.className : ''} ${el.id ? '#' + el.id : ''}
    └─ Data (${el.dataLength} chars): ${el.dataPreview.substring(0, 150)}...`
).join('\n')}

${result.test_result.hoxtonElements.length === 0 ? 
    `❗ No DOM Hoxton elements found but HTML contains hoxton text!
    This suggests dynamic loading or custom element registration.` : 
    result.test_result.hoxtonElements.some(el => el.hasDataAttr) ?
        '✅ Found Hoxton elements with data attributes!' :
        '⚠️ Found Hoxton elements but no data attributes!'
}
            `;
            
            // Show in a modal-like notification
            this.showDetailedNotification('Hoxton Test Results', testInfo);
            
        } catch (error) {
            this.showNotification('Hoxton test failed: ' + error.message, 'error');
        } finally {
            this.hideLoadingOverlay();
        }
    }

    async checkHoxtonData() {
        const url = this.bannerUrlInput.value.trim();
        if (!this.isValidUrl(url)) {
            this.showNotification('Please enter a valid URL or file path', 'error');
            return;
        }
        
        try {
            this.showLoadingOverlay();
            this.loadingText.textContent = 'Checking Hoxton data extraction...';
            
            debugLog('🌐 Sending request to /check-hoxton-data...');
            
            const response = await fetch('/check-hoxton-data', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url: url })
            });
            
            debugLog('📦 Response received:', response.status);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            debugLog('📊 Response data:', result);
            
            // Show simple success message
            this.showNotification(`✅ Check completed! Check terminal for detailed logs.`, 'success');
            
        } catch (error) {
            console.error('❌ Error:', error);
            this.showNotification('Check failed: ' + error.message, 'error');
        } finally {
            this.hideLoadingOverlay();
        }
    }

    showDetailedNotification(title, content) {
        // Create a modal-like notification for debug info
        const modal = document.createElement('div');
        modal.className = 'debug-modal';
        modal.innerHTML = `
            <div class="debug-modal-content">
                <div class="debug-modal-header">
                    <h3>${this.escapeHtml(title)}</h3>
                    <button class="debug-modal-close" onclick="this.parentElement.parentElement.parentElement.remove()">×</button>
                </div>
                <div class="debug-modal-body">
                    <pre>${this.escapeHtml(content)}</pre>
                </div>
            </div>
        `;
        
        // Add modal styles if not already present
        if (!document.querySelector('#debug-modal-styles')) {
            const style = document.createElement('style');
            style.id = 'debug-modal-styles';
            style.textContent = `
                .debug-modal {
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background-color: rgba(0, 0, 0, 0.8);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 10001;
                    animation: fadeIn 0.3s ease;
                }
                .debug-modal-content {
                    background: white;
                    border-radius: 8px;
                    max-width: 80%;
                    max-height: 80%;
                    overflow: hidden;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                }
                .debug-modal-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 20px;
                    border-bottom: 1px solid #ddd;
                    background-color: #f8f9fa;
                }
                .debug-modal-header h3 {
                    margin: 0;
                    color: #333;
                }
                .debug-modal-close {
                    background: none;
                    border: none;
                    font-size: 24px;
                    cursor: pointer;
                    color: #666;
                    padding: 0;
                }
                .debug-modal-body {
                    padding: 20px;
                    overflow: auto;
                    max-height: 60vh;
                }
                .debug-modal-body pre {
                    margin: 0;
                    font-family: 'Courier New', monospace;
                    font-size: 14px;
                    line-height: 1.4;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                }
                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
            `;
            document.head.appendChild(style);
        }
        
        document.body.appendChild(modal);
        
        // Close on background click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }

    addSingleUrl() {
        const url = this.bannerUrlInput.value.trim();
        if (this.isValidUrl(url) && !this.urls.some(item => item.url === url)) {
            this.urls.push({
                id: Date.now(),
                url: url,
                status: 'pending',
                filename: this.generateFilename(url),
                imageData: null,
                error: null
            });
            this.bannerUrlInput.value = '';
            this.updateUI();
        } else if (!this.isValidUrl(url)) {
            this.showNotification('Please enter a valid URL', 'error');
        } else {
            this.showNotification('URL already exists in the list', 'warning');
        }
    }

    addBulkUrls() {
        const urls = this.bulkUrlsTextarea.value
            .split('\n')
            .map(url => url.trim())
            .filter(url => url && url.length > 0); // Remove empty lines
        
        let addedCount = 0;
        let skippedCount = 0;
        let invalidCount = 0;
        
        urls.forEach(url => {
            if (this.isValidUrl(url)) {
                if (!this.urls.some(item => item.url === url)) {
                    this.urls.push({
                        id: Date.now() + Math.random(),
                        url: url,
                        status: 'pending',
                        filename: this.generateFilename(url),
                        imageData: null,
                        error: null
                    });
                    addedCount++;
                } else {
                    skippedCount++;
                }
            } else {
                invalidCount++;
                console.warn('Invalid URL skipped:', url);
            }
        });
        
        if (addedCount > 0) {
            this.bulkUrlsTextarea.value = '';
            this.updateUI();
            
            let message = `Added ${addedCount} URLs`;
            if (skippedCount > 0) message += `, skipped ${skippedCount} duplicates`;
            if (invalidCount > 0) message += `, ignored ${invalidCount} invalid URLs`;
            
            this.showNotification(message, 'success');
        } else if (invalidCount > 0) {
            this.showNotification(`${invalidCount} invalid URLs found. Please check the format.`, 'warning');
        } else if (skippedCount > 0) {
            this.showNotification('All URLs already exist in the list', 'warning');
        } else {
            this.showNotification('No valid new URLs found', 'warning');
        }
    }

    removeUrl(id) {
        this.urls = this.urls.filter(item => item.id !== id);
        this.updateUI();
    }

    clearAllUrls() {
        if (confirm('Are you sure you want to clear all URLs?')) {
            this.urls = [];
            this.updateUI();
            this.showNotification('All URLs cleared', 'info');
        }
    }

    async generateAllImages() {
        if (this.isProcessing || this.urls.length === 0) return;
        
        debugLog('🚀 Starting generateAllImages with URLs:', this.urls.length);
        debugLog('📋 URL list:', this.urls.map(u => u.url));
        debugLog('🔒 Setting isProcessing to true');
        
        this.isProcessing = true;
        this.currentProcessIndex = 0;
        this.showLoadingOverlay();
        
        // Initialize progress display
        this.updateProgressParallel(0, this.urls.length);
        
        // Reset all statuses
        this.urls.forEach(item => {
            item.status = 'pending';
            item.imageData = null;
            item.error = null;
        });
        
        this.updateUI();
        
        try {
            // Parallel processing with configurable concurrency
            const maxConcurrency = this.getOptimalConcurrency();
            const processingBatches = this.createProcessingBatches(this.urls, maxConcurrency);
            
            debugLog('📦 Created batches:', processingBatches.length, 'batches');
            debugLog('📊 Batch details:', processingBatches.map(batch => ({ length: batch.length, urls: batch.map(u => u.url) })));
            
            this.showNotification(`Processing ${this.urls.length} banners with ${maxConcurrency} parallel workers...`, 'info');
            
            let completedCount = 0;
            debugLog('🔢 Initial completedCount:', completedCount);
            
            for (const batch of processingBatches) {
                // Process batch in parallel
                const batchPromises = batch.map(async (urlItem, batchIndex) => {
                    try {
                        urlItem.status = 'processing';
                        this.updateUrlItem(urlItem);
                        
                        const result = await this.captureScreenshot(urlItem);
                        urlItem.status = 'completed';
                        urlItem.imageData = result.imageData;
                        urlItem.format = result.format;
                        urlItem.dimensions = result.dimensions;
                        urlItem.detectedDimensions = result.detectedDimensions;
                        urlItem.filename = result.filename;
                        
                        // Calculate and store file size information
                        const imageSizeBytes = result.imageData ? atob(result.imageData).length : 0;
                        urlItem.fileSizeKB = Math.round(imageSizeBytes / 1024 * 10) / 10;
                        
                        // Store optimization info if available
                        if (result.detectedDimensions && result.detectedDimensions.optimization) {
                            urlItem.optimization = result.detectedDimensions.optimization;
                        }
                        
                        completedCount++;
                        debugLog('✅ Completed URL:', urlItem.url, '- Count now:', completedCount, 'of', this.urls.length);
                        this.updateProgressParallel(completedCount, this.urls.length);
                        
                    } catch (error) {
                        urlItem.status = 'error';
                        urlItem.error = error.message;
                        console.error('Screenshot capture failed for:', urlItem.url, error);
                        this.showNotification(`Error capturing ${this.truncateUrl(urlItem.url)}: ${error.message}`, 'warning');
                        completedCount++;
                        debugLog('❌ Error for URL:', urlItem.url, '- Count now:', completedCount, 'of', this.urls.length);
                        this.updateProgressParallel(completedCount, this.urls.length);
                    }
                    
                    this.updateUrlItem(urlItem);
                });
                
                // Wait for current batch to complete before starting next batch
                await Promise.all(batchPromises);
                
                // Small delay between batches to prevent overwhelming the server
                if (processingBatches.indexOf(batch) < processingBatches.length - 1) {
                    await this.sleep(200);
                }
            }
            
            this.hideLoadingOverlay();
            this.updatePreview();
            
            const successCount = this.urls.filter(item => item.status === 'completed').length;
            const errorCount = this.urls.filter(item => item.status === 'error').length;
            
            if (errorCount === 0) {
                this.showNotification(`All ${successCount} images generated successfully!`, 'success');
            } else {
                this.showNotification(`Generated ${successCount} images (${errorCount} failed)`, 'warning');
            }
            
        } catch (error) {
            this.hideLoadingOverlay();
            this.showNotification('Error during batch processing: ' + error.message, 'error');
        } finally {
            this.isProcessing = false;
            this.updateUI();
        }
    }

    toggleDimensionInputs() {
        const autoDetect = this.autoDetectSizeCheckbox.checked;
        this.imageWidthInput.disabled = autoDetect;
        this.imageHeightInput.disabled = autoDetect;
        
        if (autoDetect) {
            this.imageWidthInput.style.opacity = '0.5';
            this.imageHeightInput.style.opacity = '0.5';
        } else {
            this.imageWidthInput.style.opacity = '1';
            this.imageHeightInput.style.opacity = '1';
        }
    }

    async captureScreenshot(urlItem) {
        debugLog("🚀 captureScreenshot called with:", urlItem);
        
        const settings = this.getSettings();
        debugLog("⚙️ Settings:", settings);
        
        const requestData = {
            url: urlItem.url,
            format: settings.format,
            waitTime: settings.waitTime
            // Note: Removed filename - let backend generate it from extracted banner name
        };
        
        // Only include dimensions if auto-detect is disabled
        if (!settings.autoDetect) {
            requestData.width = settings.width;
            requestData.height = settings.height;
        }
        
        debugLog("📤 Sending request to /capture with data:", requestData);
        
        try {
            const response = await fetch('/capture', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            });
            
            debugLog("📥 Response received:", response.status, response.statusText);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                console.error("❌ Response error:", errorData);
                throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            debugLog("✅ Response data:", result);
            return result;
        } catch (error) {
            console.error("💥 Fetch error:", error);
            throw error;
        }
    }

    updateUI() {
        this.urlCountSpan.textContent = this.urls.length;
        this.generateAllBtn.disabled = this.urls.length === 0 || this.isProcessing;
        this.clearAllBtn.disabled = this.urls.length === 0 || this.isProcessing;
        
        // Dynamic button text based on number of URLs
        if (this.urls.length === 1) {
            this.generateAllBtn.textContent = 'Generate Image';
        } else if (this.urls.length > 1) {
            this.generateAllBtn.textContent = `Generate All ${this.urls.length} Images`;
        } else {
            this.generateAllBtn.textContent = 'Generate Images'; // Default for 0 URLs
        }
        
        this.updateUrlList();
        this.updatePreview();
    }

    updateUrlList() {
        if (this.urls.length === 0) {
            this.urlListDiv.innerHTML = '<div class="empty-state"><p>No URLs added yet</p></div>';
            return;
        }
        
        this.urlListDiv.innerHTML = this.urls.map(item => {
            const bannerInfo = item.bannerInfo ? 
                `<small class="banner-info">📋 ${item.bannerInfo.type}: ${item.bannerInfo.title} (${item.bannerInfo.width}×${item.bannerInfo.height}px)</small>` : '';
            
            return `
            <div class="url-item" data-id="${item.id}">
                <div class="url-content">
                    <div class="url-text">${this.escapeHtml(item.url)}</div>
                    ${bannerInfo}
                </div>
                <div class="url-status ${item.status}">${item.status}</div>
                <button class="danger" onclick="utility.removeUrl(${item.id})" ${this.isProcessing ? 'disabled' : ''}>
                    Remove
                </button>
            </div>
        `}).join('');
    }

    updateUrlItem(urlItem) {
        const urlElement = this.urlListDiv.querySelector(`[data-id="${urlItem.id}"]`);
        if (urlElement) {
            const statusElement = urlElement.querySelector('.url-status');
            statusElement.textContent = urlItem.status;
            statusElement.className = `url-status ${urlItem.status}`;
        }
    }

    updatePreview() {
        const completedItems = this.urls.filter(item => item.status === 'completed' && item.imageData);
        
        // Update banner count
        if (this.bannerCountSpan) {
            this.bannerCountSpan.textContent = `${completedItems.length} banner${completedItems.length !== 1 ? 's' : ''}`;
        }
        
        if (completedItems.length === 0) {
            this.previewContainer.innerHTML = '<div class="empty-state"><p>Generated images will appear here</p></div>';
            return;
        }
        
        if (this.currentView === 'actual') {
            this.renderActualSizeView(completedItems);
        } else {
            this.renderGridView(completedItems);
        }
    }
    
    setView(viewType) {
        this.currentView = viewType;
        
        // Update toggle buttons
        this.viewGridBtn.classList.toggle('active', viewType === 'grid');
        this.viewActualBtn.classList.toggle('active', viewType === 'actual');
        
        // Re-render preview
        this.updatePreview();
    }
    
    renderGridView(completedItems) {
        this.previewContainer.innerHTML = `
            <div class="preview-grid">
                ${completedItems.map(item => {
                    const format = item.format || 'png';
                    const mimeType = format === 'png' ? 'image/png' : 'image/jpeg';
                    const dimensions = item.dimensions || {};
                    
                    return `
                    <div class="preview-item">
                        <img src="data:${mimeType};base64,${item.imageData}" 
                             alt="Banner Screenshot" class="preview-image" />
                        <div class="preview-info">
                            <div class="preview-url">${this.escapeHtml(this.truncateUrl(item.url))}</div>
                            <div class="preview-details">
                                <small>
                                    📐 ${dimensions.width || 'auto'}×${dimensions.height || 'auto'}px 
                                    📄 ${format.toUpperCase()}
                                    ${item.fileSizeKB ? `📊 ${item.fileSizeKB}KB` : ''}
                                    ${item.optimization && item.fileSizeKB <= 50 ? '✅ Optimized' : ''}
                                    ${item.optimization && item.fileSizeKB > 50 ? '⚠️ Over 50KB' : ''}
                                </small>
                                ${item.optimization ? `
                                    <div class="optimization-info">
                                        <small style="color: #666;">
                                            Quality: ${item.optimization.final_quality}% 
                                            (${item.optimization.final_size_kb}KB of 50KB limit)
                                        </small>
                                    </div>
                                ` : ''}
                            </div>
                            <div class="preview-actions">
                                <a href="data:${mimeType};base64,${item.imageData}" 
                                   download="${this.cleanFilename(item.filename)}" class="download-btn">
                                    Download
                                </a>
                            </div>
                        </div>
                    </div>
                `}).join('')}
            </div>
            <div class="actions mt-20">
                <button class="primary" onclick="utility.downloadAll()">Download All Images</button>
                <button class="secondary" onclick="utility.downloadAsZip()">Download as ZIP</button>
            </div>
        `;
    }
    
    renderActualSizeView(completedItems) {
        this.previewContainer.innerHTML = `
            <div class="preview-gallery">
                <div class="gallery-container">
                    ${completedItems.map(item => {
                        const format = item.format || 'png';
                        const mimeType = format === 'png' ? 'image/png' : 'image/jpeg';
                        const dimensions = item.dimensions || {};
                        const actualWidth = dimensions.width || 300;
                        const actualHeight = dimensions.height || 250;
                        
                        return `
                        <div class="banner-canvas" style="width: ${actualWidth}px;">
                            <div class="canvas-header">
                                ${item.bannerInfo ? item.bannerInfo.title || 'Banner' : this.truncateUrl(item.url, 25)}
                            </div>
                            <img src="data:${mimeType};base64,${item.imageData}" 
                                 alt="Banner Screenshot" 
                                 class="canvas-image"
                                 style="width: ${actualWidth}px; height: ${actualHeight}px;" />
                            <div class="canvas-footer">
                                <div class="banner-metadata">
                                    <div class="metadata-item">
                                        <div class="metadata-label">Size</div>
                                        <div class="metadata-value">${actualWidth}×${actualHeight}</div>
                                    </div>
                                    <div class="metadata-item">
                                        <div class="metadata-label">Format</div>
                                        <div class="metadata-value">${format.toUpperCase()}</div>
                                    </div>
                                    <div class="metadata-item">
                                        <div class="metadata-label">File Size</div>
                                        <div class="metadata-value">${item.fileSizeKB || 'N/A'}KB</div>
                                    </div>
                                </div>
                                ${item.optimization ? `
                                    <div style="margin-top: 8px; font-size: 10px; color: ${item.fileSizeKB <= 50 ? '#28a745' : '#dc3545'};">
                                        ${item.fileSizeKB <= 50 ? '✅ Optimized' : '⚠️ Over 50KB'} 
                                        (Quality: ${item.optimization.final_quality}%)
                                    </div>
                                ` : ''}
                                <div style="margin-top: 8px;">
                                    <a href="data:${mimeType};base64,${item.imageData}" 
                                       download="${this.cleanFilename(item.filename)}" 
                                       style="font-size: 11px; color: var(--primary-color); text-decoration: none;">
                                        📥 Download
                                    </a>
                                </div>
                            </div>
                        </div>
                    `}).join('')}
                </div>
            </div>
            <div class="actions mt-20">
                <button class="primary" onclick="utility.downloadAll()">Download All Images</button>
                <button class="secondary" onclick="utility.downloadAsZip()">Download as ZIP</button>
            </div>
        `;
    }

    downloadAll() {
        const completedItems = this.urls.filter(item => item.status === 'completed' && item.imageData);
        
        if (completedItems.length === 0) {
            this.showNotification('No images to download', 'warning');
            return;
        }
        
        completedItems.forEach((item, index) => {
            setTimeout(() => {
                const format = item.format || 'png';
                const mimeType = format === 'png' ? 'image/png' : 'image/jpeg';
                
                // Clean filename for consistency
                const cleanFilename = this.cleanFilename(item.filename || `banner_${index + 1}.${format}`);
                
                const link = document.createElement('a');
                link.href = `data:${mimeType};base64,${item.imageData}`;
                link.download = cleanFilename;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }, index * 100); // Small delay between downloads
        });
        
        this.showNotification(`Downloading ${completedItems.length} images...`, 'success');
    }
    
    cleanFilename(filename) {
        if (!filename) return 'banner.png';
        
        // Remove zero-width spaces and other invisible Unicode characters
        let clean = filename.replace(/[\u200B\u200C\u200D\uFEFF]/g, ''); // Remove zero-width chars
        clean = clean.replace(/[^\x00-\x7F]/g, ''); // Remove non-ASCII chars
        
        // Clean special characters
        clean = clean.replace(/[<>:"/\\|?*]/g, '_');
        clean = clean.replace(/\s+/g, '_');
        clean = clean.replace(/_+/g, '_'); // Remove multiple underscores
        clean = clean.replace(/^[_.]|[_.]$/g, ''); // Remove leading/trailing underscores and dots
        
        // Ensure we have a valid filename
        if (!clean || clean === '.') {
            return 'banner.png';
        }
        
        // Ensure file extension exists
        if (!clean.includes('.')) {
            clean += '.png';
        }
        
        return clean;
    }

    async downloadAsZip() {
        const completedItems = this.urls.filter(item => item.status === 'completed' && item.imageData);
        
        if (completedItems.length === 0) {
            this.showNotification('No images to download', 'warning');
            return;
        }

        if (completedItems.length === 1) {
            // For single image, use regular download
            this.downloadAll();
            return;
        }

        try {
            this.showNotification('Preparing ZIP download...', 'info');
            
            // Prepare images for ZIP
            const images = completedItems.map(item => ({
                data: `data:${item.format === 'png' ? 'image/png' : 'image/jpeg'};base64,${item.imageData}`,
                filename: this.cleanFilename(item.filename || `banner_${Math.random().toString(36).substr(2, 9)}.${item.format || 'png'}`)
            }));

            // Send to backend for ZIP creation
            const response = await fetch('/download-zip', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ images })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            // Get the ZIP file blob
            const blob = await response.blob();
            
            // Create download link
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            
            // Get filename from response headers or use default
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = 'banners.zip';
            if (contentDisposition) {
                const matches = contentDisposition.match(/filename="(.+)"/);
                if (matches) {
                    filename = matches[1];
                }
            }
            
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            // Cleanup
            window.URL.revokeObjectURL(url);
            
            this.showNotification(`Downloaded ${completedItems.length} images as ZIP`, 'success');
            
        } catch (error) {
            console.error('ZIP download error:', error);
            this.showNotification('Failed to download ZIP file', 'error');
        }
    }

    updateProgress() {
        const progress = ((this.currentProcessIndex + 1) / this.urls.length) * 100;
        this.progressFill.style.width = `${progress}%`;
        this.progressText.textContent = `${this.currentProcessIndex + 1} / ${this.urls.length} completed`;
    }

    updateProgressParallel(completed, total) {
        debugLog(`📊 Progress update: ${completed}/${total}`);
        const progress = (completed / total) * 100;
        this.progressFill.style.width = `${progress}%`;
        this.progressText.textContent = `${completed} / ${total} completed`;
        this.loadingText.textContent = `Processing ${total - completed} remaining...`;
    }

    getOptimalConcurrency() {
        // Determine optimal number of parallel workers based on banner count and fast mode
        const bannerCount = this.urls.length;
        const fastMode = this.fastModeCheckbox && this.fastModeCheckbox.checked;
        
        let baseConcurrency;
        if (bannerCount <= 3) baseConcurrency = 2;      // Small batches: 2 parallel
        else if (bannerCount <= 8) baseConcurrency = 3;  // Medium batches: 3 parallel  
        else if (bannerCount <= 15) baseConcurrency = 4; // Large batches: 4 parallel
        else baseConcurrency = 5;                        // Very large batches: 5 parallel max
        
        // Increase concurrency in fast mode
        if (fastMode) {
            return Math.min(baseConcurrency + 2, 8); // Max 8 parallel in fast mode
        }
        
        return baseConcurrency;
    }

    createProcessingBatches(items, batchSize) {
        const batches = [];
        debugLog('🧮 Creating batches for', items.length, 'items with batchSize:', batchSize);
        for (let i = 0; i < items.length; i += batchSize) {
            const batch = items.slice(i, i + batchSize);
            debugLog('📦 Created batch', batches.length + 1, 'with', batch.length, 'items:', batch.map(item => item.url || item));
            batches.push(batch);
        }
        debugLog('🎯 Total batches created:', batches.length);
        return batches;
    }

    showLoadingOverlay() {
        this.loadingOverlay.classList.remove('hidden');
    }

    hideLoadingOverlay() {
        this.loadingOverlay.classList.add('hidden');
    }

    getSettings() {
        const fastMode = this.fastModeCheckbox && this.fastModeCheckbox.checked;
        let waitTime = parseFloat(this.waitTimeInput.value) || 2;
        
        // Optimize wait time in fast mode
        if (fastMode && waitTime > 3) {
            waitTime = Math.max(1, waitTime * 0.6); // Reduce wait time by 40% in fast mode
        }
        
        return {
            autoDetect: this.autoDetectSizeCheckbox.checked,
            width: parseInt(this.imageWidthInput.value) || 160,
            height: parseInt(this.imageHeightInput.value) || 600,
            format: this.imageFormatSelect.value || 'jpg',
            waitTime: waitTime,
            fastMode: fastMode
        };
    }

    saveSettings() {
        const settings = this.getSettings();
        localStorage.setItem('banner-utility-settings', JSON.stringify(settings));
    }

    loadSettings() {
        const saved = localStorage.getItem('banner-utility-settings');
        if (saved) {
            try {
                const settings = JSON.parse(saved);
                this.autoDetectSizeCheckbox.checked = settings.autoDetect !== false; // default to true
                this.imageWidthInput.value = settings.width || 160;
                this.imageHeightInput.value = settings.height || 600;
                this.imageFormatSelect.value = settings.format || 'png';
                this.waitTimeInput.value = settings.waitTime || 5;
                this.toggleDimensionInputs();
            } catch (e) {
                console.warn('Could not load saved settings');
            }
        }
    }

    generateFilename(url) {
        let name;
        
        if (url.startsWith('file:///') || (url.length > 3 && url[1] === ':' && url[2] === '\\')) {
            // For local files, use the folder name
            const path = url.startsWith('file:///') ? url.replace('file:///', '') : url;
            const parts = path.replace(/\\/g, '/').split('/');
            const folderName = parts[parts.length - 2] || 'local_file';
            name = folderName.replace(/[^a-zA-Z0-9]/g, '_');
        } else {
            try {
                const urlObj = new URL(url);
                
                // Special handling for Hoxton and similar sharing platforms
                if (urlObj.hostname.includes('hoxton') || urlObj.hostname.includes('share')) {
                    // Extract the share ID from the path
                    const pathParts = urlObj.pathname.split('/');
                    const shareId = pathParts[pathParts.length - 1] || 'shared_banner';
                    name = `hoxton_${shareId}`;
                } else {
                    // For regular URLs, use the domain
                    const domain = urlObj.hostname.replace(/[^a-zA-Z0-9]/g, '_');
                    name = domain;
                }
            } catch (e) {
                // Fallback for malformed URLs
                name = 'banner';
            }
        }
        
        const timestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '');
        const format = this.getSettings().format;
        return `banner_${name}_${timestamp}.${format}`;
    }

    isValidUrl(string) {
        try {
            // Check for local file paths
            if (string.startsWith('file:///') || (string.length > 3 && string[1] === ':' && string[2] === '\\')) {
                return true;
            }
            
            // Check for regular URLs
            const url = new URL(string);
            return url.protocol === 'http:' || url.protocol === 'https:';
        } catch (_) {
            return false;
        }
    }

    truncateUrl(url, maxLength = 50) {
        return url.length > maxLength ? url.substring(0, maxLength) + '...' : url;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    showNotification(message, type = 'info') {
        // Create a simple notification system
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <span>${this.escapeHtml(message)}</span>
            <button onclick="this.parentElement.remove()">×</button>
        `;
        
        // Add notification styles if not already present
        if (!document.querySelector('#notification-styles')) {
            const style = document.createElement('style');
            style.id = 'notification-styles';
            style.textContent = `
                .notification {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    padding: 12px 16px;
                    border-radius: 6px;
                    color: white;
                    font-weight: 600;
                    z-index: 10000;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    max-width: 400px;
                    animation: slideIn 0.3s ease;
                }
                .notification-success { background-color: #28a745; }
                .notification-error { background-color: #dc3545; }
                .notification-warning { background-color: #ffc107; color: #333; }
                .notification-info { background-color: #007acc; }
                .notification button {
                    background: none;
                    border: none;
                    color: inherit;
                    font-size: 18px;
                    cursor: pointer;
                    padding: 0;
                    margin: 0;
                }
                @keyframes slideIn {
                    from { transform: translateX(100%); }
                    to { transform: translateX(0); }
                }
            `;
            document.head.appendChild(style);
        }
        
        document.body.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
    }
}

// Initialize the utility when the page loads
let utility;
document.addEventListener('DOMContentLoaded', () => {
    utility = new BannerToStaticUtility();
});