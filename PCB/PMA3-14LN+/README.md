# PMA3-14LN+ Changelog

## Revision C - 6/8/2026

### Added

- New thermal via grid underneath U2 for temperature management
- Layer 2 DGS underneath L1,L2,C1,C2,C3,C4 as follows:
    - Shunts L1,L2,C3,C4: 0.60mm x 0.1mm (trace pad)
    - Series C1,C2: 1.5mm x 0.5mm

### Changed

- Changed mouting pad dimensions of L1,L2,C1,C2,C3,C4 to 0.56mm x 0.62mm rounded rectangle. Previous values:
    - Shunts L1,L2: 0.37mm x 0.72mm rounded rectangle (trace pad) and 0.59mm x 0.64mm rectangle (bias pad)
    - Series C1,C2: 0.56mm x 0.37mm rounded rectangle (both)
    - Shunts C3,C4: 0.37mm x 0.72mm (trace pad) and 0.56mm x 0.62mm (bias pad)
- Increased clearance around trace components from 0.2mm to 0.3mm

## Revision B - 10/24/2023

### Added

- More PTH vias around and directly under RF components.
- Another layer of via picketing around transmission line.
- Silkscreen revision indicator.
- Dimensioning to assembly drawing.

### Changed

- Removed Hammond 1554B compatibility due to difficulties in assembly and weatherproofing SMA connectors. Overall board is smaller at 35mm x 35mm.
- SMA Connectors replaced with Mueller BU-1420761881 which have an upper frequency of 26.5 GHz and better impedance matching at the landing.
- GCPW dimensions from w = 0.415mm, s = 0.6mm, to w = 0.37mm, s = 0.2mm and added 0.375mm taper from SMA clearance to GCPW clearance.

### Fixed

- C9 footprint now correctly matches schematic (0402 --> 1206).
- Moved SMA footprints closer to board edge to reduce filing prior to assembly.

## Revision A - 4/12/2023

### First revision 🎉🎉🎉

- Board is built to 4-layer OSHPark specifications
- This amplifier showed slightly lower gain than expected, rolling off quicker with frequency. This is likely due to the SMA connector landings which had a known impedance mismatch, resulting in a steep rolloff somewhere between 12 and 18 GHz.
