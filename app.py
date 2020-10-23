import json
import struct
import requests

from flask import Flask, render_template, redirect
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
scheduler = BackgroundScheduler()

authors = {}
counts = {}
stats = {}


@scheduler.scheduled_job('interval', minutes=30)
def updateCounts():
    global authors, counts, stats
    authors.clear()
    counts.clear()
    stats.clear()

    # Grab RuneLite version from bootstrap file
    bootstrap = requests.get("https://static.runelite.net/bootstrap.json").json()
    rl_version = bootstrap['client']['version']

    # Grab the Plugin Hub manifest as a byte array
    manifest = requests.get("https://repo.runelite.net/plugins/" + rl_version + "/manifest.js").content

    # Read and remove the signature. The length is stored in the first 4 bytes
    signature_size = struct.unpack('>i', manifest[0:4])[0]
    manifest = json.loads(manifest[4 + signature_size:])

    # Link each plugin name to the respective author
    for plugin in manifest:
        author = plugin['author'].strip().lower()
        authors[plugin['internalName']] = author
        counts[author] = 0

    # Grab the recent stats for each plugin
    stats = requests.get("https://api.runelite.net/runelite-" + rl_version + "/pluginhub").json()

    # Consolidate plugin installs
    for plugin in stats:
        if plugin not in authors:
            continue

        author = authors[plugin]
        counts[author] = counts[author] + stats[plugin]

    # Sort counts and stats dicts by value for finding author/plugin ranks
    counts = {k: v for k, v in sorted(counts.items(), key=lambda item: item[1], reverse=True)}
    stats = {k: v for k, v in sorted(stats.items(), key=lambda item: item[1], reverse=True)}


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')  # Catch all and redirect to main route '/'
def get(path):
    if len(path) > 0:
        return redirect('/', 303)
    return render_template('index.html')


# API section
@app.route('/installs/author/<username>')
def getAuthorInstalls(username):
    username = str(username).strip().lower()
    if username not in counts:
        return "-1"

    return str(counts[username])


@app.route('/installs/plugin/<plugin_name>')
def getPluginInstalls(plugin_name):
    plugin_name = str(plugin_name).strip().lower().replace(" ", "-")
    if plugin_name not in stats:
        return "-1"

    return str(stats[plugin_name])


@app.route('/rank/author/<username>')
def getAuthorRank(username):
    username = str(username).strip().lower()
    for idx, name in enumerate(counts, start=1):
        if username == name:
            return str(idx)

    return "-1"


@app.route('/rank/plugin/<plugin_name>')
def getPluginRank(plugin_name):
    plugin_name = str(plugin_name).strip().lower().replace(" ", "-")
    for idx, plugin in enumerate(stats, start=1):
        if plugin_name == plugin:
            return str(idx)

    return "-1"


@app.route('/shields/installs/author/<username>')
def getAuthorInstallsBadge(username):
    return generateShieldJson(int(getAuthorInstalls(username)))


@app.route('/shields/installs/plugin/<plugin_name>')
def getPluginInstallsBadge(plugin_name):
    return generateShieldJson(int(getPluginInstalls(plugin_name)))


@app.route('/shields/rank/author/<username>')
def getAuthorRankBadge(username):
    return generateShieldJson(int(getAuthorRank(username)), "Author rank")


@app.route('/shields/rank/plugin/<plugin_name>')
def getPluginRankBadge(plugin_name):
    return generateShieldJson(int(getPluginRank(plugin_name)), "Plugin rank")


# Utilizes https://shields.io/endpoint to generate the badge dynamically
def generateShieldJson(count: int, label="Total installs"):
    return {
        "schemaVersion": 1,
        "label": label,
        "message": str(count),
        "color": "007bff" if count >= 0 else "red",
        "isError": count == -1
    }


# Initialize counts and schedule them for every 30 minutes
updateCounts()
scheduler.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0')
