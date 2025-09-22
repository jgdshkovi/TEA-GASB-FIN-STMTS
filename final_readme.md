# TEA Financial Statement Generator — Final README

A full-stack application that processes Texas school district trial balances and generates TEA/GASB-formatted financial statements with audit Trial, mapping tools, and export capabilities.

## Overview

- Backend: FastAPI (Python) with SQLite storage
- Frontend: Next.js + React + TypeScript
- Data: pandas transformations, Excel (openpyxl) and CSV exports
- Auth: Minimal JWT auth (custom), Bearer tokens

## Features

- File Upload & Parsing
  - Auto-detects encoding and delimiter (tab, comma, pipe, semicolon, single/double space)
  - Robust parsing of ASCII/CSV with normalization (numeric coercion, empty-row removal)
- Account Mapping
  - Auto-map from uploaded trial balance to default TEA/GASB buckets
  - Paginated mapping fetch and save; server-side validation
  - Delete-all resets mappings and clears audit Trial
- Financial Statements
  - Generates Government-wide and Governmental Funds statements (multiple statements combined)
- Audit Trial
  - Detailed, per-account, line-level mapping breakdown with statement line mapping and roll-up notes
  - Export audit Trial to CSV
- Export
  - Excel export with multiple sheets and basic formatting
- Frontend
  - Modern React UI (upload, mapping, statements, export, audit)
  - Authentication flow and API client with token handling

## Project Structure

```
├── main.py                      # FastAPI app and all business endpoints
├── simple_auth_endpoints.py     # Lightweight JWT auth + SQLite persistence helpers
├── mapping_rules.py             # Mapping helpers and validation
├── uploads/                     # Uploaded files
├── frontend/                    # Next.js app
│   ├── components/              # UI sections
│   ├── pages/                   # Next.js pages (index, login, register)
│   ├── services/api.ts          # API client and types
│   └── ...
├── requirements.txt             # Python deps
└── tea_financial.db             # SQLite database (created on first run)
```

## Prerequisites

- Python 3.10+
- Node.js 18+

## Backend Setup

1) Install Python dependencies
```bash
pip install -r requirements.txt
```

2) Run the API
```bash
python main.py
```
- Default: http://localhost:8000
- SQLite DB file: `tea_financial.db` (auto-initialized)

### Environment and Config
- CORS: allow-all for development
- Upload dir: `uploads/` (auto-created)
- Max file size: 25 MB
- Allowed extensions: .txt, .csv, .asc, or no extension
- JWT config (dev defaults, change for prod):
  - SECRET_KEY in `simple_auth_endpoints.py`
  - ALGORITHM HS256
  - ACCESS_TOKEN_EXPIRE_MINUTES 30

## Frontend Setup

1) Install deps
```bash
cd frontend
npm install
```

2) Start dev server
```bash
npm run dev
```
- Default: http://localhost:3000

3) Configure API base URL (optional)
- `NEXT_PUBLIC_API_BASE_URL` (defaults to `http://localhost:8000`)

## Authentication

- Endpoints under `/auth` (JWT, Bearer token):
  - POST `/auth/register` — body: `{ email, password, first_name?, last_name?, organization? }`
  - POST `/auth/login` — form data: `username` (email), `password`; returns `{ access_token, token_type }`
  - GET `/auth/me` — requires `Authorization: Bearer <token>`
- All core API routes require a valid Bearer token.

## Core API Endpoints

Base path: `http://localhost:8000`

- GET `/` — health/version

- POST `/api/upload` — Upload and parse TB
  - form-data: `file` (ASCII/CSV)
  - returns: `{ success, message, file_info { filename, encoding, delimiter, rows, columns } }`

- GET `/api/data` — Get last uploaded TB
  - returns: `{ data: any[][], file_info }`

- GET `/api/mapping` — Get mappings (paginated)
  - query: `page` (default 1), `page_size` (default 100), `search?`
  - returns: `{ mappings: Record<string, any>, pagination }`

- POST `/api/mapping/auto-map` — Auto-generate default mappings from TB
  - returns: `{ success, message, mappings, pagination }`

- POST `/api/mapping` — Save mappings
  - body: `Record<account_code, mapping>`
  - returns: `{ success, message, validation }`

- DELETE `/api/mapping` — Delete all mappings and audit Trial
  - returns: `{ success, message }`

- POST `/api/generate-statements` — Generate statements from TB + mappings
  - returns: `{ success, statements }`

- GET `/api/export/excel` — Download Excel workbook of statements
  - returns: XLSX file (binary)

- GET `/api/audit-Trial` — Build comprehensive audit data set
  - returns: `{ success, audit_data[], total_records, mapped_records, unmapped_records, file_info }`

- GET `/api/export/audit-Trial` — Download audit Trial CSV
  - returns: CSV file (binary)

All the above (except `/`) require `Authorization: Bearer <token>`.

## Frontend API Client (excerpt)

- `frontend/services/api.ts` configures `axios` with `NEXT_PUBLIC_API_BASE_URL` and injects `Authorization` header from `localStorage` token.
- Intercepts 401s to clear token and redirect to `/login`.
- Exposes typed functions: `uploadFile`, `getFileData`, `getMapping`, `saveMapping`, `deleteAllMappings`, `autoMapAccounts`, `generateStatements`, `exportToExcel`, `getAuditTrial`, `exportAuditTrial`, `login`, `register`, `getCurrentUser`, `logout`.

## Data Flow

1) Upload Trial Balance (TB) file → server detects encoding/delimiter and parses with pandas → saves JSON to SQLite per user
2) Auto-map or manually save mappings → mappings stored per user (unique by `user_id, account_code`)
3) Generate statements → aggregates TB + mappings → stores combined result per user
4) Export Excel → formats each statement into a worksheet
5) Build/export audit Trial → detailed mapping and roll-up info per account

## Statement Coverage (current)

- Statement of Net Position (government-wide)
- Statement of Activities (government-wide)
- Balance Sheet — Governmental Funds
- Statement of Revenues, Expenditures, and Changes in Fund Balances — Governmental Funds

## Validation & Roll-ups

- Server validates mapping completeness upon save
- Roll-up heuristics on object code ranges for aggregation into canonical lines (e.g., cash equivalents, receivables, liabilities)

## Security Notes

- Replace `SECRET_KEY` and configure with environment variables in production
- Consider HTTPS, stricter CORS, and longer token rotation policies

## Testing & Demo

- Start backend and frontend locally
- Register a user → Login → Upload Trial Balance → Auto-map → Generate statements → Export Excel → View/export Audit Trial

## Deployment

- Dockerfiles and Procfile included for common platforms (Render, Vercel, Heroku)
- Ensure persistent storage for `tea_financial.db` or migrate to managed DB
- Set `NEXT_PUBLIC_API_BASE_URL` in frontend environment

## Known Limitations

- SQLite single-file database (no migrations)
- Simplified statement logic; mappings may need refinement for district-specific COA
- Basic auth flow (no refresh tokens, minimal policy)

## License

Demo for AI & Automation Engineer case study.
