import sys
import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from services.clawmarket_api import app

client = TestClient(app)


@pytest.fixture
def mock_db():
    fake_state = {
        "users": {},
        "tasks": {},
        "seq": 0,
        "version": 1
    }

    
    with patch("scripts.clawmarket._load", return_value=fake_state) as mock_load, \
         patch("scripts.clawmarket._save") as mock_save:
        
        def side_effect_save(new_state):
            fake_state.update(new_state)
            
        mock_save.side_effect = side_effect_save
        yield fake_state

@pytest.fixture(autouse=True)
def reset_rate_limit():

    if hasattr(app.state, "limiter"):
        pass
    yield


def test_health_check(mock_db):
    """checks if the API is up and running and reading the (mocked) state."""
    response = client.get("/status")
    assert response.status_code == 200
    assert response.json()["ok"] is True

def test_register_rate_limit(mock_db):
    """
    test the rate limit of the registration route (set to 5/minute).
    """
    
    for i in range(5):
        response = client.post(
            "/users/register", 
            json={"phone": f"+551199999000{i}", "role": "worker"}
        )
        
        if response.status_code != 200:
            print(f"\nErro na requisição {i+1}: {response.json()}")
        # ----------------------------------
        assert response.status_code == 200, f"Falhou na requisição {i+1}"

    response = client.post(
        "/users/register", 
        json={"phone": "+5511999999999", "role": "worker"}
    )
    assert response.status_code == 429
    assert "Rate limit exceeded" in response.text

def test_create_task_rate_limit(mock_db):
    """
    test the rate limit of the task creation route (set to 10/minute).
    """
    client.post("/users/register", json={"phone": "+5500000000", "role": "requester"})

    for i in range(10):
        response = client.post(
            "/tasks",
            json={
                "requester": "+5500000000",
                "title": f"Task {i}",
                "instructions": "Do it",
                "budget": 10.0
            }
        )
        assert response.status_code == 200

    response = client.post(
        "/tasks",
        json={
            "requester": "+5500000000",
            "title": "Spam Task",
            "instructions": "Spam",
            "budget": 10.0
        }
    )
    assert response.status_code == 429

def test_read_requests_are_not_limited(mock_db):
    """
    checks if read (GET) routes are NOT being blocked by the write limiter.  
    """
    for _ in range(20):
        response = client.get("/tasks/open")
        assert response.status_code == 200