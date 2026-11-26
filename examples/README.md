# Examples

This repository does not ship climate data: invented numbers would be misleading, and NASA POWER
data is easy to download.

## Get a real sample (needs internet)
```
python -m npcga.cli --lat 31.20 --lon 29.92 --start 2015-01-01 --end 2024-12-31 --name alexandria
```
Results appear in `outputs/alexandria/`.

## Expected file format for your own files
Daily CSV files downloaded from NASA POWER look like this (header, then a table):

```
-BEGIN HEADER-
NASA/POWER Source Native Resolution Daily Data
Dates (month/day/year): 01/01/2020 through 12/31/2025 in LST
Location: latitude  26.0  longitude 85.625
elevation from MERRA-2: Average for 0.5 x 0.625 degree lat/lon region = 52.99 meters
The value for missing source data that cannot be computed or is outside of the sources availability range: -999
parameter(s):
PRECTOTCORR    MERRA-2 Precipitation Corrected (mm/day)
-END HEADER-
YEAR,DOY,PRECTOTCORR
```
(data rows follow). One file per location. Put all files of a study area in one folder, or zip them.
