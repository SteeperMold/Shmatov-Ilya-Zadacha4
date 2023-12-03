from flask import Flask, render_template, request, send_file
from pyorbital.orbital import Orbital
import datetime as dt
import math
from io import BytesIO

app = Flask(__name__)

SATELLITES = ['METEOR-M2 2', 'METEOR-M2 3', 'NOAA 18', 'NOAA 19', 'METOP-B', 'METOP-C']


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/', methods=['POST'])
def get_timetable():
    try:
        lat = float(request.form.get('lat-input'))
        lon = float(request.form.get('lon-input'))
        alt = float(request.form.get('alt-input')) / 1000
        min_elevation = float(request.form.get('min-elevation-input'))
        min_apogee = float(request.form.get('min-apogee-input'))
        start_time = dt.datetime.strptime(request.form.get('start-time-input'), '%Y-%m-%dT%H:%M')
        duration = int(request.form.get('duration-input'))
    except ValueError:
        return render_template('error.html')

    all_passes = []

    for satellite in SATELLITES:
        orb = Orbital(satellite, 'tle.txt')
        passes = orb.get_next_passes(start_time, duration, lon, lat, alt)

        def sort_by_min_apogee(datetimes):
            start, end, max_elevation = datetimes
            elevation = orb.get_observer_look(max_elevation, lon, lat, alt)[1]
            return elevation >= min_apogee

        passes = list(filter(sort_by_min_apogee, passes))

        def map_by_min_elevation(datetimes):
            start, end, max_elevation = datetimes
            mapped_start, mapped_end = start, end

            for shift in range((max_elevation - start).seconds):
                elevation = orb.get_observer_look(start + dt.timedelta(seconds=shift), lon, lat, alt)[1]

                if math.floor(elevation) >= min_elevation:
                    mapped_start = start + dt.timedelta(seconds=shift)
                    break

            for shift in range((end - max_elevation).seconds):
                elevation = orb.get_observer_look(end - dt.timedelta(seconds=shift), lon, lat, alt)[1]

                if math.floor(elevation) >= min_elevation:
                    mapped_end = end - dt.timedelta(seconds=shift)
                    break

            return mapped_start, mapped_end, max_elevation

        passes = list(map(map_by_min_elevation, passes))

        for i in passes:
            all_passes.append([satellite, *i, False])

    all_passes.sort(key=lambda data: data[1])

    for i in range(len(all_passes) - 1):
        current_end = all_passes[i][2]
        next_start = all_passes[i + 1][1]

        if next_start <= current_end:
            all_passes[i + 1][1] = current_end + dt.timedelta(seconds=1)
            all_passes[i][4] = True
            all_passes[i + 1][4] = True

    def prepare_data(data):
        name, start, end, max_elevation, is_highlighted = data
        orb = Orbital(name, 'tle.txt')
        apogee = orb.get_observer_look(max_elevation, lon, lat, alt)[1]
        return name, start.strftime('%Y.%m.%d %H:%M:%S'), end.strftime('%Y.%m.%d %H:%M:%S'), round(apogee, 2), is_highlighted

    all_passes = list(map(prepare_data, all_passes))

    return render_template('index.html', passes=all_passes, lon=lon, lat=lat, alt=alt)


@app.route('/download_trajectory', methods=['POST'])
def download_trajectory():
    data = request.get_json()
    satellite = data.get('satellite')
    start_time = dt.datetime.strptime(data.get('start'), '%Y.%m.%d %H:%M:%S')
    end_time = dt.datetime.strptime(data.get('end'), '%Y.%m.%d %H:%M:%S')
    lon = float(data.get('lon'))
    lat = float(data.get('lat'))
    alt = float(data.get('alt'))

    orb = Orbital(satellite, 'tle.txt')

    content = f'Satellite {satellite}\n'
    content += f'Start date & time {start_time.strftime("%Y-%m-%d %H:%M:%S UTC")}\n'
    content += '\n'
    content += 'Time (UTC) Azimuth Elevation\n'
    content += '\n'

    current_coords = orb.get_observer_look(start_time, lon, lat, alt)
    current_time = start_time
    shift = 0

    while current_time <= end_time:
        current_time = start_time + dt.timedelta(seconds=shift)
        content += f'{current_time.strftime("%H:%M:%S")} {current_coords[0]:.2f} {current_coords[1]:.2f}\n'
        current_coords = orb.get_observer_look(current_time, lon, lat, alt)
        shift += 1

    file = BytesIO(content.encode('utf-8'))

    return send_file(file, as_attachment=True, download_name='Траектория.txt', mimetype='text/plain')


if __name__ == '__main__':
    app.run()
