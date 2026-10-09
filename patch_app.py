with open('app.py', 'r') as f:
    content = f.read()

route = """
@app.route("/api/database/tail", methods=["GET"])
def database_tail():
    pings = storage.get_recent_pings(limit=100)
    return jsonify({"data": pings})

"""
content = content.replace('@app.route("/api/health", methods=["GET"])', route + '@app.route("/api/health", methods=["GET"])')

with open('app.py', 'w') as f:
    f.write(content)
