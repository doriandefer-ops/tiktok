# Utilise les certificats de sécurité du système (Windows/Mac) pour les connexions HTTPS.
# Évite l'erreur CERTIFICATE_VERIFY_FAILED (antivirus, proxy d'entreprise...).
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass
