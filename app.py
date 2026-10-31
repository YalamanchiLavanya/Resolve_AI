from flask import Flask, jsonify
from aiml_service.router import router

app = Flask(__name__)
app.register_blueprint(router)


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "ResolveAI AIML Flask Service is running!",
        "status": "success"
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "aiml"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
