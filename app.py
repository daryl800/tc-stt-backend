from flask import Flask, request, jsonify
from classify import classify_text

app = Flask(__name__)

@app.route("/classify", methods=["POST"])
def classify():
    content = request.json.get("text", "")
    try:
        category = classify_text(content)
        return jsonify({"category": category})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
