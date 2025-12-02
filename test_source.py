import dlt

def dummy_source():
    yield {"id": 1, "amount": 100, "customer": "Alice"}
    yield {"id": 2, "amount": 0, "customer": "Bob"}
    yield {"id": 3, "amount": 50, "customer": "Charlie"}
