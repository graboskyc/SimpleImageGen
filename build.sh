#!/bin/bash

echo
echo "+================================"
echo "| START: SimpleImageGen"
echo "+================================"
echo

source backend/.env

datehash=`date | md5sum | cut -d" " -f1`
abbrvhash=${datehash: -8}

echo
echo "Checking for TLS cert.pem and key.pem..."
if [ ! -f backend/cert.pem ] || [ ! -f backend/key.pem ]; then
    echo "Generating self-signed TLS certificate (cert.pem, key.pem) in backend/"
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout backend/key.pem -out backend/cert.pem \
        -subj "/C=US/ST=State/L=City/O=SimpleImageGen/CN=localhost"
else
    echo "TLS certificate and key already exist."
fi

echo
echo "Building container using tag ${abbrvhash}"
echo
docker build -t graboskyc/sig:latest -t graboskyc/sig:${abbrvhash} .

EXITCODE=$?

if [ $EXITCODE -eq 0 ]
    then

    echo 
    echo "Starting container"
    echo
    docker stop sig
    docker rm sig
    docker run -t -i -d -p 9999:8000 --name sig -e "FIREWORKSKEY=${FIREWORKSKEY}" --restart unless-stopped graboskyc/sig:${abbrvhash}

    echo
    echo "+================================"
    echo "| END:  SimpleImageGen"
    echo "+================================"
    echo
else
    echo
    echo "+================================"
    echo "| ERROR: Build failed"
    echo "+================================"
    echo
fi
