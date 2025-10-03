# This is a backup showing the fixes needed for text rendering quality

# Key fixes needed:

# 1. Add device_scale_factor for high-quality text rendering
context = browser.new_context(
    viewport={'width': 1920, 'height': 1080},
    device_scale_factor=2,  # 2x scaling for crisp text
    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
)

# 2. Set exact viewport size matching banner dimensions
page.set_viewport_size({'width': width, 'height': height})  # Exact match, no padding

# 3. Add font smoothing and text rendering options
page.add_init_script("""
    // Force font smoothing for better text rendering
    document.documentElement.style.webkitFontSmoothing = 'antialiased';
    document.documentElement.style.mozOsxFontSmoothing = 'grayscale';
    document.documentElement.style.fontSmooth = 'always';
    document.documentElement.style.textRendering = 'optimizeLegibility';
""")

# 4. Capture at higher quality and only compress if needed
screenshot_bytes = page.screenshot(
    type='png',  # PNG preserves text quality better
    full_page=False,
    clip={'x': 0, 'y': 0, 'width': width, 'height': height}
)

# 5. Improved JPEG optimization that preserves text
def optimize_image_to_jpg_preserve_text(image_data, max_size_kb=49, min_quality=60, max_quality=95):
    """
    Convert image data to JPG format while preserving text quality
    """
    try:
        # Convert image data to PIL Image
        image = Image.open(image_io.BytesIO(image_data))
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        best_data = None
        best_quality = max_quality
        max_size_bytes = max_size_kb * 1024
        
        # Try progressively lower quality, but not below 60% to preserve text
        for quality in range(max_quality, min_quality - 1, -5):
            output = image_io.BytesIO()
            # Use subsampling=0 to preserve text sharpness
            image.save(output, format='JPEG', quality=quality, optimize=True, subsampling=0)
            jpg_data = output.getvalue()
            
            if len(jpg_data) <= max_size_bytes:
                best_data = jpg_data
                best_quality = quality
                break
        
        # If still too large, try smart resizing that preserves text
        if best_data is None:
            # Calculate scale factor needed
            current_size = len(image_data)
            target_size = max_size_bytes * 0.9  # 90% of limit for safety
            scale_factor = (target_size / current_size) ** 0.5
            
            # Resize with LANCZOS for better text preservation
            new_width = int(image.width * scale_factor)
            new_height = int(image.height * scale_factor)
            resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            output = image_io.BytesIO()
            resized_image.save(output, format='JPEG', quality=min_quality, optimize=True, subsampling=0)
            best_data = output.getvalue()
            best_quality = min_quality
        
        final_size_kb = len(best_data) / 1024
        return best_data, best_quality, final_size_kb
        
    except Exception as e:
        # Fallback to original method
        return optimize_image_to_jpg(image_data, max_size_kb, 25, max_quality)