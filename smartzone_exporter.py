# requests used to fetch API data
import requests

# Allow for silencing insecure warnings from requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Builtin JSON module for testing - might not need later
import json

# Needed for sleep and exporter start/end time metrics
import time

# argparse module used for providing command-line interface
import argparse

# Prometheus modules for HTTP server & metrics
from prometheus_client import start_http_server, Summary
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, REGISTRY

# Import Treading and queue
import queue
import threading

# Create SmartZoneCollector as a class - in Python3, classes inherit object as a base class
# Only need to specify for compatibility or in Python2

class SmartZoneCollector():

    # Initialize the class and specify required argument with no default value
    # When defining class methods, must explicitly list `self` as first argument
    def __init__(self, target, user, password, insecure):
        # Strip any trailing "/" characters from the provided url
        self._target = target.rstrip("/")
        # Take these arguments as provided, no changes needed
        self._user = user
        self._password = password
        self._insecure = insecure

        self._headers = None
        self._statuses = None

        # With the exception of uptime, all of these metrics are strings
        # Following the example of node_exporter, we'll set these string metrics with a default value of 1

    def get_session(self):
        # Disable insecure request warnings if SSL verification is disabled
        if self._insecure == False:
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

        # Session object used to keep persistent cookies and connection pooling
        s = requests.Session()

        # Set `verify` variable to enable or disable SSL checking
        # Use string method format methods to create new string with inserted value (in this case, the URL)
        s.get('{}/wsg/api/public/v12_0/session'.format(self._target), verify=self._insecure)

        # Define URL arguments as a dictionary of strings 'payload'
        payload = {'username': self._user, 'password': self._password}

        # Call the payload using the json parameter
        r = s.post('{}/wsg/api/public/v12_0/session'.format(self._target), json=payload, verify=self._insecure)

        # Raise bad requests
        r.raise_for_status()

        # Create a dictionary from the cookie name-value pair, then get the value based on the JSESSIONID key
        session_id = r.cookies.get_dict().get('JSESSIONID')

        # Add HTTP headers for all requests EXCEPT logon API
        # Integrate the session ID into the header
        self._headers = {'Content-Type': 'application/json;charset=UTF-8', 'Cookie': 'JSESSIONID={}'.format(session_id)}

    def get_metrics(self, metrics, api_path):
        # Add the individual URL paths for the API call
        self._statuses = list(metrics.keys())
        if 'query' in api_path:
            # For APs, use POST and API query to reduce number of requests and improve performance
            # To-do: set dynamic AP limit based on SmartZone inventory
            raw = {'limit': 1000}
            r = requests.post('{}/wsg/api/public/v12_0/{}'.format(self._target, api_path), json=raw,
                              headers=self._headers, verify=self._insecure)
        else:
            r = requests.get('{}/wsg/api/public/v12_0/{}'.format(self._target, api_path + '?listSize=1000'),
                             headers=self._headers,
                             verify=self._insecure)
        result = json.loads(r.text)
        return result

    def collect(self):

        controller_metrics = {
            'model':
                GaugeMetricFamily('smartzone_controller_model',
                                  'SmartZone controller model',
                                  labels=["id", "model"]),
            'description':
                GaugeMetricFamily('smartzone_controller_description',
                                  'SmartZone controller description',
                                  labels=["id", "description"]),
            'serialNumber':
                GaugeMetricFamily('smartzone_controller_serial_number',
                                  'SmartZone controller serial number',
                                  labels=["id", "serialNumber"]),
            'clusterRole':
                GaugeMetricFamily('smartzone_controller_cluster_role',
                                  'SmartZone controller cluster role',
                                  labels=["id", "serialNumber"]),
            'uptimeInSec':
                CounterMetricFamily('smartzone_controller_uptime_seconds',
                                    'Controller uptime in sections',
                                    labels=["id"]),
            'version':
                GaugeMetricFamily('smartzone_controller_version',
                                  'Controller version',
                                  labels=["id", "version"]),
            'apVersion':
                GaugeMetricFamily('smartzone_controller_ap_firmware_version',
                                  'Firmware version on controller APs',
                                  labels=["id", "apVersion"])
        }

        zone_metrics = {
            'totalAPs':
                GaugeMetricFamily('smartzone_zone_total_aps',
                                  'Total number of APs in zone',
                                  labels=["zone_name", "zone_id"]),
            'discoveryAPs':
                GaugeMetricFamily('smartzone_zone_discovery_aps',
                                  'Number of zone APs in discovery state',
                                  labels=["zone_name", "zone_id"]),
            'connectedAPs':
                GaugeMetricFamily('smartzone_zone_connected_aps',
                                  'Number of connected zone APs',
                                  labels=["zone_name", "zone_id"]),
            'disconnectedAPs':
                GaugeMetricFamily('smartzone_zone_disconnected_aps',
                                  'Number of disconnected zone APs',
                                  labels=["zone_name", "zone_id"]),
            'clients':
                GaugeMetricFamily('smartzone_zone_total_connected_clients',
                                  'Total number of connected clients in zone',
                                  labels=["zone_name", "zone_id"])
        }

        system_metric = {
            'cpu': {
                'percent':
                    GaugeMetricFamily('smartzone_system_cpu_usage',
                                      'SmartZone system CPU usage',
                                      labels=["id"])
            },
            'disk': {
                'total':
                    GaugeMetricFamily('smartzone_system_disk_size',
                                      'SmartZone system disk size',
                                      labels=["id"]),
                'free':
                    GaugeMetricFamily('smartzone_system_disk_free',
                                      'SmartZone system disk free space',
                                      labels=["id"]),
            },
            'memory': {
                'percent':
                    GaugeMetricFamily('smartzone_system_memory_usage',
                                      'SmartZone system memory usage',
                                      labels=["id"])
            },
            'control': {
                'rxBps':
                    GaugeMetricFamily('smartzone_system_port_rxBps',
                                      'SmartZone system port  rxBps (Throughput)',
                                      labels=["id", "port"]),
                'rxBytes':
                    GaugeMetricFamily('smartzone_system_port_rxBytes',
                                      'SmartZone system port  total rxBytes',
                                      labels=["id", "port"]),
                'rxDropped':
                    GaugeMetricFamily('smartzone_system_port_rxDropped',
                                      'SmartZone system port  total rxDropped',
                                      labels=["id", "port"]),
                'rxPackets':
                    GaugeMetricFamily('smartzone_system_port_rxPackets',
                                      'SmartZone system port  total rxPackets',
                                      labels=["id", "port"]),
                'txBps':
                    GaugeMetricFamily('smartzone_system_port_txBps',
                                      'SmartZone system port  txBps (Throughput)',
                                      labels=["id", "port"]),
                'txBytes':
                    GaugeMetricFamily('smartzone_system_port_txBytes',
                                      'SmartZone system port  total txBytes',
                                      labels=["id", "port"]),
                'txDropped':
                    GaugeMetricFamily('smartzone_system_port_txDropped',
                                      'SmartZone system port  total txDropped',
                                      labels=["id", "port"]),
                'txPackets':
                    GaugeMetricFamily('smartzone_system_port_txPackets',
                                      'SmartZone system port  total txPackets',
                                      labels=["id", "port"])
            },
            'port1': {
                'rxBps':
                    GaugeMetricFamily('smartzone_system_port_rxBps',
                                      'SmartZone system port rxBps (Throughput)',
                                      labels=["id", "port"]),
                'rxBytes':
                    GaugeMetricFamily('smartzone_system_port_rxBytes',
                                      'SmartZone system port total rxBytes',
                                      labels=["id", "port"]),
                'rxDropped':
                    GaugeMetricFamily('smartzone_system_port_rxDropped',
                                      'SmartZone system port total rxDropped',
                                      labels=["id", "port"]),
                'rxPackets':
                    GaugeMetricFamily('smartzone_system_port_rxPackets',
                                      'SmartZone system port total rxPackets',
                                      labels=["id", "port"]),
                'txBps':
                    GaugeMetricFamily('smartzone_system_port_txBps',
                                      'SmartZone system port txBps (Throughput)',
                                      labels=["id", "port"]),
                'txBytes':
                    GaugeMetricFamily('smartzone_system_port_txBytes',
                                      'SmartZone system port total txBytes',
                                      labels=["id", "port"]),
                'txDropped':
                    GaugeMetricFamily('smartzone_system_port_txDropped',
                                      'SmartZone system port total txDropped',
                                      labels=["id", "port"]),
                'txPackets':
                    GaugeMetricFamily('smartzone_system_port_txPackets',
                                      'SmartZone system port total txPackets',
                                      labels=["id", "port"])
            },
            'port2': {
                'rxBps':
                    GaugeMetricFamily('smartzone_system_port_rxBps',
                                      'SmartZone system port rxBps (Throughput)',
                                      labels=["id", "port"]),
                'rxBytes':
                    GaugeMetricFamily('smartzone_system_port_rxBytes',
                                      'SmartZone system port total rxBytes',
                                      labels=["id", "port"]),
                'rxDropped':
                    GaugeMetricFamily('smartzone_system_port_rxDropped',
                                      'SmartZone system port total rxDropped',
                                      labels=["id", "port"]),
                'rxPackets':
                    GaugeMetricFamily('smartzone_system_port_rxPackets',
                                      'SmartZone system port total rxPackets',
                                      labels=["id", "port"]),
                'txBps':
                    GaugeMetricFamily('smartzone_system_port_txBps',
                                      'SmartZone system port txBps (Throughput)',
                                      labels=["id", "port"]),
                'txBytes':
                    GaugeMetricFamily('smartzone_system_port_txBytes',
                                      'SmartZone system port total txBytes',
                                      labels=["id", "port"]),
                'txDropped':
                    GaugeMetricFamily('smartzone_system_port_txDropped',
                                      'SmartZone system port total txDropped',
                                      labels=["id", "port"]),
                'txPackets':
                    GaugeMetricFamily('smartzone_system_port_txPackets',
                                      'SmartZone system port total txPackets',
                                      labels=["id", "port"])
            }
        }

        system_summary_metric = {
            'maxApOfCluster':
                GaugeMetricFamily('smartzone_cluster_maxAPs',
                                  'SmartZone Cluster number of maximum possible connected APs',
                                  labels=["id"]),
            'totalRemainingApCapacity':
                GaugeMetricFamily('smartzone_cluster_totalRemainingApCapacity',
                                  'SmartZone Cluster number of total remaining possible connected APs',
                                  labels=["id"]),
        }

        ap_list = {
            'deviceName' :
                GaugeMetricFamily('smartzone_ap_deviceName', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'description':
                GaugeMetricFamily('smartzone_ap_description', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'description']),
            'status':
                GaugeMetricFamily('smartzone_ap_status', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'status']),
            'alerts':
                GaugeMetricFamily('smartzone_ap_alerts', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'ip':
                GaugeMetricFamily('smartzone_ap_ip', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'ip']),
            'ipv6Address':
                GaugeMetricFamily('smartzone_ap_ipv6Address', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'ipv6Address']),
            'txRx':
                GaugeMetricFamily('smartzone_ap_txRx', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'noise24G':
                GaugeMetricFamily('smartzone_ap_noise24G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'noise5G':
                GaugeMetricFamily('smartzone_ap_noise5G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'noise6G':
                GaugeMetricFamily('smartzone_ap_noise6G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'airtime24G':
                GaugeMetricFamily('smartzone_ap_airtime24G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'airtime5G':
                GaugeMetricFamily('smartzone_ap_airtime5G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'airtime6G':
                GaugeMetricFamily('smartzone_ap_airtime6G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'latency24G':
                GaugeMetricFamily('smartzone_ap_latency24G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'latency50G':
                GaugeMetricFamily('smartzone_ap_latency50G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'latency6G':
                GaugeMetricFamily('smartzone_ap_latency6G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'capacity':
                GaugeMetricFamily('smartzone_ap_capacity', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'capacity24G':
                GaugeMetricFamily('smartzone_ap_capacity24G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'capacity50G':
                GaugeMetricFamily('smartzone_ap_capacity50G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'capacity6G':
                GaugeMetricFamily('smartzone_ap_capacity6G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'connectionFailure':
                GaugeMetricFamily('smartzone_ap_connectionFailure', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'model':
                GaugeMetricFamily('smartzone_ap_model', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'model']),
            'apMac':
                GaugeMetricFamily('smartzone_ap_apMac', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'apMac']),
            'channel24G':
                GaugeMetricFamily('smartzone_ap_channel24G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'channel24G']),
            'channel5G':
                GaugeMetricFamily('smartzone_ap_channel5G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'channel5G']),
            'channel6G':
                GaugeMetricFamily('smartzone_ap_channel6G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'channel6G']),
            'channel24gValue':
                GaugeMetricFamily('smartzone_ap_channel24gValue', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'channel50gValue':
                GaugeMetricFamily('smartzone_ap_channel50gValue', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'channel6gValue':
                GaugeMetricFamily('smartzone_ap_channel6gValue', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'meshRole':
                GaugeMetricFamily('smartzone_ap_meshRole', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'meshRole']),
            'meshMode':
                GaugeMetricFamily('smartzone_ap_meshMode', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'meshMode']),
            'zoneName':
                GaugeMetricFamily('smartzone_ap_zoneName', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'zoneName']),
            'zoneAffinityProfileName':
                GaugeMetricFamily('smartzone_ap_zoneAffinityProfileName', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'zoneAffinityProfileName']),
            'apGroupName':
                GaugeMetricFamily('smartzone_ap_apGroupName', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'apGroupName']),
            'extIp':
                GaugeMetricFamily('smartzone_ap_extIp', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'extIp']),
            'extPort':
                GaugeMetricFamily('smartzone_ap_extPort', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'extPort']),
            'firmwareVersion':
                GaugeMetricFamily('smartzone_ap_firmwareVersion', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'firmwareVersion']),
            'serial':
                GaugeMetricFamily('smartzone_ap_serial', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'serial']),
            'retry24G':
                GaugeMetricFamily('smartzone_ap_retry24G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'retry5G':
                GaugeMetricFamily('smartzone_ap_retry5G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'retry6G':
                GaugeMetricFamily('smartzone_ap_retry6G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'configurationStatus':
                GaugeMetricFamily('smartzone_ap_configurationStatus', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'configurationStatus']),
            'lastSeen':
                GaugeMetricFamily('smartzone_ap_lastSeen', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'numClients':
                GaugeMetricFamily('smartzone_ap_numClients', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'numClients24G':
                GaugeMetricFamily('smartzone_ap_numClients24G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'numClients5G':
                GaugeMetricFamily('smartzone_ap_numClients5G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'numClients6G':
                GaugeMetricFamily('smartzone_ap_numClients6G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'tx':
                GaugeMetricFamily('smartzone_ap_tx', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'tx24G':
                GaugeMetricFamily('smartzone_ap_tx24G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'tx50G':
                GaugeMetricFamily('smartzone_ap_tx50G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'tx6G':
                GaugeMetricFamily('smartzone_ap_tx6G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'rx':
                GaugeMetricFamily('smartzone_ap_rx', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'rx24G':
                GaugeMetricFamily('smartzone_ap_rx24G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'rx50G':
                GaugeMetricFamily('smartzone_ap_rx50G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'rx6G':
                GaugeMetricFamily('smartzone_ap_rx6G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'txRx24G':
                GaugeMetricFamily('smartzone_ap_txRx24G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'txRx50G':
                GaugeMetricFamily('smartzone_ap_txRx50G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'txRx6G':
                GaugeMetricFamily('smartzone_ap_txRx6G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'location':
                GaugeMetricFamily('smartzone_ap_location', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'location']),
            'wlanGroup24Id':
                GaugeMetricFamily('smartzone_ap_wlanGroup24Id', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'wlanGroup24Id']),
            'wlanGroup50Id':
                GaugeMetricFamily('smartzone_ap_wlanGroup50Id', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'wlanGroup50Id']),
            'wlanGroup6gId':
                GaugeMetricFamily('smartzone_ap_wlanGroup6gId', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'wlanGroup6gId']),
            'wlanGroup24Name':
                GaugeMetricFamily('smartzone_ap_wlanGroup24Name', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'wlanGroup24Name']),
            'wlanGroup50Name':
                GaugeMetricFamily('smartzone_ap_wlanGroup50Name', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'wlanGroup50Name']),
            'wlanGroup6gName':
                GaugeMetricFamily('smartzone_ap_wlanGroup6gName', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'wlanGroup6gName']),
            'enabledBonjourGateway':
                GaugeMetricFamily('smartzone_ap_enabledBonjourGateway', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'enabledBonjourGateway']),
            'controlBladeName':
                GaugeMetricFamily('smartzone_ap_controlBladeName', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'controlBladeName']),
            'lbsStatus':
                GaugeMetricFamily('smartzone_ap_lbsStatus', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'lbsStatus']),
            'administrativeState':
                GaugeMetricFamily('smartzone_ap_administrativeState', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'administrativeState']),
            'registrationState':
                GaugeMetricFamily('smartzone_ap_registrationState', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'registrationState']),
            'provisionMethod':
                GaugeMetricFamily('smartzone_ap_provisionMethod', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'provisionMethod']),
            'provisionStage':
                GaugeMetricFamily('smartzone_ap_provisionStage', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'provisionStage']),
            'registrationTime':
                GaugeMetricFamily('smartzone_ap_registrationTime', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'managementVlan':
                GaugeMetricFamily('smartzone_ap_managementVlan', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'configOverride':
                GaugeMetricFamily('smartzone_ap_configOverride', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'configOverride']),
            'apGroupId':
                GaugeMetricFamily('smartzone_ap_apGroupId', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'apGroupId']),
            'deviceGps':
                GaugeMetricFamily('smartzone_ap_deviceGps', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'deviceGps']),
            'connectionStatus':
                GaugeMetricFamily('smartzone_ap_connectionStatus', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'connectionStatus']),
            'zoneId':
                GaugeMetricFamily('smartzone_ap_zoneId', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'zoneId']),
            'zoneFirmwareVersion':
                GaugeMetricFamily('smartzone_ap_zoneFirmwareVersion', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'zoneFirmwareVersion']),
            'domainId':
                GaugeMetricFamily('smartzone_ap_domainId', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'domainId']),
            'domainName':
                GaugeMetricFamily('smartzone_ap_domainName', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'domainName']),
            'partnerDomainId':
                GaugeMetricFamily('smartzone_ap_partnerDomainId', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'partnerDomainId']),
            'controlBladeId':
                GaugeMetricFamily('smartzone_ap_controlBladeId', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'controlBladeId']),
            'isCriticalAp':
                GaugeMetricFamily('smartzone_ap_isCriticalAp', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'isCriticalAp']),
            'crashDump':
                GaugeMetricFamily('smartzone_ap_crashDump', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'isOverallHealthStatusFlagged':
                GaugeMetricFamily('smartzone_ap_isOverallHealthStatusFlagged', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'isOverallHealthStatusFlagged']),
            'isLatency24GFlagged':
                GaugeMetricFamily('smartzone_ap_isLatency24GFlagged', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'isLatency24GFlagged']),
            'isLatency50GFlagged':
                GaugeMetricFamily('smartzone_ap_isLatency50GFlagged', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'isLatency50GFlagged']),
            'isLatency6GFlagged':
                GaugeMetricFamily('smartzone_ap_isLatency6GFlagged', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'isLatency6GFlagged']),
            'isCapacity24GFlagged':
                GaugeMetricFamily('smartzone_ap_isCapacity24GFlagged', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'isCapacity24GFlagged']),
            'isCapacity50GFlagged':
                GaugeMetricFamily('smartzone_ap_isCapacity50GFlagged', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'isCapacity50GFlagged']),
            'isCapacity6GFlagged':
                GaugeMetricFamily('smartzone_ap_isCapacity6GFlagged', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'isCapacity6GFlagged']),
            'isConnectionFailure24GFlagged':
                GaugeMetricFamily('smartzone_ap_isConnectionFailure24GFlagged', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'isConnectionFailure24GFlagged']),
            'isConnectionFailure50GFlagged':
                GaugeMetricFamily('smartzone_ap_isConnectionFailure50GFlagged', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'isConnectionFailure50GFlagged']),
            'isConnectionFailure6GFlagged':
                GaugeMetricFamily('smartzone_ap_isConnectionFailure6GFlagged', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'isConnectionFailure6GFlagged']),
            'isConnectionTotalCountFlagged':
                GaugeMetricFamily('smartzone_ap_isConnectionTotalCountFlagged', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'isConnectionTotalCountFlagged']),
            'isConnectionFailureFlagged':
                GaugeMetricFamily('smartzone_ap_isConnectionFailureFlagged', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'isConnectionFailureFlagged']),
            'isAirtimeUtilization24GFlagged':
                GaugeMetricFamily('smartzone_ap_isAirtimeUtilization24GFlagged', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'isAirtimeUtilization24GFlagged']),
            'isAirtimeUtilization50GFlagged':
                GaugeMetricFamily('smartzone_ap_isAirtimeUtilization50GFlagged', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'isAirtimeUtilization50GFlagged']),
            'isAirtimeUtilization6GFlagged':
                GaugeMetricFamily('smartzone_ap_isAirtimeUtilization6GFlagged', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'isAirtimeUtilization6GFlagged']),
            'uptime':
                GaugeMetricFamily('smartzone_ap_uptime', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'eirp24G':
                GaugeMetricFamily('smartzone_ap_eirp24G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'eirp50G':
                GaugeMetricFamily('smartzone_ap_eirp50G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'eirp6G':
                GaugeMetricFamily('smartzone_ap_eirp6G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'ipType':
                GaugeMetricFamily('smartzone_ap_ipType', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'ipType']),
            'ipv6Type':
                GaugeMetricFamily('smartzone_ap_ipv6Type', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'ipv6Type']),
            'packetCaptureState':
                GaugeMetricFamily('smartzone_ap_packetCaptureState', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'packetCaptureState']),
            'medianTxRadioMCSRate24G':
                GaugeMetricFamily('smartzone_ap_medianTxRadioMCSRate24G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'medianTxRadioMCSRate50G':
                GaugeMetricFamily('smartzone_ap_medianTxRadioMCSRate50G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'medianTxRadioMCSRate6G':
                GaugeMetricFamily('smartzone_ap_medianTxRadioMCSRate6G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'medianRxRadioMCSRate24G':
                GaugeMetricFamily('smartzone_ap_medianRxRadioMCSRate24G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'medianRxRadioMCSRate50G':
                GaugeMetricFamily('smartzone_ap_medianRxRadioMCSRate50G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'medianRxRadioMCSRate6G':
                GaugeMetricFamily('smartzone_ap_medianRxRadioMCSRate6G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'monitoringEnabled':
                GaugeMetricFamily('smartzone_ap_monitoringEnabled', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'monitoringEnabled']),
            'txPowerOffset24G':
                GaugeMetricFamily('smartzone_ap_txPowerOffset24G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'txPowerOffset5G':
                GaugeMetricFamily('smartzone_ap_txPowerOffset5G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'txPowerOffset6G':
                GaugeMetricFamily('smartzone_ap_txPowerOffset6G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'rxDesense24G':
                GaugeMetricFamily('smartzone_ap_rxDesense24G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'rxDesense5G':
                GaugeMetricFamily('smartzone_ap_rxDesense5G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'rxDesense6G':
                GaugeMetricFamily('smartzone_ap_rxDesense6G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'poePortStatus':
                GaugeMetricFamily('smartzone_ap_poePortStatus', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'poePortStatus']),
            'cumulativeTx24G':
                GaugeMetricFamily('smartzone_ap_cumulativeTx24G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'cumulativeTx5G':
                GaugeMetricFamily('smartzone_ap_cumulativeTx5G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'cumulativeTx6G':
                GaugeMetricFamily('smartzone_ap_cumulativeTx6G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'cumulativeRx24G':
                GaugeMetricFamily('smartzone_ap_cumulativeRx24G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'cumulativeRx5G':
                GaugeMetricFamily('smartzone_ap_cumulativeRx5G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'cumulativeRx6G':
                GaugeMetricFamily('smartzone_ap_cumulativeRx6G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'cumulativeTxRx24G':
                GaugeMetricFamily('smartzone_ap_cumulativeTxRx24G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'cumulativeTxRx5G':
                GaugeMetricFamily('smartzone_ap_cumulativeTxRx5G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'cumulativeTxRx6G':
                GaugeMetricFamily('smartzone_ap_cumulativeTxRx6G', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac']),
            'isDual5gMode':
                GaugeMetricFamily('smartzone_ap_isDual5gMode', 'SmartZone AP',
                                labels=['zone_id', 'ap_name', 'ap_mac', 'isDual5gMode']),
        }

        ap_metrics = {
            'mac':
                GaugeMetricFamily('smartzone_ap_mac',
                                  'SmartZone AP mac',
                                  labels=["ap_mac", "mac"]),
            'model':
                GaugeMetricFamily('smartzone_ap_model',
                                  'SmartZone AP model',
                                  labels=["ap_mac", "model"]),
            'version':
                GaugeMetricFamily('smartzone_ap_version',
                                  'SmartZone AP version',
                                  labels=["ap_mac", "version"]),
            'description':
                GaugeMetricFamily('smartzone_ap_description',
                                  'SmartZone AP description',
                                  labels=["ap_mac", "description"]),
            'zoneId':
                GaugeMetricFamily('smartzone_ap_zoneId',
                                  'SmartZone AP zone id',
                                  labels=["ap_mac", "zoneId"]),
            'connectionState':
                GaugeMetricFamily('smartzone_ap_connectionState',
                                  'SmartZone AP connection state',
                                  labels=["ap_mac", "connectionState"]),
             'wifi6gChannel':
                 GaugeMetricFamily('smartzone_ap_wifi6gChannel',
                                   'SmartZone AP 6GHz channel number',
                                   labels=["ap_mac"]),
            'wifi50Channel':
                GaugeMetricFamily('smartzone_ap_wifi50Channel',
                                  'SmartZone AP 5GHz channel number',
                                  labels=["ap_mac"]),
            'wifi24Channel':
                GaugeMetricFamily('smartzone_ap_wifi24Channel',
                                  'SmartZone AP 2.4GHz channel number',
                                  labels=["ap_mac"]),
            'approvedTime':
                GaugeMetricFamily('smartzone_ap_approvedTime',
                                  'SmartZone AP approved time',
                                  labels=["ap_mac"]),
            'lastSeenTime':
                GaugeMetricFamily('smartzone_ap_lastSeenTime',
                                  'SmartZone AP last seen time',
                                  labels=["ap_mac"]),
            'uptime':
                GaugeMetricFamily('smartzone_ap_uptime',
                                  'SmartZone AP uptime',
                                  labels=["mac"]),
            'clientCount':
                GaugeMetricFamily('smartzone_ap_clientCount',
                                  'SmartZone AP client count',
                                  labels=["ap_mac"])
        }

        ap_summary_list = {
            'location':
                GaugeMetricFamily('smartzone_aps_location',
                                  'SmartZone AP location',
                                  labels=["ap_name", "ap_mac", "location"]),
            'configState':
                GaugeMetricFamily('smartzone_aps_configState',
                                  'SmartZone AP configState',
                                  labels=["ap_name", "ap_mac", "configState"]),
            'criticalCount':
                GaugeMetricFamily('smartzone_aps_alarms_criticalCount',
                                  'SmartZone AP criticalCount alarm',
                                  labels=["ap_name", "ap_mac"]),
            'majorCount':
                GaugeMetricFamily('smartzone_aps_alarms_majorCount',
                                  'SmartZone majorCount alarms',
                                  labels=["ap_name", "ap_mac"]),
            'minorCount':
                GaugeMetricFamily('smartzone_aps_alarms_minorCount',
                                  'SmartZone AP minorCount alarms',
                                  labels=["ap_name", "ap_mac"]),
            'warningCount':
                GaugeMetricFamily('smartzone_aps_alarms_warningCount',
                                  'SmartZone AP warningCount alarm',
                                  labels=["ap_name", "ap_mac"])
        }

        domain_metrics = {
            'domainType':
                GaugeMetricFamily('smartzone_domain_type',
                                  'SmartZone Domain name',
                                  labels=["domain_id", "domain_name", "domainType"]),
            'parentDomainId':
                GaugeMetricFamily('smartzone_domain_parentDomainId',
                                  'SmartZone Domain parent domain ID',
                                  labels=["domain_id", "domain_name", "parentDomainId"]),
            'subDomainCount':
                GaugeMetricFamily('smartzone_domain_subDomainCount',
                                  'SmartZone Domain sub domain numbers',
                                  labels=["domain_id", "domain_name"]),
            'apCount':
                GaugeMetricFamily('smartzone_domain_apCount',
                                  'SmartZone Domain total count of APs',
                                  labels=["domain_id", "domain_name"]),
            'zoneCount':
                GaugeMetricFamily('smartzone_domain_zoneCount',
                                  'SmartZone Domain count of zones',
                                  labels=["domain_id", "domain_name"])
        }

        license_metrics = {
            'description':
                GaugeMetricFamily('smartzone_license_description',
                                  'SmartZone License description',
                                  labels=["license_name", "description"]),
            'count':
                GaugeMetricFamily('smartzone_license_count',
                                  'SmartZone License count',
                                  labels=["license_name"]),
            'createTime':
                GaugeMetricFamily('smartzone_license_createTime',
                                  'SmartZone License created date',
                                  labels=["license_name", "createTime"]),
            'expireDate':
                GaugeMetricFamily('smartzone_license_expireDate',
                                  'SmartZone License expire date',
                                  labels=["license_name", "expireDate"])
        }

        wlan_list = {
            'ssid':
                GaugeMetricFamily('smartzone_wlan_ssid',
                                  'SmartZone SSID',
                                  labels=["zoneId", "name", "ssid"]),
            'clients':
                GaugeMetricFamily('smartzone_wlan_clients',
                                  'SmartZone WLAN clients',
                                  labels=["zoneId", "name"]),
            'traffic':
                GaugeMetricFamily('smartzone_wlan_traffic',
                                  'SmartZone WLAN traffic',
                                  labels=["zoneId", "name"]),
            'trafficUplink':
                GaugeMetricFamily('smartzone_wlan_traffic_uplink',
                                  'SmartZone WLAN traffic Uplink',
                                  labels=["zoneId", "name"]),
            'trafficDownlink':
                GaugeMetricFamily('smartzone_wlan_traffic_downlink',
                                  'SmartZone WLAN traffic Downlink',
                                  labels=["zoneId", "name"]),
            'vlan':
                GaugeMetricFamily('smartzone_wlan_vlan',
                                  'SmartZone WLAN vlan',
                                  labels=["zoneId", "name"]),
}

        self.get_session()

        id = 0
        # Get SmartZone controller metrics
        for c in self.get_metrics(controller_metrics, 'controller')['list']:
            id = c['id']
            for s in self._statuses:
                if s == 'uptimeInSec':
                    controller_metrics[s].add_metric([id], c.get(s))
                # Export a dummy value for string-only metrics
                else:
                    extra = c[s]
                    controller_metrics[s].add_metric([id, extra], 1)

        for m in controller_metrics.values():
            yield m

        # Get SmartZone system metric

        path = 'controller/' + id + '/statistics'
        system = self.get_metrics(system_metric, path)
        for c in system_metric:
            varList = list(system_metric[c].keys())
            for s in varList:
                # Add dummy comment (port name) for port statistic
                if c == 'port1' or c == 'port2' or c == 'control' or c == 'cluster' or c == 'management':
                    system_metric[c][s].add_metric([id, c], system[0][c].get(s))
                # For normal metric
                else:
                    system_metric[c][s].add_metric([id], system[0][c].get(s))
            for m in system_metric[c].values():
                yield m

        # Ges SmartZone system summary
        c = self.get_metrics(system_summary_metric, 'system/devicesSummary')
        for s in self._statuses:
            system_summary_metric[s].add_metric([id], c.get(s))

        for m in system_summary_metric.values():
            yield m

        # Get SmartZone inventory per zone
        # For each zone captured from the query:
        # - Grab the zone name and zone ID for labeling purposes
        # - Loop through the statuses in statuses
        # - For each status, get the value for the status in each zone and add to the metric

        for zone in self.get_metrics(zone_metrics, 'system/inventory')['list']:
            zone_name = zone['zoneName']
            zone_id = zone['zoneId']
            for s in self._statuses:
                zone_metrics[s].add_metric([zone_name, zone_id], zone.get(s))

        for m in zone_metrics.values():
            yield m


       # Get WLANs list per zone or a domain
        for wlan in self.get_metrics(wlan_list, 'query/wlan')['list']:
            wlan_name = wlan['name']
            zone_id = wlan['zoneId']
            for w in self._statuses:
                if wlan.get(w) == None:
                    wlan.update({w: 0})
                if w == 'traffic' or w == 'trafficUplink' or w == 'trafficDownlink' or w == 'clients' or w == 'vlan':
                    wlan_list[w].add_metric([zone_id, wlan_name, extra], wlan.get(w))

                # Export a dummy value for string-only metrics
                else:
                    extra = wlan[w]
                    wlan_list[w].add_metric([zone_id, wlan_name, extra], 1)

        for w in wlan_list.values():
            yield w
       # Get APs list per zone or a domain
        for ap in self.get_metrics(ap_list, 'query/ap')['list']:
            zone_id = ap['zoneId']
            ap_name = ap['deviceName']
            ap_mac = ap['apMac']
            for a in self._statuses:
                if ap.get(a) == None:
                    ap.update({a: 0})
                elif ap.get(a) == 'false':
                    ap.update({a: 0})
                elif ap.get(a) == 'true':
                    ap.update({a: 1})

                if isinstance(ap.get(a), (int, float)):
                     ap_list[a].add_metric([zone_id, ap_name, ap_mac, extra], ap.get(a))
                else:
                    extra = ap[a]
                    ap_list[a].add_metric([zone_id, ap_name, ap_mac, extra], 1)

        for a in ap_list.values():
            yield a



        # Get APs summary information
        for ap in self.get_metrics(ap_summary_list, 'aps/lineman')['list']:
            ap_name = ap['name']
            ap_mac = ap['mac']
            for s in self._statuses:
                if s == 'criticalCount' or s == 'majorCount' or s == 'minorCount' or s == 'warningCount':
                    ap_summary_list[s].add_metric([ap_name, ap_mac], ap['alarms'].get(s))
                else:
                    extra = ap[s]
                    ap_summary_list[s].add_metric([ap_name, ap_mac, extra], 1)

        for m in ap_summary_list.values():
            yield m

        # Collect domain information
        for c in self.get_metrics(domain_metrics, 'domains')['list']:
            domain_id = c['id']
            domain_name = c['name']
            for s in self._statuses:
                if s == 'domainType' or s == 'parentDomainId':
                    extra = c[s]
                    domain_metrics[s].add_metric([domain_id, domain_name, extra], 1)
                else:
                    domain_metrics[s].add_metric([domain_id, domain_name], c.get(s))

        for m in domain_metrics.values():
            yield m

        # Collect license information
        for c in self.get_metrics(license_metrics, 'licenses')['list']:
            license_name = c['name']
            for s in self._statuses:
                if s == 'count':
                    license_metrics[s].add_metric([license_name], c.get(s))
                else:
                    extra = c[s]
                    license_metrics[s].add_metric([license_name, extra], 1)

        for m in license_metrics.values():
            yield m


# Function to parse command line arguments and pass them to the collector
def parse_args():
    parser = argparse.ArgumentParser(description='Ruckus SmartZone exporter for Prometheus')

    # Use add_argument() method to specify options
    # By default argparse will treat any arguments with flags (- or --) as optional
    # Rather than make these required (considered bad form), we can create another group for required options
    required_named = parser.add_argument_group('required named arguments')
    required_named.add_argument('-u', '--user', help='SmartZone API user', required=True)
    required_named.add_argument('-p', '--password', help='SmartZone API password', required=True)
    required_named.add_argument('-t', '--target',
                                help='Target URL and port to access SmartZone, e.g. https://smartzone.example.com:8443',
                                required=True)

    # Add store_false action to store true/false values, and set a default of True
    parser.add_argument('--insecure', action='store_false', help='Allow insecure SSL connections to Smartzone')

    # Specify integer type for the listening port
    parser.add_argument('--port', type=int, default=9345,
                        help='Port on which to expose metrics and web interface (default=9345)')

    # Now that we've added the arguments, parse them and return the values as output
    return parser.parse_args()


def main():
    try:
        args = parse_args()
        port = int(args.port)
        REGISTRY.register(SmartZoneCollector(args.target, args.user, args.password, args.insecure))
        # Start HTTP server on specified port
        start_http_server(port)
        if args.insecure == False:
            print('WARNING: Connection to {} may not be secure.'.format(args.target))
        print("Polling {}. Listening on ::{}".format(args.target, port))
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(" Keyboard interrupt, exiting...")
        exit(0)


if __name__ == "__main__":
    main()