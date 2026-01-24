import sys
import os
from werkzeug.middleware.proxy_fix import ProxyFix

# Ensure we can import app.py from the current directory
sys.path.insert(0, os.path.dirname(__file__))

from app import app as flask_app

# 1. Fix IP and Scheme (HTTP/HTTPS) handling behind cPanel/Nginx
flask_app.wsgi_app = ProxyFix(flask_app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# 2. Middleware to force SCRIPT_NAME for subdirectory hosting
class SubdirectoryMiddleware:
    def __init__(self, app, prefix):
        self.app = app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        # Force SCRIPT_NAME so url_for() generates /concordance/...
        environ['SCRIPT_NAME'] = self.prefix
        
        # Strip the prefix from PATH_INFO if it's there (prevent double pathing)
        path_info = environ.get('PATH_INFO', '')
        if path_info.startswith(self.prefix):
            environ['PATH_INFO'] = path_info[len(self.prefix):] or '/'
            
        return self.app(environ, start_response)

# Passenger looks for 'application' callable
application = SubdirectoryMiddleware(flask_app.wsgi_app, '/concordance')
