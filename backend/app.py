from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json()
    input_value = data.get("input")
    result = f"Cozy score for '{input_value}' is 87%"
    return jsonify({"result": result})

if __name__ == "__main__":
    app.run(port=5000)
