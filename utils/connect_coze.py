import os
import uuid
import jwt
import time
import requests

def connect_coze():
# 读取私钥
    path = os.path.dirname(os.path.abspath(__file__))
    with open(f"{path}/private_key.pem", "r") as f:
        private_key = f.read()

    header = {
        "alg": "RS256",
        "typ": "JWT",
        "kid": "oVHi6clkKMcuM5oSfZB4vWLkeGdrcLUNRY5Hqdis6g8"
    }

    #JWT开始生效的时间，秒级时间戳
    iat = int(time.time())
    exp = iat + 86400
    jti = uuid.uuid4().hex

    payload = {
        "iss": "1154636721069",
        "aud": "api.coze.cn",
        "iat": iat,
        "exp": exp,
        "jti": f"{jti}"
    }

    token = jwt.encode(payload, private_key, algorithm="RS256", headers=header)
    header = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    data = {
        "duration_seconds": 86399,
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer"
    }

    url = "https://api.coze.cn/api/permission/oauth2/token"
    resp = requests.post(url, headers=header, json=data)
    access_token = resp.json().get("access_token", None)
    return access_token

