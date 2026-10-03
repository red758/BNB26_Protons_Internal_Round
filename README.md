# ProvLedger (ModelLedger)

**Cryptographic Provenance & Lineage Verification Engine for AI Assets**

ProvLedger provides end-to-end verification, C2PA manifest extraction/injection, salted prompt commitments, and resilient neural embedding similarity search (via ResNet/CLIP + pgvector HNSW) against adversarial image manipulations (compression, cropping, transforms).

---

## 📁 Repository Structure

```
.
├── docker-compose.yml              # Runs Postgres + pgvector, Backend, Frontend
├── .gitignore
├── README.md
│
├── backend/                        # Python FastAPI High-Throughput Engine
│   ├── Dockerfile                  # Python 3.11, C2PA deps, PyTorch
│   ├── requirements.txt            # FastAPI, pgvector, torch, c2pa, Pillow
│   ├── .env.example                # Configuration template
│   ├── main.py                     # FastAPI application entry point & CORS
│   ├── app/
│   │   ├── config.py               # Pydantic Settings
│   │   ├── api/                    # Registration & Verification REST routes
│   │   │   ├── registration.py     # AI artifact ingest -> embedding -> ledger anchor
│   │   │   └── verification.py     # Stream upload -> HNSW visual lookup & C2PA check
│   │   ├── core/                   # Cryptographic & ML Engines
│   │   │   ├── inference.py        # ResNet/CLIP neural embedding feature vector extractor
│   │   │   ├── crypto.py           # Salted prompt commitments & attestation signing
│   │   │   └── c2pa_engine.py      # C2PA manifest parser and injection engine
│   │   └── database/               # State persistence & similarity indexing
│   │       ├── connection.py       # Connection pooling & health checks
│   │       └── repository.py       # pgvector HNSW search & ledger records
│   └── tests/
│       └── test_adversarial.py     # Cropping/compression robustness test suite
│
└── frontend/                       # Next.js UI Application Tier
    ├── Dockerfile                  # Production multi-stage build
    ├── package.json
    ├── tailwind.config.js
    ├── next.config.js
    ├── .env.example
    └── src/
        ├── app/                    # Next.js App Router
        │   ├── layout.tsx
        │   ├── page.tsx            # Main Landing / Dashboard Workspace
        │   ├── register/page.tsx   # AI Model Developer Registry Screen
        │   └── verify/page.tsx     # Public Lineage Verification Portal Dropzone
        ├── components/             # Reusable UI Blocks & Interactive Trees
        │   ├── ui/                 # Buttons, Inputs, Cards
        │   ├── DragDropZone.tsx    # Drag-and-drop file stream dropzone
        │   └── LineageTree.tsx     # Asset origin & parent chain graph visualizer
        └── services/
            └── client.ts           # Axios client integrated with backend APIs
```

---

## 🚀 Getting Started

### 1. Launch with Docker Compose (Recommended)

```bash
docker-compose up --build
```

- **Frontend UI:** http://localhost:3000
- **Backend API & Swagger Docs:** http://localhost:8000/docs
- **PostgreSQL pgvector Database:** `localhost:5432`

---

### 2. Manual Local Setup

#### Backend (FastAPI)
```bash
cd backend
python -m venv venv
# On Windows: venv\Scripts\activate | On Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

#### Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev
```

---

## 🧪 Running Adversarial Robustness Tests

```bash
cd backend
python -m unittest tests/test_adversarial.py
```
