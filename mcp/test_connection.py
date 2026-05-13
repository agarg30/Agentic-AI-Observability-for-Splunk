import urllib.request, ssl, base64, json
from pathlib import Path

env = {}
for line in Path('.env').read_text().splitlines():
    if '=' in line and not line.startswith('#'):
        k, _, v = line.partition('=')
        env[k.strip()] = v.strip()

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Test 1: Basic auth
creds = base64.b64encode(f"{env['SPLUNK_USERNAME']}:{env['SPLUNK_PASSWORD']}".encode()).decode()

payload = json.dumps({
    'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
    'params': {'protocolVersion': '2024-11-05', 'clientInfo': {'name': 'test', 'version': '1.0'}, 'capabilities': {}}
}).encode()

for label, auth in [("Basic Auth", f"Basic {creds}"), ("Bearer Token", f"Bearer {env.get('MCP_AUTH_TOKEN','')}")]:
    req = urllib.request.Request(
        'https://localhost:8089/services/mcp', data=payload,
        headers={'Authorization': auth, 'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            print(f"{label}: {r.status} OK")
            print(r.read().decode()[:300])
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        print(f"{label}: HTTP {e.code} {e.reason}")
        print(body[:300])
    print()
