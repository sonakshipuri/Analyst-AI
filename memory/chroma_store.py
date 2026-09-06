# memory/chroma_store.py
import os
import re
import time
from typing import Any, cast
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

# Make ChromaDB path absolute relative to project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_PATH = os.path.join(PROJECT_ROOT, "chroma_store")

client = chromadb.PersistentClient(path=CHROMA_PATH)
embed_fn = DefaultEmbeddingFunction()


def sanitize_session_id(session_id: str) -> str:
    """Ensure session_id fits ChromaDB collection naming rules."""
    clean = re.sub(r"[^a-zA-Z0-9._-]", "_", str(session_id))
    clean = clean.strip("_.-")
    if not clean:
        clean = "session"
    return clean


def get_collection(session_id: str):
    """Get or create a collection for the session, ensuring creation timestamp."""
    safe_id = sanitize_session_id(session_id)
    collection_name = f"session_{safe_id}"

    # Check if collection exists
    existing_collections = client.list_collections()
    exists = any(col.name == collection_name for col in existing_collections)

    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=cast(Any, embed_fn)
    )

    # If collection is new, set creation timestamp in metadata
    if not exists:
        try:
            collection.modify(metadata={"created_at": str(time.time())})
        except Exception:
            # Fallback: some ChromaDB versions may not support modify
            pass

    return collection


def store_insights(session_id: str, insights: list[dict], description: str):
    """Store all insights and descriptions as searchable vector documents."""
    collection = get_collection(session_id)
    safe_id = sanitize_session_id(session_id)

    documents = [f"Dataset overview: {description}"]
    ids = [f"{safe_id}_desc"]
    metadatas = [{"type": "description"}]

    for idx, insight in enumerate(insights or []):
        documents.append(
            f"Q: {insight.get('question', 'Unknown Question')}\n"
            f"A: {insight.get('answer', 'No Answer')}"
        )
        ids.append(f"{safe_id}_insight_{idx}")
        metadatas.append({
            "type": "insight",
            "confidence": insight.get("confidence", "unknown"),
            "visualization_source": insight.get("visualization_source", "none")
        })

    if documents:
        collection.upsert(
            documents=documents,
            ids=ids,
            metadatas=cast(Any, metadatas)
        )


def retrieve_context(session_id: str, user_question: str, n: int = 3) -> str:
    """Find the most relevant past context matching a user query."""
    try:
        collection = get_collection(session_id)
        count = collection.count()
        if count == 0:
            return ""

        results = collection.query(
            query_texts=[user_question],
            n_results=min(n, count)
        )
        documents = (results or {}).get("documents") or []
        docs = documents[0] if documents else []
        return "\n".join(docs)
    except Exception:
        return ""


def clear_session(session_id: str):
    """Delete all database entries for the specific session."""
    try:
        safe_id = sanitize_session_id(session_id)
        client.delete_collection(name=f"session_{safe_id}")
    except Exception:
        pass


def clean_old_sessions(days: int = 7):
    """
    Remove ChromaDB collections older than the specified number of days.
    Useful for preventing disk bloat during long testing periods.
    """
    now = time.time()
    cutoff = now - (days * 24 * 60 * 60)

    collections = client.list_collections()
    for col in collections:
        try:
            meta = col.metadata
            created_str = meta.get("created_at") if meta else None
            if created_str:
                created_ts = float(created_str)
                if created_ts < cutoff:
                    client.delete_collection(col.name)
                    print(f"[Chroma] Deleted old collection: {col.name}")
            else:
                # No timestamp – delete if it's a session collection and older than 30 days
                if col.name.startswith("session_") and hasattr(col, "name"):
                    # Fallback: check file modification time of the collection directory
                    collection_dir = os.path.join(CHROMA_PATH, col.name)
                    if os.path.exists(collection_dir):
                        mtime = os.path.getmtime(collection_dir)
                        if mtime < cutoff:
                            client.delete_collection(col.name)
                            print(f"[Chroma] Deleted old collection (no timestamp): {col.name}")
        except Exception as e:
            print(f"[Chroma] Error cleaning collection {col.name}: {e}")