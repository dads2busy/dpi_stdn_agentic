# Stage 2 Materials Sweet-Spot Tradeoffs

This report summarizes stability, plausibility, silver recall proxy, convergence, and runtime by materials agent-count `N`.

## Per-technology metrics by N

| Technology | N | Stability Jaccard (mean) | Stability CI lo | Stability CI hi | #Materials mean | #Materials median | Not-plausible rate | Plausible rate | Judge n | Silver recall proxy | Silver ref size | Convergence mean | Runtime mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Autoclave (Steam Sterilizer) | 1 | 0.288 | 0.285 | 0.290 | 145.10 | 143.00 | NA | NA | 0 | 0.474 | 19 | NA | NA |
| Autoclave (Steam Sterilizer) | 2 | 0.328 | 0.228 | 0.436 | 40.20 | 17.50 | 0.344 | 0.656 | 32 | 0.474 | 19 | NA | NA |
| Autoclave (Steam Sterilizer) | 3 | 0.291 | 0.211 | 0.377 | 41.00 | 24.50 | 0.379 | 0.621 | 29 | 0.316 | 19 | NA | NA |
| Autoclave (Steam Sterilizer) | 4 | 0.277 | 0.201 | 0.361 | 57.40 | 73.50 | 0.400 | 0.600 | 30 | 0.474 | 19 | NA | NA |
| Autoclave (Steam Sterilizer) | 5 | 0.248 | 0.177 | 0.318 | 48.20 | 53.00 | 0.436 | 0.564 | 39 | 0.368 | 19 | NA | NA |
| Bioreactor | 1 | 0.291 | 0.288 | 0.295 | 147.80 | 146.00 | NA | NA | 0 | 0.652 | 23 | NA | NA |
| Bioreactor | 2 | 0.321 | 0.239 | 0.407 | 46.80 | 48.00 | 0.500 | 0.500 | 26 | 0.478 | 23 | NA | NA |
| Bioreactor | 3 | 0.352 | 0.291 | 0.414 | 55.70 | 67.00 | 0.440 | 0.560 | 25 | 0.348 | 23 | NA | NA |
| Bioreactor | 4 | 0.340 | 0.264 | 0.420 | 27.70 | 8.00 | 0.471 | 0.529 | 34 | 0.304 | 23 | NA | NA |
| Bioreactor | 5 | 0.311 | 0.224 | 0.401 | 31.60 | 7.50 | 0.522 | 0.478 | 46 | 0.348 | 23 | NA | NA |
| Capacitive Soil Moisture Sensor Probe (with MCU + radio) | 1 | 0.275 | 0.273 | 0.278 | 152.36 | 145.50 | NA | NA | 0 | 0.611 | 36 | NA | NA |
| Capacitive Soil Moisture Sensor Probe (with MCU + radio) | 2 | 0.386 | 0.279 | 0.498 | 43.10 | 30.00 | 0.324 | 0.676 | 34 | 0.389 | 36 | NA | NA |
| Capacitive Soil Moisture Sensor Probe (with MCU + radio) | 3 | 0.393 | 0.304 | 0.481 | 53.40 | 65.50 | 0.412 | 0.588 | 34 | 0.361 | 36 | NA | NA |
| Capacitive Soil Moisture Sensor Probe (with MCU + radio) | 4 | 0.311 | 0.236 | 0.385 | 37.70 | 9.50 | 0.333 | 0.667 | 48 | 0.333 | 36 | NA | NA |
| Capacitive Soil Moisture Sensor Probe (with MCU + radio) | 5 | 0.216 | 0.153 | 0.286 | 35.50 | 37.00 | 0.333 | 0.667 | 51 | 0.250 | 36 | NA | NA |
| Capsule Filling Machine | 1 | 0.267 | 0.264 | 0.270 | 121.14 | 123.00 | NA | NA | 0 | 0.412 | 17 | NA | NA |
| Capsule Filling Machine | 2 | 0.430 | 0.337 | 0.523 | 41.50 | 51.50 | 0.565 | 0.435 | 23 | 0.353 | 17 | NA | NA |
| Capsule Filling Machine | 3 | 0.315 | 0.252 | 0.380 | 50.30 | 55.00 | 0.542 | 0.458 | 24 | 0.412 | 17 | NA | NA |
| Capsule Filling Machine | 4 | 0.295 | 0.223 | 0.370 | 33.80 | 24.50 | 0.480 | 0.520 | 25 | 0.353 | 17 | NA | NA |
| Capsule Filling Machine | 5 | 0.357 | 0.271 | 0.440 | 21.70 | 7.50 | 0.600 | 0.400 | 25 | 0.235 | 17 | NA | NA |
| Computer Graphics Processing Units (GPUs) | 1 | 0.270 | 0.268 | 0.273 | 163.44 | 160.00 | NA | NA | 0 | 0.619 | 21 | NA | NA |
| Computer Graphics Processing Units (GPUs) | 2 | 0.275 | 0.201 | 0.350 | 51.10 | 49.00 | 0.481 | 0.519 | 27 | 0.476 | 21 | NA | NA |
| Computer Graphics Processing Units (GPUs) | 3 | 0.321 | 0.241 | 0.409 | 28.40 | 8.00 | 0.452 | 0.548 | 31 | 0.286 | 21 | NA | NA |
| Computer Graphics Processing Units (GPUs) | 4 | 0.237 | 0.177 | 0.302 | 34.50 | 24.50 | 0.486 | 0.514 | 37 | 0.286 | 21 | NA | NA |
| Computer Graphics Processing Units (GPUs) | 5 | 0.350 | 0.266 | 0.438 | 22.60 | 7.00 | 0.513 | 0.487 | 39 | 0.286 | 21 | NA | NA |
| DNA Sequencer (NGS platform) | 1 | 0.300 | 0.298 | 0.303 | 151.76 | 155.00 | NA | NA | 0 | 0.471 | 17 | NA | NA |
| DNA Sequencer (NGS platform) | 2 | 0.556 | 0.478 | 0.632 | 86.40 | 92.00 | 0.738 | 0.262 | 42 | 0.353 | 17 | NA | NA |
| DNA Sequencer (NGS platform) | 3 | 0.352 | 0.274 | 0.432 | 71.30 | 82.00 | 0.787 | 0.213 | 47 | 0.412 | 17 | NA | NA |
| DNA Sequencer (NGS platform) | 4 | 0.387 | 0.301 | 0.473 | 64.70 | 82.50 | 0.760 | 0.240 | 50 | 0.353 | 17 | NA | NA |
| DNA Sequencer (NGS platform) | 5 | 0.403 | 0.315 | 0.499 | 67.00 | 82.50 | 0.735 | 0.265 | 49 | 0.353 | 17 | NA | NA |
| Electric Vehicle Battery | 1 | 0.334 | 0.331 | 0.338 | 164.88 | 164.00 | NA | NA | 0 | 0.692 | 13 | NA | NA |
| Electric Vehicle Battery | 2 | 0.289 | 0.222 | 0.356 | 76.50 | 87.50 | 0.591 | 0.409 | 22 | 0.538 | 13 | NA | NA |
| Electric Vehicle Battery | 3 | 0.291 | 0.235 | 0.350 | 69.70 | 58.50 | 0.625 | 0.375 | 24 | 0.538 | 13 | NA | NA |
| Electric Vehicle Battery | 4 | 0.301 | 0.240 | 0.367 | 71.80 | 77.50 | 0.593 | 0.407 | 27 | 0.538 | 13 | NA | NA |
| Electric Vehicle Battery | 5 | 0.238 | 0.183 | 0.299 | 73.70 | 66.00 | 0.667 | 0.333 | 27 | 0.538 | 13 | NA | NA |
| Electric Vehicle Motor | 1 | 0.298 | 0.294 | 0.301 | 147.98 | 149.50 | NA | NA | 0 | 0.545 | 22 | NA | NA |
| Electric Vehicle Motor | 2 | 0.266 | 0.184 | 0.361 | 57.40 | 57.50 | 0.571 | 0.429 | 28 | 0.409 | 22 | NA | NA |
| Electric Vehicle Motor | 3 | 0.375 | 0.282 | 0.460 | 35.60 | 8.00 | 0.574 | 0.426 | 47 | 0.364 | 22 | NA | NA |
| Electric Vehicle Motor | 4 | 0.281 | 0.208 | 0.356 | 63.10 | 73.00 | 0.548 | 0.452 | 42 | 0.318 | 22 | NA | NA |
| Electric Vehicle Motor | 5 | 0.231 | 0.159 | 0.309 | 44.60 | 33.00 | 0.641 | 0.359 | 39 | 0.364 | 22 | NA | NA |
| Flow Cytometer | 1 | 0.317 | 0.314 | 0.320 | 191.50 | 190.00 | NA | NA | 0 | 0.690 | 29 | NA | NA |
| Flow Cytometer | 2 | 0.343 | 0.244 | 0.450 | 51.30 | 35.50 | 0.500 | 0.500 | 34 | 0.379 | 29 | NA | NA |
| Flow Cytometer | 3 | 0.330 | 0.252 | 0.405 | 49.50 | 60.00 | 0.568 | 0.432 | 37 | 0.379 | 29 | NA | NA |
| Flow Cytometer | 4 | 0.375 | 0.284 | 0.465 | 35.30 | 10.50 | 0.511 | 0.489 | 45 | 0.345 | 29 | NA | NA |
| Flow Cytometer | 5 | 0.391 | 0.306 | 0.484 | 30.70 | 9.00 | 0.569 | 0.431 | 51 | 0.345 | 29 | NA | NA |
| Freeze Dryer (Lyophilizer) | 1 | 0.308 | 0.304 | 0.311 | 129.10 | 129.50 | NA | NA | 0 | 0.409 | 22 | NA | NA |
| Freeze Dryer (Lyophilizer) | 2 | 0.257 | 0.192 | 0.324 | 62.20 | 62.50 | 0.519 | 0.481 | 27 | 0.318 | 22 | NA | NA |
| Freeze Dryer (Lyophilizer) | 3 | 0.267 | 0.215 | 0.317 | 74.60 | 86.00 | 0.429 | 0.571 | 28 | 0.318 | 22 | NA | NA |
| Freeze Dryer (Lyophilizer) | 4 | 0.254 | 0.189 | 0.324 | 51.60 | 53.50 | 0.469 | 0.531 | 32 | 0.227 | 22 | NA | NA |
| Freeze Dryer (Lyophilizer) | 5 | 0.240 | 0.176 | 0.308 | 36.30 | 25.00 | 0.441 | 0.559 | 34 | 0.227 | 22 | NA | NA |
| Hydroponic Systems | 1 | 0.307 | 0.304 | 0.310 | 163.84 | 166.50 | NA | NA | 0 | 0.378 | 37 | NA | NA |
| Hydroponic Systems | 2 | 0.366 | 0.261 | 0.478 | 73.20 | 67.00 | 0.600 | 0.400 | 40 | 0.297 | 37 | NA | NA |
| Hydroponic Systems | 3 | 0.340 | 0.251 | 0.436 | 67.90 | 51.00 | 0.362 | 0.638 | 47 | 0.297 | 37 | NA | NA |
| Hydroponic Systems | 4 | 0.338 | 0.253 | 0.424 | 60.70 | 10.50 | 0.583 | 0.417 | 48 | 0.324 | 37 | NA | NA |
| Hydroponic Systems | 5 | 0.300 | 0.217 | 0.380 | 84.00 | 67.00 | 0.553 | 0.447 | 38 | 0.297 | 37 | NA | NA |
| MALE ISR UAV (Generic) | 1 | 0.285 | 0.282 | 0.288 | 140.02 | 147.00 | NA | NA | 0 | 0.568 | 37 | NA | NA |
| MALE ISR UAV (Generic) | 2 | 0.463 | 0.348 | 0.591 | 34.20 | 6.00 | 0.211 | 0.789 | 38 | 0.243 | 37 | NA | NA |
| MALE ISR UAV (Generic) | 3 | 0.284 | 0.209 | 0.370 | 44.80 | 24.00 | 0.125 | 0.875 | 32 | 0.297 | 37 | NA | NA |
| MALE ISR UAV (Generic) | 4 | 0.206 | 0.145 | 0.273 | 47.00 | 39.50 | 0.229 | 0.771 | 35 | 0.324 | 37 | NA | NA |
| MALE ISR UAV (Generic) | 5 | 0.305 | 0.233 | 0.381 | 32.80 | 9.50 | 0.306 | 0.694 | 49 | 0.189 | 37 | NA | NA |
| MRI Machine | 1 | 0.312 | 0.309 | 0.314 | 173.86 | 173.00 | NA | NA | 0 | 0.385 | 39 | NA | NA |
| MRI Machine | 2 | 0.322 | 0.221 | 0.432 | 58.40 | 20.50 | 0.488 | 0.512 | 43 | 0.359 | 39 | NA | NA |
| MRI Machine | 3 | 0.294 | 0.221 | 0.372 | 57.80 | 57.00 | 0.449 | 0.551 | 49 | 0.256 | 39 | NA | NA |
| MRI Machine | 4 | 0.323 | 0.234 | 0.414 | 39.20 | 9.00 | 0.448 | 0.552 | 58 | 0.231 | 39 | NA | NA |
| MRI Machine | 5 | 0.423 | 0.339 | 0.504 | 23.40 | 6.00 | 0.436 | 0.564 | 55 | 0.179 | 39 | NA | NA |
| Man-Portable Thermal Imaging Sight | 1 | 0.339 | 0.335 | 0.343 | 195.86 | 194.00 | NA | NA | 0 | 0.442 | 52 | NA | NA |
| Man-Portable Thermal Imaging Sight | 2 | 0.439 | 0.319 | 0.571 | 57.00 | 6.00 | 0.278 | 0.722 | 54 | 0.346 | 52 | NA | NA |
| Man-Portable Thermal Imaging Sight | 3 | 0.294 | 0.212 | 0.380 | 69.70 | 61.00 | 0.283 | 0.717 | 53 | 0.327 | 52 | NA | NA |
| Man-Portable Thermal Imaging Sight | 4 | 0.322 | 0.238 | 0.412 | 48.30 | 9.00 | 0.306 | 0.694 | 62 | 0.288 | 52 | NA | NA |
| Man-Portable Thermal Imaging Sight | 5 | 0.337 | 0.248 | 0.432 | 47.60 | 8.00 | 0.283 | 0.717 | 60 | 0.269 | 52 | NA | NA |
| Night Vision Goggles | 1 | 0.297 | 0.294 | 0.300 | 184.35 | 182.00 | NA | NA | 0 | 0.462 | 39 | NA | NA |
| Night Vision Goggles | 2 | 0.268 | 0.179 | 0.369 | 67.00 | 28.00 | 0.381 | 0.619 | 42 | 0.385 | 39 | NA | NA |
| Night Vision Goggles | 3 | 0.312 | 0.222 | 0.400 | 64.80 | 41.50 | 0.343 | 0.657 | 35 | 0.333 | 39 | NA | NA |
| Night Vision Goggles | 4 | 0.306 | 0.233 | 0.384 | 94.70 | 114.50 | 0.364 | 0.636 | 55 | 0.359 | 39 | NA | NA |
| Night Vision Goggles | 5 | 0.283 | 0.204 | 0.364 | 60.50 | 8.00 | 0.370 | 0.630 | 54 | 0.487 | 39 | NA | NA |
| PC Laptop | 1 | 0.296 | 0.293 | 0.299 | 217.95 | 207.00 | NA | NA | 0 | 0.700 | 30 | NA | NA |
| PC Laptop | 2 | 0.242 | 0.176 | 0.316 | 126.10 | 149.50 | 0.167 | 0.833 | 30 | 0.700 | 30 | NA | NA |
| PC Laptop | 3 | 0.366 | 0.261 | 0.463 | 55.80 | 10.00 | 0.324 | 0.676 | 37 | 0.467 | 30 | NA | NA |
| PC Laptop | 4 | 0.222 | 0.164 | 0.282 | 130.00 | 173.00 | 0.294 | 0.706 | 34 | 0.567 | 30 | NA | NA |
| PC Laptop | 5 | 0.394 | 0.311 | 0.474 | 47.40 | 8.50 | 0.340 | 0.660 | 47 | 0.533 | 30 | NA | NA |
| Real-Time PCR (qPCR) Thermocycler | 1 | 0.280 | 0.278 | 0.283 | 173.80 | 173.00 | NA | NA | 0 | 0.640 | 25 | NA | NA |
| Real-Time PCR (qPCR) Thermocycler | 2 | 0.428 | 0.303 | 0.548 | 48.30 | 6.00 | 0.469 | 0.531 | 32 | 0.440 | 25 | NA | NA |
| Real-Time PCR (qPCR) Thermocycler | 3 | 0.359 | 0.271 | 0.451 | 38.00 | 9.00 | 0.477 | 0.523 | 44 | 0.560 | 25 | NA | NA |
| Real-Time PCR (qPCR) Thermocycler | 4 | 0.284 | 0.212 | 0.362 | 47.60 | 38.50 | 0.513 | 0.487 | 39 | 0.400 | 25 | NA | NA |
| Real-Time PCR (qPCR) Thermocycler | 5 | 0.188 | 0.126 | 0.254 | 40.70 | 35.00 | 0.500 | 0.500 | 42 | 0.440 | 25 | NA | NA |
| Roller Compactor | 1 | 0.269 | 0.266 | 0.272 | 134.62 | 134.50 | NA | NA | 0 | 0.412 | 17 | NA | NA |
| Roller Compactor | 2 | 0.291 | 0.226 | 0.366 | 54.20 | 60.50 | 0.690 | 0.310 | 29 | 0.235 | 17 | NA | NA |
| Roller Compactor | 3 | 0.304 | 0.229 | 0.385 | 38.30 | 27.00 | 0.738 | 0.262 | 42 | 0.235 | 17 | NA | NA |
| Roller Compactor | 4 | 0.290 | 0.218 | 0.359 | 38.40 | 43.00 | 0.791 | 0.209 | 43 | 0.176 | 17 | NA | NA |
| Roller Compactor | 5 | 0.291 | 0.222 | 0.364 | 29.90 | 9.50 | 0.696 | 0.304 | 46 | 0.235 | 17 | NA | NA |
| Smartphone | 1 | 0.520 | 0.516 | 0.525 | 341.47 | 342.00 | NA | NA | 0 | 0.720 | 25 | NA | NA |
| Smartphone | 2 | 0.306 | 0.195 | 0.422 | 123.30 | 27.00 | 0.333 | 0.667 | 27 | 0.600 | 25 | NA | NA |
| Smartphone | 3 | 0.319 | 0.216 | 0.425 | 142.50 | 140.00 | 0.306 | 0.694 | 36 | 0.560 | 25 | NA | NA |
| Smartphone | 4 | 0.243 | 0.183 | 0.309 | 117.12 | 32.00 | 0.303 | 0.697 | 33 | 0.560 | 25 | NA | NA |
| Smartphone | 5 | 0.415 | 0.320 | 0.507 | 56.70 | 8.00 | 0.375 | 0.625 | 40 | 0.440 | 25 | NA | NA |
| Smartphone Application Processor (SoC) Package | 1 | 0.291 | 0.288 | 0.295 | 143.14 | 146.00 | NA | NA | 0 | 0.556 | 36 | NA | NA |
| Smartphone Application Processor (SoC) Package | 2 | 0.431 | 0.361 | 0.496 | 98.20 | 99.00 | 0.273 | 0.727 | 33 | 0.500 | 36 | NA | NA |
| Smartphone Application Processor (SoC) Package | 3 | 0.346 | 0.270 | 0.431 | 84.50 | 102.50 | 0.286 | 0.714 | 35 | 0.389 | 36 | NA | NA |
| Smartphone Application Processor (SoC) Package | 4 | 0.438 | 0.369 | 0.510 | 99.90 | 108.50 | 0.255 | 0.745 | 47 | 0.389 | 36 | NA | NA |
| Smartphone Application Processor (SoC) Package | 5 | 0.418 | 0.335 | 0.503 | 80.50 | 98.00 | 0.172 | 0.828 | 29 | 0.278 | 36 | NA | NA |
| Solar Panel | 1 | 0.402 | 0.398 | 0.406 | 193.06 | 191.50 | NA | NA | 0 | 0.500 | 22 | NA | NA |
| Solar Panel | 2 | 0.314 | 0.231 | 0.398 | 77.30 | 86.00 | 0.481 | 0.519 | 27 | 0.409 | 22 | NA | NA |
| Solar Panel | 3 | 0.368 | 0.272 | 0.471 | 37.50 | 6.50 | 0.483 | 0.517 | 29 | 0.318 | 22 | NA | NA |
| Solar Panel | 4 | 0.376 | 0.274 | 0.487 | 46.10 | 41.50 | 0.452 | 0.548 | 31 | 0.318 | 22 | NA | NA |
| Solar Panel | 5 | 0.323 | 0.228 | 0.430 | 50.30 | 56.00 | 0.357 | 0.643 | 28 | 0.318 | 22 | NA | NA |
| Superconducting Quantum Computer (Dilution Refrigerator-based) | 1 | 0.351 | 0.348 | 0.355 | 200.56 | 198.00 | NA | NA | 0 | 0.553 | 38 | NA | NA |
| Superconducting Quantum Computer (Dilution Refrigerator-based) | 2 | 0.448 | 0.316 | 0.577 | 62.90 | 6.00 | 0.474 | 0.526 | 38 | 0.395 | 38 | NA | NA |
| Superconducting Quantum Computer (Dilution Refrigerator-based) | 3 | 0.235 | 0.169 | 0.307 | 88.30 | 71.00 | 0.350 | 0.650 | 40 | 0.368 | 38 | NA | NA |
| Superconducting Quantum Computer (Dilution Refrigerator-based) | 4 | 0.297 | 0.222 | 0.377 | 85.40 | 105.50 | 0.381 | 0.619 | 42 | 0.368 | 38 | NA | NA |
| Superconducting Quantum Computer (Dilution Refrigerator-based) | 5 | 0.335 | 0.252 | 0.418 | 41.00 | 7.50 | 0.434 | 0.566 | 53 | 0.263 | 38 | NA | NA |
| Tablet Press (Rotary Tablet Press) | 1 | 0.313 | 0.310 | 0.315 | 156.24 | 157.00 | NA | NA | 0 | 0.565 | 23 | NA | NA |
| Tablet Press (Rotary Tablet Press) | 2 | 0.320 | 0.232 | 0.412 | 74.30 | 100.00 | 0.533 | 0.467 | 30 | 0.391 | 23 | NA | NA |
| Tablet Press (Rotary Tablet Press) | 3 | 0.338 | 0.251 | 0.427 | 61.20 | 76.00 | 0.500 | 0.500 | 32 | 0.304 | 23 | NA | NA |
| Tablet Press (Rotary Tablet Press) | 4 | 0.330 | 0.251 | 0.408 | 39.64 | 9.00 | 0.604 | 0.396 | 48 | 0.261 | 23 | NA | NA |
| Tablet Press (Rotary Tablet Press) | 5 | 0.399 | 0.301 | 0.497 | 32.60 | 6.00 | 0.575 | 0.425 | 40 | 0.304 | 23 | NA | NA |
| Triple Quadrupole LC–MS Mass Spectrometer | 1 | 0.285 | 0.282 | 0.289 | 194.08 | 194.00 | NA | NA | 0 | 0.531 | 32 | NA | NA |
| Triple Quadrupole LC–MS Mass Spectrometer | 2 | 0.357 | 0.253 | 0.467 | 64.80 | 59.00 | 0.474 | 0.526 | 38 | 0.406 | 32 | NA | NA |
| Triple Quadrupole LC–MS Mass Spectrometer | 3 | 0.374 | 0.268 | 0.477 | 58.10 | 10.00 | 0.415 | 0.585 | 41 | 0.469 | 32 | NA | NA |
| Triple Quadrupole LC–MS Mass Spectrometer | 4 | 0.286 | 0.211 | 0.362 | 57.50 | 38.50 | 0.479 | 0.521 | 48 | 0.312 | 32 | NA | NA |
| Triple Quadrupole LC–MS Mass Spectrometer | 5 | 0.389 | 0.306 | 0.464 | 23.80 | 8.00 | 0.532 | 0.468 | 47 | 0.281 | 32 | NA | NA |


## Macro summary by N

| N | Techs | Stability (median) | Stability (mean) | Stability mean 95% CI | Δ Stability mean vs N=1 (95% CI) | Δ Stability median vs N=1 (95% CI) | Not-plausible (median) | Not-plausible (mean) | Not-plausible mean 95% CI | Δ Not-plausible mean vs N=1 (95% CI) | Δ Not-plausible median vs N=1 (95% CI) | % techs improved (invalid) | Precision (median) | Precision (mean) | #Materials (median) | #Materials (mean) | #Materials mean 95% CI | Δ #Materials mean vs N=1 (95% CI) | Δ #Materials median vs N=1 (95% CI) | Silver recall (median) | Silver recall (mean) | Silver recall mean 95% CI | Δ Silver recall mean vs N=1 (95% CI) | Δ Silver recall median vs N=1 (95% CI) | Final conv (median) | Final conv (mean) | Final conv mean 95% CI | Δ Final conv mean vs N=1 (95% CI) | Δ Final conv median vs N=1 (95% CI) | Runtime (median) | Runtime (mean) | Runtime mean 95% CI | Δ Runtime mean vs N=1 (95% CI) | Δ Runtime median vs N=1 (95% CI) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 24 | 0.297 | 0.312 | [0.295, 0.335] | NA | NA | NA | NA | NA | NA | NA | NA | NA | NA | 163.64 | 172.00 | [157.48, 190.29] | NA | NA | 0.549 | 0.541 | [0.496, 0.583] | NA | NA | NA | NA | NA | NA | NA | NA | NA | NA | NA | NA |
| 2 | 24 | 0.325 | 0.352 | [0.322, 0.385] | [0.001, 0.077] | [0.005, 0.096] | 0.481 | 0.458 | [0.402, 0.514] | NA | NA | NA | 0.519 | 0.542 | 60.30 | 65.65 | [56.91, 75.64] | [-127.28, -87.56] | [-124.55, -84.48] | 0.393 | 0.411 | [0.371, 0.455] | [-0.188, -0.070] | [-0.213, -0.063] | NA | NA | NA | NA | NA | NA | NA | NA | NA | NA |
| 3 | 24 | 0.326 | 0.326 | [0.311, 0.341] | [-0.015, 0.038] | [0.004, 0.055] | 0.434 | 0.444 | [0.387, 0.504] | NA | NA | NA | 0.566 | 0.556 | 56.80 | 59.95 | [51.90, 69.83] | [-133.09, -93.54] | [-129.80, -87.65] | 0.354 | 0.371 | [0.338, 0.408] | [-0.225, -0.113] | [-0.259, -0.104] | NA | NA | NA | NA | NA | NA | NA | NA | NA | NA |
| 4 | 24 | 0.299 | 0.305 | [0.284, 0.327] | [-0.039, 0.022] | [-0.021, 0.029] | 0.470 | 0.461 | [0.407, 0.519] | NA | NA | NA | 0.530 | 0.539 | 49.95 | 59.55 | [49.74, 70.40] | [-134.00, -93.26] | [-135.03, -91.26] | 0.329 | 0.350 | [0.313, 0.391] | [-0.247, -0.131] | [-0.272, -0.129] | NA | NA | NA | NA | NA | NA | NA | NA | NA | NA |
| 5 | 24 | 0.329 | 0.324 | [0.297, 0.353] | [-0.023, 0.045] | [-0.009, 0.086] | 0.471 | 0.474 | [0.420, 0.530] | NA | NA | NA | 0.529 | 0.526 | 40.85 | 44.30 | [37.48, 51.37] | [-147.80, -110.47] | [-143.65, -103.89] | 0.301 | 0.326 | [0.288, 0.365] | [-0.271, -0.157] | [-0.308, -0.142] | NA | NA | NA | NA | NA | NA | NA | NA | NA | NA |


## Recommended sweet-spot N

Recommended N: 2

### Why this N was picked

Constraints (macro-median metrics):
- not_plausible_median <= NA (no constraint)
- final_convergence_median >= NA (no constraint)
- runtime_median_seconds <= NA (no constraint)

Near-best stability requirement: stability_median >= best_feasible_stability * 0.980
Guardrail: require plausibility present (not_plausible_median non-NA): False

Best feasible stability_median: 0.329
Stability threshold (near-best): 0.322

Near-best candidates: N=2 (stability_median=0.325, runtime_median=NA), N=3 (stability_median=0.326, runtime_median=NA), N=5 (stability_median=0.329, runtime_median=NA).

Selected: N=2 (smallest N among near-best candidates; runtime_median=NA).
