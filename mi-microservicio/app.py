from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/")
def hola():
    return jsonify({"mensaje": "hola mundo"})

app.run(host="0.0.0.0", port=5000)