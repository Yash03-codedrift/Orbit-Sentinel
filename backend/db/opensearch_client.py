from opensearchpy import OpenSearch
from backend.config import settings

client = OpenSearch(hosts=[settings.OPENSEARCH_URL]) if settings.OPENSEARCH_URL else None
INDEX = "conjunctions"

def index_conjunction(doc: dict):
    if client is None:
        return
    try:
        client.index(index=INDEX, id=doc.get("pair_key"), body=doc)
    except Exception:
        pass

def search_conjunctions_os(q: str):
    if client is None:
        return []
    try:
        res = client.search(index=INDEX, body={"query": {"query_string": {"query": q}}})
        return [hit["_source"] for hit in res["hits"]["hits"]]
    except Exception:
        return []