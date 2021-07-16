#!/bin/sh
# See ingress-istio.yaml and its TLS configuration

# Generate a route certificate and store somewhere super safe (HSM ideally)
openssl req -x509 -sha256 -nodes -days 365 -newkey rsa:4096 -subj '/O=Spring Music Inc./CN=adamfowler.co.uk' -keyout adamfowler.co.uk.key -out adamfowler.co.uk.crt

# Certificate signing request for child cert
openssl req -out sm.adamfowler.co.uk.csr -newkey rsa:4096 -nodes -keyout sm.adamfowler.co.uk.key -subj "/CN=sm.adamfowler.co.uk/O=springmusic organization"
# Generate of child cert
openssl x509 -req -days 365 -CA adamfowler.co.uk.crt -CAkey adamfowler.co.uk.key -set_serial 0 -in sm.adamfowler.co.uk.csr -out sm.adamfowler.co.uk.crt
