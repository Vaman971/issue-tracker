import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient):
    response = await client.post(
        "/auth/register", # the api which needs to be tested
        json={
            "email":"test@example.com",
            "password": "testpassword123"
        }, # the request format which neeeds to be sent
    )

    assert response.status_code == 201

    data = response.json()

    assert data["email"] == "test@example.com"
    assert data["role"] == "viewer"

    assert "hashed_password" not in data # as we were returning a pydantic data model, which filteres out sensitive information from the response, therefore this checks if the model is returning it or not

@pytest.mark.asyncio
async def test_login_user(client: AsyncClient):

    # register the user first for this test session to check for login
    await client.post(
        "/auth/register",
        json={
            "email": "login@example.com",
            "password": "testpassword123",
        },
    )

    response = await client.post(
        "/auth/login",
        json={
            "email": "login@example.com",
            "password": "testpassword123",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    response = await client.post(
        "/auth/login",
        json={
            "email": "wrong@example.com",
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 401 # as we did not register a user in  this session, therefore the user on login will not exist,and the response code should be not found

    data = response.json()

    assert data["detail"] == "Invalid credentials"

@pytest.mark.asyncio
async def test_refresh_token_success(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={
            "email": "refresh@example.com",
            "password": "testpassword123",
        },
    )

    login_response = await client.post(
        "/auth/login",
        json={
            "email": "refresh@example.com",
            "password": "testpassword123",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    refresh_response = await client.post(
        "/auth/refresh",
        json={
            "refresh_token": refresh_token,
        },
    )

    assert refresh_response.status_code == 200

    data = refresh_response.json()

    assert "access_token" in data
    assert "refresh_token" in data
    assert data["refresh_token"] != refresh_token


@pytest.mark.asyncio
async def test_refresh_token_cannot_be_reused(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={
            "email": "reuse@example.com",
            "password": "testpassword123",
        },
    )

    login_response = await client.post(
        "/auth/login",
        json={
            "email": "reuse@example.com",
            "password": "testpassword123",
        },
    )

    old_refresh_token = login_response.json()["refresh_token"]

    first_refresh_response = await client.post(
        "/auth/refresh",
        json={
            "refresh_token": old_refresh_token,
        },
    )

    assert first_refresh_response.status_code == 200

    second_refresh_response = await client.post(
        "/auth/refresh",
        json={
            "refresh_token": old_refresh_token,
        },
    )

    assert second_refresh_response.status_code == 401