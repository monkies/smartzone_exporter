# SmartZone Exporter

Ruckus SmartZone exporter for https://prometheus.io, written in Python.

Forked from jakubjastrabik/smartzone_exporter and ddericco/smartzone_exporter and modified to add more metrics and support an environment running Smartzone VSz-H v7 and Wifi7 APs and 6Ghz radios

Provided as-is. 
### Example
```
python smartzone_exporter.py -u jimmy -p jangles -t https://ruckus.jjangles.com:8443 --insecure
```

## Requirements
This exporter has been tested on the following versions:

| Model | Version |
|-------|---------|
| vSZ-H | 7       |

## Installation
```
git clone https://github.com/monkies/smartzone_exporter.git
cd smartzone_exporter
pip3 -r requirements.txt
```
