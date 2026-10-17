"""Private-LAN TLS pairing; the laptop remains the only inference host."""
import base64
import hashlib
import io
import ipaddress
import json
import secrets
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
import qrcode
import qrcode.image.svg

def lan_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(("1.1.1.1", 80))  # Chooses a local route; sends no UDP packet.
            return sock.getsockname()[0]
        except OSError:
            return "127.0.0.1"

def prepare(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    config_path = directory / "pairing.json"
    config = json.loads(config_path.read_text()) if config_path.exists() else {"token":secrets.token_urlsafe(32)}
    now = datetime.now(timezone.utc)
    ca_key_path, ca_path = directory / "ca-key.pem", directory / "ca.pem"
    if not ca_path.exists():
        key = rsa.generate_private_key(public_exponent=65537,key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "YouAI private laptop CA")])
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(days=1))
                .not_valid_after(now+timedelta(days=3650)).add_extension(x509.BasicConstraints(ca=True,path_length=0),True)
                .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),False)
                .add_extension(x509.KeyUsage(False,False,False,False,False,True,True,None,None),True)
                .sign(key,hashes.SHA256()))
        ca_key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        ca_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    ca_key = serialization.load_pem_private_key(ca_key_path.read_bytes(),password=None)
    ca = x509.load_pem_x509_certificate(ca_path.read_bytes())
    try:
        ca.extensions.get_extension_for_class(x509.SubjectKeyIdentifier)
    except x509.ExtensionNotFound:
        builder = (x509.CertificateBuilder().subject_name(ca.subject).issuer_name(ca.issuer)
            .public_key(ca_key.public_key()).serial_number(ca.serial_number)
            .not_valid_before(ca.not_valid_before_utc).not_valid_after(ca.not_valid_after_utc))
        for extension in ca.extensions:
            builder = builder.add_extension(extension.value, extension.critical)
        ca = builder.add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),False).sign(ca_key,hashes.SHA256())
        ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
        config.pop('host',None)
    address = lan_ip()
    leaf_path = directory / "server.pem"
    renew = not leaf_path.exists() or (leaf_path.exists() and x509.load_pem_x509_certificate(leaf_path.read_bytes()).not_valid_after_utc < now + timedelta(days=7))
    if config.get("host") != address or renew:
        key = rsa.generate_private_key(public_exponent=65537,key_size=2048)
        cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,"YouAI laptop")]))
            .issuer_name(ca.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now-timedelta(days=1)).not_valid_after(now+timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=False,path_length=None),True)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),False)
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(address)),
                x509.IPAddress(ipaddress.ip_address("127.0.0.1")),x509.DNSName("localhost")]),False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),False)
            .sign(ca_key,hashes.SHA256()))
        (directory/"server-key.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        (directory/"server.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM)+ca.public_bytes(serialization.Encoding.PEM))
    config.update(host=address,port=8768,pin=ca.fingerprint(hashes.SHA256()).hex())
    config_path.write_text(json.dumps(config))
    return config

def read_config(directory):
    path = directory / "pairing.json"
    return json.loads(path.read_text()) if path.exists() else None

def pairing(config):
    url = f"https://{config['host']}:{config['port']}"
    link = "youai://pair?" + urlencode({"url":url,"token":config["token"],"pin":config["pin"]})
    image = qrcode.make(link,image_factory=qrcode.image.svg.SvgPathImage)
    output = io.BytesIO(); image.save(output)
    return {"url":url,"link":link,"qr":"data:image/svg+xml;base64,"+base64.b64encode(output.getvalue()).decode()}

def valid_token(value, config):
    return bool(config and value and secrets.compare_digest(value, config["token"]))
