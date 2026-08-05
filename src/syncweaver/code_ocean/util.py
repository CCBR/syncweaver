from codeocean import CodeOcean
import os


def auth_client(domain="poc-nci.codeocean.io", token=None):
    if token is None:
        token = os.getenv("CODE_OCEAN_TOKEN")
    client = CodeOcean(domain=f"https://{domain}", token=token)
    return client
