# Naive Component Baseline (Normalized)

Evaluation of naive single-shot LLM extraction against gold standard. Component names normalized through canonical vocabulary before evaluation.

- **Date**: 2026-04-15 11:35
- **Extraction model**: `openai:gpt-4.1-mini`
- **Judge model**: `openai:gpt-4.1`
- **Normalization model**: `openai:gpt-4.1`
- **Runs per technology**: 5
- **Prompt**: `What are the primary manufacturing components of a {technology}? List each component on its own line.`

## Extraction Summary

| Technology | Union | Mean/run | Min | Max | Stability (Jaccard) |
| --- | --- | --- | --- | --- | --- |
| 5G Base Station (Macro Cell) | 12 | 9.8 | 7 | 12 | 0.769 |
| AESA Radar Module (Military) | 16 | 12.8 | 12 | 14 | 0.848 |
| Automated Guided Vehicle (AGV) Controller | 11 | 9.8 | 9 | 10 | 0.835 |
| Automotive ECU (Engine Control Unit) | 12 | 9.8 | 9 | 10 | 0.802 |
| Automotive LED Headlamp Module | 11 | 8.8 | 8 | 9 | 0.783 |
| Automotive Night Vision System | 11 | 7.4 | 6 | 8 | 0.731 |
| Automotive Tire Pressure Monitoring System (TPMS) | 7 | 4.2 | 3 | 7 | 0.650 |
| Autonomous Vehicle Compute Platform | 20 | 12.2 | 11 | 13 | 0.576 |
| CNC Machine Tool Controller | 13 | 8.8 | 8 | 10 | 0.740 |
| CT Scanner | 12 | 9.6 | 9 | 11 | 0.718 |
| Collaborative Robot (Cobot) Arm | 13 | 9.6 | 9 | 10 | 0.662 |
| Contactless Payment Card | 8 | 6.2 | 5 | 7 | 0.827 |
| CubeSat On-Board Computer | 8 | 7.2 | 7 | 8 | 0.950 |
| Data Center Server | 9 | 8.6 | 8 | 9 | 0.933 |
| Digital Signage Player | 11 | 10.0 | 10 | 10 | 0.927 |
| Drone Flight Controller | 13 | 12.0 | 10 | 13 | 0.874 |
| EV On-Board Charger | 15 | 10.4 | 8 | 12 | 0.653 |
| EV Traction Inverter | 11 | 8.8 | 8 | 9 | 0.828 |
| Edge AI Inference Box | 9 | 8.4 | 8 | 9 | 0.933 |
| Electronic Warfare Jammer Pod | 16 | 12.0 | 11 | 14 | 0.706 |
| Enterprise Storage Array (SAN) | 12 | 10.2 | 9 | 11 | 0.793 |
| Face Recognition Access Control System | 17 | 11.6 | 10 | 13 | 0.631 |
| Fiber-Optic Communication Terminal | 14 | 9.8 | 7 | 11 | 0.635 |
| Fiber-Optic Illumination System | 7 | 6.6 | 6 | 7 | 0.914 |
| GPS Timing Receiver | 19 | 12.2 | 10 | 15 | 0.642 |
| Hearing Aid | 10 | 8.4 | 7 | 9 | 0.848 |
| Implantable Cardiac Defibrillator (ICD) | 6 | 5.2 | 5 | 6 | 0.800 |
| Industrial IoT Gateway | 11 | 8.4 | 7 | 9 | 0.682 |
| Industrial Motor Drive (Variable Frequency) | 14 | 9.4 | 9 | 10 | 0.702 |
| Industrial PLC Module | 9 | 6.8 | 6 | 7 | 0.727 |
| Industrial Welding Robot Controller | 14 | 10.8 | 10 | 12 | 0.749 |
| Inertial Navigation System | 9 | 5.8 | 5 | 7 | 0.574 |
| LED Luminaire | 8 | 7.8 | 7 | 8 | 0.950 |
| Laptop PC | 37 | 15.8 | 15 | 17 | 0.412 |
| Large-Format OLED Television | 18 | 12.0 | 8 | 14 | 0.590 |
| Laser Projector | 10 | 8.2 | 7 | 9 | 0.766 |
| LiDAR Sensor System | 10 | 9.4 | 9 | 10 | 0.940 |
| MRI Machine | 15 | 11.0 | 10 | 12 | 0.762 |
| Medical Ultrasound System | 11 | 10.0 | 10 | 10 | 0.927 |
| Microwave Backhaul Radio | 16 | 11.4 | 10 | 13 | 0.656 |
| Military Avionics Module | 16 | 10.0 | 6 | 12 | 0.613 |
| Near-Infrared Spectroscopy Instrument | 9 | 7.4 | 7 | 8 | 0.903 |
| Network Switch/Router | 11 | 8.6 | 8 | 10 | 0.817 |
| Point-of-Sale Terminal | 13 | 9.6 | 8 | 11 | 0.787 |
| Pulse Oximeter | 9 | 7.6 | 7 | 9 | 0.885 |
| Satellite Communication Terminal | 21 | 11.2 | 9 | 13 | 0.480 |
| Servo Motor Drive | 10 | 8.0 | 7 | 9 | 0.783 |
| Small Cell (5G Picocell) | 17 | 13.2 | 11 | 14 | 0.694 |
| Smart Doorbell Camera | 14 | 13.0 | 12 | 14 | 0.913 |
| Smart Speaker / Voice Assistant Device | 19 | 12.8 | 12 | 14 | 0.690 |
| Smartphone | 17 | 16.6 | 16 | 17 | 0.965 |
| Solar String Inverter | 20 | 11.4 | 10 | 13 | 0.558 |
| Space-Grade Solar Array Power Regulator | 15 | 9.2 | 7 | 10 | 0.538 |
| Space-Hardened Satellite Computer | 14 | 9.6 | 9 | 11 | 0.606 |
| Star Tracker (Satellite Attitude Sensor) | 10 | 8.0 | 7 | 9 | 0.726 |
| Submarine Cable Repeater | 15 | 10.0 | 8 | 12 | 0.590 |
| Surveillance DVR/NVR | 13 | 10.6 | 10 | 12 | 0.799 |
| Thermal Imaging Sight | 9 | 8.2 | 8 | 9 | 0.956 |
| UV-C Disinfection System | 12 | 8.2 | 7 | 9 | 0.660 |
| WiFi 7 Access Point | 52 | 12.8 | 10 | 14 | 0.093 |

## Judge Validation Against Gold Standard

| Technology | Gold Std | Naive | TP | FP | TN | FN | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **AGGREGATE** | 0 | 0 | 0 | 0 | 0 | 0 | — | — | — |
