# Mechanical Design Partner (Copilot)

## 🚀 Getting Started

### Prerequisites
- Node.js 18+
- Python 3.10+

### Automatic Startup
Run the creation script to launch both Frontend and Backend:
```bash
start_all.bat
```

### Manual Startup

**Backend (FastAPI)**
```bash
conda env create -f backend/environment.yml
conda activate mech_copilot_v2
cd backend
python main.py
```
*Runs on http://localhost:8000*

**Frontend (Next.js)**
```bash
cd frontend
npm install
npm run dev
```
*Runs on http://localhost:3000*

## 🏗️ Architecture
- **Frontend**: Next.js 14, TailwindCSS, React-Katex.
- **Backend**: FastAPI, LangChain (Mocked), Pint (Units).
- **Database**: ChromaDB (Local Vector Store).

## ✨ Features
- **Dynamic Tool Generation**: The AI creates calculators on the fly based on your query.
- **Expert Chat**: Context-aware mechanical engineering advice.
