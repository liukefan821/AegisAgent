# scripts

Deployment, gas reports, build scripts.
Owner: **HE Huzhengxiong**

## Modules

| Module | Purpose |
|---|---|
| `dev-setup.sh` | Guided one-click startup — prompts for mock/live mode, configures env files, starts all servers |
| `dev-lan.sh` | LAN server runner — detects LAN IP, starts frontend and TEE agent for phone testing |

See the [root README](../README.md#quick-start) for how to use `dev-setup.sh`.

## Manual Setup (without script)

If `dev-setup.sh` fails or you prefer to start services manually, follow the
steps below.

### Mock mode (frontend only)

```bash
cd frontend
npm install
cp .env.example .env.local
# .env.local already has NEXT_PUBLIC_USE_MOCK=true by default
npm run dev
```

Open http://localhost:3000.

### Live mode (frontend + TEE agent)

**Terminal 1 — TEE agent:**

```bash
cd tee-agent
pip install -r requirements.txt
cp .env.example .env.local
```

Edit `tee-agent/.env.local`:

```
LLM_PROVIDER=gemini
GEMINI_API_KEY=<your-key>
GEMINI_MODEL=gemini-2.5-flash-lite
AEGIS_MOCK_QUOTE=true
ENCLAVE_IMAGE_HASH=0x0000000000000000000000000000000000000000000000000000000000000001
MOCK_MR_ENCLAVE=0000000000000000000000000000000000000000000000000000000000000001
AEGIS_FRONTEND_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Start the server:

```bash
uvicorn aegis_agent.main:app --host 0.0.0.0 --port 8080
```

**Terminal 2 — Frontend:**

```bash
cd frontend
npm install
cp .env.example .env.local
```

Edit `frontend/.env.local`:

```
NEXT_PUBLIC_USE_MOCK=false
NEXT_PUBLIC_VAULT_ADDRESS=0x4d046e39071b5650b6486e4997f7e5629cdf3f1d
NEXT_PUBLIC_REGISTRY_ADDRESS=0x77c75bd03df409906130fde880b3c9303ff35227
NEXT_PUBLIC_VERIFIER_ADDRESS=0x5c949780db9482ab63dd004a23d2d82b719176fd
NEXT_PUBLIC_AGENT_URL=http://localhost:8080
```

Start the dev server:

```bash
npm run dev
```

Open http://localhost:3000.
