"""
Cleanup job for orphaned study sessions.

This runs on backend startup and cleans up any sessions that were marked as 
'active' but haven't been touched in 24+ hours (likely due to crashes).

It will:
1. Find sessions with status='active' older than 24 hours
2. Delete their ChromaDB collections via the chroma manager
3. Mark them as status='interrupted'
"""

from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
from db.chroma import delete_session_collection


async def cleanup_orphaned_sessions(db: AsyncIOMotorDatabase):
    """
    Clean up sessions stuck in 'active' status for more than 24 hours.
    
    Args:
        db: MongoDB database instance
    """
    cutoff_time = datetime.utcnow() - timedelta(hours=24)
    
    print(f"[CLEANUP] Starting cleanup job at {datetime.utcnow()}")
    print(f"[CLEANUP] Looking for active sessions older than {cutoff_time}")
    
    # Find orphaned sessions
    orphaned_sessions = await db.sessions.find({
        "status": "active",
        "started_at": {"$lt": cutoff_time}
    }).to_list(length=None)
    
    if not orphaned_sessions:
        print("[CLEANUP] No orphaned sessions found. ✓")
        return
    
    print(f"[CLEANUP] Found {len(orphaned_sessions)} orphaned session(s)")
    
    for session in orphaned_sessions:
        session_id = str(session["_id"])
        
        # Delete ChromaDB collection via manager
        delete_session_collection(session_id)
        
        # Mark session as interrupted
        await db.sessions.update_one(
            {"_id": session["_id"]},
            {
                "$set": {
                    "status": "interrupted",
                    "ended_at": datetime.utcnow()
                }
            }
        )
        print(f"[CLEANUP] Marked session {session_id} as interrupted")
    
    print(f"[CLEANUP] Cleanup complete. Processed {len(orphaned_sessions)} session(s). ✓")
