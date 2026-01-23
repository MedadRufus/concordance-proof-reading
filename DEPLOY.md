Quick deploy (cPanel Passenger WSGI) — secure & production notes

1. Ensure `requirements.txt` includes `Flask` and `odfpy` (already present).
2. Create a Python app in cPanel and point its app root to this repo folder.
3. cPanel will install packages from `requirements.txt` automatically; confirm `Flask` and `odfpy` installed.
4. `passenger_wsgi.py` is included and exposes the Flask `application` callable.
5. After starting the app, visit the app URL. The root page provides the upload UI.

Production & Security recommendations:
- HTTPS: Always enable TLS (let’s encrypt or your certificate). HSTS header is set by the app; make sure your site is only served over HTTPS.
- Max upload size: Default is 5 MB. You can tune this by setting the `MAX_CONTENT_LENGTH` environment variable in cPanel.
- Data handling: Files are processed in memory and not persisted to disk by default. Uploaded content is ephemeral and removed after `UPLOAD_TTL` seconds (default 10 minutes).
- Multi-process note: the in-memory store is per-process. For scaled deployments or persistence across processes, use a shared store (Redis, S3) and adapt the app accordingly.
- Input validation: The app validates that uploaded .odt files are valid ODT (zip containing `content.xml`).
- Limit abuse: Configure `UPLOAD_RATE_LIMIT` and `RATE_LIMIT_WINDOW` environment variables to limit uploads per IP.
- Headers & CSP: The app sets strict security headers (CSP, HSTS, X-Frame-Options, nosniff, Referrer-Policy).
- Logging & monitoring: Enable access/error logging and rotate logs. Monitor conversion errors and resource usage.
- Hardening: Consider adding WAF rules, fail2ban, and IP whitelisting if you expect targeted attacks.

Operational notes:
- Environment variables you can set in cPanel: `MAX_CONTENT_LENGTH`, `UPLOAD_TTL`, `UPLOAD_RATE_LIMIT`, `RATE_LIMIT_WINDOW`.
- If you need persistent downloads or long-lived storage, upload converted files to S3 and provide signed URLs rather than keeping long-lived in-memory state.
- Test with representative ODT files and enable HTTPS before exposing publicly.

Support:
- If you'd like, I can add Redis-backed storage (to support multiple processes), add authentication, or integrate virus scanning for uploaded files.
