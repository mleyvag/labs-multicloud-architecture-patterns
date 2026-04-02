# 🧪 Lab 01 — De Docker Compose On-Premise a CaaS en Azure
### *Cotizador de insumos: del servidor local al cloud sin tocar la lógica*

**Nivel:** Intermedio | **Duración:** 60 min | **Plataforma:** Azure + Docker

---

## 1. Objetivo y Alcance

Migrar un servicio de cotización que corre con Docker Compose en un servidor local hacia **Azure Container Apps**, cambiando únicamente la configuración de almacenamiento, sin modificar la lógica de negocio.

| Componente | On-Premise | Azure |
|---|---|---|
| Ejecución | Docker Compose | Azure Container Apps |
| Almacenamiento entrada (CSV) | Carpeta local `/input` | Azure Blob Storage → `input` |
| Almacenamiento salida (JSON) | Carpeta local `/output` | Azure Blob Storage → `output` |

---

## 2. Prerrequisitos

```bash
docker --version          # Docker 24+
docker compose version    # Compose v2
az --version              # Azure CLI 2.55+
az login
```

**Variables del laboratorio — define esto primero:**

```bash
export RG="rg-lab01"
export LOCATION="eastus2"
export SA="stlab01$(shuf -i 1000-9999 -n 1)"
export ACR="acrlab01$(shuf -i 1000-9999 -n 1)"
export ACA_ENV="env-lab01"
export ACA_APP="ca-cotizador"
```

---

## 3. El Problema

La empresa **LogiStock** tiene un cotizador que corre en un servidor físico de oficina con Docker Compose. El servicio lee un CSV con productos, calcula precios y guarda el resultado en una carpeta local.

**El problema:** si el servidor se apaga, el servicio cae. No hay acceso remoto fácil ni escalado.

**La solución:** mover el contenedor a Azure sin reescribir código.

---

## 4. Estructura del Proyecto

```
lab-01/
├── app.py                  ← API Flask (lógica de negocio)
├── storage.py              ← Abstracción LOCAL / AZURE_BLOB
├── requirements.txt
├── Dockerfile
├── docker-compose.yml      ← Configuración on-premise
└── input/
    └── pedido.csv          ← Archivo de prueba
```

---

## 5. Laboratorio Guiado

### Parte A — Construir el Sistema Local

**Paso 1 — Crear la carpeta del proyecto**

```bash
mkdir lab-01 && cd lab-01
mkdir input output
```

**Paso 2 — `storage.py` (la capa que cambia entre local y Azure)**

```python
# storage.py
import os

BACKEND = os.getenv("STORAGE_BACKEND", "LOCAL")

def read_csv(filename):
    if BACKEND == "AZURE_BLOB":
        from azure.storage.blob import BlobServiceClient
        client = BlobServiceClient.from_connection_string(os.environ["AZURE_CONN_STR"])
        blob = client.get_blob_client(container="input", blob=filename)
        return blob.download_blob().readall().decode("utf-8")
    else:
        with open(f"/app/input/{filename}") as f:
            return f.read()

def write_json(filename, content):
    if BACKEND == "AZURE_BLOB":
        from azure.storage.blob import BlobServiceClient
        client = BlobServiceClient.from_connection_string(os.environ["AZURE_CONN_STR"])
        blob = client.get_blob_client(container="output", blob=filename)
        blob.upload_blob(content.encode(), overwrite=True)
        return f"https://{client.account_name}.blob.core.windows.net/output/{filename}"
    else:
        path = f"/app/output/{filename}"
        with open(path, "w") as f:
            f.write(content)
        return path
```

**Paso 3 — `app.py` (lógica de negocio — no cambia en la migración)**

```python
# app.py
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
```

**Paso 4 — `requirements.txt`**

```
flask==3.0.3
gunicorn==22.0.0
azure-storage-blob==12.19.0
```

**Paso 5 — `Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py storage.py ./
RUN mkdir -p /app/input /app/output
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
```

**Paso 6 — `docker-compose.yml` (configuración on-premise)**

```yaml
services:
  cotizador:
    build: .
    ports:
      - "5000:5000"
    environment:
      - STORAGE_BACKEND=LOCAL
    volumes:
      - ./input:/app/input
      - ./output:/app/output
```

**Paso 7 — Archivo de prueba `input/pedido.csv`**

```csv
sku,cantidad
TORNILLO-M6,100
TUERCA-M6,100
DISCO-CORTE,10
CASCO,5
```

**Paso 8 — Probar en local**

```bash
docker compose up --build -d

# Health check
curl http://localhost:5000/health

# Generar cotización
curl -X POST http://localhost:5000/cotizar \
  -H "Content-Type: application/json" \
  -d '{"archivo": "pedido.csv", "cliente": "Constructora ABC"}'

# Ver el JSON generado localmente
cat output/pedido_cotizacion.json

docker compose down
```

> ✅ Sistema on-premise funcionando. Ahora lo llevamos a Azure.

---

### Parte B — Migrar a Azure

**Paso 1 — Crear infraestructura Azure**

```bash
# Resource Group
az group create --name $RG --location $LOCATION

# Storage Account
az storage account create --name $SA --resource-group $RG \
  --location $LOCATION --sku Standard_LRS

# Obtener connection string
export CONN_STR=$(az storage account show-connection-string \
  --name $SA --resource-group $RG --query connectionString -o tsv)

# Crear contenedores blob
az storage container create --name input  --connection-string "$CONN_STR"
az storage container create --name output --connection-string "$CONN_STR"

# Subir el CSV de prueba
az storage blob upload --container-name input \
  --file ./input/pedido.csv --name pedido.csv \
  --connection-string "$CONN_STR"
```

**Paso 2 — Publicar imagen en ACR**

```bash
az acr create --resource-group $RG --name $ACR --sku Basic --admin-enabled true

az acr build --registry $ACR --image cotizador:v1 --resource-group $RG .
```

**Paso 3 — Crear el entorno de Container Apps**

```bash
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App

az containerapp env create \
  --name $ACA_ENV --resource-group $RG --location $LOCATION
```

**Paso 4 — Desplegar la Container App**

```bash
ACR_USER=$(az acr credential show --name $ACR --query username -o tsv)
ACR_PASS=$(az acr credential show --name $ACR --query passwords[0].value -o tsv)

az containerapp create \
  --name $ACA_APP \
  --resource-group $RG \
  --environment $ACA_ENV \
  --image "${ACR}.azurecr.io/cotizador:v1" \
  --registry-server "${ACR}.azurecr.io" \
  --registry-username $ACR_USER \
  --registry-password $ACR_PASS \
  --target-port 5000 \
  --ingress external \
  --min-replicas 0 --max-replicas 3 \
  --env-vars "STORAGE_BACKEND=AZURE_BLOB" \
  --secrets "connstr=$CONN_STR" \
  --env-vars "STORAGE_BACKEND=AZURE_BLOB" "AZURE_CONN_STR=secretref:connstr"
```

**Paso 5 — Probar en Azure**

```bash
URL=$(az containerapp show --name $ACA_APP --resource-group $RG \
  --query "properties.configuration.ingress.fqdn" -o tsv)

# Health check
curl "https://$URL/health"

# Cotizar desde Azure
curl -X POST "https://$URL/cotizar" \
  -H "Content-Type: application/json" \
  -d '{"archivo": "pedido.csv", "cliente": "Constructora ABC"}'
```

**Resultado esperado:**
```json
{
  "total": 2145.90,
  "archivo_salida": "https://stlab01xxxx.blob.core.windows.net/output/pedido_cotizacion.json"
}
```

**Verificar el JSON en el blob de salida:**
```bash
az storage blob list --container-name output \
  --connection-string "$CONN_STR" --output table
```

---

## 6. Laboratorio Propuesto

Agrega un segundo endpoint `POST /subir` que reciba un CSV vía `multipart/form-data` y lo suba directamente al Blob Storage sin usar la CLI.

```bash
curl -X POST "https://$URL/subir" -F "file=@./input/pedido.csv"
```

Criterios:
- Funciona con `STORAGE_BACKEND=AZURE_BLOB` (sube al blob `input`).
- Funciona con `STORAGE_BACKEND=LOCAL` (guarda en `/app/input`).
- Retorna la ruta o URL del archivo subido.

---

## 7. Limpieza

```bash
az group delete --name $RG --yes --no-wait
echo "✅ Recursos eliminados."
```
