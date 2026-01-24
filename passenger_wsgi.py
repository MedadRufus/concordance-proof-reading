"""WSGI entry point for Phusion Passenger.

This file is required by the cPanel Phusion Passenger server. It imports
the Flask `app` object and renames it to `application`, which is the
default name Passenger looks for.
"""

# pylint: disable=unused-import
from app import app as application

# Passenger (cPanel) will look for `application` callable.
