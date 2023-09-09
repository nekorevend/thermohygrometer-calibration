# thermohygrometer-calibration
Calibrate temperature and humidity sensors for ESPHome.

Using reference sensors alongside the sensors you want to calibrate, the tool will print out ESPHome-compatible YAML lines to calibrate the uncalibrated sensors.

**This is assuming you already have reference sensors and that they have been placed next to the uncalibrated sensors.** Wait a few days to gather enough data/variance for the tool to provide good calibration output.

You will not recognize the humidity calibration output because it is custom. I write about it, and a whole lot more about my adventure, [here](https://victorchang.codes/humidity-readings-a-rabbit-hole).

There are two entry points into this tool:

## From InfluxDB
When provided necessary authentication details in an `influx_config.py` file you create, the tool is able to query the database directly to get the necessary values.

Example command:
```
python from_influx.py
    --start_time "2023-08-31 07:00:00" --end_time "2023-09-03 07:00:00"
    --reference_temperature_sensors sensor_a_temp,sensor_b_temp
    --reference_humidity_sensors sensor_a_hum,sensor_b_hum
    --uncalibrated_temperature_sensors sensor_c_temp,sensor_d_temp
    --uncalibrated_humidity_sensors sensor_c_hum,sensor_d_hum
```

This command treats "a" and "b" as reference sensors, ie. the ones we believe are reporting the correct values.
No two sensors are ever identical, so the sensor values are averaged into a single "truth".

Sensors "c" and "d" are then compared against the reference "truth", and calibration YAML is outputted for each of these sensors.

The `influx_config.py` should contain this:

```python
INFLUX_ORG='your_org'
INFLUX_BUCKET='your_bucket'  # probably "homeassistant"
INFLUX_TOKEN='your_token'
INFLUX_URL='http://your_db_ip:8086'
```

## From CSV
If you already have the values on hand, you can pass them in using CSV files in the format:

`SENSOR_ID,TIMESTAMP,VALUE`

Which looks like this:

```
sensor_c_temp,2023-08-05T09:02:03Z,24.15
```

Example command:
```
python from_csv.py 
    --reference_temperature_csv ref_temp.csv
    --reference_humidity_csv ref_hum.csv
    --uncalibrated_temperature_csv uncal_temp.csv
    --uncalibrated_humidity_csv uncal_hum.csv
```

This route will behave the same as the Influx route. In fact, you can add `--output_to_csv` to the `from_influx.py` command and it will create the four CSVs that you can then pass into `from_csv.py` to output identical calibration configurations.

## Example output
```yaml
Sensor: sensor_c_temp

========== Temperature Calibration ==========
calibrate_linear:
  method: exact
  datapoints:
    - 21.985 -> 20.100
    - 23.958 -> 22.200
    - 25.942 -> 24.300
    - 27.808 -> 26.400
    - 29.633 -> 28.500
    - 31.490 -> 30.600
    - 33.600 -> 32.700
    - 35.722 -> 34.800

=========== Humidity Calibration ============
lambda: |-
  static auto expected1 = [](float x) -> float {
    return 38.065;
  };
  static auto expected2 = [](float x) -> float {
    return 48.819;
  };
  static auto measured1 = [](float x) -> float {
    static std::vector<std::vector<float>> mapping = {
      {23.116, 36.839}, {31.777, 38.114}
    };
    return segmented_linear(mapping, x);
  };
  static auto measured2 = [](float x) -> float {
    static std::vector<std::vector<float>> mapping = {
      {20.678, 44.844}, {28.367, 46.836}
    };
    return segmented_linear(mapping, x);
  };
  return calibrated_humidity(
    id(temperature).state,
    x, expected1, expected2, measured1, measured2
  );
```

## The calibration.h file
You'll notice that the Humidity Calibration section calls `segmented_linear()` and `calibrated_humidity()`. These are not provided by ESPHome. I've provided these functions in `to_esphome/calibration.h`. Copy that file to your ESPHome instance and import it in your YAML like so:

```yaml
esphome:
  name: my_sensor
  includes:
    - calibration.h
```
# How to Install
Every platform is different so these instructions are only in general terms.

1. Or install [git](https://git-scm.com/) and `git clone` this repository.
1. Use a [Python virtual environment](https://docs.python.org/3/library/venv.html) with [pip](https://packaging.python.org/en/latest/key_projects/#pip) to set up the dependency for this tool.
    - Dependency installation command is typically: `python3 -m pip install -r requirements.txt`

# Assumptions made

To avoid complicating the logic, I've made some assumptions about what's being provided to the tool.

1. The set of sensors given for `uncalibrated_temperature_sensors` and `uncalibrated_humidity_sensors` are identical. Same length and contains the same sensors.
    - This means that your sensors are expected to be temperature+humidity combo sensors. This is true for me so I did not dive in further. If you are trying to calibrate sensors that are only one of these types... try to fake some dummy data. I would duplicate the data from another sensor and just change the name in the CSV, then use the `from_csv.py` route.
        - Make sure the dummy name matches the format of the sensor you want to calibrate, see the next assumption below.
    - Note that this restriction does not apply to the reference sensors. The tool will just average them together before using the data.
2. Your sensor names are consistent between temperature and humidity. To match up the temperature and humidity entities for each sensor, I am assuming that the list of temperature entities and list of humidity entities would alpha-sort into the same order.
    - The respective sensors at each index of both lists should end up referring to the same actual sensor.