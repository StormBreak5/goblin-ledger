import urllib.request

js_url = "https://undermine.exchange/assets/index-DgMKjmz7.js"
js = urllib.request.urlopen(js_url).read().decode("utf-8")
with open("scratch/index.js", "w", encoding="utf-8") as f:
    f.write(js)
