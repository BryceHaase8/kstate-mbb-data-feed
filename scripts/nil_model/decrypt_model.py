#!/usr/bin/env python3
"""Decrypt fitted model inside the GitHub Actions runner only. Never print key or output."""
import os,base64,pathlib,sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
base=pathlib.Path(__file__).resolve().parent
secret=os.environ.get('NIL_MODEL_KEY','').strip()
if not secret:sys.exit('NIL_MODEL_KEY missing. Do not publish new NIL valuations.')
try:
 key=base64.b64decode(secret,validate=True)
 if len(key)!=32:raise ValueError('Invalid key length')
 payload=(base/'model.joblib.aesgcm').read_bytes()
 if not payload.startswith(b'NILMODEL1') or len(payload)<50:raise ValueError('Invalid model envelope')
 raw=AESGCM(key).decrypt(payload[9:21],payload[21:],b'NIL Model CatBoost model artifact v1')
 (base/'nil_estimation_model_core_shadow.joblib').write_bytes(raw)
 print('Decrypted NIL Estimation Model artifact in isolated runner. Bytes:',len(raw))
except Exception as e:
 sys.exit('Model decryption failed: incorrect secret or corrupted encrypted artifact')
