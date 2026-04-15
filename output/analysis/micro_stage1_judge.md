# Stage 1 Component Validity (Normalized Outputs; Per-Run)
This report uses an LLM judge to label whether each extracted component is a plausible **primary manufacturing component** for a given technology. Candidates are sourced from **normalized STDN output CSVs** and evaluated per run. A cache keyed by (technology, component) avoids repeated judge calls.

- normalized_dir: `output/normalized`
- configs: v1v1v1, d2v1v1, d3v1v1, d4v1v1, d5v1v1
- judge_model: `openai:gpt-4.1`
- cache: `output/analysis/stage1_component_judge_cache.jsonl`
- judged_new: 1567
- judged_cached: 16

## Per-configuration variability summary (per-run invalid rate)

| config | runs_entries | invalid_rate_median | invalid_rate_mean | invalid_rate_min | invalid_rate_max | component_count_median | component_count_mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v1v1v1 | 300 | 0.000 | 0.063 | 0.000 | 0.600 | 7.000 | 7.050 |
| d2v1v1 | 298 | 0.000 | 0.070 | 0.000 | 0.500 | 5.000 | 5.218 |
| d3v1v1 | 293 | 0.000 | 0.049 | 0.000 | 0.500 | 6.000 | 6.137 |
| d4v1v1 | 290 | 0.000 | 0.065 | 0.000 | 0.500 | 6.000 | 6.666 |
| d5v1v1 | 295 | 0.000 | 0.067 | 0.000 | 0.571 | 6.000 | 6.559 |

## Per-technology comparison (median invalid rate across runs)

| technology | v1v1v1_median_invalid_rate | d3v1v1_median_invalid_rate | delta_d3_minus_v1 |
| --- | --- | --- | --- |
| 5G Base Station (Macro Cell) | 0.000 | 0.000 | 0.000 |
| AESA Radar Module (Military) | 0.000 | 0.000 | 0.000 |
| Automated Guided Vehicle (AGV) Controller | 0.000 | 0.000 | 0.000 |
| Automotive ECU (Engine Control Unit) | 0.400 | 0.200 | -0.200 |
| Automotive LED Headlamp Module | 0.125 | 0.000 | -0.125 |
| Automotive Night Vision System | 0.000 | 0.000 | 0.000 |
| Automotive Tire Pressure Monitoring System (TPMS) | 0.200 | 0.000 | -0.200 |
| Autonomous Vehicle Compute Platform | 0.000 | 0.000 | 0.000 |
| CNC Machine Tool Controller | 0.000 | 0.091 | 0.091 |
| CT Scanner | 0.000 | 0.000 | 0.000 |
| Collaborative Robot (Cobot) Arm | 0.000 | 0.000 | 0.000 |
| Contactless Payment Card | 0.250 | 0.000 | -0.250 |
| CubeSat On-Board Computer | 0.125 | 0.167 | 0.042 |
| Data Center Server | 0.111 | 0.083 | -0.028 |
| Digital Signage Player | 0.000 | 0.200 | 0.200 |
| Drone Flight Controller | 0.400 | 0.250 | -0.150 |
| EV On-Board Charger | 0.000 | 0.000 | 0.000 |
| EV Traction Inverter | 0.000 | 0.000 | 0.000 |
| Edge AI Inference Box | 0.000 | 0.000 | 0.000 |
| Electronic Warfare Jammer Pod | 0.000 | 0.000 | 0.000 |
| Enterprise Storage Array (SAN) | 0.000 | 0.000 | 0.000 |
| Face Recognition Access Control System | 0.000 | 0.000 | 0.000 |
| Fiber-Optic Communication Terminal | 0.143 | 0.000 | -0.143 |
| Fiber-Optic Illumination System | 0.000 | 0.000 | 0.000 |
| GPS Timing Receiver | 0.143 | 0.000 | -0.143 |
| Hearing Aid | 0.167 | 0.143 | -0.024 |
| Implantable Cardiac Defibrillator (ICD) | 0.000 | 0.000 | 0.000 |
| Industrial IoT Gateway | 0.000 | 0.000 | 0.000 |
| Industrial Motor Drive (Variable Frequency) | 0.000 | 0.000 | 0.000 |
| Industrial PLC Module | 0.167 | 0.125 | -0.042 |
| Industrial Welding Robot Controller | 0.000 | 0.000 | 0.000 |
| Inertial Navigation System | 0.125 | 0.000 | -0.125 |
| LED Luminaire | 0.000 | 0.000 | 0.000 |
| Laptop PC | 0.000 | 0.059 | 0.059 |
| Large-Format OLED Television | 0.000 | 0.000 | 0.000 |
| Laser Projector | 0.000 | 0.000 | 0.000 |
| LiDAR Sensor System | 0.143 | 0.000 | -0.143 |
| MRI Machine | 0.000 | 0.000 | 0.000 |
| Medical Ultrasound System | 0.000 | 0.000 | 0.000 |
| Microwave Backhaul Radio | 0.000 | 0.000 | 0.000 |
| Military Avionics Module | 0.000 | 0.000 | 0.000 |
| Near-Infrared Spectroscopy Instrument | 0.000 | 0.000 | 0.000 |
| Network Switch/Router | 0.000 | 0.000 | 0.000 |
| Point-of-Sale Terminal | 0.000 | 0.000 | 0.000 |
| Pulse Oximeter | 0.143 | 0.000 | -0.143 |
| Satellite Communication Terminal | 0.000 | 0.000 | 0.000 |
| Servo Motor Drive | 0.000 | 0.143 | 0.143 |
| Small Cell (5G Picocell) | 0.000 | 0.000 | 0.000 |
| Smart Doorbell Camera | 0.000 | 0.143 | 0.143 |
| Smart Speaker / Voice Assistant Device | 0.167 | 0.000 | -0.167 |
| Smartphone | 0.200 | 0.400 | 0.200 |
| Solar String Inverter | 0.000 | 0.000 | 0.000 |
| Space-Grade Solar Array Power Regulator | 0.000 | 0.250 | 0.250 |
| Space-Hardened Satellite Computer | 0.000 | 0.000 | 0.000 |
| Star Tracker (Satellite Attitude Sensor) | 0.286 | 0.113 | -0.173 |
| Submarine Cable Repeater | 0.286 | 0.167 | -0.119 |
| Surveillance DVR/NVR | 0.000 | 0.000 | 0.000 |
| Thermal Imaging Sight | 0.000 | 0.000 | 0.000 |
| UV-C Disinfection System | 0.000 | 0.000 | 0.000 |
| WiFi 7 Access Point | 0.000 | 0.000 | 0.000 |
