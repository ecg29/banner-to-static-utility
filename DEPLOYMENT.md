# Deployment Guide

## 🚀 Deploying to GitHub Pages

### Step 1: Enable GitHub Pages
1. Go to your repository settings
2. Scroll to "Pages" section
3. Source: "Deploy from a branch"
4. Branch: `main` / (root)
5. Save

### Step 2: Update Configuration
Edit `config.js` and update the production API URL:
```javascript
return 'https://your-api-endpoint.netlify.app/.netlify/functions';
```

### Step 3: Backend Deployment Options

#### Option A: Netlify Functions (Recommended)
1. Create account at netlify.com
2. Connect your GitHub repository
3. Deploy with these settings:
   - Build command: `pip install -r requirements.txt && python -m playwright install`
   - Functions directory: `netlify/functions`

#### Option B: Vercel
1. Create account at vercel.com
2. Import your GitHub repository
3. Vercel will auto-detect Python and deploy

#### Option C: Railway
1. Create account at railway.app
2. Connect GitHub repository
3. Add environment variables if needed
4. Deploy automatically

### Step 4: Test Production
1. Visit your GitHub Pages URL
2. Test with sample banner URLs
3. Verify image generation works

## 🔧 Environment Variables

For production deployment, you may need:
- `PLAYWRIGHT_BROWSERS_PATH` (for custom browser location)
- `PORT` (for custom port configuration)

## 📱 Access Your App

Your app will be available at:
`https://yourusername.github.io/banner-to-static-utility`

Replace `yourusername` with your actual GitHub username.