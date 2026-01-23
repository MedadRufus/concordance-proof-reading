Quick deploy instructions for cPanel (Passenger WSGI)

1. Ensure `requirements.txt` includes `Flask` and `odfpy` (already present).
2. Create a Python app in cPanel and point its app root to this repo folder.
3. cPanel will install packages from `requirements.txt` automatically; confirm `Flask` and `odfpy` installed.
4. passenger_wsgi.py is already included and exposes the Flask `application` callable.
5. After starting the app, visit the app URL. The root page provides the upload UI.

Notes and tips:
- App stores temporary inputs/outputs in the system temp directory. You may want to add a cron job to clean old tmp directories in production.
- If you need HTTPS or a custom domain, configure it using cPanel's app settings.
- If you expect heavy use, consider persisting converted files to an S3-like store rather than keeping them in tmp.
