#!/bin/sh
set -eu
mkdir -p /etc/nginx/certs
if [ ! -s /etc/nginx/certs/tls.crt ] || [ ! -s /etc/nginx/certs/tls.key ]; then
  openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/certs/tls.key \
    -out /etc/nginx/certs/tls.crt \
    -subj "/CN=${TLS_CN:-localhost}"
fi
