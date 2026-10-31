
from flask import Flask
from genai_service.router import router

# Create Flask application
app = Flask(__name__)

# Register GenAI Blueprint
app.register_blueprint(router)


# Home route
@app.route("/", methods=["GET"])
def home():
    return {
        "message": "ResolveAI GenAI Service is running!",
        "status": "success"
    }


# Run Flask application
if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5001,
        debug=True
    )
