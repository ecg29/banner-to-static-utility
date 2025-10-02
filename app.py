from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import base64
import os
import tempfile
import logging
import time
import re
from datetime import datetime
from urllib.parse import urlparse
import json
import zipfile
import io
from PIL import Image
import io as image_io

# Import Playwright for web scraping and screenshot capture
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Warning: Playwright not installed. Install with: pip install playwright")

# Setup file logging
def log_to_file(message):
    """Write log message to file with timestamp"""
    with open('debug.log', 'a', encoding='utf-8') as f:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"[{timestamp}] {message}\n")
        f.flush()

# Setup logging to both file and console
log_file = 'banner_utility.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.')
CORS(app)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def optimize_image_to_jpg(image_data, max_size_kb=50, min_quality=30, max_quality=95):
    """
    Convert image data to JPG format and optimize to stay under size limit
    
    Args:
        image_data: Raw image data (bytes)
        max_size_kb: Maximum file size in KB (default: 50)
        min_quality: Minimum JPG quality to try (default: 30)
        max_quality: Maximum JPG quality to start with (default: 95)
    
    Returns:
        tuple: (optimized_jpg_data, final_quality, final_size_kb)
    """
    try:
        # Convert image data to PIL Image
        image = Image.open(image_io.BytesIO(image_data))
        
        # Convert to RGB if necessary (for JPG compatibility)
        if image.mode in ('RGBA', 'LA', 'P'):
            # Create white background for transparency
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
            image = background
        
        # Try different quality levels to find optimal size
        max_size_bytes = max_size_kb * 1024
        best_quality = max_quality
        best_data = None
        
        for quality in range(max_quality, min_quality - 1, -5):
            output = image_io.BytesIO()
            image.save(output, format='JPEG', quality=quality, optimize=True)
            jpg_data = output.getvalue()
            
            if len(jpg_data) <= max_size_bytes:
                best_quality = quality
                best_data = jpg_data
                break
        
        # If still too large, try with minimum quality
        if best_data is None:
            output = image_io.BytesIO()
            image.save(output, format='JPEG', quality=min_quality, optimize=True)
            best_data = output.getvalue()
            best_quality = min_quality
        
        final_size_kb = len(best_data) / 1024
        
        log_to_file(f"Image optimized: Quality {best_quality}%, Size: {final_size_kb:.1f}KB")
        
        return best_data, best_quality, final_size_kb
        
    except Exception as e:
        log_to_file(f"Error optimizing image: {str(e)}")
        raise Exception(f"Failed to optimize image: {str(e)}")

class BrowserPool:
    """Manages a pool of browser instances for better performance"""
    def __init__(self, pool_size=3):
        self.pool_size = pool_size
        self.available_browsers = []
        self.in_use_browsers = []
        self.playwright_instances = []
        
    def get_browser_context(self):
        """Get or create a browser context from the pool"""
        if not PLAYWRIGHT_AVAILABLE:
            raise Exception("Playwright is not installed. Please install it with: pip install playwright")
        
        # Try to reuse an existing browser
        if self.available_browsers:
            browser_info = self.available_browsers.pop()
            self.in_use_browsers.append(browser_info)
            
            # Create new context on existing browser
            context = browser_info['browser'].new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
            )
            
            return browser_info['playwright'], browser_info['browser'], context
        
        # Create new browser if pool not full
        if len(self.in_use_browsers) < self.pool_size:
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-extensions',
                    '--disable-background-timer-throttling',
                    '--disable-renderer-backgrounding',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-features=TranslateUI',
                    '--disable-ipc-flooding-protection',
                    '--disable-web-security',  # Faster loading
                    '--disable-features=VizDisplayCompositor'  # Reduce overhead
                ]
            )
            
            browser_info = {'playwright': playwright, 'browser': browser}
            self.in_use_browsers.append(browser_info)
            
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
            )
            
            return playwright, browser, context
        
        # If pool is full, create temporary browser (fallback)
        return self._create_temporary_browser()
    
    def return_browser(self, playwright, browser):
        """Return a browser to the pool for reuse"""
        browser_info = {'playwright': playwright, 'browser': browser}
        
        if browser_info in self.in_use_browsers:
            self.in_use_browsers.remove(browser_info)
            self.available_browsers.append(browser_info)
    
    def _create_temporary_browser(self):
        """Create a temporary browser (not pooled)"""
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        )
        return playwright, browser, context
    
    def cleanup(self):
        """Clean up all browsers in the pool"""
        for browser_info in self.available_browsers + self.in_use_browsers:
            try:
                browser_info['browser'].close()
                browser_info['playwright'].stop()
            except:
                pass
        self.available_browsers.clear()
        self.in_use_browsers.clear()

# Global browser pool instance
browser_pool = BrowserPool(pool_size=4)

class ScreenshotService:
    def __init__(self):
        self.use_pool = True  # Enable browser pooling for better performance
        
    def get_browser_context(self):
        """Get a browser context (using pool if enabled)"""
        if self.use_pool:
            return browser_pool.get_browser_context()
        else:
            # Fallback to old method
            return self._create_fresh_browser_context()
    
    def _create_fresh_browser_context(self):
        """Create a fresh browser context (legacy method)"""
        if not PLAYWRIGHT_AVAILABLE:
            raise Exception("Playwright is not installed. Please install it with: pip install playwright")
            
        # Create a fresh playwright instance for each request
        playwright = sync_playwright().start()
        
        # Launch browser with optimized settings
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-extensions',
                '--disable-background-timer-throttling',
                '--disable-renderer-backgrounding',
                '--disable-backgrounding-occluded-windows',
                '--disable-features=TranslateUI',
                '--disable-ipc-flooding-protection'
            ]
        )
        
        # Create a new context with optimized settings
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        )
        
        return playwright, browser, context
        
    def capture_screenshot(self, url, width=None, height=None, format='png', wait_time=3):
        """Capture screenshot of the given URL"""
        playwright = None
        browser = None
        context = None
        page = None
        
        try:
            # Get fresh browser context for this request
            playwright, browser, context = self.get_browser_context()
            
            # Create a new page
            page = context.new_page()
            
            # Navigate to the URL first to get actual dimensions
            logger.info(f"Navigating to: {url}")
            page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Wait for page to fully load including dynamic content
            time.sleep(2)
            
            # First, let's do a simple check for Hoxton elements
            hoxton_debug = page.evaluate("""
                () => {
                    const debug = {};
                    
                    // Check for any hoxton elements
                    const hoxtonElements = document.querySelectorAll('hoxton');
                    debug.hoxtonElementsFound = hoxtonElements.length;
                    
                    // Check for elements with data attributes
                    const dataElements = document.querySelectorAll('[data]');
                    debug.dataElementsFound = dataElements.length;
                    
                    // Check page source for 'hoxton' keyword
                    debug.pageHasHoxtonText = document.documentElement.outerHTML.includes('hoxton');
                    debug.pageHasReportingLabel = document.documentElement.outerHTML.includes('reportingLabel');
                    
                    // Get a sample of elements with data attributes
                    debug.sampleDataElements = [];
                    for (let i = 0; i < Math.min(5, dataElements.length); i++) {
                        const el = dataElements[i];
                        debug.sampleDataElements.push({
                            tagName: el.tagName,
                            className: el.className,
                            id: el.id,
                            dataAttrLength: el.getAttribute('data')?.length || 0
                        });
                    }
                    
                    return debug;
                }
            """)
            
            logger.info(f"Hoxton debug info: {hoxton_debug}")
            
            # Also check the page source for hoxton content
            page_source_sample = page.evaluate("""
                () => {
                    const html = document.documentElement.outerHTML;
                    const hoxtonIndex = html.toLowerCase().indexOf('hoxton');
                    if (hoxtonIndex !== -1) {
                        return html.substring(Math.max(0, hoxtonIndex - 100), hoxtonIndex + 500);
                    }
                    return 'No hoxton text found in page source';
                }
            """)
            logger.info(f"Page source sample around 'hoxton': {page_source_sample}")
            
            # Get the actual dimensions of the banner content and metadata
            banner_info = page.evaluate(r"""
                () => {
                    // Try to find the banner container or body dimensions
                    const body = document.body;
                    const html = document.documentElement;
                    
                    // Function to extract banner name from various sources
                    function extractBannerName() {
                        const debug = { attempts: [], found: null };
                        
                        // Function to extract hoxton data from a document (main or iframe)
                        function extractFromDocument(doc, source) {
                            const hoxtonElements = doc.querySelectorAll('hoxton');
                            debug.attempts.push(`[${source}] Found ${hoxtonElements.length} hoxton elements`);
                            
                            for (const hoxtonEl of hoxtonElements) {
                                const dataAttr = hoxtonEl.getAttribute('data');
                                if (dataAttr) {
                                    debug.attempts.push(`[${source}] Found hoxton with data attr, length: ${dataAttr.length}`);
                                    try {
                                        // Handle double URL encoding
                                        let decoded = dataAttr;
                                        
                                        // First decode
                                        decoded = decodeURIComponent(decoded);
                                        debug.attempts.push(`[${source}] First decode: ${decoded.substring(0, 100)}...`);
                                        
                                        // Check if still encoded (contains %)
                                        if (decoded.includes('%')) {
                                            decoded = decodeURIComponent(decoded);
                                            debug.attempts.push(`[${source}] Second decode: ${decoded.substring(0, 100)}...`);
                                        }
                                        
                                        const jsonData = JSON.parse(decoded);
                                        debug.attempts.push(`[${source}] Parsed JSON, keys: ${Object.keys(jsonData).join(', ')}`);
                                        
                                        // Priority 1: Use reportingLabel if it exists and is NOT a placeholder
                                        if (jsonData.reportingLabel && 
                                            jsonData.reportingLabel.trim() !== '' && 
                                            !jsonData.reportingLabel.includes('{') && 
                                            !jsonData.reportingLabel.includes('}')) {
                                            debug.found = `[${source}] reportingLabel: ${jsonData.reportingLabel}`;
                                            return jsonData.reportingLabel;
                                        }
                                        
                                        // Priority 2: Fall back to name if reportingLabel is placeholder/blank
                                        if (jsonData.name) {
                                            debug.found = `[${source}] name (reportingLabel was placeholder/blank): ${jsonData.name}`;
                                            return jsonData.name;
                                        }
                                        
                                        // Priority 3: Use reportingLabel even if it's a placeholder (last resort)
                                        if (jsonData.reportingLabel) {
                                            debug.found = `[${source}] reportingLabel (using placeholder): ${jsonData.reportingLabel}`;
                                            return jsonData.reportingLabel;
                                        }
                                        
                                    } catch (e) {
                                        debug.attempts.push(`[${source}] JSON parse error: ${e.message}`);
                                    }
                                }
                            }
                            return null;
                        }
                        
                        // FIRST: Check main document for hoxton elements
                        const mainResult = extractFromDocument(document, 'main-doc');
                        if (mainResult) {
                            return { result: mainResult, debug };
                        }
                        
                        // SECOND: Try to find iframe URLs for later processing
                        const iframes = document.querySelectorAll('iframe');
                        debug.attempts.push(`Found ${iframes.length} iframes to check`);
                        
                        const iframeUrls = [];
                        for (let i = 0; i < iframes.length; i++) {
                            const iframe = iframes[i];
                            if (iframe.src) {
                                iframeUrls.push(iframe.src);
                                debug.attempts.push(`Iframe ${i} src: ${iframe.src}`);
                            }
                            
                            try {
                                const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
                                if (iframeDoc) {
                                    debug.attempts.push(`Successfully accessed iframe ${i}`);
                                    const iframeResult = extractFromDocument(iframeDoc, `iframe-${i}`);
                                    if (iframeResult) {
                                        return { result: iframeResult, debug };
                                    }
                                } else {
                                    debug.attempts.push(`Cannot access iframe ${i} (cross-origin or not loaded)`);
                                }
                            } catch (e) {
                                debug.attempts.push(`Error accessing iframe ${i}: ${e.message}`);
                            }
                        }
                        
                        // Store iframe URLs for server-side processing
                        if (iframeUrls.length > 0) {
                            debug.iframeUrls = iframeUrls;
                            debug.attempts.push(`Found ${iframeUrls.length} iframe URLs for server processing`);
                        }
                        
                        // THIRD: Try other data attributes in main document
                        const dataBannerName = document.querySelector('[data-banner-name]')?.getAttribute('data-banner-name');
                        if (dataBannerName) {
                            debug.found = `data-banner-name: ${dataBannerName}`;
                            return { result: dataBannerName, debug };
                        }
                        
                        const dataCreativeName = document.querySelector('[data-creative-name]')?.getAttribute('data-creative-name');
                        if (dataCreativeName) {
                            debug.found = `data-creative-name: ${dataCreativeName}`;
                            return { result: dataCreativeName, debug };
                        }
                        
                        const dataName = document.querySelector('[data-name]')?.getAttribute('data-name');
                        if (dataName) {
                            debug.found = `data-name: ${dataName}`;
                            return { result: dataName, debug };
                        }
                        
                        // FOURTH: Try page title (cleaned)
                        const title = document.title;
                        if (title && title !== 'Untitled' && title !== 'Banner' && title !== 'Preview' && title !== 'Share' && title.length > 3) {
                            debug.found = `page title: ${title}`;
                            return { result: title, debug };
                        }
                        
                        // Store iframe URLs for server-side processing even if no name found
                        if (iframeUrls.length > 0) {
                            debug.iframeUrls = iframeUrls;
                        }
                        
                        debug.found = 'nothing found';
                        return { result: '', debug };
                    }
                    
                    // Function to extract additional metadata
                    function extractMetadata() {
                        const meta = {};
                        
                        // Function to extract hoxton metadata from a document
                        function extractHoxtonFromDoc(doc, source) {
                            const hoxtonElement = doc.querySelector('hoxton[data]');
                            if (hoxtonElement) {
                                try {
                                    const encodedData = hoxtonElement.getAttribute('data');
                                    const decodedData = decodeURIComponent(encodedData);
                                    const jsonData = JSON.parse(decodedData);
                                    
                                    return {
                                        source: source,
                                        hoxtonData: {
                                            name: jsonData.name,
                                            reportingLabel: jsonData.reportingLabel,
                                            adType: jsonData.adType,
                                            adSize: jsonData.adSize,
                                            platform: jsonData.platform
                                        },
                                        dataWidth: jsonData.adSize ? parseInt(jsonData.adSize.width) : null,
                                        dataHeight: jsonData.adSize ? parseInt(jsonData.adSize.height) : null,
                                        format: jsonData.adType ? jsonData.adType.toLowerCase() : null,
                                        platform: jsonData.platform
                                    };
                                } catch (e) {
                                    console.log(`Error parsing Hoxton metadata from ${source}:`, e);
                                }
                            }
                            return null;
                        }
                        
                        // Extract rich Hoxton metadata - PRIORITY #1: Main document
                        let hoxtonMeta = extractHoxtonFromDoc(document, 'main-doc');
                        
                        // If not found in main document, check iframes
                        if (!hoxtonMeta) {
                            const iframes = document.querySelectorAll('iframe');
                            for (let i = 0; i < iframes.length; i++) {
                                try {
                                    const iframeDoc = iframes[i].contentDocument || iframes[i].contentWindow?.document;
                                    if (iframeDoc) {
                                        hoxtonMeta = extractHoxtonFromDoc(iframeDoc, `iframe-${i}`);
                                        if (hoxtonMeta) break;
                                    }
                                } catch (e) {
                                    // Ignore iframe access errors
                                }
                            }
                        }
                        
                        // Apply hoxton metadata if found
                        if (hoxtonMeta) {
                            Object.assign(meta, hoxtonMeta);
                        }
                        
                        // Try to get dimensions from standard data attributes (if not from Hoxton)
                        if (!meta.dataWidth || !meta.dataHeight) {
                            const dataWidth = document.querySelector('[data-width]')?.getAttribute('data-width');
                            const dataHeight = document.querySelector('[data-height]')?.getAttribute('data-height');
                            if (dataWidth && dataHeight) {
                                meta.dataWidth = parseInt(dataWidth);
                                meta.dataHeight = parseInt(dataHeight);
                            }
                        }
                        
                        // Try to get format info (if not from Hoxton)
                        if (!meta.format) {
                            const format = document.querySelector('[data-format]')?.getAttribute('data-format') ||
                                         document.querySelector('[data-type]')?.getAttribute('data-type');
                            if (format) {
                                meta.format = format;
                            }
                        }
                        
                        // Try to get campaign or client info
                        const campaign = document.querySelector('[data-campaign]')?.getAttribute('data-campaign');
                        const client = document.querySelector('[data-client]')?.getAttribute('data-client');
                        if (campaign) meta.campaign = campaign;
                        if (client) meta.client = client;
                        
                        return meta;
                    }
                    
                    // Look for common banner container selectors in order of priority
                    const containers = [
                        '#mainHolder', '#container', '#main', '#banner-container',
                        // Hoxton-specific selectors
                        '.creative-container', '.banner-frame', '.ad-frame', 
                        '[data-creative]', '[data-banner]', '.hoxton-banner',
                        // General selectors
                        'canvas', '.banner', '#banner', '.ad', '#ad', 
                        '.creative', '#creative', '.container', 'main',
                        'div[style*="width"]', 'div[style*="height"]',
                        '.banner-wrap', '.ad-wrap', '.creative-wrap',
                        // Frame/iframe content
                        'body > div:first-child', 'body > *:first-child'
                    ];
                    
                    let bannerWidth = 0;
                    let bannerHeight = 0;
                    let detectionMethod = 'fallback';
                    
                    // Extract banner name and metadata
                    const bannerNameResult = extractBannerName();
                    const bannerName = bannerNameResult.result || bannerNameResult || '';
                    const bannerNameDebug = bannerNameResult.debug || null;
                    const metadata = extractMetadata();
                    
                    // Use Hoxton dimensions if available and reliable
                    if (metadata.hoxtonData && metadata.dataWidth && metadata.dataHeight) {
                        bannerWidth = metadata.dataWidth;
                        bannerHeight = metadata.dataHeight;
                        detectionMethod = 'Hoxton adSize data (exact)';
                    }
                    
                    // Special handling for Hoxton or other banner sharing platforms
                    const isHoxtonOrSimilar = window.location.hostname.includes('hoxton') || 
                                            document.querySelector('.creative-container, .banner-frame, [data-creative]');
                    
                    // Try to find a container with explicit dimensions
                    for (const selector of containers) {
                        const elements = document.querySelectorAll(selector);
                        for (const element of elements) {
                            const rect = element.getBoundingClientRect();
                            const computedStyle = window.getComputedStyle(element);
                            
                            // Check if element has explicit width/height
                            if (rect.width > 0 && rect.height > 0) {
                                // For banner-specific containers, prioritize them highly
                                if (selector.includes('mainHolder') || selector.includes('container') || 
                                    selector.includes('banner') || selector.includes('creative') || 
                                    selector.includes('ad') || selector.includes('hoxton')) {
                                    
                                    // For sharing platforms, look for reasonably sized content
                                    if (isHoxtonOrSimilar && rect.width < 2000 && rect.height < 2000 && 
                                        rect.width >= 120 && rect.height >= 120) {
                                        bannerWidth = Math.ceil(rect.width);
                                        bannerHeight = Math.ceil(rect.height);
                                        detectionMethod = `${selector} (banner platform priority)`;
                                        break;
                                    } else if (!isHoxtonOrSimilar) {
                                        bannerWidth = Math.ceil(rect.width);
                                        bannerHeight = Math.ceil(rect.height);
                                        detectionMethod = `${selector} (banner container priority)`;
                                        break;
                                    }
                                }
                                
                                // Prefer elements with explicit CSS dimensions
                                const cssWidth = computedStyle.width;
                                const cssHeight = computedStyle.height;
                                
                                if ((cssWidth && cssWidth !== 'auto' && !cssWidth.includes('%')) || 
                                    (cssHeight && cssHeight !== 'auto' && !cssHeight.includes('%'))) {
                                    
                                    // Ensure reasonable banner dimensions
                                    if (rect.width < 2000 && rect.height < 2000 && 
                                        rect.width >= 120 && rect.height >= 120) {
                                        bannerWidth = Math.ceil(rect.width);
                                        bannerHeight = Math.ceil(rect.height);
                                        detectionMethod = `${selector} (CSS dimensions)`;
                                        break;
                                    }
                                }
                                
                                // If no CSS dimensions but has reasonable banner size, use it
                                if (rect.width < 2000 && rect.height < 2000 && 
                                    rect.width >= 120 && rect.height >= 120) {
                                    bannerWidth = Math.ceil(rect.width);
                                    bannerHeight = Math.ceil(rect.height);
                                    detectionMethod = `${selector} (computed size)`;
                                    break;
                                }
                            }
                        }
                        if (bannerWidth > 0 && bannerHeight > 0) break;
                    }
                    
                    // Special case: Look for the actual creative content on banner platforms
                    if ((bannerWidth === 0 || bannerHeight === 0) && isHoxtonOrSimilar) {
                        // Try to find iframe content or embedded content
                        const iframe = document.querySelector('iframe');
                        if (iframe) {
                            const iframeRect = iframe.getBoundingClientRect();
                            if (iframeRect.width > 0 && iframeRect.height > 0 && 
                                iframeRect.width < 2000 && iframeRect.height < 2000) {
                                bannerWidth = Math.ceil(iframeRect.width);
                                bannerHeight = Math.ceil(iframeRect.height);
                                detectionMethod = 'iframe content';
                            }
                        }
                        
                        // Look for content with explicit pixel dimensions in style
                        if (bannerWidth === 0 || bannerHeight === 0) {
                            const elementsWithStyle = document.querySelectorAll('[style*="px"]');
                            for (const el of elementsWithStyle) {
                                const style = el.getAttribute('style');
                                const widthMatch = style.match(/width:\\s*(\\d+)px/);
                                const heightMatch = style.match(/height:\\s*(\\d+)px/);
                                
                                if (widthMatch && heightMatch) {
                                    const w = parseInt(widthMatch[1]);
                                    const h = parseInt(heightMatch[1]);
                                    if (w >= 120 && h >= 120 && w < 2000 && h < 2000) {
                                        bannerWidth = w;
                                        bannerHeight = h;
                                        detectionMethod = 'inline style dimensions';
                                        break;
                                    }
                                }
                            }
                        }
                    }
                    
                    // Fallback to body/viewport dimensions if no container found
                    if (bannerWidth === 0 || bannerHeight === 0) {
                        const viewportWidth = window.innerWidth;
                        const viewportHeight = window.innerHeight;
                        const bodyRect = body.getBoundingClientRect();
                        const htmlRect = html.getBoundingClientRect();
                        
                        // Use the smallest reasonable dimensions
                        bannerWidth = Math.min(viewportWidth, bodyRect.width || viewportWidth, htmlRect.width || viewportWidth);
                        bannerHeight = Math.min(viewportHeight, bodyRect.height || viewportHeight, htmlRect.height || viewportHeight);
                        
                        // Clamp to reasonable banner sizes
                        bannerWidth = Math.max(120, Math.min(bannerWidth, 2000));
                        bannerHeight = Math.max(120, Math.min(bannerHeight, 2000));
                        
                        detectionMethod = 'viewport/body fallback';
                    }
                    
                    return {
                        width: bannerWidth,
                        height: bannerHeight,
                        detectionMethod: detectionMethod,
                        viewportWidth: window.innerWidth,
                        viewportHeight: window.innerHeight,
                        bodyWidth: body.getBoundingClientRect().width,
                        bodyHeight: body.getBoundingClientRect().height,
                        isHoxtonOrSimilar: isHoxtonOrSimilar,
                        hostname: window.location.hostname,
                        bannerName: bannerName,
                        bannerNameDebug: bannerNameDebug,
                        metadata: metadata
                    };
                }
            """)

            # Apply the SAME successful hoxton detection logic as the test endpoint
            logger.info("Applying enhanced hoxton detection...")
            
            enhanced_hoxton_result = page.evaluate("""
                () => {
                    // Function to extract hoxton data from an element
                    function extractHoxtonData(el, source) {
                        const dataAttr = el.getAttribute('data');
                        let decodedData = null;
                        let parsedData = null;
                        
                        if (dataAttr) {
                            try {
                                decodedData = decodeURIComponent(dataAttr);
                                parsedData = JSON.parse(decodedData);
                            } catch (e) {
                                // ignore parsing errors for now
                            }
                        }
                        
                        return {
                            source: source,
                            hasDataAttr: el.hasAttribute('data'),
                            dataLength: dataAttr?.length || 0,
                            parsedName: parsedData?.name || null,
                            parsedReportingLabel: parsedData?.reportingLabel || null,
                            rawParsedData: parsedData
                        };
                    }
                    
                    const result = {
                        foundHoxtonElements: [],
                        totalHoxtonFound: 0
                    };
                    
                    // Check main document for hoxton elements
                    const mainHoxtonEls = document.querySelectorAll('hoxton, HOXTON');
                    for (const el of mainHoxtonEls) {
                        result.foundHoxtonElements.push(extractHoxtonData(el, 'main-document'));
                    }
                    
                    // Check all iframes for hoxton elements  
                    const iframes = document.querySelectorAll('iframe');
                    for (let i = 0; i < iframes.length; i++) {
                        const iframe = iframes[i];
                        try {
                            const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
                            if (iframeDoc) {
                                const iframeHoxtonEls = iframeDoc.querySelectorAll('hoxton, HOXTON');
                                for (const el of iframeHoxtonEls) {
                                    result.foundHoxtonElements.push(extractHoxtonData(el, `iframe-${i}`));
                                }
                            }
                        } catch (e) {
                            // Cross-origin iframe, skip
                        }
                    }
                    
                    result.totalHoxtonFound = result.foundHoxtonElements.length;
                    return result;
                }
            """)
            
            logger.info(f"Enhanced hoxton detection found: {enhanced_hoxton_result['totalHoxtonFound']} hoxton elements")
            
            # Process enhanced hoxton results to update banner info
            if enhanced_hoxton_result['totalHoxtonFound'] > 0:
                for hoxton_el in enhanced_hoxton_result['foundHoxtonElements']:
                    logger.info(f"Found hoxton element from {hoxton_el['source']}")
                    logger.info(f"  - Has data: {hoxton_el['hasDataAttr']}")
                    logger.info(f"  - Data length: {hoxton_el['dataLength']}")
                    logger.info(f"  - Parsed name: {hoxton_el.get('parsedName')}")
                    logger.info(f"  - Parsed reportingLabel: {hoxton_el.get('parsedReportingLabel')}")
                    
                    # Update banner_info with hoxton data
                    if (hoxton_el.get('parsedReportingLabel') and 
                        hoxton_el['parsedReportingLabel'] != '{versionName}'):
                        banner_info['bannerName'] = hoxton_el['parsedReportingLabel']
                        banner_info['hoxtonData'] = hoxton_el.get('rawParsedData')
                        logger.info(f"✅ Updated banner name from reportingLabel: {banner_info['bannerName']}")
                        break
                    elif hoxton_el.get('parsedName'):
                        banner_info['bannerName'] = hoxton_el['parsedName']
                        banner_info['hoxtonData'] = hoxton_el.get('rawParsedData')
                        logger.info(f"✅ Updated banner name from name: {banner_info['bannerName']}")
                        break
            else:
                logger.warning("❌ Enhanced hoxton detection found no elements")

            # Check if we need to extract Hoxton data from iframes (if not found in main document)
            banner_name_debug = banner_info.get('bannerNameDebug', {})
            iframe_urls = banner_name_debug.get('iframeUrls', [])
            
            logger.info(f"Banner name from JavaScript: '{banner_info.get('bannerName', '')}'")
            logger.info(f"Banner name debug found: '{banner_name_debug.get('found', 'Not available')}'")
            logger.info(f"Iframe URLs detected: {iframe_urls}")
            
            # Skip iframe URL processing if we already found hoxton data
            if banner_info.get('bannerName') and banner_info.get('hoxtonData'):
                logger.info("✅ Already found hoxton data, skipping iframe URL processing")
            elif (not banner_info.get('bannerName') or banner_info.get('bannerName') == '') and iframe_urls:
                logger.info(f"No banner name found in main document, trying {len(iframe_urls)} iframe URLs")
                
                for i, iframe_url in enumerate(iframe_urls):
                    try:
                        # Convert relative URLs to absolute
                        from urllib.parse import urljoin
                        absolute_iframe_url = urljoin(url, iframe_url)
                        
                        logger.info(f"Trying to extract Hoxton data from iframe {i}: {absolute_iframe_url}")
                        
                        # Create new browser context for iframe
                        iframe_context = browser.new_context()
                        iframe_page = iframe_context.new_page()
                        
                        # Navigate to iframe URL
                        iframe_page.goto(absolute_iframe_url, wait_until='networkidle', timeout=30000)
                        time.sleep(3)  # Wait for content
                        
                        # Try to extract hoxton data from iframe
                        iframe_hoxton_data = iframe_page.evaluate("""
                            () => {
                                const hoxtonElement = document.querySelector('hoxton[data]');
                                if (hoxtonElement) {
                                    try {
                                        const encodedData = hoxtonElement.getAttribute('data');
                                        const decodedData = decodeURIComponent(encodedData);
                                        const jsonData = JSON.parse(decodedData);
                                        
                                        return {
                                            success: true,
                                            name: jsonData.name,
                                            reportingLabel: jsonData.reportingLabel,
                                            adType: jsonData.adType,
                                            adSize: jsonData.adSize,
                                            platform: jsonData.platform
                                        };
                                    } catch (e) {
                                        return { success: false, error: e.message };
                                    }
                                }
                                return { success: false, error: 'No hoxton element found' };
                            }
                        """)
                        
                        iframe_context.close()
                        
                        if iframe_hoxton_data.get('success'):
                            logger.info(f"Successfully extracted Hoxton data from iframe: {iframe_hoxton_data}")
                            
                            # Update banner_info with iframe data
                            if iframe_hoxton_data.get('reportingLabel') and iframe_hoxton_data['reportingLabel'] != '{versionName}':
                                banner_info['bannerName'] = iframe_hoxton_data['reportingLabel']
                                logger.info(f"Updated banner name from iframe reportingLabel: {banner_info['bannerName']}")
                            elif iframe_hoxton_data.get('name'):
                                banner_info['bannerName'] = iframe_hoxton_data['name']
                                logger.info(f"Updated banner name from iframe name: {banner_info['bannerName']}")
                            
                            # Add hoxton metadata to banner_info
                            banner_info['hoxtonData'] = iframe_hoxton_data
                            break  # Found data, stop trying other iframes
                        else:
                            logger.warning(f"Failed to extract from iframe {i}: {iframe_hoxton_data.get('error')}")
                            
                    except Exception as e:
                        logger.error(f"Error processing iframe {i} ({iframe_url}): {str(e)}")
                        continue
            else:
                logger.info(f"Skipping iframe processing - banner name: '{banner_info.get('bannerName')}', iframe URLs: {len(iframe_urls)}")

            # Use auto-detected dimensions if not specified
            if width is None:
                width = banner_info['width']
            if height is None:
                height = banner_info['height']
                
            logger.info(f"Detection method: {banner_info['detectionMethod']}")
            logger.info(f"Detected dimensions: {banner_info['width']}x{banner_info['height']}")
            logger.info(f"Viewport: {banner_info['viewportWidth']}x{banner_info['viewportHeight']}")
            logger.info(f"Body: {banner_info['bodyWidth']}x{banner_info['bodyHeight']}")
            logger.info(f"Banner name: {banner_info.get('bannerName', 'Not detected')}")
            
            # Log banner name debug info
            banner_name_debug = banner_info.get('bannerNameDebug')
            if banner_name_debug:
                logger.info(f"Banner name debug - Found: {banner_name_debug.get('found', 'nothing')}")
                for attempt in banner_name_debug.get('attempts', []):
                    logger.info(f"  - {attempt}")
            
            logger.info(f"Final dimensions to use: {width}x{height}")
            
            # Set viewport to be larger than the banner to avoid scrollbars
            viewport_width = max(width + 100, 800)
            viewport_height = max(height + 100, 600)
            page.set_viewport_size({'width': viewport_width, 'height': viewport_height})
            
            # Wait for animations and dynamic content to complete
            # Wait for initial load
            time.sleep(2)
            
            # Wait for animations to complete by checking if elements are still changing
            logger.info("Waiting for animations to complete...")
            for i in range(wait_time * 2):  # Check every 0.5 seconds
                try:
                    # Check if there are any running animations or transitions
                    has_animations = page.evaluate("""
                        () => {
                            // Check for CSS animations
                            const elements = document.querySelectorAll('*');
                            for (let el of elements) {
                                const style = window.getComputedStyle(el);
                                const animation = style.getPropertyValue('animation-name');
                                const transition = style.getPropertyValue('transition-property');
                                
                                if (animation !== 'none' || transition !== 'none') {
                                    return true;
                                }
                            }
                            
                            // Check for canvas animations (common in banner ads)
                            const canvases = document.querySelectorAll('canvas');
                            return canvases.length > 0;
                        }
                    """)
                    
                    time.sleep(0.5)
                    
                    # If no animations detected in the last check, break early
                    if not has_animations and i > 4:  # At least 2 seconds
                        logger.info("No animations detected, proceeding with screenshot")
                        break
                        
                except:
                    pass
            
            # Final wait to ensure everything is settled
            time.sleep(1)
            
            # Take screenshot with proper format
            logger.info(f"Taking screenshot with dimensions: {width}x{height}, format: {format}")
            
            # Ensure we're using the correct format
            screenshot_format = 'png' if format.lower() in ['png'] else 'jpeg'
            
            screenshot_bytes = page.screenshot(
                type='png',  # Always capture as PNG first for quality
                full_page=False,  # Only capture viewport
                clip={'x': 0, 'y': 0, 'width': width, 'height': height}
            )
            
            # Always convert to JPG with size optimization for compliance
            try:
                optimized_jpg_data, final_quality, final_size_kb = optimize_image_to_jpg(screenshot_bytes)
                screenshot_base64 = base64.b64encode(optimized_jpg_data).decode('utf-8')
                actual_format = 'jpeg'
                
                logger.info(f"📷 Image optimized: {final_size_kb:.1f}KB at {final_quality}% quality")
                
                # Add optimization info to banner_info for reporting
                banner_info['optimization'] = {
                    'original_format': 'png',
                    'final_format': 'jpeg',
                    'final_quality': final_quality,
                    'final_size_kb': round(final_size_kb, 1),
                    'size_limit_kb': 50
                }
                
            except Exception as e:
                logger.error(f"Failed to optimize image: {str(e)}")
                # Fallback to original PNG if optimization fails
                screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                actual_format = 'png'
            
            # Convert to base64
            # screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            
            # Debug: Log final banner_info before returning
            logger.info(f"🔍 Final banner_info before return:")
            logger.info(f"  - bannerName: '{banner_info.get('bannerName', 'NOT SET')}'")
            logger.info(f"  - hoxtonData present: {bool(banner_info.get('hoxtonData'))}")
            logger.info(f"  - width: {banner_info.get('width')}")
            logger.info(f"  - height: {banner_info.get('height')}")
            
            return {
                'success': True,
                'imageData': screenshot_base64,
                'format': actual_format,
                'dimensions': {'width': width, 'height': height},
                'detectedDimensions': banner_info,
                'url': url
            }
            
        except Exception as e:
            logger.error(f"Screenshot capture failed for {url}: {str(e)}")
            raise Exception(f"Failed to capture screenshot: {str(e)}")
            
        finally:
            # Clean up resources for this request
            if page:
                page.close()
            if context:
                context.close()
            if browser:
                browser.close()
            if playwright:
                playwright.stop()
    
    def cleanup(self):
        """Clean up browser resources - no longer needed as we use fresh contexts"""
        pass

# Global screenshot service instance
screenshot_service = ScreenshotService()

async def extract_hoxton_from_iframe_url(iframe_url, playwright_instance, browser_instance):
    """Extract Hoxton metadata directly from iframe URL"""
    try:
        logger.info(f"Attempting to extract Hoxton data from iframe: {iframe_url}")
        
        # Create a new page for the iframe
        context = await browser_instance.new_context()
        page = await context.new_page()
        
        # Navigate directly to the iframe URL
        await page.goto(iframe_url, wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(3000)  # Wait for content to load
        
        # Extract hoxton data from the iframe page
        hoxton_data = await page.evaluate("""
            () => {
                // Look for hoxton element with data
                const hoxtonElement = document.querySelector('hoxton[data]');
                if (hoxtonElement) {
                    try {
                        const encodedData = hoxtonElement.getAttribute('data');
                        const decodedData = decodeURIComponent(encodedData);
                        const jsonData = JSON.parse(decodedData);
                        
                        return {
                            success: true,
                            name: jsonData.name,
                            reportingLabel: jsonData.reportingLabel,
                            adType: jsonData.adType,
                            adSize: jsonData.adSize,
                            platform: jsonData.platform,
                            rawData: decodedData
                        };
                    } catch (e) {
                        return { success: false, error: e.message };
                    }
                }
                return { success: false, error: 'No hoxton element found' };
            }
        """)
        
        await context.close()
        
        if hoxton_data.get('success'):
            logger.info(f"Successfully extracted Hoxton data: {hoxton_data}")
            return hoxton_data
        else:
            logger.warning(f"Failed to extract Hoxton data: {hoxton_data.get('error')}")
            return None
            
    except Exception as e:
        logger.error(f"Error extracting from iframe {iframe_url}: {str(e)}")
        return None

def generate_banner_filename(banner_info, url, format='png', index=None):
    """Generate a descriptive filename based on banner metadata"""
    import re
    
    # Debug logging
    logger.info(f"🎯 FILENAME GENERATION DEBUG:")
    logger.info(f"  - banner_info keys: {list(banner_info.keys()) if banner_info else 'None'}")
    logger.info(f"  - bannerName: '{banner_info.get('bannerName', 'NOT SET')}'")
    logger.info(f"  - hoxtonData: {banner_info.get('hoxtonData', 'NOT SET')}")
    
    # Extract Hoxton metadata if available
    hoxton_data = banner_info.get('hoxtonData', {})
    logger.info(f"  - hoxton_data extracted: {hoxton_data}")
    
    # Priority order for naming:
    # 1. Hoxton reportingLabel (if not a placeholder)
    # 2. Hoxton name 
    # 3. Regular bannerName
    # 4. Fallback to generic name
    
    banner_name = ''
    name_source = ''
    
    # Check Hoxton reportingLabel first
    reporting_label = hoxton_data.get('reportingLabel', '')
    if reporting_label and reporting_label != '{versionName}' and reporting_label.strip():
        banner_name = reporting_label.strip()
        name_source = 'hoxton_reportingLabel'
        logger.info(f"Using Hoxton reportingLabel: '{banner_name}'")
    
    # Check Hoxton name if no reportingLabel
    elif hoxton_data.get('name', '').strip():
        banner_name = hoxton_data.get('name', '').strip()
        name_source = 'hoxton_name'
        logger.info(f"Using Hoxton name: '{banner_name}'")
    
    # Fallback to regular banner name
    elif banner_info.get('bannerName', '').strip():
        banner_name = banner_info.get('bannerName', '').strip()
        name_source = 'banner_name'
        logger.info(f"Using extracted banner name: '{banner_name}'")
    
    # Clean banner name for filename use
    if banner_name:
        # Remove file extensions if present
        banner_name = re.sub(r'\.(png|jpg|jpeg|gif|svg|webp)$', '', banner_name, flags=re.IGNORECASE)
        
        # Remove zero-width spaces and other invisible Unicode characters
        clean_name = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', banner_name)  # Remove zero-width chars
        clean_name = re.sub(r'[^\x00-\x7F]', '', clean_name)  # Remove non-ASCII chars
        
        # Clean special characters and normalize
        clean_name = re.sub(r'[<>:"/\\|?*]', '_', clean_name)
        clean_name = re.sub(r'\s+', '_', clean_name)
        clean_name = re.sub(r'_+', '_', clean_name)  # Remove multiple underscores
        clean_name = clean_name.strip('_')  # Remove leading/trailing underscores
        clean_name = clean_name[:60]  # Limit length but allow longer for descriptive names
        logger.info(f"Cleaned banner name: '{clean_name}' (from {name_source})")
    else:
        clean_name = ''
        logger.info("No banner name found, using fallback naming")
    
    # Get additional metadata for filename enrichment
    width = banner_info.get('width', 0)
    height = banner_info.get('height', 0)
    
    # Extract platform/format info from Hoxton if available
    platform = hoxton_data.get('platform', '')
    ad_type = hoxton_data.get('adType', '')
    
    # Get domain/platform info
    hostname = banner_info.get('hostname', '')
    if hostname:
        domain = hostname.replace('www.', '').split('.')[0]
    else:
        domain = 'banner'
    
    # Build filename parts intelligently
    parts = []
    
    # Always start with the main name if we have one
    if clean_name:
        parts.append(clean_name)
    
    # Add dimensions if reasonable and not already in name
    if width > 0 and height > 0:
        dimension_str = f'{width}x{height}'
        if not clean_name or dimension_str not in clean_name:
            parts.append(dimension_str)
    
    # Add platform info if meaningful and not redundant
    if platform and platform not in ['web', 'html5'] and (not clean_name or platform.lower() not in clean_name.lower()):
        parts.append(platform.lower())
    
    # Add ad type if meaningful and not redundant
    if ad_type and ad_type not in ['banner', 'display'] and (not clean_name or ad_type.lower() not in clean_name.lower()):
        parts.append(ad_type.lower())
    
    # Add domain if it's helpful and not already included
    if domain and domain != 'banner' and domain != 'hoxton' and (not clean_name or domain.lower() not in clean_name.lower()):
        parts.append(domain)
    
    # Add index if provided (for batch processing)
    if index is not None:
        parts.append(f'{index+1:02d}')
    
    # Don't add timestamp - use clean names only
    # This gives us readable filenames like: 123_Payworld_Display_Think_IAB_market_300x600.png
    
    # Combine parts
    if parts:
        filename_base = '_'.join(parts)
    else:
        # Fallback only if we have no name at all
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename_base = f'banner_{timestamp}'
    
    # Final cleanup
    filename_base = re.sub(r'_+', '_', filename_base)  # Remove multiple underscores
    filename_base = filename_base.strip('_')  # Remove leading/trailing underscores
    
    # Final Unicode cleanup to ensure no invisible characters remain
    filename_base = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', filename_base)  # Remove zero-width chars
    filename_base = re.sub(r'[^\w\-_.]', '', filename_base)  # Keep only safe filename characters
    filename_base = filename_base.strip('_.')  # Remove any trailing underscores or dots
    
    result_filename = f'{filename_base}.{format}'
    logger.info(f"Generated filename: '{result_filename}' (name_source: {name_source})")
    
    return result_filename

def clean_filename_for_zip(filename):
    """Clean filename for ZIP archive consistency"""
    if not filename:
        return 'banner.png'
    
    # Remove zero-width spaces and other invisible Unicode characters
    clean_name = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', filename)  # Remove zero-width chars
    clean_name = re.sub(r'[^\x00-\x7F]', '', clean_name)  # Remove non-ASCII chars
    
    # Clean special characters that might cause issues in ZIP files
    clean_name = re.sub(r'[<>:"/\\|?*]', '_', clean_name)
    clean_name = re.sub(r'\s+', '_', clean_name)
    clean_name = re.sub(r'_+', '_', clean_name)  # Remove multiple underscores
    clean_name = clean_name.strip('_.')  # Remove leading/trailing underscores and dots
    
    # Ensure we have a valid filename
    if not clean_name or clean_name == '.':
        return 'banner.png'
    
    # Ensure file extension exists
    if '.' not in clean_name:
        clean_name += '.png'
    
    return clean_name

@app.route('/')
def index():
    """Serve the main HTML file"""
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    """Serve static files (CSS, JS, etc.)"""
    return send_from_directory('.', filename)

@app.route('/test-hoxton', methods=['POST'])
def test_hoxton():
    """Test endpoint to debug Hoxton element detection"""
    try:
        data = request.get_json()
        url = data.get('url', '')
        
        if not url:
            return jsonify({'error': 'URL required'}), 400
            
        logger.info(f"Testing Hoxton detection for: {url}")
        
        # Get fresh browser context
        playwright, browser, context = screenshot_service.get_browser_context()
        page = context.new_page()
        
        try:
            # Navigate to URL
            page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Wait much longer for custom elements and dynamic content
            time.sleep(10)
            
            # Try to wait for hoxton element specifically
            try:
                page.wait_for_selector('hoxton', timeout=10000)
                logger.info("Hoxton element found after waiting!")
            except:
                logger.info("Hoxton element not found even after waiting")
            
            # Use the SAME logic as the working test endpoint
            test_result = page.evaluate("""
                () => {
                    // Function to extract hoxton data from an element
                    function extractHoxtonData(el, source) {
                        const dataAttr = el.getAttribute('data');
                        let decodedData = null;
                        let parsedData = null;
                        
                        if (dataAttr) {
                            try {
                                decodedData = decodeURIComponent(dataAttr);
                                parsedData = JSON.parse(decodedData);
                            } catch (e) {
                                // ignore parsing errors for now
                            }
                        }
                        
                        return {
                            source: source,
                            tagName: el.tagName,
                            hasDataAttr: el.hasAttribute('data'),
                            dataLength: dataAttr?.length || 0,
                            dataPreview: dataAttr?.substring(0, 300) || 'no data',
                            decodedPreview: decodedData?.substring(0, 300) || 'no decoded data',
                            parsedName: parsedData?.name || 'no parsed name',
                            parsedReportingLabel: parsedData?.reportingLabel || 'no parsed reportingLabel',
                            rawParsedData: parsedData
                        };
                    }
                    
                    // Check main document for hoxton elements
                    const mainHoxtonEls = document.querySelectorAll('hoxton, HOXTON');
                    const foundHoxtonElements = [];
                    
                    for (const el of mainHoxtonEls) {
                        foundHoxtonElements.push(extractHoxtonData(el, 'main-document'));
                    }
                    
                    // Check all iframes for hoxton elements  
                    const iframes = document.querySelectorAll('iframe');
                    const iframeInfo = [];
                    
                    for (let i = 0; i < iframes.length; i++) {
                        const iframe = iframes[i];
                        const info = {
                            index: i,
                            src: iframe.src,
                            accessible: false,
                            hoxtonElements: []
                        };
                        
                        try {
                            const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
                            if (iframeDoc) {
                                info.accessible = true;
                                const iframeHoxtonEls = iframeDoc.querySelectorAll('hoxton, HOXTON');
                                
                                for (const el of iframeHoxtonEls) {
                                    const hoxtonData = extractHoxtonData(el, `iframe-${i}`);
                                    foundHoxtonElements.push(hoxtonData);
                                    info.hoxtonElements.push(hoxtonData);
                                }
                            }
                        } catch (e) {
                            info.error = e.message;
                        }
                        
                        iframeInfo.push(info);
                    }
                    
                    return {
                        foundHoxtonElements: foundHoxtonElements,
                        iframeInfo: iframeInfo,
                        totalHoxtonFound: foundHoxtonElements.length
                    };
                }
            """)
            
            # More comprehensive test for Hoxton elements including iframes
            test_result = page.evaluate("""
                () => {
                    const result = {
                        pageTitle: document.title,
                        hoxtonElements: [],
                        pageContainsHoxton: document.documentElement.outerHTML.includes('hoxton'),
                        pageContainsReportingLabel: document.documentElement.outerHTML.includes('reportingLabel'),
                        allElementsWithData: [],
                        bodyStructure: [],
                        customElements: [],
                        iframeAnalysis: [],
                        rawHTMLSearch: {
                            hoxtonMatches: [],
                            reportingLabelMatches: []
                        }
                    };
                    
                    // Search for hoxton in raw HTML
                    const fullHTML = document.documentElement.outerHTML;
                    const hoxtonRegex = /<hoxton[^>]*>/gi;
                    const hoxtonMatches = fullHTML.match(hoxtonRegex) || [];
                    result.rawHTMLSearch.hoxtonMatches = hoxtonMatches.slice(0, 5);
                    
                    // Search for reportingLabel in raw HTML
                    const reportingRegex = /reportingLabel[^}]{0,100}/gi;
                    const reportingMatches = fullHTML.match(reportingRegex) || [];
                    result.rawHTMLSearch.reportingLabelMatches = reportingMatches.slice(0, 5);
                    
                    // Function to extract hoxton data from an element
                    function extractHoxtonData(el, source) {
                        const dataAttr = el.getAttribute('data');
                        let decodedData = null;
                        let parsedData = null;
                        
                        if (dataAttr) {
                            try {
                                decodedData = decodeURIComponent(dataAttr);
                                parsedData = JSON.parse(decodedData);
                            } catch (e) {
                                // ignore parsing errors for now
                            }
                        }
                        
                        return {
                            source: source,
                            tagName: el.tagName,
                            hasDataAttr: el.hasAttribute('data'),
                            dataLength: dataAttr?.length || 0,
                            dataPreview: dataAttr?.substring(0, 300) || 'no data',
                            decodedPreview: decodedData?.substring(0, 300) || 'no decoded data',
                            parsedName: parsedData?.name || 'no parsed name',
                            parsedReportingLabel: parsedData?.reportingLabel || 'no parsed reportingLabel',
                            outerHTMLPreview: el.outerHTML.substring(0, 500)
                        };
                    }
                    
                    // Check main document for hoxton elements
                    const mainHoxtonEls = document.querySelectorAll('hoxton, HOXTON');
                    for (const el of mainHoxtonEls) {
                        result.hoxtonElements.push(extractHoxtonData(el, 'main-document'));
                    }
                    
                    // Check all iframes for hoxton elements
                    const iframes = document.querySelectorAll('iframe');
                    for (let i = 0; i < iframes.length; i++) {
                        const iframe = iframes[i];
                        const iframeInfo = {
                            index: i,
                            src: iframe.src,
                            id: iframe.id,
                            className: iframe.className,
                            accessible: false,
                            hoxtonElementsFound: 0,
                            hoxtonElements: [],
                            bodyStructure: []
                        };
                        
                        try {
                            // Try to access iframe content
                            const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
                            if (iframeDoc) {
                                iframeInfo.accessible = true;
                                
                                // Look for hoxton elements in iframe
                                const iframeHoxtonEls = iframeDoc.querySelectorAll('hoxton, HOXTON');
                                iframeInfo.hoxtonElementsFound = iframeHoxtonEls.length;
                                
                                for (const el of iframeHoxtonEls) {
                                    const hoxtonData = extractHoxtonData(el, `iframe-${i}`);
                                    result.hoxtonElements.push(hoxtonData);
                                    iframeInfo.hoxtonElements.push(hoxtonData);
                                }
                                
                                // Get iframe body structure
                                if (iframeDoc.body) {
                                    const iframeBodyChildren = Array.from(iframeDoc.body.children);
                                    for (let j = 0; j < Math.min(10, iframeBodyChildren.length); j++) {
                                        const el = iframeBodyChildren[j];
                                        iframeInfo.bodyStructure.push({
                                            index: j,
                                            tagName: el.tagName,
                                            className: el.className,
                                            id: el.id,
                                            hasDataAttr: el.hasAttribute('data'),
                                            dataLength: el.getAttribute('data')?.length || 0,
                                            isHoxton: el.tagName && el.tagName.toLowerCase() === 'hoxton'
                                        });
                                    }
                                }
                            }
                        } catch (e) {
                            iframeInfo.error = e.message;
                        }
                        
                        result.iframeAnalysis.push(iframeInfo);
                    }
                    
                    // Get main document body structure
                    const bodyChildren = Array.from(document.body.children);
                    for (let i = 0; i < Math.min(15, bodyChildren.length); i++) {
                        const el = bodyChildren[i];
                        result.bodyStructure.push({
                            index: i,
                            tagName: el.tagName,
                            className: el.className,
                            id: el.id,
                            hasDataAttr: el.hasAttribute('data'),
                            dataLength: el.getAttribute('data')?.length || 0,
                            outerHTMLPreview: el.outerHTML.substring(0, 300),
                            isHoxton: el.tagName && el.tagName.toLowerCase() === 'hoxton',
                            isIframe: el.tagName && el.tagName.toLowerCase() === 'iframe'
                        });
                    }
                    
                    return result;
                }
            """)
            
            # Process the hoxton detection results
            logger.info(f"Hoxton detection results: {test_result}")
            
            hoxton_banner_name = None
            hoxton_metadata = None
            
            if test_result['totalHoxtonFound'] > 0:
                logger.info(f"Found {test_result['totalHoxtonFound']} hoxton elements!")
                
                # Use the first hoxton element with good data
                for hoxton_el in test_result['foundHoxtonElements']:
                    logger.info(f"Processing hoxton element from {hoxton_el['source']}")
                    logger.info(f"  - Parsed name: {hoxton_el.get('parsedName')}")
                    logger.info(f"  - Parsed reportingLabel: {hoxton_el.get('parsedReportingLabel')}")
                    
                    # Try reportingLabel first (but skip {versionName})
                    if (hoxton_el.get('parsedReportingLabel') and 
                        hoxton_el['parsedReportingLabel'] != 'no parsed reportingLabel' and
                        hoxton_el['parsedReportingLabel'] != '{versionName}'):
                        hoxton_banner_name = hoxton_el['parsedReportingLabel']
                        hoxton_metadata = hoxton_el.get('rawParsedData')
                        logger.info(f"Using reportingLabel: {hoxton_banner_name}")
                        break
                    
                    # Try name field
                    elif (hoxton_el.get('parsedName') and 
                          hoxton_el['parsedName'] != 'no parsed name'):
                        hoxton_banner_name = hoxton_el['parsedName']
                        hoxton_metadata = hoxton_el.get('rawParsedData')
                        logger.info(f"Using name: {hoxton_banner_name}")
                        break
            else:
                logger.warning("No hoxton elements found in enhanced detection!")
                
            return jsonify({
                'success': True,
                'url': url,
                'test_result': test_result,
                'extracted_banner_name': hoxton_banner_name,
                'hoxton_metadata': hoxton_metadata
            })
            
        finally:
            try:
                context.close()
                browser.close()
                playwright.stop()
            except:
                pass
                
    except Exception as e:
        logger.error(f"Error in test-hoxton: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.before_request
def log_request_info():
    log_to_file(f"🌐 HTTP Request: {request.method} {request.path}")
    print(f"🌐 HTTP Request: {request.method} {request.path}", flush=True)
    if request.method == 'POST':
        log_to_file(f"📦 POST Data: {request.get_data()}")
        print(f"📦 POST Data: {request.get_data()}", flush=True)

@app.route('/test', methods=['GET'])
def test_endpoint():
    """Simple test endpoint"""
    print("🧪 TEST ENDPOINT CALLED! (using print)")
    logger.info("🧪 TEST ENDPOINT CALLED! (using logger)")
    return jsonify({"status": "success", "message": "Server is working!"})

@app.route('/check-hoxton-data', methods=['POST'])
def check_hoxton_data():
    """Endpoint to check Hoxton data extraction with comprehensive logging"""
    log_to_file("=" * 50)
    log_to_file("🔍 CHECK HOXTON DATA ENDPOINT CALLED!")
    log_to_file("=" * 50)
    print("=" * 50, flush=True)
    print("🔍 CHECK HOXTON DATA ENDPOINT CALLED!", flush=True)
    print("=" * 50, flush=True)
    logger.info("🔍 CHECK HOXTON DATA ENDPOINT CALLED!")
    
    try:
        data = request.get_json()
        log_to_file(f"📥 Request data: {data}")
        print(f"📥 Request data: {data}", flush=True)
        
        if not data or 'url' not in data:
            log_to_file("❌ No URL provided in request")
            print("❌ No URL provided in request", flush=True)
            return jsonify({'error': 'URL is required'}), 400
        
        url = data['url']
        log_to_file(f"🌐 Processing URL: {url}")
        print(f"🌐 Processing URL: {url}", flush=True)
        
        # Initialize Playwright
        log_to_file("🚀 Starting Playwright...")
        print("🚀 Starting Playwright...", flush=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            log_to_file(f"📖 Loading page: {url}")
            print(f"📖 Loading page: {url}", flush=True)
            page.goto(url, wait_until='networkidle', timeout=30000)
            
            log_to_file("🔍 Extracting banner name...")
            print("🔍 Extracting banner name...", flush=True)
            # Use the same JavaScript evaluation as in the capture endpoint
            banner_name_result = page.evaluate("""
                (() => {
                    function extractBannerName() {
                        const debug = { attempts: [], found: null };
                        
                        function extractFromDocument(doc, source = 'main') {
                            try {
                                debug.attempts.push(`Searching in ${source} document`);
                                
                                // Look for Hoxton elements
                                const hoxtonElements = Array.from(doc.querySelectorAll('*')).filter(el => 
                                    el.tagName && el.tagName.toLowerCase().includes('hoxton')
                                );
                                
                                debug.attempts.push(`Found ${hoxtonElements.length} Hoxton elements in ${source}`);
                                
                                for (const element of hoxtonElements) {
                                    const dataAttr = element.getAttribute('data') || element.getAttribute('data-banner') || element.getAttribute('data-creative');
                                    if (dataAttr) {
                                        debug.attempts.push(`Found data attribute in ${source}: ${dataAttr.substring(0, 100)}...`);
                                        try {
                                            // Handle double URL encoding
                                            let decoded = dataAttr;
                                            
                                            // First decode
                                            decoded = decodeURIComponent(decoded);
                                            debug.attempts.push(`First decode: ${decoded.substring(0, 100)}...`);
                                            
                                            // Check if still encoded (contains %)
                                            if (decoded.includes('%')) {
                                                decoded = decodeURIComponent(decoded);
                                                debug.attempts.push(`Second decode: ${decoded.substring(0, 100)}...`);
                                            }
                                            
                                            const parsed = JSON.parse(decoded);
                                            debug.attempts.push(`Successfully parsed JSON with keys: ${Object.keys(parsed).join(', ')}`);
                                            
                                            // Priority 1: Check for reportingLabel, but only if it's not a placeholder or blank
                                            if (parsed.reportingLabel && 
                                                parsed.reportingLabel.trim() !== '' && 
                                                !parsed.reportingLabel.includes('{') && 
                                                !parsed.reportingLabel.includes('}')) {
                                                debug.found = `${source} Hoxton reportingLabel: ${parsed.reportingLabel}`;
                                                return parsed.reportingLabel;
                                            }
                                            
                                            // Priority 2: Fall back to name if reportingLabel is placeholder/blank
                                            if (parsed.name) {
                                                debug.found = `${source} Hoxton name (reportingLabel was placeholder/blank): ${parsed.name}`;
                                                return parsed.name;
                                            }
                                            
                                            // Priority 3: Use reportingLabel even if it's a placeholder (last resort)
                                            if (parsed.reportingLabel) {
                                                debug.found = `${source} Hoxton reportingLabel (using placeholder): ${parsed.reportingLabel}`;
                                                return parsed.reportingLabel;
                                            }
                                        } catch (e) {
                                            debug.attempts.push(`Parse error in ${source}: ${e.message}`);
                                        }
                                    }
                                }
                                
                                return null;
                            } catch (e) {
                                debug.attempts.push(`Error in ${source}: ${e.message}`);
                                return null;
                            }
                        }
                        
                        // Try main document first
                        const mainResult = extractFromDocument(document, 'main');
                        if (mainResult) {
                            return { result: mainResult, debug };
                        }
                        
                        // Try iframes
                        const iframes = document.querySelectorAll('iframe');
                        debug.attempts.push(`Found ${iframes.length} iframes to check`);
                        
                        for (let i = 0; i < iframes.length; i++) {
                            try {
                                const iframeDoc = iframes[i].contentDocument || iframes[i].contentWindow?.document;
                                if (iframeDoc) {
                                    const iframeResult = extractFromDocument(iframeDoc, `iframe-${i}`);
                                    if (iframeResult) {
                                        return { result: iframeResult, debug };
                                    }
                                } else {
                                    debug.attempts.push(`Cannot access iframe ${i} (cross-origin)`);
                                }
                            } catch (e) {
                                debug.attempts.push(`Error accessing iframe ${i}: ${e.message}`);
                            }
                        }
                        
                        return { result: null, debug };
                    }
                    
                    return extractBannerName();
                })()
            """)
            
            log_to_file(f"📊 Banner name extraction result: {banner_name_result}")
            print(f"📊 Banner name extraction result: {banner_name_result}", flush=True)
            
            if banner_name_result and banner_name_result.get('result'):
                log_to_file(f"✅ Successfully extracted banner name: {banner_name_result['result']}")
                print(f"✅ Successfully extracted banner name: {banner_name_result['result']}", flush=True)
            else:
                log_to_file(f"❌ No banner name found. Debug info: {banner_name_result.get('debug', {})}")
                print(f"❌ No banner name found. Debug info: {banner_name_result.get('debug', {})}", flush=True)
            
            browser.close()
            log_to_file("🔚 Browser closed, request complete!")
            print("🔚 Browser closed, request complete!", flush=True)
            
        return jsonify({
            'status': 'success',
            'extraction_result': banner_name_result,
            'message': 'Hoxton data extraction completed - check debug.log file for detailed logs'
        })
        
    except Exception as e:
        error_msg = f"Error checking Hoxton data: {str(e)}"
        log_to_file(f"❌ {error_msg}")
        print(f"❌ {error_msg}", flush=True)
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

@app.route('/capture', methods=['POST'])
def capture_screenshot():
    """API endpoint to capture screenshot"""
    print("🚀 CAPTURE ENDPOINT CALLED! (using print)")
    logger.info("🚀 CAPTURE ENDPOINT CALLED!")
    
    try:
        data = request.get_json()
        print(f"📥 Request data: {data}")
        logger.info(f"📥 Request data: {data}")
        
        if not data or 'url' not in data:
            logger.error("❌ No URL provided in request")
            return jsonify({'error': 'URL is required'}), 400
        
        url = data['url']
        width = data.get('width', None)  # None means auto-detect
        height = data.get('height', None)  # None means auto-detect
        format = data.get('format', 'png')
        wait_time = data.get('waitTime', 3)
        
        logger.info(f"🎯 Processing URL: {url}")
        logger.info(f"⚙️ Settings - Width: {width}, Height: {height}, Format: {format}, Wait: {wait_time}")
        
        # Don't generate filename yet - wait for banner_info
        
        # Validate URL or local file path
        try:
            # Check if it's a local file path
            if url.startswith('file:///') or (len(url) > 3 and url[1:3] == ':\\'):
                # Convert Windows path to file URL if needed
                if not url.startswith('file:///'):
                    # Handle Windows path like C:\path\to\file
                    url = 'file:///' + url.replace('\\', '/')
                
                # Validate that the file exists
                file_path = url.replace('file:///', '').replace('/', '\\')
                if not os.path.exists(file_path):
                    return jsonify({'error': f'Local file not found: {file_path}'}), 400
                    
            else:
                # Validate regular URL
                parsed_url = urlparse(url)
                if not parsed_url.scheme or not parsed_url.netloc:
                    return jsonify({'error': 'Invalid URL format. Use http://, https://, or local file path'}), 400
        except Exception:
            return jsonify({'error': 'Invalid URL format'}), 400
        
        # Validate dimensions (only if provided - None means auto-detect)
        if width is not None and not (100 <= width <= 3000):
            return jsonify({'error': 'Invalid width. Width must be between 100 and 3000 pixels'}), 400
        if height is not None and not (100 <= height <= 3000):
            return jsonify({'error': 'Invalid height. Height must be between 100 and 3000 pixels'}), 400
        
        # Validate format
        if format not in ['png', 'jpg', 'jpeg', 'webp']:
            return jsonify({'error': 'Invalid format. Supported formats: png, jpg, jpeg, webp'}), 400
        
        # Validate wait time
        if not (1 <= wait_time <= 30):
            return jsonify({'error': 'Invalid wait time. Must be between 1 and 30 seconds'}), 400
        
        # Capture screenshot
        logger.info(f"📸 About to call screenshot_service.capture_screenshot()")
        logger.info(f"📸 Parameters: url={url}, width={width}, height={height}, format={format}, wait_time={wait_time}")
        
        try:
            result = screenshot_service.capture_screenshot(url, width, height, format, wait_time)
            logger.info(f"✅ Screenshot service returned result with keys: {result.keys() if result else 'None'}")
            
            # Generate descriptive filename using banner info
            banner_info = result.get('detectedDimensions', {})
            logger.info(f"🏷️ About to generate filename with banner_info keys: {banner_info.keys() if banner_info else 'None'}")
            
            # Use the actual format returned (should be 'jpeg' after optimization)
            actual_format = result.get('format', 'jpeg')
            file_extension = 'jpg' if actual_format == 'jpeg' else actual_format
            
            filename = data.get('filename') or generate_banner_filename(banner_info, url, file_extension)
            result['filename'] = filename
            
            logger.info(f"✅ Final result filename: {filename}")
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"Error capturing screenshot: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    except Exception as e:
        logger.error(f"Error in capture_screenshot: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/scan-preview', methods=['POST'])
def scan_preview():
    """Scan a preview page for multiple banners and extract their URLs"""
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({'error': 'Preview URL is required'}), 400
        
        preview_url = data['url']
        
        # Validate URL
        try:
            parsed_url = urlparse(preview_url)
            if not parsed_url.scheme or not parsed_url.netloc:
                return jsonify({'error': 'Invalid preview URL format'}), 400
        except Exception:
            return jsonify({'error': 'Invalid preview URL format'}), 400
        
        # Use screenshot service to scan the preview page
        playwright = None
        browser = None
        context = None
        page = None
        
        try:
            # Get fresh browser context for this request
            playwright, browser, context = screenshot_service.get_browser_context()
            page = context.new_page()
            
            logger.info(f"Scanning preview page: {preview_url}")
            page.goto(preview_url, wait_until='networkidle', timeout=30000)
            
            # Wait for page to load completely
            import time
            time.sleep(3)
            
            # Extract banner information from the preview page
            banner_info = page.evaluate("""
                () => {
                    const banners = [];
                    
                    // Look for iframes (common in preview pages)
                    const iframes = document.querySelectorAll('iframe');
                    iframes.forEach((iframe, index) => {
                        const src = iframe.src;
                        const rect = iframe.getBoundingClientRect();
                        
                        if (src && rect.width > 0 && rect.height > 0) {
                            banners.push({
                                type: 'iframe',
                                url: src,
                                width: Math.ceil(rect.width),
                                height: Math.ceil(rect.height),
                                index: index + 1,
                                title: iframe.title || `Banner ${index + 1}`,
                                id: iframe.id || `iframe-${index + 1}`
                            });
                        }
                    });
                    
                    // Look for embedded banner containers
                    const containers = document.querySelectorAll('[data-banner-url], [data-src], .banner-container, .ad-container');
                    containers.forEach((container, index) => {
                        const bannerUrl = container.getAttribute('data-banner-url') || 
                                        container.getAttribute('data-src') ||
                                        container.querySelector('a')?.href;
                        const rect = container.getBoundingClientRect();
                        
                        if (bannerUrl && rect.width > 0 && rect.height > 0) {
                            banners.push({
                                type: 'container',
                                url: bannerUrl,
                                width: Math.ceil(rect.width),
                                height: Math.ceil(rect.height),
                                index: iframes.length + index + 1,
                                title: container.getAttribute('title') || `Container Banner ${index + 1}`,
                                id: container.id || `container-${index + 1}`
                            });
                        }
                    });
                    
                    // Look for links that might point to banners
                    const links = document.querySelectorAll('a[href*="banner"], a[href*="creative"], a[href*="ad"], a[href*=".html"]');
                    links.forEach((link, index) => {
                        const href = link.href;
                        const text = link.textContent.trim();
                        const rect = link.getBoundingClientRect();
                        
                        // Only include if it looks like a banner link
                        if (href && (href.includes('banner') || href.includes('creative') || href.includes('ad') || text.toLowerCase().includes('banner'))) {
                            banners.push({
                                type: 'link',
                                url: href,
                                width: 0, // Unknown, will auto-detect
                                height: 0, // Unknown, will auto-detect
                                index: iframes.length + containers.length + index + 1,
                                title: text || `Link Banner ${index + 1}`,
                                id: link.id || `link-${index + 1}`
                            });
                        }
                    });
                    
                    // Look for preview thumbnails with data attributes
                    const thumbnails = document.querySelectorAll('[data-preview-url], .preview-item, .banner-preview');
                    thumbnails.forEach((thumb, index) => {
                        const previewUrl = thumb.getAttribute('data-preview-url') ||
                                         thumb.querySelector('a')?.href;
                        const rect = thumb.getBoundingClientRect();
                        
                        if (previewUrl) {
                            banners.push({
                                type: 'preview',
                                url: previewUrl,
                                width: Math.ceil(rect.width) || 0,
                                height: Math.ceil(rect.height) || 0,
                                index: iframes.length + containers.length + links.length + index + 1,
                                title: thumb.getAttribute('alt') || thumb.textContent?.trim() || `Preview ${index + 1}`,
                                id: thumb.id || `preview-${index + 1}`
                            });
                        }
                    });
                    
                    return {
                        totalFound: banners.length,
                        banners: banners,
                        pageTitle: document.title,
                        pageUrl: window.location.href
                    };
                }
            """)
            
            return jsonify({
                'success': True,
                'previewUrl': preview_url,
                'pageTitle': banner_info['pageTitle'],
                'totalBanners': banner_info['totalFound'],
                'banners': banner_info['banners']
            })
            
        finally:
            # Clean up resources
            if page:
                page.close()
            if context:
                context.close()
            if browser:
                browser.close()
            if playwright:
                playwright.stop()
            
    except Exception as e:
        logger.error(f"Error in scan_preview: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/debug-dimensions', methods=['POST'])
def debug_dimensions():
    """Debug endpoint to check detected dimensions without taking screenshot"""
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({'error': 'URL is required'}), 400
        
        url = data['url']
        
        # Validate URL or local file path
        try:
            # Check if it's a local file path
            if url.startswith('file:///') or (len(url) > 3 and url[1:3] == ':\\'):
                # Convert Windows path to file URL if needed
                if not url.startswith('file:///'):
                    # Handle Windows path like C:\path\to\file
                    url = 'file:///' + url.replace('\\', '/')
                
                # Validate that the file exists
                file_path = url.replace('file:///', '').replace('/', '\\')
                if not os.path.exists(file_path):
                    return jsonify({'error': f'Local file not found: {file_path}'}), 400
                    
            else:
                # Validate regular URL
                parsed_url = urlparse(url)
                if not parsed_url.scheme or not parsed_url.netloc:
                    return jsonify({'error': 'Invalid URL format. Use http://, https://, or local file path'}), 400
        except Exception:
            return jsonify({'error': 'Invalid URL format'}), 400
        
        # Use screenshot service to detect dimensions
        playwright = None
        browser = None
        context = None
        page = None
        
        try:
            # Get fresh browser context for this request
            playwright, browser, context = screenshot_service.get_browser_context()
            page = context.new_page()
            
            # Navigate to the URL
            logger.info(f"Debug: Navigating to: {url}")
            page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Get dimensions using the same logic as screenshot capture
            actual_dimensions = page.evaluate("""
                () => {
                    // Try to find the banner container or body dimensions
                    const body = document.body;
                    const html = document.documentElement;
                    
                    // Look for common banner container selectors in order of priority
                    const containers = [
                        '#mainHolder', '#container', '#main', '#banner-container',
                        // Hoxton-specific selectors
                        '.creative-container', '.banner-frame', '.ad-frame', 
                        '[data-creative]', '[data-banner]', '.hoxton-banner',
                        // General selectors
                        'canvas', '.banner', '#banner', '.ad', '#ad', 
                        '.creative', '#creative', '.container', 'main',
                        'div[style*="width"]', 'div[style*="height"]',
                        '.banner-wrap', '.ad-wrap', '.creative-wrap',
                        // Frame/iframe content
                        'body > div:first-child', 'body > *:first-child'
                    ];
                    
                    let bannerWidth = 0;
                    let bannerHeight = 0;
                    let detectionMethod = 'fallback';
                    let foundElements = [];
                    
                    // Special handling for Hoxton or other banner sharing platforms
                    const isHoxtonOrSimilar = window.location.hostname.includes('hoxton') || 
                                            document.querySelector('.creative-container, .banner-frame, [data-creative]');
                    
                    // Try to find a container with explicit dimensions
                    for (const selector of containers) {
                        const elements = document.querySelectorAll(selector);
                        for (const element of elements) {
                            const rect = element.getBoundingClientRect();
                            const computedStyle = window.getComputedStyle(element);
                            
                            foundElements.push({
                                selector: selector,
                                width: rect.width,
                                height: rect.height,
                                cssWidth: computedStyle.width,
                                cssHeight: computedStyle.height,
                                tagName: element.tagName,
                                id: element.id || 'no-id',
                                className: element.className || 'no-class'
                            });
                            
                            // Check if element has explicit width/height
                            if (rect.width > 0 && rect.height > 0) {
                                // For banner-specific containers, prioritize them highly
                                if (selector.includes('mainHolder') || selector.includes('container') || 
                                    selector.includes('banner') || selector.includes('creative') || 
                                    selector.includes('ad')) {
                                    bannerWidth = Math.ceil(rect.width);
                                    bannerHeight = Math.ceil(rect.height);
                                    detectionMethod = `${selector} (banner container priority)`;
                                    break;
                                }
                                
                                // Prefer elements with explicit CSS dimensions
                                const cssWidth = computedStyle.width;
                                const cssHeight = computedStyle.height;
                                
                                if ((cssWidth && cssWidth !== 'auto') || (cssHeight && cssHeight !== 'auto')) {
                                    bannerWidth = Math.ceil(rect.width);
                                    bannerHeight = Math.ceil(rect.height);
                                    detectionMethod = `${selector} (CSS dimensions)`;
                                    break;
                                }
                                
                                // If no CSS dimensions but has reasonable banner size, use it
                                if (rect.width < 2000 && rect.height < 2000 && 
                                    rect.width > 50 && rect.height > 50) {
                                    bannerWidth = Math.ceil(rect.width);
                                    bannerHeight = Math.ceil(rect.height);
                                    detectionMethod = `${selector} (computed size)`;
                                    break;
                                }
                            }
                        }
                        if (bannerWidth > 0 && bannerHeight > 0) break;
                    }
                    
                    // Fallback to body/viewport dimensions if no container found
                    if (bannerWidth === 0 || bannerHeight === 0) {
                        const viewportWidth = window.innerWidth;
                        const viewportHeight = window.innerHeight;
                        const bodyRect = body.getBoundingClientRect();
                        const htmlRect = html.getBoundingClientRect();
                        
                        // Use the smallest reasonable dimensions
                        bannerWidth = Math.min(viewportWidth, bodyRect.width || viewportWidth, htmlRect.width || viewportWidth);
                        bannerHeight = Math.min(viewportHeight, bodyRect.height || viewportHeight, htmlRect.height || viewportHeight);
                        
                        // Clamp to reasonable banner sizes
                        bannerWidth = Math.max(100, Math.min(bannerWidth, 2000));
                        bannerHeight = Math.max(100, Math.min(bannerHeight, 2000));
                        
                        detectionMethod = 'viewport/body fallback';
                    }
                    
                    return {
                        width: bannerWidth,
                        height: bannerHeight,
                        detectionMethod: detectionMethod,
                        viewportWidth: window.innerWidth,
                        viewportHeight: window.innerHeight,
                        bodyWidth: body.getBoundingClientRect().width,
                        bodyHeight: body.getBoundingClientRect().height,
                        foundElements: foundElements
                    };
                }
            """)
            
            return jsonify({
                'success': True,
                'url': url,
                'detectedDimensions': actual_dimensions,
                'recommendedWidth': actual_dimensions['width'],
                'recommendedHeight': actual_dimensions['height']
            })
            
        finally:
            # Clean up resources
            if page:
                page.close()
            if context:
                context.close()
            if browser:
                browser.close()
            if playwright:
                playwright.stop()
            
    except Exception as e:
        logger.error(f"Error in debug_dimensions: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'playwright_available': PLAYWRIGHT_AVAILABLE,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/batch-capture', methods=['POST'])
def batch_capture():
    """API endpoint to capture multiple screenshots"""
    try:
        data = request.get_json()
        
        if not data or 'urls' not in data:
            return jsonify({'error': 'URLs array is required'}), 400
        
        urls = data['urls']
        settings = data.get('settings', {})
        
        if not isinstance(urls, list) or len(urls) == 0:
            return jsonify({'error': 'URLs must be a non-empty array'}), 400
        
        if len(urls) > 20:  # Limit batch size
            return jsonify({'error': 'Maximum 20 URLs allowed per batch'}), 400
        
        results = []
        
        # Process each URL
        for i, url_data in enumerate(urls):
            if isinstance(url_data, str):
                url = url_data
                url_settings = settings
            else:
                url = url_data.get('url')
                url_settings = {**settings, **url_data.get('settings', {})}
            
            try:
                width = url_settings.get('width', 1200)
                height = url_settings.get('height', 630)
                format = url_settings.get('format', 'png')
                wait_time = url_settings.get('waitTime', 3)
                
                # Capture screenshot first to get banner info
                result = screenshot_service.capture_screenshot(url, width, height, format, wait_time)
                
                # Generate descriptive filename using banner info
                banner_info = result.get('detectedDimensions', {})
                filename = generate_banner_filename(banner_info, url, format, i)
                result['filename'] = filename
                result['index'] = i
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error capturing {url}: {str(e)}")
                results.append({
                    'success': False,
                    'error': str(e),
                    'url': url,
                    'index': i
                })
        
        return jsonify({
            'success': True,
            'results': results,
            'total': len(urls),
            'successful': len([r for r in results if r.get('success')])
        })
        
    except Exception as e:
        logger.error(f"Error in batch_capture: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/download-zip', methods=['POST'])
def download_zip():
    """Create a ZIP file from multiple images"""
    try:
        data = request.get_json()
        if not data or 'images' not in data:
            return jsonify({'error': 'No images provided'}), 400
        
        images = data['images']
        if not images:
            return jsonify({'error': 'Empty images list'}), 400
        
        # Create a BytesIO object to store the ZIP in memory
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for i, image_data in enumerate(images):
                if 'data' not in image_data or 'filename' not in image_data:
                    continue
                
                # Decode base64 image data
                try:
                    image_bytes = base64.b64decode(image_data['data'].split(',')[1])
                    original_filename = image_data['filename'] or f'banner_{i+1}.png'
                    
                    # Clean filename for ZIP consistency
                    cleaned_filename = clean_filename_for_zip(original_filename)
                    
                    zip_file.writestr(cleaned_filename, image_bytes)
                except Exception as e:
                    logging.error(f"Failed to add image {i} to ZIP: {str(e)}")
                    continue
        
        zip_buffer.seek(0)
        
        # Generate timestamp for unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_filename = f'banners_{timestamp}.zip'
        
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=zip_filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        logging.error(f"ZIP download error: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("Starting Banner to Static Image Utility Server...")
    print("=" * 50)
    
    if not PLAYWRIGHT_AVAILABLE:
        print("⚠️  WARNING: Playwright not installed!")
        print("   Please install it with:")
        print("   pip install playwright")
        print("   playwright install chromium")
        print("=" * 50)
    else:
        print("✅ Playwright is available")
        print("=" * 50)
    
    print("📱 Web Interface: http://localhost:5000")
    print("🔧 Health Check: http://localhost:5000/health")
    print("=" * 50)
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    finally:
        # Cleanup
        try:
            screenshot_service.cleanup()
        except:
            pass