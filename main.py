from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import httpx
import os
import uvicorn
from sqlalchemy import create_engine, Column, String, Float, Integer, JSON, Table, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, declarative_base, Session
from sqlalchemy.future import select


# Настройка базы данных SQLite
DB_NAME = "test_weather.db" if os.getenv("TEST") else "weather.db"
DATABASE_URL = f"sqlite:///./{DB_NAME}"

# Настройка SQLAlchemy
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI()


# Промежуточная таблица для связи пользователей и городов
user_city_association = Table(
    'user_city_association', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('city_id', Integer, ForeignKey('cities.id'), primary_key=True)
)

# Модель города
class City(Base):
    __tablename__ = "cities"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    weather_data = Column(JSON)

    # Связь с пользователями через промежуточную таблицу
    users = relationship("User", secondary=user_city_association, back_populates="cities")

# Модель пользователя
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)

    # Связь с городами через промежуточную таблицу
    cities = relationship("City", secondary=user_city_association, back_populates="users")


Base.metadata.create_all(bind=engine)


# Функция получения 
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Модель ответа с данными о погоде
class WeatherResponse(BaseModel):
    temperature: Optional[float] = None
    wind_speed: Optional[float] = None
    pressure: Optional[float] = None
    humidity: Optional[float] = None
    precipitation: Optional[float] = None
    

# Функция для получения прогноза погоды с API open-meteo
async def get_weather(latitude: float, longitude: float, parameters: List[str], hourly: bool = False):
    async with httpx.AsyncClient(timeout=10) as client:
        if hourly:
            request = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&hourly="
        else:
            request = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current="
        for parameter in parameters:
            request += parameter + ','
        response = await client.get(request)
        response.raise_for_status()
        if hourly:
            return response.json()["hourly"]
        else:
            return response.json()["current"]


# Функция для обновления прогноза погоды в фоновом режиме
async def update_weather(city_name: str):
    while True:
        db = SessionLocal()
        try:
            city = db.execute(select(City).where(City.name == city_name)).scalars().first()
            if city:
                parameters = ["temperature_2m", "wind_speed_10m", "pressure_msl", "relative_humidity_2m", "precipitation"]
                new_weather_data = await get_weather(latitude=city.latitude, longitude=city.longitude, parameters=parameters, hourly=True)
                city.weather_data = new_weather_data
                db.commit()
        finally:
            db.close()
        await asyncio.sleep(900)


# Эндпоинт получения текущей погоды по координатам
@app.post("/weather/by-coordinates", response_model=WeatherResponse, response_model_exclude_none=True)
async def get_weather_by_coordinates(latitude: float, longitude: float):
    parameters = ["temperature_2m", "wind_speed_10m", "pressure_msl"]
    response = await get_weather(latitude=latitude, longitude=longitude, parameters=parameters)
    return WeatherResponse(
                temperature = response[parameters[0]],
                wind_speed = response[parameters[1]],
                pressure = response[parameters[2]],
            )


# Эндпоинт для добавления города в список отслеживаемых
@app.post("/city/{user_id}", response_model=str)
async def add_city(city_name: str, latitude: float, longitude: float, background_tasks: BackgroundTasks, user_id: int, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.id == user_id)).scalars().first()
    if user:
        city = db.execute(select(City).where(City.name == city_name)).scalars().first()
        user_cities_id = db.execute(select(user_city_association.c.city_id).where(user_city_association.c.user_id == user_id)).scalars().all()
        if not city:
            parameters = ["temperature_2m", "wind_speed_10m", "pressure_msl", "relative_humidity_2m", "precipitation"]
            weather_data = await get_weather(latitude=latitude, longitude=longitude, parameters=parameters, hourly=True)
            city = City(
                name=city_name, 
                latitude=latitude, 
                longitude=longitude, 
                weather_data=weather_data
            )
            db.add(city)
            city.users.append(user)
            db.commit()
            background_tasks.add_task(update_weather, city_name)
            return f"City {city_name} added and weather tracking started."
        elif city.id not in user_cities_id:
            city.users.append(user)
            db.commit()
            return f"City {city_name} added and weather tracking started."
        else:
            raise HTTPException(status_code=400, detail=f"City {city_name} is already being tracked.")
    else:
        raise HTTPException(status_code=404, detail="User not found.")


# Эндпоинт для получения списка городов
@app.get("/cities/{user_id}", response_model=List[str])
async def get_cities(user_id: str, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.id == user_id)).scalars().first()
    if user:
        user_cities_id = db.execute(select(user_city_association.c.city_id).where(user_city_association.c.user_id == user.id)).scalars().all()
        user_cities = []
        for id in user_cities_id:
            city_name = db.execute(select(City.name).where(City.id == id)).scalars().first()
            user_cities.append(city_name)
        return user_cities
    else:
        raise HTTPException(status_code=404, detail="User not found.")


# Эндпоинт получения погоды по названию города и времени
@app.post("/weather/by-city-and-time/{user_id}", response_model=WeatherResponse, response_model_exclude_none=True)
async def get_weather_by_city_and_time(city_name: str, time: str, user_id: int, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.id == user_id)).scalars().first()
    if user:
        city = db.execute(select(City).where(City.name == city_name)).scalars().first()
        user_cities_id = db.execute(select(user_city_association.c.city_id).where(user_city_association.c.user_id == user_id)).scalars().all()
        if city is not None:
            if city.id in user_cities_id:
                parameters = ["temperature_2m", "wind_speed_10m", "relative_humidity_2m", "precipitation"]
                city = db.execute(select(City).where(City.name == city_name)).scalars().first()
                if not city:
                    raise HTTPException(status_code=400, detail="City not found.")
                weather_data = city.weather_data
                time_list = [time[-5:] for time in weather_data["time"][:24]]
                if time not in time_list:
                    raise HTTPException(status_code=404, detail="Weather data not available at this time.")
                response = {}
                for i in range(24):
                    if time == weather_data["time"][i][-5:]:
                        for parameter in parameters:
                            response[parameter] = weather_data[parameter][i]
                        break
                return WeatherResponse(
                    temperature = response["temperature_2m"],
                    wind_speed = response["wind_speed_10m"],
                    humidity = response["relative_humidity_2m"],
                    precipitation = response["precipitation"]
                )
            else:
                raise HTTPException(status_code=400, detail=f"{city_name} is not being tracked for user with id: {user_id}")
        else:
            raise HTTPException(status_code=404, detail=f"{city_name} is not being tracked for any of users")
    else:
        raise HTTPException(status_code=404, detail="User not found.")


# Эндпоинт для добавления пользователя
@app.post("/user", response_model=int)
async def add_user(username: str, db: Session = Depends(get_db)):
    if not db.execute(select(User).where(User.username == username)).scalars().first():
        user = User(username = username)
        db.add(user)
        db.commit()
        return user.id
    else:
        raise HTTPException(status_code=400, detail="User already exists.")


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)