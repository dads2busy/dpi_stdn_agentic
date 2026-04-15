# Naive Component Baseline (Raw)

Evaluation of naive single-shot LLM extraction against gold standard. Component names used as-is from LLM output (no canonical normalization).

- **Date**: 2026-04-15 11:19
- **Extraction model**: `openai:gpt-4.1-mini`
- **Judge model**: `openai:gpt-4.1`
- **Normalization model**: `openai:gpt-4.1`
- **Runs per technology**: 5
- **Prompt**: `What are the primary manufacturing components of a {technology}? List each component on its own line.`

## Extraction Summary

| Technology | Union | Mean/run | Min | Max | Stability (Jaccard) |
| --- | --- | --- | --- | --- | --- |
| 5G Base Station (Macro Cell) | 37 | 12.2 | 10 | 15 | 0.221 |
| AESA Radar Module (Military) | 45 | 13.8 | 13 | 15 | 0.251 |
| Automated Guided Vehicle (AGV) Controller | 39 | 11.4 | 10 | 12 | 0.150 |
| Automotive ECU (Engine Control Unit) | 39 | 12.4 | 11 | 13 | 0.189 |
| Automotive LED Headlamp Module | 44 | 10.6 | 10 | 11 | 0.062 |
| Automotive Night Vision System | 34 | 9.0 | 8 | 10 | 0.126 |
| Automotive Tire Pressure Monitoring System (TPMS) | 37 | 9.0 | 8 | 12 | 0.075 |
| Autonomous Vehicle Compute Platform | 46 | 12.8 | 12 | 14 | 0.154 |
| CNC Machine Tool Controller | 36 | 10.6 | 10 | 12 | 0.181 |
| CT Scanner | 21 | 10.6 | 10 | 13 | 0.512 |
| Collaborative Robot (Cobot) Arm | 42 | 9.8 | 9 | 10 | 0.042 |
| Contactless Payment Card | 26 | 7.0 | 7 | 7 | 0.141 |
| CubeSat On-Board Computer | 36 | 10.2 | 9 | 11 | 0.141 |
| Data Center Server | 27 | 10.4 | 10 | 11 | 0.376 |
| Digital Signage Player | 30 | 10.2 | 10 | 11 | 0.206 |
| Drone Flight Controller | 43 | 13.2 | 12 | 15 | 0.182 |
| EV On-Board Charger | 51 | 12.4 | 11 | 14 | 0.083 |
| EV Traction Inverter | 32 | 10.0 | 9 | 11 | 0.188 |
| Edge AI Inference Box | 37 | 10.0 | 10 | 10 | 0.147 |
| Electronic Warfare Jammer Pod | 44 | 13.8 | 12 | 15 | 0.193 |
| Enterprise Storage Array (SAN) | 25 | 10.4 | 10 | 11 | 0.306 |
| Face Recognition Access Control System | 46 | 12.4 | 12 | 13 | 0.105 |
| Fiber-Optic Communication Terminal | 47 | 12.8 | 11 | 14 | 0.155 |
| Fiber-Optic Illumination System | 41 | 8.8 | 8 | 10 | 0.018 |
| GPS Timing Receiver | 50 | 12.6 | 11 | 15 | 0.087 |
| Hearing Aid | 23 | 10.6 | 10 | 11 | 0.482 |
| Implantable Cardiac Defibrillator (ICD) | 44 | 10.0 | 9 | 11 | 0.049 |
| Industrial IoT Gateway | 37 | 10.0 | 10 | 10 | 0.110 |
| Industrial Motor Drive (Variable Frequency) | 39 | 9.8 | 9 | 10 | 0.064 |
| Industrial PLC Module | 36 | 10.6 | 10 | 12 | 0.142 |
| Industrial Welding Robot Controller | 44 | 11.4 | 10 | 12 | 0.113 |
| Inertial Navigation System | 19 | 8.2 | 7 | 9 | 0.450 |
| LED Luminaire | 37 | 9.8 | 9 | 10 | 0.133 |
| Laptop PC | 37 | 15.8 | 15 | 17 | 0.412 |
| Large-Format OLED Television | 60 | 15.0 | 12 | 17 | 0.097 |
| Laser Projector | 43 | 9.4 | 8 | 10 | 0.024 |
| LiDAR Sensor System | 27 | 9.4 | 9 | 10 | 0.247 |
| MRI Machine | 45 | 12.2 | 12 | 13 | 0.110 |
| Medical Ultrasound System | 20 | 10.6 | 10 | 12 | 0.488 |
| Microwave Backhaul Radio | 42 | 15.6 | 15 | 16 | 0.272 |
| Military Avionics Module | 49 | 13.8 | 10 | 15 | 0.116 |
| Near-Infrared Spectroscopy Instrument | 27 | 8.4 | 8 | 9 | 0.208 |
| Network Switch/Router | 35 | 11.2 | 10 | 13 | 0.226 |
| Point-of-Sale Terminal | 37 | 12.0 | 10 | 14 | 0.194 |
| Pulse Oximeter | 30 | 10.0 | 10 | 10 | 0.195 |
| Satellite Communication Terminal | 40 | 12.4 | 11 | 15 | 0.172 |
| Servo Motor Drive | 29 | 9.0 | 8 | 11 | 0.203 |
| Small Cell (5G Picocell) | 45 | 14.8 | 14 | 15 | 0.234 |
| Smart Doorbell Camera | 48 | 14.0 | 12 | 16 | 0.147 |
| Smart Speaker / Voice Assistant Device | 51 | 13.4 | 12 | 14 | 0.106 |
| Smartphone | 59 | 19.4 | 18 | 20 | 0.210 |
| Solar String Inverter | 55 | 12.8 | 11 | 16 | 0.044 |
| Space-Grade Solar Array Power Regulator | 51 | 11.0 | 10 | 13 | 0.026 |
| Space-Hardened Satellite Computer | 45 | 10.4 | 10 | 12 | 0.067 |
| Star Tracker (Satellite Attitude Sensor) | 44 | 9.4 | 9 | 11 | 0.017 |
| Submarine Cable Repeater | 48 | 12.0 | 10 | 13 | 0.085 |
| Surveillance DVR/NVR | 43 | 12.2 | 11 | 14 | 0.139 |
| Thermal Imaging Sight | 38 | 10.4 | 10 | 11 | 0.145 |
| UV-C Disinfection System | 38 | 10.4 | 10 | 12 | 0.109 |
| WiFi 7 Access Point | 52 | 12.8 | 10 | 14 | 0.093 |

## Judge Validation Against Gold Standard

| Technology | Gold Std | Naive | TP | FP | TN | FN | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **AGGREGATE** | 0 | 0 | 0 | 0 | 0 | 0 | — | — | — |
