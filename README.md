# 🖼️ Banner to Static Image Utility

A powerful web-based utility that generates backup static images from banner URLs with one click. Perfect for creating fallback images for dynamic banners, social media previews, or archiving web content.

## ✨ Features

- **Batch Processing**: Process multiple banner URLs simultaneously
- **One-Click Generation**: Generate all images with a single click
- **Customizable Settings**: Adjust image dimensions, format, and wait times
- **Real-time Preview**: See generated images immediately
- **Bulk Download**: Download all images at once or individually
- **Multiple Formats**: Support for PNG, JPG, and WebP formats
- **Responsive Design**: Works on desktop and mobile devices
- **Progress Tracking**: Visual progress indicator during batch processing

## 🚀 Quick Start

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

### Installation

1. **Clone or download this repository**
   ```powershell
   git clone <repository-url>
   cd banner-to-static-utility
   ```

2. **Install Python dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Install Playwright browsers**
   ```powershell
   playwright install chromium
   ```

4. **Start the server**
   ```powershell
   python app.py
   ```

5. **Open your browser**
   Navigate to: `http://localhost:5000`

## 📖 How to Use

### Adding URLs

1. **Single URL/Path**: 
   - Web URL: `https://example.com/banner.html`
   - Local file: `C:\Users\ADMIN\Desktop\banner\index.html`
   - File URL: `file:///C:/path/to/banner.html`
2. **Multiple URLs/Paths**: Paste multiple URLs or file paths (one per line) in the textarea

### Supported Input Types

- **Web URLs**: `https://example.com/banner.html`
- **Local File Paths**: `C:\Users\ADMIN\Desktop\OLA\2025\banner\index.html`
- **File URLs**: `file:///C:/Users/ADMIN/Desktop/banner/index.html`

The utility automatically detects the input type and handles both local files and web URLs seamlessly.

### Configuring Settings

- **Image Width/Height**: Set the dimensions for generated images (100-3000px)
- **Image Format**: Choose between PNG, JPG, or WebP
- **Wait Time**: Set how long to wait for banner content to load (1-30 seconds)

### Generating Images

1. Add your banner URLs
2. Adjust settings if needed
3. Click "Generate All Images"
4. Wait for processing to complete
5. Download individual images or use "Download All Images"

## 🛠️ Technical Details

### Backend Architecture

- **Flask**: Web framework for Python
- **Playwright**: Browser automation for screenshot capture
- **Async Processing**: Non-blocking screenshot generation
- **CORS Support**: Cross-origin resource sharing enabled

### Frontend Features

- **Vanilla JavaScript**: No external dependencies
- **Responsive CSS**: Mobile-friendly design
- **LocalStorage**: Settings persistence
- **Real-time Updates**: Dynamic UI updates during processing

### API Endpoints

- `GET /` - Main web interface
- `POST /capture` - Single screenshot capture
- `POST /batch-capture` - Multiple screenshot capture
- `GET /health` - Server health check

## 📁 Project Structure

```
banner-to-static-utility/
├── app.py              # Python Flask backend
├── index.html          # Main web interface
├── styles.css          # CSS styling
├── script.js           # Frontend JavaScript
├── requirements.txt    # Python dependencies
└── README.md           # This documentation
```

## ⚙️ Configuration Options

### Screenshot Settings

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| Width | 1200px | 100-3000px | Image width |
| Height | 630px | 100-3000px | Image height |
| Format | PNG | PNG/JPG/WebP | Output format |
| Wait Time | 3s | 1-30s | Loading wait time |

### Browser Settings

The utility uses Chromium with optimized settings:
- Headless mode enabled
- No sandbox (for compatibility)
- Disabled GPU acceleration
- Optimized for screenshots

## 🔧 Advanced Usage

### Custom API Requests

You can also use the API directly:

```javascript
// Single screenshot
fetch('/capture', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        url: 'https://example.com/banner.html',
        width: 1200,
        height: 630,
        format: 'png',
        waitTime: 3
    })
})

// Batch screenshots
fetch('/batch-capture', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        urls: ['https://example.com/banner1.html', 'https://example.com/banner2.html'],
        settings: { width: 1200, height: 630, format: 'png', waitTime: 3 }
    })
})
```

### Environment Variables

- `FLASK_ENV=development` - Enable debug mode
- `PORT=5000` - Change server port

## 🚨 Troubleshooting

### Common Issues

1. **"Playwright not installed" error**
   ```powershell
   pip install playwright
   playwright install chromium
   ```

2. **Browser launch fails**
   - Try running with administrator privileges
   - Check antivirus software isn't blocking Chromium

3. **Screenshot capture fails**
   - Verify the URL is accessible
   - Check if the site requires authentication
   - Increase wait time for slow-loading content

4. **Memory issues with large batches**
   - Process fewer URLs at once
   - Restart the server periodically

### Error Messages

- **"Invalid URL format"**: Ensure URLs include http:// or https://
- **"Invalid dimensions"**: Width/height must be 100-3000px
- **"Maximum 20 URLs allowed"**: Reduce batch size
- **"Failed to capture screenshot"**: Check URL accessibility

## 🔒 Security Considerations

- The utility runs a local server - only use trusted URLs
- Screenshots may include sensitive content - review before sharing
- Consider firewall settings when running on shared networks

## 🎯 Use Cases

### Web Development
- Generate fallback images for animated banners
- Create static previews for dynamic content
- Archive website states for client presentations

### Marketing
- Capture banner variations for A/B testing
- Create social media preview images
- Generate thumbnails for banner campaigns

### Quality Assurance
- Visual regression testing
- Cross-browser banner verification
- Documentation screenshots

## 📈 Performance Tips

1. **Optimize batch sizes**: Process 5-10 URLs at once for best performance
2. **Adjust wait times**: Reduce for simple banners, increase for complex animations
3. **Choose appropriate formats**: PNG for quality, JPG for smaller files
4. **Monitor memory usage**: Restart server if processing many large images

## 🤝 Contributing

Feel free to submit issues, feature requests, or pull requests to improve this utility.

## 📄 License

This project is open source and available under the MIT License.

---

**Made with ❤️ for developers and marketers who need reliable banner backup images.**