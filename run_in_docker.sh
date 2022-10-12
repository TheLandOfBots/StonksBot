#!/bin/sh

docker run --env-file .env --volume `pwd`/data/:/app/data/ igorpidik/stonks_bot:latest
