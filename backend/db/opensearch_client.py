from opensearchpy import OpenSearch
from backend.config import settings

client = OpenSearch(hosts=[settings.OPENSEARCH_URL])
INDEX = "conjunctions"

def index_conjunction(doc: dict):
    try:
        client.index(index=INDEX, id=doc.get("pair_key"), body=doc)
    except Exception:
        pass

def search_conjunctions_os(q: str):
    try:
        res = client.search(index=INDEX, body={"query": {"query_string": {"query": q}}})
        return [hit["_source"] for hit in res["hits"]["hits"]]
    except Exception:
        return []