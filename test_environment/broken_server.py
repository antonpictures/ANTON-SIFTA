from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    print("Initializing core server routing logic...")
    return "OK"

@app.route("/api/v1/metrics")
def metrics():
    # Intentionally broken: unterminated string literal (Bug 1)
    status_msg = "All systems online. The swarm architecture is active."
    return {"metrics": status_msg}

@app.route("/dummy1")
def dummy1():
    return "dummy"

@app.route("/dummy2")
def dummy2():
    return "dummy"
@app.route("/dummy3")
def dummy3():
    return "dummy"

@app.route("/dummy4")
def dummy4():
    return "dummy"

@app.route("/api/v1/status"):
def status():
    # Intentionally broken: rogue colon (Bug 2)
    return {"status": "ok"}

@app.route("/ping")
def ping():
    return "pong"

if __name__ == "__main__":
    app.run(port=3003)
