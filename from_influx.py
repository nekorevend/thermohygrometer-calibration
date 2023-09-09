from collections import defaultdict
from influx_config import INFLUX_BUCKET, INFLUX_ORG, INFLUX_TOKEN, INFLUX_URL
from datetime import datetime, timezone
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
import argparse
from calibrator import Calibrator

def dict_to_csv(d) -> str:
    lines = ['ENTITY_ID,TIMESTAMP,VALUE']
    for sensor in list(d.keys()):
        for dt, val in d[sensor]:
            lines.append('{},{},{}'.format(sensor, dt.strftime('%Y-%m-%dT%H:%M:%SZ'), val))
    return '\n'.join(sorted(lines))

parser = argparse.ArgumentParser(description='Calibrate temperature and humidity by reading directly from InfluxDB')
parser.add_argument('--start_time', required=True, type=str, help='Start time (in UTC) of the time period we want to query. Use the format "YYYY-MM-DD HH:MM:SS".')
parser.add_argument('--end_time', required=True, type=str, help='End time (in UTC) of the time period we want to query. Use the format "YYYY-MM-DD HH:MM:SS".')
parser.add_argument('--reference_temperature_sensors', required=True, type=str, help='List of entity_ids for reference (calibrated) thermometers. Use CSV format.')
parser.add_argument('--reference_humidity_sensors', required=True, type=str, help='List of entity_ids for reference (calibrated) hygrometers. Use CSV format.')
parser.add_argument('--uncalibrated_temperature_sensors', required=True, type=str, help='List of entity_ids for uncalibrated temperature sensors. Use CSV format.')
parser.add_argument('--uncalibrated_humidity_sensors', required=True, type=str, help='List of entity_ids for uncalibrated humidity sensors. Use CSV format.')
parser.add_argument('--output_to_csv', action=argparse.BooleanOptionalAction, help='Just output the query results to CSV files. Will create files in the current directory.')
parser.add_argument('--stored_temp_unit', default='C', type=str, help='What unit are the temperature values stored in? Defaults to "C".')
parser.add_argument('--reported_temp_unit', default='C', type=str, help='What unit are the temperature values reported in? Defaults to "C".')
args = parser.parse_args()

def f_to_c(v):
    return (v - 32) / 1.8

def c_to_f(v):
    return (v * 1.8) + 32

convert_temp = lambda v: v
if args.stored_temp_unit == 'C' and args.reported_temp_unit == 'F':
    convert_temp = lambda v: c_to_f(v)
if args.stored_temp_unit == 'F' and args.reported_temp_unit == 'C':
    convert_temp = lambda v: f_to_c(v)

client = influxdb_client.InfluxDBClient(
    url=INFLUX_URL,
    token=INFLUX_TOKEN,
    org=INFLUX_ORG
)

start_dt = datetime.strptime(args.start_time, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
end_dt = datetime.strptime(args.end_time, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
reference_temp_sensors = args.reference_temperature_sensors.split(',')
reference_hum_sensors = args.reference_humidity_sensors.split(',')
uncalibrated_temp_sensors = args.uncalibrated_temperature_sensors.split(',')
uncalibrated_hum_sensors = args.uncalibrated_humidity_sensors.split(',')
thirty_sec_ts_to_hum = {}
hum_to_ts = defaultdict(list)
precision = 3
relaxed_precision = 1

start_dt_str = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
end_dt_str = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

query_reference_temperatures = 'from(bucket:"{}")\
|> range(start: {}, stop: {})\
|> filter(fn: (r) => ({}))\
|> filter(fn: (r) => r["_field"] == "value")\
|> filter(fn: (r) => r["_measurement"] == "°{}")'.format(
        INFLUX_BUCKET,
        start_dt_str,
        end_dt_str,
        ' or '.join('r["entity_id"] == "{}"'.format(s) for s in reference_temp_sensors),
        args.stored_temp_unit)

query_uncalibrated_temperatures = 'from(bucket:"{}")\
|> range(start: {}, stop: {})\
|> filter(fn: (r) => ({}))\
|> filter(fn: (r) => r["_field"] == "value")\
|> filter(fn: (r) => r["_measurement"] == "°{}")'.format(
        INFLUX_BUCKET,
        start_dt_str,
        end_dt_str,
        ' or '.join('r["entity_id"] == "{}"'.format(s) for s in uncalibrated_temp_sensors),
        args.stored_temp_unit)

query_reference_humidities = 'from(bucket:"{}")\
|> range(start: {}, stop: {})\
|> filter(fn: (r) => ({}))\
|> filter(fn: (r) => (r._field == "value"))'.format(
        INFLUX_BUCKET,
        start_dt_str,
        end_dt_str,
        ' or '.join('r["entity_id"] == "{}"'.format(s) for s in reference_hum_sensors))

query_uncalibrated_humidities = 'from(bucket:"{}")\
|> range(start: {}, stop: {})\
|> filter(fn: (r) => ({}))\
|> filter(fn: (r) => (r._field == "value"))'.format(
        INFLUX_BUCKET,
        start_dt_str,
        end_dt_str,
        ' or '.join('r["entity_id"] == "{}"'.format(s) for s in uncalibrated_hum_sensors))

query_api = client.query_api()
query_result = query_api.query(org=INFLUX_ORG, query=query_reference_temperatures)
reference_temp_sensors = defaultdict(list)
for table in query_result:
    for record in table.records:
        reference_temp_sensors[record['entity_id']].append((record.get_time(), convert_temp(record.get_value())))

query_result = query_api.query(org=INFLUX_ORG, query=query_reference_humidities)
reference_hum_results = defaultdict(list)
for table in query_result:
    for record in table.records:
        reference_hum_results[record['entity_id']].append((record.get_time(), record.get_value()))

query_api = client.query_api()
query_result = query_api.query(org=INFLUX_ORG, query=query_uncalibrated_temperatures)
uncalibrated_temp_sensors = defaultdict(list)
for table in query_result:
    for record in table.records:
        uncalibrated_temp_sensors[record['entity_id']].append((record.get_time(), convert_temp(record.get_value())))

query_result = query_api.query(org=INFLUX_ORG, query=query_uncalibrated_humidities)
uncalibrated_hum_results = defaultdict(list)
for table in query_result:
    for record in table.records:
        uncalibrated_hum_results[record['entity_id']].append((record.get_time(), record.get_value()))

if args.output_to_csv:
    start_str = start_dt.strftime('%Y%m%d_%H%M%S')
    end_str = end_dt.strftime('%Y%m%d_%H%M%S')
    reference_temp_file = 'reference_temperatures_{}_{}.csv'.format(start_str, end_str)
    reference_hum_file = 'reference_humidities_{}_{}.csv'.format(start_str, end_str)
    uncalibrated_temp_file = 'uncalibrated_temperatures_{}_{}.csv'.format(start_str, end_str)
    uncalibrated_hum_file = 'uncalibrated_humidities_{}_{}.csv'.format(start_str, end_str)
    with open(reference_temp_file, 'w') as f:
        f.write(dict_to_csv(reference_temp_sensors))
    with open(reference_hum_file, 'w') as f:
        f.write(dict_to_csv(reference_hum_results))
    with open(uncalibrated_temp_file, 'w') as f:
        f.write(dict_to_csv(uncalibrated_temp_sensors))
    with open(uncalibrated_hum_file, 'w') as f:
        f.write(dict_to_csv(uncalibrated_hum_results))
else:
    cal = Calibrator(reference_temp_sensors, reference_hum_results, uncalibrated_temp_sensors, uncalibrated_hum_results)
    cal.print_sensor_calibrations()