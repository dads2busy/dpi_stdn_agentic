# Stage 1 Component Validity (Normalized Outputs; Per-Run)
This report uses an LLM judge to label whether each extracted component is a plausible **primary manufacturing component** for a given technology. Candidates are sourced from **normalized STDN output CSVs** and evaluated per run. A cache keyed by (technology, component) avoids repeated judge calls.

- normalized_dir: `output/normalized_techscope_a`
- configs: v1v1v1, d3v1v1, d5v1v1, biotech_v1v1v1, biotech_d3v1v1, biotech_d5v1v1, pharma_v1v1v1, pharma_d3v1v1, pharma_d5v1v1, fxmicro_v1v1v1, fxmicro_d3v1v1, fxbiotech_v1v1v1, fxbiotech_d3v1v1, fxpharma_v1v1v1, fxpharma_d3v1v1
- judge_model: `openai:gpt-4.1`
- cache: `output/analysis/judge_cache_techscope_a.jsonl`
- judged_new: 463
- judged_cached: 1982

## Per-configuration variability summary (per-run invalid rate)

| config | runs_entries | invalid_rate_median | invalid_rate_mean | invalid_rate_min | invalid_rate_max | component_count_median | component_count_mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v1v1v1 | 315 | 0.000 | 0.033 | 0.000 | 0.400 | 7.000 | 7.444 |
| d3v1v1 | 308 | 0.000 | 0.026 | 0.000 | 0.500 | 6.000 | 6.162 |
| d5v1v1 | 295 | 0.000 | 0.031 | 0.000 | 0.400 | 6.000 | 6.492 |
| biotech_v1v1v1 | 267 | 0.000 | 0.028 | 0.000 | 0.857 | 7.000 | 7.221 |
| biotech_d3v1v1 | 291 | 0.000 | 0.029 | 0.000 | 1.000 | 6.000 | 5.983 |
| biotech_d5v1v1 | 300 | 0.000 | 0.032 | 0.000 | 1.000 | 7.000 | 6.553 |
| pharma_v1v1v1 | 243 | 0.000 | 0.021 | 0.000 | 0.333 | 7.000 | 7.374 |
| pharma_d3v1v1 | 295 | 0.000 | 0.016 | 0.000 | 0.500 | 6.000 | 5.769 |
| pharma_d5v1v1 | 300 | 0.000 | 0.020 | 0.000 | 0.600 | 6.000 | 6.227 |
| fxmicro_v1v1v1 | 300 | 0.000 | 0.030 | 0.000 | 0.429 | 7.000 | 7.353 |
| fxmicro_d3v1v1 | 300 | 0.000 | 0.030 | 0.000 | 0.400 | 6.000 | 6.153 |
| fxbiotech_v1v1v1 | 300 | 0.000 | 0.026 | 0.000 | 0.833 | 7.000 | 7.203 |
| fxbiotech_d3v1v1 | 300 | 0.000 | 0.032 | 0.000 | 1.000 | 6.000 | 5.833 |
| fxpharma_v1v1v1 | 300 | 0.000 | 0.023 | 0.000 | 0.500 | 7.000 | 7.300 |
| fxpharma_d3v1v1 | 300 | 0.000 | 0.018 | 0.000 | 0.667 | 6.000 | 5.920 |

## Per-technology comparison (median invalid rate across runs)

| technology | v1v1v1_median_invalid_rate | d3v1v1_median_invalid_rate | delta_d3_minus_v1 |
| --- | --- | --- | --- |
| 5G Base Station (Macro Cell) | 0.000 | 0.000 | 0.000 |
| AESA Radar Module (Military) | 0.000 | 0.000 | 0.000 |
| Algae Photobioreactor | NA | NA | NA |
| Ampoule Forming and Sealing Machine | NA | NA | NA |
| Aseptic Vial Filling Line | NA | NA | NA |
| Autoclave Sterilizer (Pharmaceutical Grade) | NA | NA | NA |
| Automated Guided Vehicle (AGV) Controller | 0.000 | 0.000 | 0.000 |
| Automated Immunoassay Analyzer | NA | NA | NA |
| Automated Liquid Handling Robot | NA | NA | NA |
| Automated Molecular Cloning Workstation | NA | NA | NA |
| Automated Nucleic Acid Extraction System | NA | NA | NA |
| Automotive ECU (Engine Control Unit) | 0.143 | 0.125 | -0.018 |
| Automotive LED Headlamp Module | 0.000 | 0.000 | 0.000 |
| Automotive Night Vision System | 0.000 | 0.000 | 0.000 |
| Automotive Tire Pressure Monitoring System (TPMS) | 0.200 | 0.000 | -0.200 |
| Autonomous Vehicle Compute Platform | 0.000 | 0.000 | 0.000 |
| Benchtop DNA Printer | NA | NA | NA |
| Bioethanol Distillation Column | NA | NA | NA |
| Biopesticide Fermentation Unit | NA | NA | NA |
| Blister Packaging Machine | NA | NA | NA |
| Blood Gas Analyzer | NA | NA | NA |
| Bottle Filling and Capping Line | NA | NA | NA |
| CNC Machine Tool Controller | 0.000 | 0.000 | 0.000 |
| CRISPR Electroporation System | NA | NA | NA |
| CT Scanner | 0.000 | 0.000 | 0.000 |
| Capillary Electrophoresis Genetic Analyzer | NA | NA | NA |
| Cartoning Machine | NA | NA | NA |
| Cell Washing and Concentration System | NA | NA | NA |
| Centrifugal Solids Discharge Filter | NA | NA | NA |
| Clean Steam Generator | NA | NA | NA |
| Clinical Flow Cytometer | NA | NA | NA |
| Clinical Labeling and Randomization System | NA | NA | NA |
| Closed-System Cell Expansion Bioreactor | NA | NA | NA |
| Collaborative Robot (Cobot) Arm | 0.111 | 0.000 | -0.111 |
| Colloid Mill (Topical Formulation) | NA | NA | NA |
| Comparator Sourcing and Over-Encapsulation Machine | NA | NA | NA |
| Cone Mill (Screening/Sizing) | NA | NA | NA |
| Confocal Laser Scanning Microscope | NA | NA | NA |
| Contactless Payment Card | 0.167 | 0.000 | -0.167 |
| Continuous Centrifuge Separator | NA | NA | NA |
| Continuous Crystallization Unit | NA | NA | NA |
| Continuous Direct Compression Press | NA | NA | NA |
| Continuous Flow Reactor System | NA | NA | NA |
| Continuous Glucose Monitor | NA | NA | NA |
| Continuous mRNA Manufacturing System | NA | NA | NA |
| Cryo-Electron Microscope | NA | NA | NA |
| Cryopreservation Controlled-Rate Freezer | NA | NA | NA |
| CubeSat On-Board Computer | 0.125 | 0.000 | -0.125 |
| Data Center Server | 0.000 | 0.000 | 0.000 |
| Dermal Penetration Test Apparatus (Franz Cell) | NA | NA | NA |
| Digital Pathology Slide Scanner | NA | NA | NA |
| Digital Signage Player | 0.000 | 0.000 | 0.000 |
| Dissolution Testing Apparatus | NA | NA | NA |
| Drone Flight Controller | 0.143 | 0.167 | 0.024 |
| EV On-Board Charger | 0.000 | 0.000 | 0.000 |
| EV Traction Inverter | 0.143 | 0.143 | 0.000 |
| Edge AI Inference Box | 0.000 | 0.000 | 0.000 |
| Electronic Warfare Jammer Pod | 0.000 | 0.000 | 0.000 |
| Endotoxin Detection System (LAL/rFC) | NA | NA | NA |
| Enterprise Storage Array (SAN) | 0.000 | 0.000 | 0.000 |
| Face Recognition Access Control System | 0.000 | 0.000 | 0.000 |
| Fiber-Optic Communication Terminal | 0.000 | 0.000 | 0.000 |
| Fiber-Optic Illumination System | 0.000 | 0.000 | 0.000 |
| Film Coating System | NA | NA | NA |
| Fluid Bed Dryer/Granulator | NA | NA | NA |
| Fluid Bed Pellet Coater | NA | NA | NA |
| Friability Tester | NA | NA | NA |
| GPS Timing Receiver | 0.000 | 0.000 | 0.000 |
| Gene Assembly Platform | NA | NA | NA |
| Glass-Lined Chemical Reactor | NA | NA | NA |
| HPLC System (Pharmaceutical Grade) | NA | NA | NA |
| Handheld Pulse Oximeter | NA | NA | NA |
| Hard Capsule Filling Machine | NA | NA | NA |
| Hearing Aid | 0.125 | 0.125 | 0.000 |
| Hematology Analyzer | NA | NA | NA |
| High-Pressure Hydrogenation Vessel | NA | NA | NA |
| High-Throughput Microplate Reader | NA | NA | NA |
| Hot Cell Shielded Workstation | NA | NA | NA |
| Hot-Melt Extrusion System | NA | NA | NA |
| IV Bag Manufacturing System | NA | NA | NA |
| Illumina Short-Read DNA Sequencer | NA | NA | NA |
| Implantable Cardiac Defibrillator (ICD) | 0.000 | 0.000 | 0.000 |
| Implantable Drug Infusion Pump | NA | NA | NA |
| In-Line PAT (Process Analytical Technology) Probe | NA | NA | NA |
| Industrial Enzyme Fermenter (50000L) | NA | NA | NA |
| Industrial Freeze Dryer (Lyophilizer) | NA | NA | NA |
| Industrial IoT Gateway | 0.000 | 0.000 | 0.000 |
| Industrial Motor Drive (Variable Frequency) | 0.000 | 0.000 | 0.000 |
| Industrial PLC Module | 0.000 | 0.000 | 0.000 |
| Industrial Welding Robot Controller | 0.000 | 0.000 | 0.000 |
| Inertial Navigation System | 0.000 | 0.000 | 0.000 |
| Interactive Response Technology (IRT) Dispensing Unit | NA | NA | NA |
| Isolator-Based Sterility Test System | NA | NA | NA |
| Jet Mill (Micronization) | NA | NA | NA |
| Karl Fischer Titrator | NA | NA | NA |
| LED Luminaire | 0.143 | 0.000 | -0.143 |
| Laboratory Sample Storage Freezer (-80C) | NA | NA | NA |
| Laptop PC | 0.000 | 0.000 | 0.000 |
| Large-Format OLED Television | 0.125 | 0.000 | -0.125 |
| Laser Projector | 0.000 | 0.000 | 0.000 |
| Lateral Flow Immunoassay Reader | NA | NA | NA |
| Lentiviral Transfection System | NA | NA | NA |
| LiDAR Sensor System | 0.000 | 0.000 | 0.000 |
| Lipid Nanoparticle Encapsulation System | NA | NA | NA |
| MRI Machine | 0.000 | 0.000 | 0.000 |
| Medical Cyclotron | NA | NA | NA |
| Medical Ultrasound System | 0.000 | 0.000 | 0.000 |
| Metered-Dose Inhaler | NA | NA | NA |
| Microarray Scanner | NA | NA | NA |
| Microsphere Encapsulation System | NA | NA | NA |
| Microwave Backhaul Radio | 0.000 | 0.000 | 0.000 |
| Military Avionics Module | 0.000 | 0.000 | 0.000 |
| Monoclonal Antibody Perfusion Bioreactor | NA | NA | NA |
| Nanopore Sequencer | NA | NA | NA |
| Near-Infrared Spectroscopy Instrument | 0.000 | 0.000 | 0.000 |
| Network Switch/Router | 0.000 | 0.000 | 0.000 |
| Ointment Filling and Sealing Machine | NA | NA | NA |
| Oligonucleotide Synthesizer | NA | NA | NA |
| Osmotic Tablet Core Press | NA | NA | NA |
| PET Tracer Automated Synthesis Module | NA | NA | NA |
| PHA Bioplastic Extractor | NA | NA | NA |
| Particle Size Analyzer (Laser Diffraction) | NA | NA | NA |
| Pharmaceutical Lyophilizer | 0.000 | 0.000 | 0.000 |
| Phenotyping Imaging Robot | NA | NA | NA |
| Plant Transformation Gene Gun | NA | NA | NA |
| Point-of-Sale Terminal | 0.143 | 0.143 | 0.000 |
| Portable Blood Coagulation Meter | NA | NA | NA |
| Prefilled Syringe Autoinjector | NA | NA | NA |
| Protein A Chromatography Column | NA | NA | NA |
| Pulse Oximeter | 0.000 | 0.000 | 0.000 |
| Radiochemical Dose Calibrator | NA | NA | NA |
| Rapid Molecular Diagnostic Cartridge System | NA | NA | NA |
| Real-Time PCR Thermocycler | NA | NA | NA |
| Reverse Osmosis/Electrodeionization Purification System | NA | NA | NA |
| Robotic Colony Picker | NA | NA | NA |
| Roller Compactor (Dry Granulation) | NA | NA | NA |
| Rotary Tablet Press | 0.000 | 0.000 | 0.000 |
| Rotary Vacuum Dryer | NA | NA | NA |
| Sanitizable Distribution Loop Skid | NA | NA | NA |
| Satellite Communication Terminal | 0.000 | 0.000 | 0.000 |
| Seed Trait Analysis Platform | NA | NA | NA |
| Serialization and Track-and-Trace System | NA | NA | NA |
| Servo Motor Drive | 0.000 | 0.000 | 0.000 |
| Single-Cell RNA-Seq Instrument | NA | NA | NA |
| Single-Use Stirred-Tank Bioreactor (2000L) | NA | NA | NA |
| Single-use Bioreactor | 0.000 | 0.000 | 0.000 |
| Small Animal PET/CT Scanner | NA | NA | NA |
| Small Cell (5G Picocell) | 0.000 | 0.000 | 0.000 |
| Small-Scale Encapsulator (Clinical Batches) | NA | NA | NA |
| Smart Doorbell Camera | 0.000 | 0.000 | 0.000 |
| Smart Speaker / Voice Assistant Device | 0.125 | 0.000 | -0.125 |
| Smartphone | 0.000 | 0.000 | 0.000 |
| Solar String Inverter | 0.125 | 0.155 | 0.030 |
| Space-Grade Solar Array Power Regulator | 0.000 | 0.250 | 0.250 |
| Space-Hardened Satellite Computer | 0.000 | 0.000 | 0.000 |
| Stainless Steel Fed-Batch Bioreactor | NA | NA | NA |
| Star Tracker (Satellite Attitude Sensor) | 0.000 | 0.000 | 0.000 |
| Sterile Filtration Skid | NA | NA | NA |
| Submarine Cable Repeater | 0.125 | 0.000 | -0.125 |
| Super-Resolution Fluorescence Microscope | NA | NA | NA |
| Surveillance DVR/NVR | 0.000 | 0.143 | 0.143 |
| TOC (Total Organic Carbon) Analyzer | NA | NA | NA |
| Tablet Deduster and Metal Detector | NA | NA | NA |
| Tamper-Evident Seal Applicator | NA | NA | NA |
| Tangential Flow Filtration Cassette System | NA | NA | NA |
| Technetium-99m Generator | NA | NA | NA |
| Temperature-Controlled Shipping Container | NA | NA | NA |
| Thermal Imaging Sight | 0.000 | 0.000 | 0.000 |
| Tissue Culture Growth Chamber | NA | NA | NA |
| Transdermal Patch Laminator | NA | NA | NA |
| Transdermal Patch Manufacturing System | NA | NA | NA |
| Twin-Screw Wet Granulator (Continuous) | NA | NA | NA |
| UV-C Disinfection System | 0.000 | 0.000 | 0.000 |
| V-Blender (Powder Mixing) | NA | NA | NA |
| Vaccine Fill-Finish Line | NA | NA | NA |
| Vacuum Emulsifying Mixer (Cream/Ointment) | NA | NA | NA |
| Viral Vector Production Bioreactor | NA | NA | NA |
| Water for Injection (WFI) Distillation Unit | NA | NA | NA |
| WiFi 7 Access Point | 0.000 | 0.000 | 0.000 |
| Wiped Film Evaporator | NA | NA | NA |
| Wurster Column Coating Insert | NA | NA | NA |
| Yeast Propagation Tank | NA | NA | NA |
