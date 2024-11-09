from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/", methods=['GET'])
def home():
    return "Hello, this is your Flask server!"

# Webhook 路徑，LINE Bot 會在這裡傳送請求
@app.route("/webhook", methods=['POST'])
def webhook():
    data = request.json
    print("Received data:", data)
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(port=5000)
