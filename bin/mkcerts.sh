if [ "$1" = "" ]
then
    echo "Usage: $0 cert-name" >&2
    exit 1
fi
if [ "$2" = "" ]
then
    ROOT="./"
else
    ROOT="$2"
fi
CERT_NAME="$1"
CERT_FILE="${ROOT}etc/ssl/certs/$CERT_NAME.pem"
CERT_KEY="${ROOT}etc/ssl/private/$CERT_NAME.key"
set -x
if [ ! -r "$CERT_FILE" -o ! -r "$CERT_KEY" ]
then
    openssl genrsa -out "$CERT_NAME.key" 2048
    openssl req -x509 -new -nodes -key "$CERT_NAME.key" -sha256 -days 1024 -out "$CERT_NAME.pem" << EOF 
US
Louisiana
Baton Rouge
Louisiana State University
Center for Computation and Technology
localhost
sbrandt@cct.lsu.edu
EOF
    mkdir -p etc/ssl/private
    cp "$CERT_NAME.key" "$CERT_KEY"

    mkdir -p etc/ssl/certs
    cp "$CERT_NAME.pem" "$CERT_FILE"
fi

#c.JupyterHub.ssl_cert = '/etc/ssl/certs/etk.cct.lsu.edu.cer'
#c.JupyterHub.ssl_key =  '/etc/ssl/private/etk.cct.lsu.edu.key'
#c.JupyterHub.ssl_ciphers =  'ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384'
