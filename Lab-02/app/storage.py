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