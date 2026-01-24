Quick deploy (cPanel Passenger WSGI) — secure & production notes

1. Clone this repo to your server
2. Create a Python app in cPanel and point its app root to this repo folder.
3. Run the pip installer via the cPanel Python app UI
4. After restarting the app, visit the app URL. The root page provides the upload UI.

Production & Security recommendations:
- HTTPS: Always enable TLS (let’s encrypt or your certificate). HSTS header is set by the app; make sure your site is only served over HTTPS.
- Max upload size: Default is 5 MB. You can tune this by setting the `MAX_CONTENT_LENGTH` environment variable in cPanel.
- Data handling: Files are processed in memory and not persisted to disk by default. Uploaded content is ephemeral and removed after `UPLOAD_TTL` seconds (default 10 minutes).
- Multi-process note: the in-memory store is per-process. 
- Input validation: The app validates that uploaded .odt files are valid ODT (zip containing `content.xml`).
- Limit abuse: Configure `UPLOAD_RATE_LIMIT` and `RATE_LIMIT_WINDOW` environment variables to limit uploads per IP.
- Headers & CSP: The app sets strict security headers (CSP, HSTS, X-Frame-Options, nosniff, Referrer-Policy).

Operational notes:
- Environment variables you can set in cPanel: `MAX_CONTENT_LENGTH`, `UPLOAD_TTL`, `UPLOAD_RATE_LIMIT`, `RATE_LIMIT_WINDOW`.
