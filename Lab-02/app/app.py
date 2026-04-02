import csv, json, io
from flask import Flask, request, jsonify
from storage import read_csv, write_json

app = Flask(__name__)

PRECIOS = {
    "TORNILLO-M6": 12.50,
    "TUERCA-M6":    8.75,
    "DISCO-CORTE":  2.80,
    "CASCO":       22.00,
}

@app.route("/health")
def health():
    return jsonify({"status": "ok", "backend": __import__('os').getenv("STORAGE_BACKEND","LOCAL")})

@app.route("/cotizar", methods=["POST"])
def cotizar():
    data = request.get_json()
    csv_text = read_csv(data["archivo"])

    items, total = [], 0
    for row in csv.DictReader(io.StringIO(csv_text)):
        precio = PRECIOS.get(row["sku"], 0)
        subtotal = precio * int(row["cantidad"])
        items.append({"sku": row["sku"], "cantidad": row["cantidad"],
                      "precio": precio, "subtotal": subtotal})
        total += subtotal

    resultado = json.dumps({"cliente": data.get("cliente","N/A"),
                             "items": items, "igv": round(total*0.18,2),
                             "total": round(total*1.18,2)}, indent=2)

    salida = data["archivo"].replace(".csv", "_cotizacion.json")
    url = write_json(salida, resultado)
    return jsonify({"total": round(total*1.18,2), "archivo_salida": url})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)