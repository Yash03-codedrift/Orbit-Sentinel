from bson import ObjectId
from datetime import datetime
from typing import Any

def serialize_mongo_doc(doc: Any) -> Any:
    """
    Recursively converts MongoDB document types to JSON-serializable Python types.
    Handles ObjectId -> str and datetime -> ISO string.
    """
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize_mongo_doc(item) for item in doc]
    if isinstance(doc, dict):
        return {key: serialize_mongo_doc(value) for key, value in doc.items()}
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc