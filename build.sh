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
