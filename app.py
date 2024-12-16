from flask import Flask, render_template, request
import requests
import json
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import pandas as pd

API_KEY = "XzKIblRO445awcuauGkULV8S3lzcAQLS"
LOCATION_URL = "http://dataservice.accuweather.com/locations/v1/cities/autocomplete"
FIVE_DAY_FORECAST_URL = "http://dataservice.accuweather.com/forecasts/v1/daily/5day/{}"

server = Flask(__name__)
app = dash.Dash(__name__, server=server, url_base_pathname='/')

# Функция для получения координат города
def get_location_key(city_name):
    params = {
        "apikey": API_KEY,
        "q": city_name
    }
    try:
        response = requests.get(LOCATION_URL, params=params)
        response.raise_for_status()
        data = response.json()
        if data:
            return data[0]["Key"]
        else:
            return None
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к AccuWeather Location API: {e}")
        return None
    except (IndexError, KeyError) as e:
        print(f"Ошибка при обработке данных Location API: {e}")
        return None

# Функция для получения данных о погоде
def get_weather_data(location_key):
    try:
        response = requests.get(FIVE_DAY_FORECAST_URL.format(location_key), params={"apikey": API_KEY, "metric": True})
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к AccuWeather Forecast API: {e}")
        return None
    except (IndexError, KeyError) as e:
        print(f"Ошибка обработки данных Forecast API: {e}")
        return None

# Модель для оценки неблагоприятных погодных условий
def check_bad_weather(weather_data):
    if not weather_data or "DailyForecasts" not in weather_data:
        return "Нет данных о погоде"

    try:
        daily_forecasts = weather_data["DailyForecasts"]
        results = []
        for forecast in daily_forecasts:
            temperature_max = forecast["Temperature"]["Maximum"]["Value"]
            temperature_min = forecast["Temperature"]["Minimum"]["Value"]
            wind_speed_day = forecast.get("Day", {}).get("Wind", {}).get("Speed", {}).get("Value", 0)
            wind_speed_night = forecast.get("Night", {}).get("Wind", {}).get("Speed", {}).get("Value", 0)
            precipitation_day = forecast.get("Day", {}).get("HasPrecipitation", False)
            precipitation_night = forecast.get("Night", {}).get("HasPrecipitation", False)

            if temperature_max > 30 or temperature_min < -5:
                results.append("Ой-ой, погода плохая (температура)")
            elif wind_speed_day > 10 or wind_speed_night > 10:
                results.append("Ой-ой, погода плохая (ветер)")
            elif precipitation_day or precipitation_night:
                results.append("Ой-ой, погода плохая (осадки)")
            else:
                results.append("Погода — супер")

        return results

    except KeyError as e:
        print(f"Ошибка: в данных о погоде нет ключа {e}: {weather_data}")
        return ["Недостаточно данных о погоде"] * len(daily_forecasts)

# Структура приложения
app.layout = html.Div([
    html.H1("Прогноз погоды для маршрута"),
    html.Div([
        html.Label("Начальный город:"),
        dcc.Input(id='start_city', type='text', required=True),
        html.Br(),
        html.Label("Конечный город:"),
        dcc.Input(id='end_city', type='text', required=True),
        html.Br(),
        html.Button('Узнать погоду', id='submit-val', n_clicks=0),
    ]),
    html.Div(id='weather-output')
])

# Коллбэк для обработки запроса и вывода результатов
@app.callback(
    Output('weather-output', 'children'),
    Input('submit-val', 'n_clicks'),
    dash.dependencies.State('start_city', 'value'),
    dash.dependencies.State('end_city', 'value')
)
def update_output(n_clicks, start_city, end_city):
    if n_clicks > 0:
        if not start_city or not end_city:
            return "Пожалуйста, введите названия обоих городов."

        start_location_key = get_location_key(start_city)
        end_location_key = get_location_key(end_city)

        if not start_location_key or not end_location_key:
            return "Не удалось определить местоположение одного или обоих городов."

        start_weather_data = get_weather_data(start_location_key)
        end_weather_data = get_weather_data(end_location_key)

        start_weather_status = check_bad_weather(start_weather_data)
        end_weather_status = check_bad_weather(end_weather_data)
        
        # Подготовка данных для графиков
        start_weather_df = pd.DataFrame(start_weather_data['DailyForecasts'])
        end_weather_df = pd.DataFrame(end_weather_data['DailyForecasts'])

        # Создание графиков
        start_fig = go.Figure()
        end_fig = go.Figure()

        # Добавление данных на графики для начального города
        start_fig.add_trace(go.Scatter(x=start_weather_df.index, y=start_weather_df['Temperature'].apply(lambda x: x['Maximum']['Value']),
                             mode='lines+markers', name='Макс. температура'))
        start_fig.add_trace(go.Scatter(x=start_weather_df.index, y=start_weather_df['Temperature'].apply(lambda x: x['Minimum']['Value']),
                             mode='lines+markers', name='Мин. температура'))
        start_fig.update_layout(title=f'Погода в {start_city}', xaxis_title='День', yaxis_title='Температура (°C)')

        # Добавление данных на графики для конечного города
        end_fig.add_trace(go.Scatter(x=end_weather_df.index, y=end_weather_df['Temperature'].apply(lambda x: x['Maximum']['Value']),
                           mode='lines+markers', name='Макс. температура'))
        end_fig.add_trace(go.Scatter(x=end_weather_df.index, y=end_weather_df['Temperature'].apply(lambda x: x['Minimum']['Value']),
                           mode='lines+markers', name='Мин. температура'))
        end_fig.update_layout(title=f'Погода в {end_city}', xaxis_title='День', yaxis_title='Температура (°C)')

        # Вывод результатов
        return html.Div([
            html.H3(f"Прогноз погоды для {start_city}"),
            dcc.Graph(figure=start_fig),
            html.Ul(children=[html.Li(status) for status in start_weather_status]),

            html.H3(f"Прогноз погоды для {end_city}"),
            dcc.Graph(figure=end_fig),
            html.Ul(children=[html.Li(status) for status in end_weather_status])
        ])

    return ""

if __name__ == "__main__":
    app.run_server(debug=True)