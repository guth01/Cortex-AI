from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
import os

from dotenv import load_dotenv

from cleanup import cleanup_orphaned_sessions
from db.chroma import get_chroma_client
from routes.deps import set_database
from routes.auth import router as auth_router
from routes.subjects import router as subjects_router
from routes.documents import router as documents_router
from routes.sessions import router as sessions_router
from routes.chat import router as chat_router
from routes.google_oauth import router as google_oauth_router
from routes.flashcards import router as flashcards_router
from routes.export import router as export_router

# Load environment variables
load_dotenv()

# MongoDB client (global for lifespan management)
mongo_client: AsyncIOMotorClient = None



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    global mongo_client

    # ========== STARTUP ==========
    print("=" * 60)
    print("🚀 Starting Study Agent Backend...")
    print("=" * 60)

    mongodb_uri = os.getenv("MONGODB_URI")
    if not mongodb_uri:
        print("❌ FATAL: MONGODB_URI not found in environment variables!")
        raise RuntimeError("MONGODB_URI is required")

    try:
        print("📡 Connecting to MongoDB Atlas...")
        mongo_client = AsyncIOMotorClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        await mongo_client.admin.command("ping")
        print("✓ MongoDB Atlas connection successful!")

        database = mongo_client.study_agent

        # Share the database with route modules
        set_database(database)

        # Verify all collections exist
        existing_collections = await database.list_collection_names()
        required_collections = ["users", "subjects", "documents", "sessions", "flashcards"]

        print("\n📚 Initializing collections...")
        for name in required_collections:
            if name not in existing_collections:
                await database.create_collection(name)
                print(f"  ✓ Created collection: {name}")
            else:
                print(f"  ✓ Collection exists: {name}")

        # Create indexes
        print("\n🔍 Creating indexes...")
        await database.users.create_index("email", unique=True)
        print("  ✓ Unique index on users.email")
        await database.subjects.create_index([("user_id", 1)])
        print("  ✓ Index on subjects.user_id")
        await database.sessions.create_index([("user_id", 1), ("status", 1)])
        print("  ✓ Compound index on sessions.user_id + status")
        await database.documents.create_index([("user_id", 1), ("subject_id", 1)])
        print("  ✓ Compound index on documents.user_id + subject_id")
        await database.flashcards.create_index([("user_id", 1), ("subject_id", 1)])
        print("  ✓ Compound index on flashcards.user_id + subject_id")
        await database.flashcards.create_index([("user_id", 1), ("due_date", 1)])
        print("  ✓ Compound index on flashcards.user_id + due_date (for spaced repetition)")

        # Embedder is now lazy-loaded on first use
        # (This drastically speeds up backend startup)

        # Initialize ChromaDB
        print("\n📦 Initializing ChromaDB...")
        client = get_chroma_client()
        collections = client.list_collections()
        print(f"  ✓ ChromaDB ready ({len(collections)} existing collections)")

        # Run cleanup job
        print("\n🧹 Running cleanup job...")
        await cleanup_orphaned_sessions(database)

        print("\n" + "=" * 60)
        print("✅ Backend ready! All systems operational.")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ FATAL ERROR during startup: {e}")
        print("Cannot proceed without database connection.")
        raise

    yield

    # ========== SHUTDOWN ==========
    print("\n🛑 Shutting down Study Agent Backend...")
    if mongo_client:
        mongo_client.close()
        print("✓ MongoDB connection closed")
    print("Goodbye! 👋\n")


# ============================================================================
# APP SETUP
# ============================================================================

app = FastAPI(
    title="Study Agent API",
    description="AI-powered personalized study companion",
    version="1.0.0",
    lifespan=lifespan,
)

from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from routes.deps import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
allow_origins_list = ["http://localhost:3000"]
if frontend_url and frontend_url not in allow_origins_list:
    allow_origins_list.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins_list,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(auth_router)
app.include_router(google_oauth_router)   # Day 5: Google OAuth
app.include_router(subjects_router)
app.include_router(documents_router)
app.include_router(sessions_router)
app.include_router(flashcards_router)     # Day 6: Flashcard list + SM-2 review
app.include_router(chat_router)
app.include_router(export_router)         # Day 7: PDF export


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "Study Agent API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
