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

        # Define metrics for client vlan membership (for WLANs with dynamic vlan assignment)

        vlan_totals_metric = GaugeMetricFamily(
            'smartzone_clients_per_vlan',
            'Total number of clients on each VLAN',
            labels=["zone_id", "vlan_id"]
            )
        vlan_ssid_metric = GaugeMetricFamily(
            'smartzone_clients_per_vlan_ssid',
            'Total number of clients on each VLAN per SSID',
            labels=["zone_id", "vlan_id", "ssid"]
        )

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
            'apGroupId':
                GaugeMetricFamily('smartzone_aps_list_ap_groupId',
                                  'SmartZone APs list ap groupId',
                                  labels=["zone_id", "ap_mame", "ap_mac", "groupId"]),
            'serial':
                GaugeMetricFamily('smartzone_aps_list_ap_serial',
                                  'SmartZone APs list ap serial number',
                                  labels=["zone_id", "ap_mame", "ap_mac", "serial"])
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
                                  labels=["ap_mame", "ap_mac", "location"]),
            'configState':
                GaugeMetricFamily('smartzone_aps_configState',
                                  'SmartZone AP configState',
                                  labels=["ap_mame", "ap_mac", "configState"]),
            'criticalCount':
                GaugeMetricFamily('smartzone_aps_alarms_criticalCount',
                                  'SmartZone AP criticalCount alarm',
                                  labels=["ap_mame", "ap_mac"]),
            'majorCount':
                GaugeMetricFamily('smartzone_aps_alarms_majorCount',
                                  'SmartZone majorCount alarms',
                                  labels=["ap_mame", "ap_mac"]),
            'minorCount':
                GaugeMetricFamily('smartzone_aps_alarms_minorCount',
                                  'SmartZone AP minorCount alarms',
                                  labels=["ap_mame", "ap_mac"]),
            'warningCount':
                GaugeMetricFamily('smartzone_aps_alarms_warningCount',
                                  'SmartZone AP warningCount alarm',
                                  labels=["ap_mame", "ap_mac"])
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

        # Get APs list per zone or a domain
        # For each APs captured from the query:
        # - Grab the zone ID for labeling purposes
        # - For each APs, get mac, zoneID, apGroupIdm, name, lanPortSize

        ap_glob_mac = []
        for ap in self.get_metrics(ap_list, 'aps')['list']:
            zone_id = ap['zoneId']
            ap_mame = ap['name']
            ap_mac = ap['mac']
            ap_glob_mac.append(ap_mac)
            for s in self._statuses:
                # Export a dummy value for string-only metrics
                extra = ap[s]
                ap_list[s].add_metric([zone_id, ap_mame, ap_mac, extra], 1)




        for m in ap_list.values():
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

        # Get client list and calculate VLAN client count
        import collections
        clients = self.get_metrics({}, 'query/client')['list']
        vlan_totals = collections.Counter()
        vlan_ssid_totals = collections.Counter()
        for client in clients:
            vlan = client.get('vlan') or client.get('accessVlan')
            ssid = client.get('ssid')
            zone_id = client.get('zoneId')
            if vlan is None or zone_id is None:
                continue
            vlan = str(vlan)
            zone_id = str(zone_id)
            vlan_totals[(zone_id, vlan)] += 1
            if ssid:
                vlan_ssid_totals[(zone_id, vlan, ssid)] += 1
        for (zone_id, vlan_id), total in vlan_totals.items():
            vlan_totals_metric.add_metric([zone_id, vlan_id], total)
        for (zone_id, vlan_id, ssid), count in vlan_ssid_totals.items():
            vlan_ssid_metric.add_metric([zone_id, vlan_id, ssid], count)
        yield vlan_totals_metric
        yield vlan_ssid_metric

        for w in wlan_list.values():
            yield w



        num_worker_threads = 10

        def source():
            return ap_glob_mac

        def worker():
            while True:
                item = q.get()
                if item is None:
                    break
                path = 'aps/' + item + '/operational/summary'
                r.put(self.get_metrics(ap_metrics, path))
                q.task_done()

        # Queue for threads
        q = queue.Queue()

        # Queue for result from api
        r = queue.Queue()

        threads = []

        for i in range(num_worker_threads):
            t = threading.Thread(target=worker)
            t.start()
            threads.append(t)

        for item in source():
            q.put(item)

        # block until all tasks are done
        q.join()

        # stop workers
        for i in range(num_worker_threads):
            q.put(None)

        for t in threads:
            t.join()

        ap_mac = 0
        for i in range(r.qsize()):
            ap_detail = r.get(block=True, timeout=None)
            for d in list(ap_metrics.keys()):
                if (d == "description") & (ap_detail.get("description") == None):
                    ap_detail.update({"description": "None"})
                elif ap_detail.get(d) == None:
                    ap_detail.update({d: 0})
                if d == 'mac':
                    ap_mac = ap_detail[d]
                if d == 'description' or d == 'version' or d == 'model' or d == 'zoneId' or d == 'mac' or d == 'connectionState':
                    extra = ap_detail[d]
                    ap_metrics[d].add_metric([ap_mac, extra], 1)
                else:
                    ap_metrics[d].add_metric([ap_mac], ap_detail.get(d))

        for m in ap_metrics.values():
            yield m

        # Get APs summary information
        for ap in self.get_metrics(ap_summary_list, 'aps/lineman')['list']:
            ap_mame = ap['name']
            ap_mac = ap['mac']
            for s in self._statuses:
                if s == 'criticalCount' or s == 'majorCount' or s == 'minorCount' or s == 'warningCount':
                    ap_summary_list[s].add_metric([ap_mame, ap_mac], ap['alarms'].get(s))
                else:
                    extra = ap[s]
                    ap_summary_list[s].add_metric([ap_mame, ap_mac, extra], 1)

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
