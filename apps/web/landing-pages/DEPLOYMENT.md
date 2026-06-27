# Landing Pages — Deployment Guide

## Option A: Cloudflare Pages (Recommended — free, fast, on your existing Cloudflare account)

### Steps:
1. Log in to Cloudflare dashboard → Pages
2. Click **"Create a project"** → **"Connect to Git"**
3. Select the `empireenglishcommunity-glitch/Claude` repository
4. Configure build settings:
   - **Production branch:** `main`
   - **Build command:** (leave empty — static files, no build needed)
   - **Build output directory:** `web`
5. Click **"Save and Deploy"**
6. After deploy, go to **Custom domains** → Add `empireenglish.online` (or `www.empireenglish.online`)
7. Cloudflare auto-configures DNS since you already use Cloudflare NS

### Result:
- Arabic landing page: `https://empireenglish.online/` (default)
- English landing page: `https://empireenglish.online/en`
- Or direct: `https://empireenglish.online/index.html` / `https://empireenglish.online/index-ar.html`

### Custom domain:
Since `empireenglish.online` is already on Cloudflare (from the Tunnel setup), adding it to Pages is one click. Use the root domain or a subdomain like `www.empireenglish.online`.

---

## Option B: GitHub Pages (Alternative — also free)

### Steps:
1. Go to GitHub repo → Settings → Pages
2. Under "Build and deployment":
   - Source: **Deploy from a branch**
   - Branch: `main`
   - Folder: `/web`
3. Click Save
4. Pages will be live at: `https://empireenglishcommunity-glitch.github.io/Claude/`

### Custom domain (GitHub Pages):
1. In the Pages settings, add custom domain: `empireenglish.online`
2. In Cloudflare DNS, add a CNAME record:
   - Name: `@` (or `www`)
   - Target: `empireenglishcommunity-glitch.github.io`
   - Proxied: YES

---

## File Structure

```
web/
├── index.html        ← English landing page
├── index-ar.html     ← Arabic (RTL) landing page (DEFAULT)
├── _redirects        ← Routing rules (Cloudflare Pages/Netlify)
├── _headers          ← Security headers
└── DEPLOYMENT.md     ← This file
```

## Post-Deployment Checklist

- [ ] Verify both pages load (EN + AR)
- [ ] Test on mobile (responsive)
- [ ] Add real OG image (`og-image.png` in web/ folder)
- [ ] Update the Telegram bot's "How Empire works" route to include landing page link
- [ ] Add TikTok bio link pointing to landing page
- [ ] Consider adding analytics (Plausible free tier or Cloudflare Web Analytics — both free)

## Monthly Cost: $0
Both Cloudflare Pages and GitHub Pages are 100% free for static sites.
