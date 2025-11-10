from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

def test_hello():
    response = client.get("/v1/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "hello"}

