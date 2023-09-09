from collections import defaultdict
from datetime import datetime, timezone
from calibrator import Calibrator
import argparse

def parse_csv(s):
    d = defaultdict(list)
    for line in s.split('\n'):
        if 'TIMESTAMP' in line:
            continue
        entity, ts, value = line.split(',')
        d[entity].append((datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc), float(value)))
    return d

parser = argparse.ArgumentParser(description='''Calibrate temperature and humidity by reading from CSV files.
                                                The expected format is: SENSOR_ID,TIMESTAMP,VALUE''')
parser.add_argument('--reference_temperature_csv', '--rt', required=True, type=str, help='Path to CSV file for reference temperature data.')
parser.add_argument('--reference_humidity_csv', '--rh', required=True, type=str, help='Path to CSV file for reference humidity data.')
parser.add_argument('--uncalibrated_temperature_csv', '--ut', required=True, type=str, help='Path to CSV file for uncalibrated temperature data.')
parser.add_argument('--uncalibrated_humidity_csv', '--uh', required=True, type=str, help='Path to CSV file for uncalibrated humidity data.')
args = parser.parse_args()

reference_temp_sensors = None
with open(args.reference_temperature_csv, 'r') as f:
    reference_temp_sensors = parse_csv(f.read())
reference_hum_sensors = None
with open(args.reference_humidity_csv, 'r') as f:
    reference_hum_sensors = parse_csv(f.read())
uncalibrated_temp_sensors = None
with open(args.uncalibrated_temperature_csv, 'r') as f:
    uncalibrated_temp_sensors = parse_csv(f.read())
uncalibrated_hum_sensors = None
with open(args.uncalibrated_humidity_csv, 'r') as f:
    uncalibrated_hum_sensors = parse_csv(f.read())

if not reference_temp_sensors or not reference_hum_sensors or not uncalibrated_temp_sensors or not uncalibrated_hum_sensors:
    raise Exception('Unable to read all CSVs.')

cal = Calibrator(reference_temp_sensors, reference_hum_sensors, uncalibrated_temp_sensors, uncalibrated_hum_sensors)
cal.print_sensor_calibrations()