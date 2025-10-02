// Configuration for different environments
const CONFIG = {
    // Auto-detect environment
    isDevelopment: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1',
    
    // API endpoints
    getApiUrl() {
        if (this.isDevelopment) {
            return 'http://localhost:5000';
        } else {
            // For production, you can use:
            // 1. Netlify Functions: https://your-app.netlify.app/.netlify/functions
            // 2. Vercel: https://your-app.vercel.app/api
            // 3. Railway: https://your-app.railway.app
            return 'https://your-banner-utility-api.netlify.app/.netlify/functions';
        }
    },
    
    // Feature flags
    features: {
        debugMode: false, // Set to false for production
        analytics: false, // Enable if you want to add analytics
        errorReporting: false // Enable if you want error reporting
    }
};

// Export for use in other files
window.CONFIG = CONFIG;