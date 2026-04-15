# LLM Judge Validation Against Gold Standard

- **Date**: 2026-04-15 09:05
- **Judge model**: `openai:gpt-4.1`
- **Normalization model**: `openai:gpt-4.1`
- **Pipeline configs**: d3v1v1, v1v1v1
- **Technologies**: Pharmaceutical Lyophilizer, Rotary tablet press, Single-use bioreactor, Smartphone

## Methodology

The gold standard lists known-valid primary manufacturing components per technology. Both gold standard and pipeline component names are normalized through the same canonical vocabulary. The LLM judge is run on the union of gold standard and pipeline components. Precision/recall/F1 measure how well the judge's plausibility verdicts align with gold standard membership.

**Caveat**: The gold standard may not be exhaustive. Components NOT in the gold standard that the judge labels plausible may actually be valid — the false positive count is an upper bound, and precision is a lower bound.

## Per-Technology Results

| Technology | Gold Std | Pipeline | TP | FP | TN | FN | Precision | Recall | F1 | Pipeline Recall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pharmaceutical Lyophilizer | 9 | 21 | 9 | 16 | 1 | 0 | 0.360 | 1.000 | 0.529 | 0.444 |
| Rotary tablet press | 9 | 0 | 9 | 0 | 0 | 0 | 1.000 | 1.000 | 1.000 | 0.000 |
| Single-use bioreactor | 11 | 0 | 11 | 0 | 0 | 0 | 1.000 | 1.000 | 1.000 | 0.000 |
| Smartphone | 24 | 6 | 23 | 4 | 2 | 1 | 0.852 | 0.958 | 0.902 | 0.000 |
| **AGGREGATE** | 53 | 27 | 52 | 20 | 3 | 1 | 0.722 | 0.981 | 0.832 | — |

## False Negatives (Gold Standard Components Judge Rejected)

These are components in the gold standard that the judge labeled implausible.

### Smartphone

- **Connectors**: Connectors are important secondary components used to interconnect primary modules in a smartphone, such as the display, battery, and motherboard. However, they are not considered primary manufacturing components as they are small parts rather than major subassemblies or functional modules with distinct supply chains.

## False Positives (Pipeline-Only Components Judge Accepted)

These are components NOT in the gold standard that the judge labeled plausible. Some may actually be valid components missing from the gold standard.

### Pharmaceutical Lyophilizer

- **Actuation and Mounting System**: The 'Actuation and Mounting System' is a plausible primary manufacturing component for a pharmaceutical lyophilizer, as it likely encompasses key mechanical subassemblies responsible for precise movement and positioning of shelves, trays, or other elements within the lyophilizer chamber. These functional modules are typically sourced or engineered as distinct units in the industry.
- **Chamber Door and Sealing System**: The chamber door and sealing system is a critical structural and functional subassembly in a pharmaceutical lyophilizer, as it maintains the vacuum integrity required for the freeze-drying process. This system is typically procured or manufactured as a distinct unit and is essential to the lyophilizer's operation, making it a plausible primary manufacturing component.
- **Condensate Drainage System**: The condensate drainage system is a primary subassembly in a pharmaceutical lyophilizer, responsible for removing condensed moisture generated during the freeze-drying process. It is typically procured or manufactured as a distinct module, forming a crucial functional boundary for reliable lyophilizer operation.
- **Condenser and Cold Trap System**: The condenser and cold trap system is a critical primary component of a pharmaceutical lyophilizer, responsible for capturing and condensing water vapor during the freeze-drying process. It is a distinct subsystem with its own supply chain and functional boundaries, typically supplied or manufactured as a complete unit. Its role is central to the operational success and core architecture of the lyophilizer.
- **Control Electronics (Timer, Sensors, Safety Interlocks)**: Control electronics, including timer, sensors, and safety interlocks, form a core subassembly for a pharmaceutical lyophilizer. These electronics are essential for process control, monitoring, and operational safety, and are typically procured or manufactured as a distinct functional module, making them a plausible primary manufacturing component.
- **Cryostat Vacuum Chamber And Structural Frame**: The cryostat vacuum chamber and structural frame are core components of a pharmaceutical lyophilizer, providing the primary enclosure for the freeze-drying process and maintaining the vacuum environment. These assemblies are typically manufactured and supplied as major subassemblies with distinct fabrication requirements. Thus, they are plausible primary manufacturing components.
- **Door Assembly**: The door assembly of a pharmaceutical lyophilizer is a major subassembly with its own supply chain, incorporating seals, locking mechanisms, and sometimes viewports. It is critical for maintaining the vacuum and sterile environment required in lyophilization, making it a primary manufacturing component.
- **Freeze Dryer Vacuum Chamber**: The freeze dryer vacuum chamber is a major structural and functional assembly at the core of a pharmaceutical lyophilizer. It is procured or manufactured as a distinct unit, forms the primary environment for the lyophilization process, and has a separate supply chain.
- **Heating System (Shelf Heaters or Jacket Heating)**: The heating system in a pharmaceutical lyophilizer, such as shelf heaters or jacket heating, is a critical primary subassembly. It controls temperature and facilitates sublimation during the freeze-drying process, and is typically procured or designed as a distinct module with separate supply chain considerations.
- **Load/Unload and Tray Handling System**: The Load/Unload and Tray Handling System is a major subassembly of a pharmaceutical lyophilizer, responsible for the automated handling and transfer of trays containing vials or product. It has its own supply chain, is procured as a functional module, and is critical for efficient and sterile manufacturing operations.
- **Pressure Vessel**: The pressure vessel is a core structural assembly in a pharmaceutical lyophilizer, providing the contained environment necessary for the sublimation process during freeze drying. It is typically manufactured and supplied as a major subassembly with strict regulatory and engineering requirements. Thus, it is a plausible primary manufacturing component.
- **Refrigeration System (Cascade or Single-stage Refrigeration Unit)**: The refrigeration system, whether cascade or single-stage, is a primary manufacturing component for a pharmaceutical lyophilizer. It is a major functional module with its own supply chain and is critical for creating the low temperatures required for the lyophilization (freeze-drying) process.
- **Shelf System With Temperature Control**: The shelf system with temperature control is a major subassembly in pharmaceutical lyophilizers, directly holding and thermally regulating product vials during freeze-drying. It is typically manufactured and sourced as a complete unit and forms a core functional architecture within the lyophilizer.
- **Shelf System with Heating Plates**: The shelf system with heating plates is a primary manufacturing component of a pharmaceutical lyophilizer, serving as a core subassembly where product vials sit during the freeze-drying process. It is essential for both controlled heating and uniform drying, and is typically procured as a distinct, complex module from specialized suppliers.
- **Temperature Controlled Shelf System**: The temperature controlled shelf system is a primary manufacturing component in pharmaceutical lyophilizers, as it functions as a major subassembly responsible for precisely controlling product temperature during the freeze-drying process. It is typically procured or manufactured as a distinct unit and is critical for the functional architecture of the equipment.
- **Vacuum System (Vacuum Pump)**: The vacuum system (vacuum pump) is a core functional module in a pharmaceutical lyophilizer, responsible for creating the low-pressure environment required for the freeze-drying process. It is procured as a distinct unit, has its own dedicated supply chain, and is essential for primary lyophilizer operation.

### Smartphone

- **Lithium-ion Battery Module**: The lithium-ion battery module is a primary manufacturing component in smartphones. It is procured as a discrete unit, has dedicated suppliers, and forms a critical functional subassembly that powers the device. As such, it meets all criteria for a core manufacturing component in modern smartphone production.
- **Printed Circuit Board (PCB) Assembly**: The Printed Circuit Board (PCB) Assembly is a core functional subassembly in smartphones, responsible for interconnecting and supporting all major electronic components such as the processor, memory, and power management. It is manufactured and supplied as a distinct unit, representing a primary manufacturing component by industry standards.
- **Structural Enclosure and Chassis**: The structural enclosure and chassis are major subassemblies in smartphones, forming the core physical framework that houses and protects internal components. These elements are manufactured as separate units, often procured from specialized suppliers, and represent a primary dependency boundary in smartphone production.
- **User Interface Module (Display and Keypad/Touchscreen)**: The 'User Interface Module', comprising the display and keypad/touchscreen, is an industry-standard, primary assembly in modern smartphones. It forms the main functional interface between user and device, is typically procured as a discrete unit from specialized suppliers, and represents a crucial architectural assembly. Therefore, it is a plausible primary manufacturing component.

