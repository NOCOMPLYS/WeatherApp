import pytest
import os
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

os.environ["TEST"] = '1'
from main import app, get_db, Base


# Фикстура для настройки тестовой БД
@pytest.fixture()
def test_session():
    TEST_DB_NAME = "test_weather.db"
    TEST_DATABASE_URL = f"sqlite:///./{TEST_DB_NAME}"
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    yield TestingSessionLocal
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

# Фикстура для создания тестового клиента с тестовой БД
@pytest.fixture()
def db_client(test_session):
    def override_get_db():
        TestingSessionLocal = test_session()
        yield TestingSessionLocal

    app.dependency_overrides[get_db] = override_get_db
    
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# Фикстура добавления пользователя
@pytest.fixture()
def add_users(db_client):
    user_id_1 = db_client.post("/user", params={"username": "testuser1"}).json()
    user_id_2 = db_client.post("/user", params={"username": "testuser2"}).json()
    return {"user_id_1": user_id_1, "user_id_2": user_id_2}

# Фикстура добавления городов
@pytest.fixture()
def add_cities(db_client, add_users):
    user_id_1, user_id_2 = add_users["user_id_1"], add_users["user_id_2"]

    with patch("main.update_weather"): # Заглушка для фоновой задачи обновления погоды

        db_client.post(f"/city/{user_id_2}", params={
            "city_name": "Saint-Petersburg",
            "latitude": 59.944962,
            "longitude": 30.344624
        })

        db_client.post(f"/city/{user_id_2}", params={
            "city_name": "Moscow",
            "latitude": 55.753544,
            "longitude": 37.621202
        })

    return {"user_1": {"id": user_id_1, "cities": []}, "user_2": {"id": user_id_2, "cities": ["Saint-Petersburg", "Moscow"]}}


# Тест добавления пользователя
def test_add_user(db_client):
    
    # Тест на стандартное поведение при добавлении пользователя
    response = db_client.post("/user", params={"username": "testuser1"})
    assert response.status_code == 200
    assert isinstance(response.json(), int)

    # Тест на поведение при добавлении уже существующего пользователя
    response = db_client.post("/user", params={"username": "testuser1"})
    assert response.status_code == 400
    assert "User already exists." in response.json()["detail"]


# Тест добавления города
@patch("main.update_weather") # Заглушка для фоновой задачи обновления погоды
def test_add_cities(mock_update_weather, db_client, add_users):
    user_id = add_users['user_id_1']
    params = {
        "city_name": "Moscow",
        "latitude": 55.753544,
        "longitude": 37.621202
    }

    # Тест на стандартное поведение эндпоинта
    response = db_client.post(f"/city/{user_id}", params=params)
    assert response.status_code == 200
    assert "City Moscow added and weather tracking started." in response.json()
    mock_update_weather.assert_called_once_with("Moscow")

    # Тест на поведение эндпоинта, если выбранный город уже отслеживается для пользователя
    response = db_client.post(f"/city/{user_id}", params=params)
    assert response.status_code == 400
    assert "City Moscow is already being tracked." in response.json()["detail"]

    # Тест на поведение эндпоинта, если выбранный пользователь отсутствует в БД
    response = db_client.post(f"/city/{user_id + 1000}", params=params)
    assert response.status_code == 404
    assert "User not found." in response.json()["detail"]


# Тест получения списка городов, отслеживаемых пользователем
def test_get_cities(db_client, add_cities):
    
    user_id_1, user_id_2 = add_cities["user_1"]["id"], add_cities["user_2"]["id"]
    cities = add_cities["user_2"]["cities"]

    # Тест на поведение эндпоинта, если у пользователя нет отслеживаемых городов
    response = db_client.get(f"/cities/{user_id_1}")
    assert response.status_code == 200
    assert [] == response.json()
    
    # Тест на поведение эндпоинта, если у пользователя есть отслеживаемые города
    response = db_client.get(f"/cities/{user_id_2}")
    assert response.status_code == 200
    assert cities == response.json()

    # Тест на поведение эндпоинта, если выбранный пользователь отсутствует в БД
    response = db_client.get(f"/cities/{user_id_2 + 1000}")
    assert response.status_code == 404
    assert "User not found." in response.json()["detail"]


# Тест получения погоды по названию отслеживаемого города и времени
def test_get_weather_by_city_and_time(db_client, add_cities):
    user_id_1, user_id_2 = add_cities["user_1"]["id"], add_cities["user_2"]["id"]
    cities = add_cities["user_2"]["cities"]

    # Тест на стандартное поведение эндпоинта
    response = db_client.post(f"/weather/by-city-and-time/{user_id_2}", params={
        "city_name": f"{cities[0]}",
        "time": "16:00"
    })
    assert response.status_code == 200

    parameters = ["temperature", "wind_speed", "humidity", "precipitation"]
    data = response.json()
    for parameter in parameters:
        assert parameter in data
    
    # Тест на поведение эндпоинта когда указано неверное время
    response = db_client.post(f"/weather/by-city-and-time/{user_id_2}", params={
        "city_name": f"{cities[0]}",
        "time": "30:00"
    })
    assert response.status_code == 404
    assert "Weather data not available at this time." in response.json()["detail"]

    # Тест на поведение эндпоинта когда указан город, не отслеживаемый никем из пользователей
    response = db_client.post(f"/weather/by-city-and-time/{user_id_2}", params={
        "city_name": "Los-Angeles",
        "time": "16:00"
    })
    assert response.status_code == 404
    assert f"Los-Angeles is not being tracked for any of users" in response.json()["detail"]

    # Тест на поведение эндпоинта когда указан город, не отслеживаемый пользователем
    response = db_client.post(f"/weather/by-city-and-time/{user_id_1}", params={
        "city_name": f"{cities[0]}",
        "time": "16:00"
    })
    assert response.status_code == 400
    assert f"{cities[0]} is not being tracked for user with id: {user_id_1}" in response.json()["detail"]

    # Тест на поведение эндпоинта когда отсутствует указанный пользователь
    response = db_client.post(f"/weather/by-city-and-time/{user_id_2 + 1000}", params={
        "city_name": f"{cities[0]}",
        "time": "16:00"
    })
    assert response.status_code == 404
    assert "User not found." in response.json()["detail"]


# Тест получения погоды по координатам
def test_get_weather_by_coordinates(db_client):
    response = db_client.post("/weather/by-coordinates", params={"latitude": 55.7558, "longitude": 37.6173})
    assert response.status_code == 200
    parameters = ["temperature", "wind_speed", "pressure"]
    data = response.json()
    for parameter in parameters:
        assert parameter in data