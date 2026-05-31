# Day 1 Setup Guide — Study Agent Backend

## 📋 What We Built

✅ FastAPI backend with Motor (async MongoDB driver)  
✅ JWT authentication (register, login, /me)  
✅ MongoDB Atlas integration with 5 collections  
✅ Subjects CRUD (create, list, delete)  
✅ Cleanup job for orphaned sessions  
✅ Proper error handling and startup validation

## 🚀 Step-by-Step Setup Instructions

### Step 1: Set Up MongoDB Atlas

1. Go to [MongoDB Atlas](https://cloud.mongodb.com)
2. Create a free account (if you don't have one)
3. Create a new cluster (M0 Free tier is fine)
4. Click "Database Access" → Add New Database User
   - Username: `studyagent`
   - Password: `<generate a strong password>`
   - Built-in Role: `Atlas admin` (or `Read and write to any database`)
5. Click "Network Access" → Add IP Address
   - Click "Allow Access from Anywhere" (0.0.0.0/0) for development
   - ⚠️ In production, restrict this to your server's IP
6. Click "Database" → "Connect" → "Connect your application"
7. Copy the connection string. It looks like:
   ```
   mongodb+srv://studyagent:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```
8. Replace `<password>` with your actual password

### Step 2: Set Up Google Cloud Console (OAuth Credentials)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing one
3. Enable the Google Calendar API:
   - Go to "APIs & Services" → "Library"
   - Search for "Google Calendar API"
   - Click "Enable"
4. Configure OAuth Consent Screen:
   - Go to "APIs & Services" → "OAuth consent screen"
   - Choose "External" (for testing)
   - Fill in:
     - App name: `Study Agent`
     - User support email: your email
     - Developer contact: your email
   - Click "Save and Continue"
   - Add scopes → Click "Save and Continue"
   - Add test users → Add your email
5. Create OAuth 2.0 Credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Application type: "Web application"
   - Name: `Study Agent Backend`
   - Authorized redirect URIs:
     - `http://localhost:8000/auth/google/callback`
   - Click "Create"
6. Copy the Client ID and Client Secret

### Step 3: Create Your .env File

```bash
# In your project directory
cp .env.example .env
```

Now edit the `.env` file with your actual values:

```env
# MongoDB Atlas
MONGODB_URI=mongodb+srv://studyagent:YOUR_PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority

# JWT Configuration
JWT_SECRET=super-secret-random-string-at-least-32-chars-long
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# Google Gemini API
GEMINI_API_KEY=your-gemini-api-key-here

# Google OAuth (for Calendar integration)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# DeepL (optional - for translation features)
DEEPLAPI_KEY=your-deepl-api-key-here

# Server
PORT=8000
```

**Important**: Generate a strong JWT_SECRET. In PowerShell:
```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Step 4: Get Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Click "Create API Key"
3. Copy the key and paste it in your `.env` file

### Step 5: Install Python Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate it (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### Step 6: Run the Server

```bash
python server.py
```

You should see:
```
============================================================
🚀 Starting Study Agent Backend...
============================================================
📡 Connecting to MongoDB Atlas...
✓ MongoDB Atlas connection successful!

📚 Initializing collections...
  ✓ Created collection: users
  ✓ Created collection: subjects
  ✓ Created collection: documents
  ✓ Created collection: sessions
  ✓ Created collection: flashcards

🔍 Creating indexes...
  ✓ Unique index on users.email
  ✓ Index on subjects.user_id
  ✓ Compound index on sessions.user_id + status

🧹 Running cleanup job...
[CLEANUP] Starting cleanup job at 2026-02-25 ...
[CLEANUP] No orphaned sessions found. ✓

============================================================
✅ Backend ready! All systems operational.
============================================================

INFO:     Uvicorn running on http://0.0.0.0:8000
```

## 🧪 Test Your API

### Register a new user
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"test@example.com\",\"password\":\"test123\",\"name\":\"Test User\"}"
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Login
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"test@example.com\",\"password\":\"test123\"}"
```

### Get current user (protected route)
```bash
curl http://localhost:8000/me \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Create a subject
```bash
curl -X POST http://localhost:8000/subjects \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Machine Learning\",\"exam_date\":\"2026-05-15T10:00:00\"}"
```

### Get all subjects
```bash
curl http://localhost:8000/subjects \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## 📁 Project Structure

```
Study-agent/
├── server.py           # Main FastAPI application
├── models.py           # Pydantic models for validation
├── auth.py             # JWT authentication utilities
├── cleanup.py          # Cleanup job for orphaned sessions
├── requirements.txt    # Python dependencies
├── .env                # Environment variables (create from .env.example)
├── .env.example        # Template for environment variables
└── .gitignore          # Git ignore rules
```

## ✅ Day 1 Checklist

- [x] FastAPI server running
- [x] MongoDB Atlas connected
- [x] 5 collections created (users, subjects, documents, sessions, flashcards)
- [x] Auth routes working (register, login, /me)
- [x] JWT authentication dependency
- [x] Subjects CRUD routes
- [x] Cleanup job runs on startup
- [x] Google OAuth credentials obtained (for Day 5)
- [x] Gemini API key configured

## 🎯 What's Next (Day 2)

- Document upload & management
- PDF parsing with PyPDF2
- File storage strategy
- Associate documents with subjects

## 🐛 Troubleshooting

### "MONGODB_URI not found"
- Make sure your `.env` file exists
- Check that `MONGODB_URI` is spelled correctly
- Restart the server after creating `.env`

### "Could not connect to MongoDB"
- Verify your MongoDB Atlas IP whitelist includes 0.0.0.0/0
- Check your username and password are correct
- Ensure your cluster is running

### "ModuleNotFoundError"
- Make sure your virtual environment is activated
- Run `pip install -r requirements.txt` again

### Port 8000 already in use
- Change `PORT=8000` in `.env` to something else (e.g., `PORT=8001`)
- Or kill the process using port 8000
