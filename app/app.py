from flask import Flask, jsonify
import csv

app = Flask(__name__)

@app.route('/')
def home():
    with open('traffic_data.csv', 'r') as f:
        data = list(csv.DictReader(f))
    return jsonify(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
