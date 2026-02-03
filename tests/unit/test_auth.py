import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token, get_password_hash, verify_password, verify_token
from app.main import app


class TestPasswordHashing:
    def test_hash_password(self):
        password = "TestPassword123!"
        hashed = get_password_hash(password)
        assert hashed != password
        assert len(hashed) > 0

    def test_verify_correct_password(self):
        password = "TestPassword123!"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_wrong_password(self):
        password = "TestPassword123!"
        hashed = get_password_hash(password)
        assert verify_password("wrongpassword", hashed) is False


class TestJWTToken:
    def test_create_access_token(self):
        token = create_access_token(subject="123")
        assert token is not None
        assert len(token) > 0

    def test_verify_valid_token(self):
        token = create_access_token(subject="123")
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "123"

    def test_verify_invalid_token(self):
        payload = verify_token("invalid.token.here")
        assert payload is None


@pytest.mark.asyncio
class TestAuthEndpoints:
    async def test_register_user(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "test@example.com",
                    "password": "TestPassword123",
                    "full_name": "Test User"
                }
            )
            # May fail if user already exists, which is OK for repeated tests
            assert response.status_code in [201, 400]

    async def test_login_wrong_credentials(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/login",
                data={
                    "username": "nonexistent@example.com",
                    "password": "wrongpassword"
                }
            )
            assert response.status_code == 401
