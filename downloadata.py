import os
import requests
import urllib3

# ── SSL bypass for corporate Cisco proxy ─────────────────────────────────────
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_orig_send = requests.Session.send
def _insecure_send(self, request, **kwargs):
    kwargs["verify"] = False
    return _orig_send(self, request, **kwargs)
requests.Session.send = _insecure_send
# ─────────────────────────────────────────────────────────────────────────────

import kagglehub

# Download latest version
path = kagglehub.dataset_download("nafisbarizki/daftar-harga-rumah-jabodetabek")

print("Path to dataset files:", path)
