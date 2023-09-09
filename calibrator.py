from bisect import bisect_left
from collections import defaultdict
from datetime import timedelta
from statistics import pstdev, mean

PRECISION = 3
RELAXED_PRECISION = 1
MINIMUM_SAMPLES = 4

def print_measurements_per_temperature(d):
    for temp in sorted(d.keys()):
        print(temp, len(d[temp]))

def get_interpolation(a, b, target_dt):
    dt_a, val_a = a
    dt_b, val_b = b
    val_diff = val_b - val_a
    dt_diff = dt_b - dt_a
    target_diff = target_dt - dt_a
    return val_a + ((target_diff / dt_diff) * val_diff)

class Sensor:
    def __init__(self, name, temp_calibration_data, hum_calibration_data):
        self.name = name
        self.temp_calibration_data = temp_calibration_data
        self.hum_calibration_data = hum_calibration_data

    def calibrate_temp_yaml(self):
        output = ['calibrate_linear:', '  method: exact', '  datapoints:']
        for point in range(len(self.temp_calibration_data)):
            uncal_temp, ref_temp = self.temp_calibration_data[point]
            output.append('    - {:.3f} -> {:.3f}'.format(round(uncal_temp, PRECISION), round(ref_temp, PRECISION)))
        return '\n'.join(output).strip()

    def calibrate_hum_lambda(self):
        # In the future we may support having more than two points of calibration.
        # This lambda is only designed for two points so if there are more than two then we will use the first and last entries.
        low_data = self.hum_calibration_data[0]
        high_data = self.hum_calibration_data[-1]
        low_ref_temp_low_hum, low_ref_hum, low_temp_low_uncal_hum = low_data[0]
        high_ref_temp_low_hum, _, high_temp_low_uncal_hum = low_data[1]
        low_ref_temp_high_hum, high_ref_hum, low_temp_high_uncal_hum = high_data[0]
        high_ref_temp_high_hum, _, high_temp_high_uncal_hum = high_data[1]
        ref_low_hum = 'return {};'.format(low_ref_hum)
        ref_high_hum = 'return {};'.format(high_ref_hum)
        raw_low_hum = ['{{{:.3f}, {:.3f}}}'.format(round(low_ref_temp_low_hum, PRECISION), round(low_temp_low_uncal_hum, PRECISION)),
                       '{{{:.3f}, {:.3f}}}'.format(round(high_ref_temp_low_hum, PRECISION), round(high_temp_low_uncal_hum, PRECISION))]
        raw_high_hum = ['{{{:.3f}, {:.3f}}}'.format(round(low_ref_temp_high_hum, PRECISION), round(low_temp_high_uncal_hum, PRECISION)),
                        '{{{:.3f}, {:.3f}}}'.format(round(high_ref_temp_high_hum, PRECISION), round(high_temp_high_uncal_hum, PRECISION))]
        output = '''
lambda: |-
  static auto expected1 = [](float x) -> float {
    %s
  };
  static auto expected2 = [](float x) -> float {
    %s
  };
  static auto measured1 = [](float x) -> float {
    static std::vector<std::vector<float>> mapping = {
      %s
    };
    return segmented_linear(mapping, x);
  };
  static auto measured2 = [](float x) -> float {
    static std::vector<std::vector<float>> mapping = {
      %s
    };
    return segmented_linear(mapping, x);
  };
  return calibrated_humidity(
    id(temperature).state,
    x, expected1, expected2, measured1, measured2
  );
''' % (ref_low_hum, ref_high_hum, ', '.join(raw_low_hum), ', '.join(raw_high_hum))
        return output.strip()


class Calibrator:
    def __init__(self, ref_temps, ref_hums, uncal_temps, uncal_hums):
        self.derive_start_end(ref_temps)
        self.interval = timedelta(seconds=30)
        # Standardized time interval, interpolated from the datapoints provided.
        self.interval_ts_to_ref_temp, self.ref_temp_to_ts = self.standardize_temp(ref_temps)
        self.interval_ts_to_ref_hum, self.ref_hum_to_ts = self.standardize_hum(ref_hums)
        self.interval_ts_uncal_temps = self.process_uncal_temps(uncal_temps)
        self.interval_ts_uncal_hums = self.process_uncal_hums(uncal_hums)
        self.sensors = self.process_sensors()

    def get_sensors(self):
        return self.sensors

    def print_sensor_calibrations(self):
        for name, obj in self.get_sensors().items():
            print('')
            print('Sensor:', name)
            print('')
            print('========== Temperature Calibration ==========')
            print(obj.calibrate_temp_yaml())
            print('')
            print('=========== Humidity Calibration ============')
            print(obj.calibrate_hum_lambda())

    def derive_start_end(self, ref_temp):
        vals = ref_temp[list(ref_temp.keys())[0]]
        self.start_dt = vals[0][0]
        self.end_dt = vals[-1][0]

    def standardize_temp(self, temp):
        ts_to_temp = {}
        temp_to_ts = defaultdict(list)
        dt = self.start_dt + self.interval
        while dt < self.end_dt:
            avg_list = []
            for sensor in temp.keys():
                values = temp[sensor]
                i = bisect_left(values, (dt, 0))
                if i < 1 or i >= len(values):
                    continue
                avg_list.append(get_interpolation(values[i-1], values[i], dt))
            if avg_list:
                ts_to_temp[dt] = mean(avg_list)
                temp_to_ts[round(ts_to_temp[dt], RELAXED_PRECISION)].append(dt)
            dt = dt + self.interval
        return (ts_to_temp, temp_to_ts)

    def standardize_hum(self, hum):
        ts_to_hum = {}
        hum_to_ts = defaultdict(list)
        dt = self.start_dt + self.interval
        while dt < self.end_dt:
            avg_list = []
            for sensor in hum.keys():
                values = hum[sensor]
                i = bisect_left(values, (dt, 0))
                if i < 1 or i >= len(values):
                    continue
                avg_list.append(get_interpolation(values[i-1], values[i], dt))
            if avg_list:
                ts_to_hum[dt] = mean(avg_list)
                hum_to_ts[round(ts_to_hum[dt], RELAXED_PRECISION)].append(dt)
            dt = dt + self.interval

        return (ts_to_hum, hum_to_ts)

    def process_uncal_temps(self, temps):
        d = {}
        for sensor in temps.keys():
            d[sensor], _ = self.standardize_temp({sensor: temps[sensor]})
        return d

    def process_uncal_hums(self, hums):
        d = {}
        for sensor in hums.keys():
            d[sensor], _ = self.standardize_hum({sensor: hums[sensor]})
        return d

    def process_temperatures(self):
        candidate_temps = []

        for temp in sorted(list(self.ref_temp_to_ts.keys())):
            # Ignore temperatures that don't have many sample points and have at least a 2 degree interval.
            if len(self.ref_temp_to_ts[temp]) > MINIMUM_SAMPLES and (not candidate_temps or (candidate_temps and temp > candidate_temps[-1][0] + 2)):
                candidate_temps.append((temp, self.ref_temp_to_ts[temp]))

        sensors = {}

        for sensor in self.interval_ts_uncal_temps.keys():
            uncal_values = self.interval_ts_uncal_temps[sensor]
            sensors[sensor] = []

            for candidate_temp, candidate_times in candidate_temps:
                values = []
                for time in candidate_times:
                    values.append(uncal_values[time])
                sensors[sensor].append((mean(values), candidate_temp))

        return sensors

    def process_humidity(self):
        all_hums = self.interval_ts_to_ref_hum.values()
        hum_mean = mean(all_hums)
        hum_stddev = pstdev(all_hums)
        hum_low = round(hum_mean-hum_stddev, PRECISION)
        hum_high = round(hum_mean+hum_stddev, PRECISION)

        low_ts = self.ref_hum_to_ts[round(hum_low, RELAXED_PRECISION)]
        # mean_ts = self.ref_hum_to_ts[round(hum_mean, RELAXED_PRECISION)]
        high_ts = self.ref_hum_to_ts[round(hum_high, RELAXED_PRECISION)]

        low_hum_temps = set()
        low_hum_temp_ts = defaultdict(set)
        for ts in low_ts:
            t = self.interval_ts_to_ref_temp[ts]
            low_hum_temps.add((t, ts))
            low_hum_temp_ts[round(t)].add((t, ts))

        # mean_hum_temps = set()
        # mean_hum_temp_ts = defaultdict(set)
        # for ts in mean_ts:
        #     t = self.interval_ts_to_ref_temp[ts]
        #     mean_hum_temps.add((t, ts))
        #     mean_hum_temp_ts[round(t)].add((t, ts))

        high_hum_temps = set()
        high_hum_temp_ts = defaultdict(set)
        for ts in high_ts:
            t = self.interval_ts_to_ref_temp[ts]
            high_hum_temps.add((t, ts))
            high_hum_temp_ts[round(t)].add((t, ts))

        # print('low_humidity_temps')
        # print_measurements_per_temperature(low_hum_temp_ts)
        # # print('mean_humidity_temps')
        # # print_measurements_per_temperature(mean_hum_temp_ts)
        # print('high_humidity_temps')
        # print_measurements_per_temperature(high_hum_temp_ts)

        # print('low humidity temps', min(low_hum_temps), max(low_hum_temps))
        # # print('mean humidity temps', min(mean_hum_temps), max(mean_hum_temps))
        # print('high humidity temps', min(high_hum_temps), max(high_hum_temps))

        low_hum_low_temp, low_hum_low_temp_ts = min(low_hum_temps)
        low_hum_high_temp, low_hum_high_temp_ts = max(low_hum_temps)
        # mean_hum_low_temp, mean_hum_low_temp_ts = min(mean_hum_temps)
        # mean_hum_high_temp, mean_hum_high_temp_ts = max(mean_hum_temps)
        high_hum_low_temp, high_hum_low_temp_ts = min(high_hum_temps)
        high_hum_high_temp, high_hum_high_temp_ts = max(high_hum_temps)
        sensors = {}

        for sensor in self.interval_ts_uncal_hums.keys():
            values = self.interval_ts_uncal_hums[sensor]

            sensors[sensor] = [((low_hum_low_temp, hum_low, values[low_hum_low_temp_ts]),
                                    (low_hum_high_temp, hum_low, values[low_hum_high_temp_ts])),
                                    ((high_hum_low_temp, hum_high, values[high_hum_low_temp_ts]),
                                    (high_hum_high_temp, hum_high, values[high_hum_high_temp_ts]))
                                    ]

        return sensors

    def process_sensors(self):
        sensor_hum = self.process_humidity()
        sensor_temp = self.process_temperatures()
        sensors = {}

        temp_names = sorted(list(self.interval_ts_uncal_temps.keys()))
        hum_names = sorted(list(self.interval_ts_uncal_hums.keys()))

        for i in range(len(temp_names)):
            sensor_name_temp = temp_names[i]
            sensor_name_hum = hum_names[i]
            temp = sensor_temp[sensor_name_temp]
            humidity = sensor_hum[sensor_name_hum]

            sensors[sensor_name_temp] = Sensor(
                sensor_name_temp,
                temp,
                humidity
            )

        return sensors
