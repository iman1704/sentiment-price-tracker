"""
See the structure of the raw data from the rss feed
"""

import feedparser
import json

feed = feedparser.parse("https://news.google.com/rss/search?q=Maybank")

raw_sample = json.dumps(feed.entries[0], indent=4, default=str)
print(raw_sample)
