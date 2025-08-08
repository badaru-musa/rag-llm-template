import pytest
import asyncio
from fastapi.testclient import TestClient
from app.main import app
from app.auth import AuthService


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def auth_service():
    """Create auth service for testing"""
    return AuthService(
        secret_key="test-secret-key",
        algorithm="HS256",
        access_token_expire_minutes=30
    )


class TestAuth:
    """Test authentication functionality"""
    
    def test_password_hashing(self, auth_service):
        """Test password hashing and verification"""
        password = "testpassword123"
        hashed = auth_service.get_password_hash(password)
        
        assert hashed != password
        assert auth_service.verify_password(password, hashed)
        assert not auth_service.verify_password("wrongpassword", hashed)
    
    def test_token_creation_and_verification(self, auth_service):
        """Test JWT token creation and verification"""
        token_data = {"sub": "testuser", "user_id": 1}
        token = auth_service.create_access_token(token_data)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Verify token
        decoded_data = auth_service.verify_token(token)
        assert decoded_data.username == "testuser"
        assert decoded_data.user_id == 1
    
    def test_invalid_token(self, auth_service):
        """Test invalid token handling"""
        with pytest.raises(Exception):  # Should raise AuthenticationError
            auth_service.verify_token("invalid.token.here")


class TestHealthEndpoints:
    """Test health check endpoints"""
    
    def test_health_check(self, client):
        """Test basic health check"""
        response = client.get("/health/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
    
    def test_ping(self, client):
        """Test ping endpoint"""
        response = client.get("/health/ping")
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "pong"
        assert "timestamp" in data
    
    def test_version(self, client):
        """Test version endpoint"""
        response = client.get("/health/version")
        assert response.status_code == 200
        
        data = response.json()
        assert "name" in data
        assert "version" in data


class TestRootEndpoint:
    """Test root endpoint"""
    
    def test_root(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "docs" in data


# Async test example
@pytest.mark.asyncio
async def test_async_functionality():
    """Test async functionality"""
    # This is a placeholder for async tests
    result = await asyncio.sleep(0.1, result="test")
    assert result == "test"


if __name__ == "__main__":
    pytest.main([__file__])
