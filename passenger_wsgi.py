from app import app as application

# Passenger (cPanel) will look for `application` callable.

# Middleware to ensure Flask generates URLs with the correct subdirectory prefix
class SubdirectoryMiddleware:
    def __init__(self, app, prefix):
        self.app = app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        # Force SCRIPT_NAME to the prefix so url_for() generates correct paths
        environ['SCRIPT_NAME'] = self.prefix
        return self.app(environ, start_response)

application.wsgi_app = SubdirectoryMiddleware(application.wsgi_app, '/concordance')
