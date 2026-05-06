# Stage 1 Component Run Identity + Core/Union Diagnostics

This report analyzes per-technology Stage 1 component sets across repeated runs to detect:
- technologies where all runs are identical (unique_run_sets = 1)
- how much of each set is a stable core (intersection across runs)
- how large the swing/tail is (union minus intersection)

- normalized_dir: `output/normalized`
- configs: v1v1v1, d3v1v1
- min_runs: 2

## Summary by configuration

| config | technologies | runs_total | technologies_all_runs_identical | pct_technologies_all_runs_identical | macro_median_unique_run_sets | macro_mean_unique_run_sets | macro_median_core_ratio | macro_mean_core_ratio | macro_median_jaccard_core_union | macro_mean_jaccard_core_union |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| d3v1v1 | 60 | 293 | 0 | 0.000 | 5.000 | 4.817 | 0.200 | 0.221 | 0.091 | 0.108 |
| v1v1v1 | 60 | 300 | 1 | 0.017 | 5.000 | 4.750 | 0.429 | 0.417 | 0.250 | 0.263 |

## Per-technology stats (per config)

| config | technology | runs | unique_run_sets | identical_runs | median_set_size | intersection_size | union_size | core_ratio | jaccard_core_union | swing_components_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| d3v1v1 | 5G Base Station (Macro Cell) | 4 | 4 | False | 7.500 | 4 | 13 | 0.533 | 0.308 | 9 |
| d3v1v1 | AESA Radar Module (Military) | 5 | 5 | False | 6.000 | 0 | 15 | 0.000 | 0.000 | 15 |
| d3v1v1 | Automated Guided Vehicle (AGV) Controller | 5 | 4 | False | 3.000 | 1 | 9 | 0.333 | 0.111 | 8 |
| d3v1v1 | Automotive ECU (Engine Control Unit) | 5 | 5 | False | 5.000 | 1 | 10 | 0.200 | 0.100 | 9 |
| d3v1v1 | Automotive LED Headlamp Module | 4 | 4 | False | 5.500 | 0 | 19 | 0.000 | 0.000 | 19 |
| d3v1v1 | Automotive Night Vision System | 5 | 5 | False | 4.000 | 1 | 9 | 0.250 | 0.111 | 8 |
| d3v1v1 | Automotive Tire Pressure Monitoring System (TPMS) | 5 | 5 | False | 4.000 | 0 | 9 | 0.000 | 0.000 | 9 |
| d3v1v1 | Autonomous Vehicle Compute Platform | 5 | 5 | False | 7.000 | 0 | 18 | 0.000 | 0.000 | 18 |
| d3v1v1 | CNC Machine Tool Controller | 5 | 5 | False | 6.000 | 2 | 16 | 0.333 | 0.125 | 14 |
| d3v1v1 | CT Scanner | 5 | 5 | False | 6.000 | 2 | 11 | 0.333 | 0.182 | 9 |
| d3v1v1 | Collaborative Robot (Cobot) Arm | 5 | 5 | False | 5.000 | 3 | 9 | 0.600 | 0.333 | 6 |
| d3v1v1 | Contactless Payment Card | 5 | 5 | False | 3.000 | 2 | 7 | 0.667 | 0.286 | 5 |
| d3v1v1 | CubeSat On-Board Computer | 5 | 5 | False | 5.000 | 0 | 14 | 0.000 | 0.000 | 14 |
| d3v1v1 | Data Center Server | 5 | 5 | False | 12.000 | 3 | 21 | 0.250 | 0.143 | 18 |
| d3v1v1 | Digital Signage Player | 5 | 5 | False | 8.000 | 3 | 14 | 0.375 | 0.214 | 11 |
| d3v1v1 | Drone Flight Controller | 5 | 5 | False | 5.000 | 1 | 11 | 0.200 | 0.091 | 10 |
| d3v1v1 | EV On-Board Charger | 5 | 5 | False | 5.000 | 2 | 8 | 0.400 | 0.250 | 6 |
| d3v1v1 | EV Traction Inverter | 5 | 5 | False | 6.000 | 2 | 13 | 0.333 | 0.154 | 11 |
| d3v1v1 | Edge AI Inference Box | 5 | 5 | False | 6.000 | 0 | 18 | 0.000 | 0.000 | 18 |
| d3v1v1 | Electronic Warfare Jammer Pod | 5 | 5 | False | 5.000 | 2 | 12 | 0.400 | 0.167 | 10 |
| d3v1v1 | Enterprise Storage Array (SAN) | 5 | 5 | False | 10.000 | 1 | 20 | 0.100 | 0.050 | 19 |
| d3v1v1 | Face Recognition Access Control System | 5 | 5 | False | 5.000 | 0 | 10 | 0.000 | 0.000 | 10 |
| d3v1v1 | Fiber-Optic Communication Terminal | 4 | 4 | False | 5.000 | 1 | 12 | 0.200 | 0.083 | 11 |
| d3v1v1 | Fiber-Optic Illumination System | 4 | 4 | False | 5.000 | 1 | 11 | 0.200 | 0.091 | 10 |
| d3v1v1 | GPS Timing Receiver | 5 | 5 | False | 5.000 | 1 | 7 | 0.200 | 0.143 | 6 |
| d3v1v1 | Hearing Aid | 5 | 5 | False | 5.000 | 2 | 12 | 0.400 | 0.167 | 10 |
| d3v1v1 | Implantable Cardiac Defibrillator (ICD) | 5 | 5 | False | 5.000 | 0 | 11 | 0.000 | 0.000 | 11 |
| d3v1v1 | Industrial IoT Gateway | 5 | 5 | False | 5.000 | 1 | 11 | 0.200 | 0.091 | 10 |
| d3v1v1 | Industrial Motor Drive (Variable Frequency) | 5 | 5 | False | 6.000 | 1 | 16 | 0.167 | 0.062 | 15 |
| d3v1v1 | Industrial PLC Module | 5 | 5 | False | 6.000 | 1 | 11 | 0.167 | 0.091 | 10 |
| d3v1v1 | Industrial Welding Robot Controller | 5 | 5 | False | 5.000 | 2 | 14 | 0.400 | 0.143 | 12 |
| d3v1v1 | Inertial Navigation System | 5 | 5 | False | 5.000 | 1 | 12 | 0.200 | 0.083 | 11 |
| d3v1v1 | LED Luminaire | 5 | 5 | False | 5.000 | 0 | 14 | 0.000 | 0.000 | 14 |
| d3v1v1 | Laptop PC | 5 | 5 | False | 13.000 | 4 | 24 | 0.308 | 0.167 | 20 |
| d3v1v1 | Large-Format OLED Television | 5 | 5 | False | 6.000 | 3 | 10 | 0.500 | 0.300 | 7 |
| d3v1v1 | Laser Projector | 5 | 5 | False | 7.000 | 1 | 15 | 0.143 | 0.067 | 14 |
| d3v1v1 | LiDAR Sensor System | 5 | 5 | False | 5.000 | 1 | 10 | 0.200 | 0.100 | 9 |
| d3v1v1 | MRI Machine | 5 | 5 | False | 5.000 | 2 | 18 | 0.400 | 0.111 | 16 |
| d3v1v1 | Medical Ultrasound System | 5 | 5 | False | 7.000 | 2 | 14 | 0.286 | 0.143 | 12 |
| d3v1v1 | Microwave Backhaul Radio | 5 | 5 | False | 7.000 | 3 | 15 | 0.429 | 0.200 | 12 |
| d3v1v1 | Military Avionics Module | 5 | 5 | False | 5.000 | 1 | 11 | 0.200 | 0.091 | 10 |
| d3v1v1 | Near-Infrared Spectroscopy Instrument | 5 | 5 | False | 6.000 | 0 | 14 | 0.000 | 0.000 | 14 |
| d3v1v1 | Network Switch/Router | 5 | 5 | False | 7.000 | 2 | 18 | 0.286 | 0.111 | 16 |
| d3v1v1 | Point-of-Sale Terminal | 5 | 5 | False | 6.000 | 2 | 14 | 0.333 | 0.143 | 12 |
| d3v1v1 | Pulse Oximeter | 5 | 5 | False | 7.000 | 0 | 12 | 0.000 | 0.000 | 12 |
| d3v1v1 | Satellite Communication Terminal | 5 | 5 | False | 5.000 | 1 | 11 | 0.200 | 0.091 | 10 |
| d3v1v1 | Servo Motor Drive | 5 | 5 | False | 7.000 | 2 | 14 | 0.286 | 0.143 | 12 |
| d3v1v1 | Small Cell (5G Picocell) | 4 | 4 | False | 8.500 | 5 | 13 | 0.588 | 0.385 | 8 |
| d3v1v1 | Smart Doorbell Camera | 5 | 5 | False | 7.000 | 2 | 13 | 0.286 | 0.154 | 11 |
| d3v1v1 | Smart Speaker / Voice Assistant Device | 5 | 5 | False | 4.000 | 2 | 9 | 0.500 | 0.222 | 7 |
| d3v1v1 | Smartphone | 5 | 2 | False | 5.000 | 1 | 5 | 0.200 | 0.200 | 4 |
| d3v1v1 | Solar String Inverter | 4 | 4 | False | 6.000 | 0 | 11 | 0.000 | 0.000 | 11 |
| d3v1v1 | Space-Grade Solar Array Power Regulator | 5 | 5 | False | 3.000 | 0 | 10 | 0.000 | 0.000 | 10 |
| d3v1v1 | Space-Hardened Satellite Computer | 5 | 5 | False | 6.000 | 0 | 20 | 0.000 | 0.000 | 20 |
| d3v1v1 | Star Tracker (Satellite Attitude Sensor) | 4 | 4 | False | 6.500 | 1 | 18 | 0.154 | 0.056 | 17 |
| d3v1v1 | Submarine Cable Repeater | 5 | 5 | False | 4.000 | 1 | 12 | 0.250 | 0.083 | 11 |
| d3v1v1 | Surveillance DVR/NVR | 5 | 5 | False | 7.000 | 1 | 19 | 0.143 | 0.053 | 18 |
| d3v1v1 | Thermal Imaging Sight | 5 | 5 | False | 6.000 | 0 | 20 | 0.000 | 0.000 | 20 |
| d3v1v1 | UV-C Disinfection System | 5 | 5 | False | 6.000 | 0 | 14 | 0.000 | 0.000 | 14 |
| d3v1v1 | WiFi 7 Access Point | 5 | 5 | False | 7.000 | 1 | 18 | 0.143 | 0.056 | 17 |
| v1v1v1 | 5G Base Station (Macro Cell) | 5 | 5 | False | 8.000 | 5 | 12 | 0.625 | 0.417 | 7 |
| v1v1v1 | AESA Radar Module (Military) | 5 | 5 | False | 7.000 | 3 | 12 | 0.429 | 0.250 | 9 |
| v1v1v1 | Automated Guided Vehicle (AGV) Controller | 5 | 4 | False | 7.000 | 4 | 10 | 0.571 | 0.400 | 6 |
| v1v1v1 | Automotive ECU (Engine Control Unit) | 5 | 5 | False | 5.000 | 3 | 9 | 0.600 | 0.333 | 6 |
| v1v1v1 | Automotive LED Headlamp Module | 5 | 5 | False | 8.000 | 3 | 12 | 0.375 | 0.250 | 9 |
| v1v1v1 | Automotive Night Vision System | 5 | 5 | False | 5.000 | 4 | 9 | 0.800 | 0.444 | 5 |
| v1v1v1 | Automotive Tire Pressure Monitoring System (TPMS) | 5 | 5 | False | 5.000 | 3 | 8 | 0.600 | 0.375 | 5 |
| v1v1v1 | Autonomous Vehicle Compute Platform | 5 | 5 | False | 7.000 | 2 | 17 | 0.286 | 0.118 | 15 |
| v1v1v1 | CNC Machine Tool Controller | 5 | 5 | False | 8.000 | 2 | 14 | 0.250 | 0.143 | 12 |
| v1v1v1 | CT Scanner | 5 | 5 | False | 9.000 | 7 | 11 | 0.778 | 0.636 | 4 |
| v1v1v1 | Collaborative Robot (Cobot) Arm | 5 | 4 | False | 7.000 | 6 | 9 | 0.857 | 0.667 | 3 |
| v1v1v1 | Contactless Payment Card | 5 | 4 | False | 4.000 | 2 | 6 | 0.500 | 0.333 | 4 |
| v1v1v1 | CubeSat On-Board Computer | 5 | 5 | False | 8.000 | 0 | 16 | 0.000 | 0.000 | 16 |
| v1v1v1 | Data Center Server | 5 | 5 | False | 9.000 | 4 | 13 | 0.444 | 0.308 | 9 |
| v1v1v1 | Digital Signage Player | 5 | 5 | False | 7.000 | 0 | 15 | 0.000 | 0.000 | 15 |
| v1v1v1 | Drone Flight Controller | 5 | 4 | False | 5.000 | 2 | 9 | 0.400 | 0.222 | 7 |
| v1v1v1 | EV On-Board Charger | 5 | 5 | False | 7.000 | 3 | 12 | 0.429 | 0.250 | 9 |
| v1v1v1 | EV Traction Inverter | 5 | 5 | False | 7.000 | 4 | 10 | 0.571 | 0.400 | 6 |
| v1v1v1 | Edge AI Inference Box | 5 | 5 | False | 8.000 | 3 | 13 | 0.375 | 0.231 | 10 |
| v1v1v1 | Electronic Warfare Jammer Pod | 5 | 5 | False | 8.000 | 2 | 15 | 0.250 | 0.133 | 13 |
| v1v1v1 | Enterprise Storage Array (SAN) | 5 | 5 | False | 9.000 | 2 | 15 | 0.222 | 0.133 | 13 |
| v1v1v1 | Face Recognition Access Control System | 5 | 4 | False | 7.000 | 3 | 12 | 0.429 | 0.250 | 9 |
| v1v1v1 | Fiber-Optic Communication Terminal | 5 | 5 | False | 6.000 | 1 | 13 | 0.167 | 0.077 | 12 |
| v1v1v1 | Fiber-Optic Illumination System | 5 | 5 | False | 6.000 | 2 | 11 | 0.333 | 0.182 | 9 |
| v1v1v1 | GPS Timing Receiver | 5 | 5 | False | 7.000 | 4 | 11 | 0.571 | 0.364 | 7 |
| v1v1v1 | Hearing Aid | 5 | 5 | False | 6.000 | 3 | 8 | 0.500 | 0.375 | 5 |
| v1v1v1 | Implantable Cardiac Defibrillator (ICD) | 5 | 5 | False | 6.000 | 4 | 8 | 0.667 | 0.500 | 4 |
| v1v1v1 | Industrial IoT Gateway | 5 | 5 | False | 7.000 | 2 | 15 | 0.286 | 0.133 | 13 |
| v1v1v1 | Industrial Motor Drive (Variable Frequency) | 5 | 5 | False | 7.000 | 3 | 12 | 0.429 | 0.250 | 9 |
| v1v1v1 | Industrial PLC Module | 5 | 5 | False | 5.000 | 3 | 8 | 0.600 | 0.375 | 5 |
| v1v1v1 | Industrial Welding Robot Controller | 5 | 5 | False | 8.000 | 1 | 16 | 0.125 | 0.062 | 15 |
| v1v1v1 | Inertial Navigation System | 5 | 5 | False | 7.000 | 1 | 20 | 0.143 | 0.050 | 19 |
| v1v1v1 | LED Luminaire | 5 | 3 | False | 7.000 | 6 | 9 | 0.857 | 0.667 | 3 |
| v1v1v1 | Laptop PC | 5 | 5 | False | 8.000 | 0 | 19 | 0.000 | 0.000 | 19 |
| v1v1v1 | Large-Format OLED Television | 5 | 5 | False | 6.000 | 2 | 12 | 0.333 | 0.167 | 10 |
| v1v1v1 | Laser Projector | 5 | 5 | False | 8.000 | 3 | 15 | 0.375 | 0.200 | 12 |
| v1v1v1 | LiDAR Sensor System | 5 | 5 | False | 7.000 | 3 | 15 | 0.429 | 0.200 | 12 |
| v1v1v1 | MRI Machine | 5 | 5 | False | 7.000 | 2 | 19 | 0.286 | 0.105 | 17 |
| v1v1v1 | Medical Ultrasound System | 5 | 4 | False | 8.000 | 6 | 12 | 0.750 | 0.500 | 6 |
| v1v1v1 | Microwave Backhaul Radio | 5 | 5 | False | 8.000 | 2 | 16 | 0.250 | 0.125 | 14 |
| v1v1v1 | Military Avionics Module | 5 | 5 | False | 7.000 | 2 | 13 | 0.286 | 0.154 | 11 |
| v1v1v1 | Near-Infrared Spectroscopy Instrument | 5 | 5 | False | 9.000 | 5 | 15 | 0.556 | 0.333 | 10 |
| v1v1v1 | Network Switch/Router | 5 | 4 | False | 7.000 | 6 | 10 | 0.857 | 0.600 | 4 |
| v1v1v1 | Point-of-Sale Terminal | 5 | 5 | False | 8.000 | 4 | 13 | 0.500 | 0.308 | 9 |
| v1v1v1 | Pulse Oximeter | 5 | 5 | False | 6.000 | 2 | 8 | 0.333 | 0.250 | 6 |
| v1v1v1 | Satellite Communication Terminal | 5 | 5 | False | 7.000 | 2 | 14 | 0.286 | 0.143 | 12 |
| v1v1v1 | Servo Motor Drive | 5 | 5 | False | 7.000 | 3 | 13 | 0.429 | 0.231 | 10 |
| v1v1v1 | Small Cell (5G Picocell) | 5 | 5 | False | 8.000 | 4 | 12 | 0.500 | 0.333 | 8 |
| v1v1v1 | Smart Doorbell Camera | 5 | 5 | False | 8.000 | 4 | 14 | 0.500 | 0.286 | 10 |
| v1v1v1 | Smart Speaker / Voice Assistant Device | 5 | 3 | False | 6.000 | 1 | 12 | 0.167 | 0.083 | 11 |
| v1v1v1 | Smartphone | 5 | 1 | True | 5.000 | 5 | 5 | 1.000 | 1.000 | 0 |
| v1v1v1 | Solar String Inverter | 5 | 5 | False | 7.000 | 3 | 14 | 0.429 | 0.214 | 11 |
| v1v1v1 | Space-Grade Solar Array Power Regulator | 5 | 5 | False | 7.000 | 3 | 12 | 0.429 | 0.250 | 9 |
| v1v1v1 | Space-Hardened Satellite Computer | 5 | 5 | False | 7.000 | 1 | 16 | 0.143 | 0.062 | 15 |
| v1v1v1 | Star Tracker (Satellite Attitude Sensor) | 5 | 5 | False | 7.000 | 4 | 13 | 0.571 | 0.308 | 9 |
| v1v1v1 | Submarine Cable Repeater | 5 | 5 | False | 6.000 | 4 | 12 | 0.667 | 0.333 | 8 |
| v1v1v1 | Surveillance DVR/NVR | 5 | 5 | False | 8.000 | 2 | 17 | 0.250 | 0.118 | 15 |
| v1v1v1 | Thermal Imaging Sight | 5 | 5 | False | 7.000 | 0 | 15 | 0.000 | 0.000 | 15 |
| v1v1v1 | UV-C Disinfection System | 5 | 5 | False | 7.000 | 0 | 25 | 0.000 | 0.000 | 25 |
| v1v1v1 | WiFi 7 Access Point | 5 | 5 | False | 8.000 | 2 | 15 | 0.250 | 0.133 | 13 |
