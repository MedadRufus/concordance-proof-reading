# Cache Directory

This directory contains cached HTML responses from kingjamesbibleonline.org.

## Purpose

- Speeds up subsequent scraping runs by avoiding network requests
- Allows offline re-running of the scraper
- Reduces load on the source website

## File Format

Files are named: `{BookName}_{ChapterNumber}.html`

Example: `Genesis_1.html` contains the HTML for Genesis Chapter 1

## Clearing Cache

To force a fresh scrape, simply delete the cache files or the entire cache directory.
The scraper will automatically recreate it and fetch fresh data.
