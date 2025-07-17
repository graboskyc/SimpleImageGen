import uvicorn


if __name__ == "__main__":
    # Set your certificate and key file paths here
    certfile = "cert.pem"  # Path to your TLS certificate
    keyfile = "key.pem"    # Path to your TLS private key
    uvicorn.run(
        "app.api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        ssl_certfile=certfile,
        ssl_keyfile=keyfile
    )