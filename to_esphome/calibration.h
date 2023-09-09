#ifndef CALIBRATION_H
#define CALIBRATION_H

#include <vector>

float segmented_linear(std::vector<std::vector<float>> mapping, float x) {
  float res = x;
  if (x < mapping[0][0]) {
    // Less than mapping
    float in_a = mapping[0][0];
    float out_a = mapping[0][1];
    float in_b = mapping[1][0];
    float out_b = mapping[1][1];
    float in_diff = in_b - in_a;
    float out_diff = out_b - out_a;
    float diff = in_a - x;
    float ratio = diff / in_diff;
    res = out_a - (ratio * out_diff);
  } else if (x > mapping[mapping.size() - 1][0]) {
    // More than mapping
    int i = mapping.size() - 1;
    float in_a = mapping[i-1][0];
    float out_a = mapping[i-1][1];
    float in_b = mapping[i][0];
    float out_b = mapping[i][1];
    float in_diff = in_b - in_a;
    float out_diff = out_b - out_a;
    float diff = x - in_b;
    float ratio = diff / in_diff;
    res = out_b + (ratio * out_diff);
  } else {
    // Within mapping
    for (int i = 1; i < mapping.size(); i++) {
      float in_a = mapping[i-1][0];
      float out_a = mapping[i-1][1];
      float in_b = mapping[i][0];
      float out_b = mapping[i][1];
      if (x <= in_b) {
        float in_diff = in_b - in_a;
        float out_diff = out_b - out_a;
        float diff = x - in_a;
        float ratio = diff / in_diff;
        res = out_a + (ratio * out_diff);
        break;
      }
    }
  }
  return res;
}

float correlation_coefficient(float x1, float y1, float x2, float y2) {
    float avg_x = (x1 + x2) / 2;
    float avg_y = (y1 + y2) / 2;
    float numerator = (x1 - avg_x) * (y1 - avg_y) + (x2 - avg_x) * (y2 - avg_y);
    float denominator = sqrt(
                            pow(x1 - avg_x, 2) +
                            pow(x2 - avg_x, 2)
                            ) *
                        sqrt(
                            pow(y1 - avg_y, 2) +
                            pow(y2 - avg_y, 2)
                        );
    return numerator / denominator;
}

std::pair<float, float> linear_fit(float x1, float y1, float x2, float y2) {
    float correlation_coefficient_value = correlation_coefficient(x1, y1, x2, y2);
    float slope = correlation_coefficient_value * (y2 - y1) / (x2 - x1);
    float intercept = y1 - slope * x1;
    return std::make_pair(slope, intercept);
}

float calibrated_humidity(
        float temp,
        float hum,
        const std::function<float(float)> &expected1,
        const std::function<float(float)> &expected2,
        const std::function<float(float)> &measured1,
        const std::function<float(float)> &measured2) {
    std::pair<float, float> pair = linear_fit(
            measured1(temp),
            expected1(temp),
            measured2(temp),
            expected2(temp)
        );
    float slope = pair.first;
    float intercept = pair.second;
    return (slope * hum) + intercept;
}

#endif