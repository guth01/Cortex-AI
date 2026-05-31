# Day 2 Complete — Document Library + Ingestion Pipeline ✅

## What Was Built

### 1. **Utilities** (`/utils/`)

#### **`file_parser.py`** — Extract text from documents
- ✅ PDF parsing with PyPDF2
- ✅ DOCX parsing with python-docx  
- ✅ Markdown and plain text parsing
- ✅ Multiple encoding support (UTF-8, Latin-1, CP1252)
- ✅ Page count extraction for PDFs
- ✅ Error handling for corrupt/scanned files

#### **`chunker.py`** — Split text into embedindable chunks
- ✅ 500 token chunks with 50 token overlap (configurable)
- ✅ Accurate token counting with tiktoken
- ✅ Metadata preservation (doc_id, filename, subject_id, chunk_index)
- ✅ Batch processing support

#### **`embedder.py`** — Generate text embeddings
- ✅ sentence-transformers/all-MiniLM-L6-v2 (384-dimensional vectors)
- ✅ Model loaded once on server startup (kept in memory)
- ✅ Single and batch embedding functions
- ✅ Cosine similarity helper
- ✅ First run downloads ~90MB (normal behavior)

---

### 2. **API Endpoints**

#### **POST /documents/upload**
Upload a document file with validation

**Request:**
```http
POST /documents/upload
Authorization: Bearer {token}
Content-Type: multipart/form-data

subject_id: "65abc123..."
file: lecture_3.pdf
```

**Validation:**
- File type: PDF, DOCX, MD, TXT only
- Max size: 20MB
- Non-empty file

**Response:**
```json
{
  "id": "65def456...",
  "user_id": "65abc123...",
  "subject_id": "65xyz789...",
  "filename": "lecture_3.pdf",
  "file_path": "./uploads/65abc123.../uuid_lecture_3.pdf",
  "source_type": "pdf",
  "file_size": 2048576,
  "uploaded_at": "2026-02-25T10:30:00",
  "page_count": 15
}
```

---

#### **GET /documents?subject_id={id}**
List user's uploaded documents

**Request:**
```http
GET /documents?subject_id=65xyz789
Authorization: Bearer {token}
```

**Response:**
```json
[
  {
    "id": "65def456...",
    "user_id": "65abc123...",
    "subject_id": "65xyz789...",
    "filename": "lecture_3.pdf",
    "file_path": "./uploads/65abc123.../uuid_lecture_3.pdf",
    "source_type": "pdf",
    "file_size": 2048576,
    "uploaded_at": "2026-02-25T10:30:00",
    "page_count": 15
  }
]
```

---

#### **DELETE /documents/{id}**
Delete document from database and disk

**Request:**
```http
DELETE /documents/65def456...
Authorization: Bearer {token}
```

**Response:**
```
204 No Content
```

**Behavior:**
- Deletes MongoDB record
- Deletes file from disk
- Only owner can delete

---

### 3. **Server Updates**

#### **Startup Enhancements:**
1. ✅ Creates `/uploads` directory
2. ✅ Loads embedding model (~5 seconds first run)
3. ✅ Creates index on `documents.user_id` + `subject_id`

#### **New Dependencies:**
```
python-docx==1.1.0           # DOCX parsing
sentence-transformers==2.3.1  # Embeddings
tiktoken==0.5.2              # Token counting
aiofiles==23.2.1             # Async file operations
```

---

## How to Test

### 1. **Install New Dependencies**

```bash
pip install -r requirements.txt
```

**Note:** First run will download embedding model (~90MB)

---

### 2. **Run Test Script**

```bash
python test_day2.py
```

**Tests:**
- ✅ File parsing (PDF, DOCX, MD, TXT)
- ✅ Chunking with token counting
- ✅ Embedding generation
- ✅ Full pipeline (parse → chunk → embed)

**Expected output:**
```
==============================================================
DAY 2 TEST SUITE
==============================================================

TEST 1: File Parser
✓ Parsed text (245 chars):...
✓ File info:
  Name: test_document.txt
  Size: 245 bytes
✅ File parser test PASSED

TEST 2: Text Chunker
Token count: 152 tokens
✓ Created 2 chunks
✅ Chunker test PASSED

TEST 3: Embedder
✓ Model loaded. Embedding dimension: 384
✓ Single embedding: Vector length: 384
✓ Batch embedding: 3 texts → 3 embeddings
✅ Embedder test PASSED

TEST 4: Full Pipeline
✓ Extracted 582 characters
✓ Created 5 chunks
✓ Generated 5 embeddings x 384
✅ Full pipeline test PASSED

🎉 ALL TESTS PASSED!
```

---

### 3. **Manual API Testing**

#### **Upload a Document**

```powershell
# Create a test PDF or text file first
"This is test content" | Out-File test.txt

# Upload it
$headers = @{Authorization="Bearer YOUR_TOKEN_HERE"}
$formData = @{
    subject_id = "YOUR_SUBJECT_ID"
    file = Get-Item -Path "test.txt"
}
Invoke-WebRequest -Uri "http://localhost:8000/documents/upload" `
    -Method POST -Headers $headers -Form $formData
```

#### **List Documents**

```powershell
$headers = @{Authorization="Bearer YOUR_TOKEN"}
Invoke-WebRequest -Uri "http://localhost:8000/documents" `
    -Headers $headers -UseBasicParsing | 
    Select-Object -ExpandProperty Content
```

#### **Delete Document**

```powershell
$headers = @{Authorization="Bearer YOUR_TOKEN"}
Invoke-WebRequest -Uri "http://localhost:8000/documents/DOCUMENT_ID" `
    -Method DELETE -Headers $headers
```

---

### 4. **Verify File Storage**

After uploading, check:

```bash
ls uploads/YOUR_USER_ID/
```

You should see: `{uuid}_{filename}`

---

## Day 2 Checklist ✅

- [x] File upload endpoint with validation
- [x] File parser for PDF, DOCX, MD, TXT
- [x] Chunker with 500 token chunks, 50 token overlap
- [x] Embedding model loaded on startup
- [x] GET /documents endpoint with filtering
- [x] DELETE /documents endpoint (DB + disk)
- [x] Files saved to `/uploads/{user_id}/{uuid}_{filename}`
- [x] Metadata stored in MongoDB `documents` collection
- [x] Test script verifies parse → chunk → embed pipeline

---

## Project Structure (Updated)

```
Study-agent/
├── server.py              # FastAPI app with document endpoints
├── models.py              # Pydantic models (added DocumentResponse)
├── auth.py                # JWT authentication
├── cleanup.py             # Orphaned session cleanup
├── test_day2.py           # Day 2 test suite
│
├── utils/
│   ├── __init__.py
│   ├── file_parser.py     # Extract text from files
│   ├── chunker.py         # Split text into chunks
│   └── embedder.py        # Generate embeddings
│
├── uploads/               # File storage (created on startup)
│   └── {user_id}/
│       └── {uuid}_{filename}
│
├── requirements.txt       # Updated with new dependencies
├── .env                   # Environment variables
└── .gitignore
```

---

## What's Next (Day 3)

**Session Management + ChromaDB Integration:**
- POST /sessions/start → Create ephemeral ChromaDB collection
- Load selected documents into session vector store
- POST /sessions/end → Delete ChromaDB collection, save summary
- Session isolation (each session = separate Chroma collection)

**Day 3 will connect documents → sessions → vector search** 🚀

---

## Troubleshooting

### "Model download failed"
- Check internet connection
- Model downloads to `~/.cache/torch/sentence_transformers/`
- First run takes 30-60 seconds

### "File upload fails"
- Check file size < 20MB
- Verify file extension is pdf/docx/md/txt
- Ensure uploads/ directory exists and is writable

### "Parsing error"
- PDFs with scanned images won't work (need OCR)
- DOCX files must not be password-protected
- Text files should be UTF-8 encoded

### "Token count seems wrong"
- tiktoken uses cl100k_base encoding (GPT-4 tokenizer)
- 1 token ≈ 4 characters on average
- Use `default_chunker.count_tokens(text)` to verify
