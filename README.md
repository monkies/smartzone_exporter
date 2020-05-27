# SmartZone Exporter

Ruckus SmartZone exporter for https://prometheus.io, written in Python.

This exporter is adapted in part from examples by [Robust Perception](https://www.robustperception.io/writing-a-jenkins-exporter-in-python/) and [Loovoo](https://github.com/lovoo/jenkins_exporter), utilizing the [Ruckus SmartZone API](http://docs.ruckuswireless.com/smartzone/5.2.0/sz100-public-api-reference-guide-520.html#access-point-operational-retrieve-operational-information-get) to query for metrics.

## Background
The goal of this exporter is twofold: provide a faster and more reliable alternative to SNMP for querying metrics from a Ruckus SmartZone controller, while also providing an opportunity to brush up on my (admittedly quite rusty) Python skills. Most of the code will be heavily commented with notes that would be obvious to more experienced developers; perhaps it will be useful for other contributors or developers. There will certainly be additional efficiencies that can be gained, more 'Pythonic' ways of doing certain tasks, or other changes that make this exporter better; contributions are always welcome!

## Features
The following metrics are currently supported:
* Controller summary (uptime, model, description, serial, version, AP firmware version, cluster role)
* System metric (cpu, disk, ram, port:{rx/txBps, rx/txBytes, rx/txDropped, rx/txPackets})
* System inventory (total APs, discovery APs, connected APs, disconnected APs, clients, max APs of cluster, total remaining ap capacity)
* AP statistics (serial, AP Group Id, model, version, description, zone Id, connection state, 5GHz channel, 2.4GHz channel, alerts, approved time,
 last seen time, connected clients, uptime, location, config state)
 * Licences
 * domain metrics (domain type, parent domain id, sub domain count, ap count, zone count)

## Docker Usage
* pull repozitory
``` docker
docker pull byjastrab/smartzone_exporter
```
* create .env file
* Run docker
``` docker
docker run -p 9345:9345 --env-file=.env --name smartzone_exporter byjastrab/smartzone_exporter
```

## Usage
```
usage: smartzone_exporter.py [-h] -u USER -p PASSWORD -t TARGET [--insecure]
                             [--port PORT]

optional arguments:
  -h, --help            show this help message and exit
  --insecure            Allow insecure SSL connections to Smartzone
  --port PORT           Port on which to expose metrics and web interface
                        (default=9345)

required named arguments:
  -u USER, --user USER  SmartZone API user
  -p PASSWORD, --password PASSWORD
                        SmartZone API password
  -t TARGET, --target TARGET
                        Target URL and port to access SmartZone, e.g.
                        https://smartzone.example.com:8443
```
### Example
```
python smartzone_exporter.py -u jimmy -p jangles -t https://ruckus.jjangles.com:8443
```

## Requirements
This exporter has been tested on the following versions:

| Model | Version     |
|-------|-------------|
| vSZ-H | 5.2.0.0.699 |

## Installation
```
git clone https://github.com/ddericco/smartzone_exporter.git
cd smartzone_exporter
pipenv install
```
