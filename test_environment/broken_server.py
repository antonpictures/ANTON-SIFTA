from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    print("Initializing core server routing logic...")
    return "OK"

@app.route("/api/v1/status")
def status():
    # Intentionally broken: unterminated string literal
    status_msg = "All systems online. The swarm architecture is active.
    return {"status": status_msg}

@app.route("/ping")
def ping():
    return "pong"

if __name__ == "__main__":
    app.run(port=3003)
