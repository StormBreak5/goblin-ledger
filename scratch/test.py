import urllib.request
import re

html = urllib.request.urlopen("https://undermine.exchange/").read().decode("utf-8")
scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
print(scripts)
