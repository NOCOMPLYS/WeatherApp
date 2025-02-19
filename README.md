
# Погодное приложение
Приложение для получения и отслеживания погоды с API Open-Meteo.
Приложение работает в многопользовательском режиме и хранит прогноз погоды для городов, добавленнных пользователями, обновляя его каждые 15 минут.

# Установка и запуск

1. Установите необходимые зависимости:
```zsh
pip install -r requirements.txt
```
2. Запустите приложение
```zsh
python3 main.py
```
3. Приложение доступно по адресу [http://127.0.0.1:8000]
4. Спецификация доступна по адресу [http://127.0.0.1:8000/docs]

# Реализованные методы

## Получение текущей погоды по координатам

- **Метод**: get_weather_by_coordinates
- **Тип метода**: POST
- **URL**: `/weather/by-coordinates`
- **Описание**: Возвращает данные о погоде (температура, скорость ветра, давление) в JSON-формате.
- **Параметры запроса**: 
  - `latitude` (Обязательно): Широта.
  - `longitude` (Обязательный): Долгота.
- **Ответ**:
  - Код 200 - Успешный ответ с данными о погоде.
- **Тело ответа**:
  ```json
  {
  "temperature": 3.2,
  "wind_speed": 16.6,
  "pressure": 1017.4,
  }
  ```

## Добавление города в отслеживаемые

- **Метод**: add_city
- **Тип метода**: POST
- **URL**: `/city/{user_id}`
- **Описание**: Добавляет город в список отслеживаемых для указанного пользователя.
- **Параметры запроса**: 
  - `city_name` (Обязательно): Название города.
  - `latitude` (Обязательно): Широта.
  - `longitude` (Обязательный): Долгота.
  - `background_tasks` (Обязательно): Функция фонового обновления погоды для добавленного города.
  - `user_id` (Обязательно): ID пользователя.
- **Ответ**:
  - Код 200 - Подтверждение добавления города в отслеживаемые.
  - Код 400 - Указанный город уже в списке отслеживаемых указанного пользователя.
  - Код 404 - Пользователь не найден.
- **Тело ответа**:
  ```json
  "City Saint-Petersburg added and weather tracking started."
  ```

## Получение списка отслеживаемых городов

- **Метод**: get_weather_by_city_and_time
- **Тип метода**: POST
- **URL**: `/cities/{user_id}`
- **Описание**: Возвращает список отслеживаемых городов для указанного пользователя.
- **Параметры запроса**: 
  - `user_id` (Обязательно): ID пользователя.
- **Ответ**:
  - Код 200 - Успешный ответ со списком отслеживаемых городов пользователя.
  - Код 404 - Пользователь не найден.
- **Тело ответа**:
  ```json
  [
  "Saint-Petersburg",
  "Moscow"
  ]
  ```

## Получение погоды на конкретное время по названию города

- **Метод**: get_weather_by_city_and_time
- **Тип метода**: POST
- **URL**: `/weather/by-city-and-time/{user_id}`
- **Описание**: Возвращает данные о погоде (температура, скорость ветра, влажность, осадки) в указанное время для указанного города в JSON-формате.
- **Параметры запроса**: 
  - `city_name` (Обязательно): Название города.
  - `time` (Обязательно): Время.
  - `user_id` (Обязательно): ID пользователя.
- **Ответ**:
  - Код 200 - Успешный ответ с данными о погоде.
  - Код 400 - Указанный город не отслеживается для указанного пользователя.
  - Код 404 - Пользователь не найден / Погода на это время в указанном городе недоступна.
- **Тело ответа**:
  ```json
  {
  "temperature": 2.9,
  "wind_speed": 15.5,
  "humidity": 95,
  "precipitation": 0
  }
  ```

## Добавление пользователя

- **Метод**: add_user
- **Тип метода**: POST
- **URL**: `/user`
- **Описание**: Добавляет нового пользователя.
- **Параметры запроса**: 
  - `username` (Обязательно): Имя пользователя.
- **Ответ**:
  - Код 200 - Успешный ответ с ID новго пользователя.
  - Код 400 - Пользователь уже существует.
- **Тело ответа**:
  ```json
  1
  ```


# Контрибьюторы
- [Мирошников Николай Юрьевич](https://github.com/NOCOMPLYS)
