import logging
import json
import yaml
import os
import requests
import pexpect
import traceback
import time

logger = logging.getLogger(__name__)


# HTTP Response handling
def convert_to_json(body):
    js = ''
    try:
        js = json.loads(body)
    except Exception as e:
        if js is None:
            pass
        else:
            logger.info('>>> Some Error occurred when converting from String to JSON.')
            logger.info('Errors : ', e.args)
    return js


# Integator class should be used after AnsibleModule class instantiated
class Integrator:
    def __init__(self):
        self.sites = ['examples',]

    def return_device_info(self, target):
        for sitename in self.sites:
            path = os.path.dirname(os.path.abspath(__name__))
            joined_path = os.path.join(path, '../ansible/group_vars/devices_' + sitename + '.yml')
            data_path = os.path.normpath(joined_path)
            with open(data_path, 'r') as uc:
                c = uc.read()
            conf = yaml.safe_load(c)

            if target.replace('#','_').lower() in conf:
                return conf[target.replace('#','_').lower()]

    def find_vplex_fe_port_by_mds(self, sitename, mds_name, vsanid):
        target_conf = self.return_device_info(target=mds_name)
        connected_vplex_port = []
        if sitename == target_conf['location']:
            connected_vplex_port = target_conf['vplex_connection']
        for vsan in connected_vplex_port:
            if vsan['vsanid'] == vsanid:
                return vsan['vplex_fe_ports']


class Unity:
    def __init__(self, ip_address, username, password):
        self.ip_address = ip_address
        self.username = username
        self.password = password

    def get_csrf_token(self):
        try:
            login_headers = {"X-EMC-REST-CLIENT": "true"}
            response = requests.Session()
            uri = 'https://' + self.ip_address + '/api/types/loginSessionInfo/instances'
            login_response = response.get(url=uri, auth=(self.username, self.password), verify=False, headers=login_headers)
            return response, login_response
        except requests.exceptions.RequestException as e:
            logger.error("Error:\n", e)
        return False

    def https_get(self, urlsuffix):
        responses = self.get_csrf_token()
        cookie = responses[0].cookies
        header_token = responses[1].headers['EMC-CSRF-TOKEN']
        headers = {"X-EMC-REST-CLIENT": "true","content-type": "application/json","EMC-CSRF-TOKEN": header_token}

        uri = 'https://' + self.ip_address + urlsuffix
        logger.info(uri)

        try:
            get_response = requests.get(url=uri, verify=False, headers=headers, cookies=cookie)
            return convert_to_json(body=get_response.text)
        except requests.exceptions.RequestException as e:
            logger.error("Error:\n",e)
        return {}

    def https_post(self, urlsuffix, data):
        responses = self.get_csrf_token()
        cookie = responses[0].cookies
        header_token = responses[1].headers['EMC-CSRF-TOKEN']
        headers = {"X-EMC-REST-CLIENT": "true","content-type": "application/json","EMC-CSRF-TOKEN": header_token}
        # logger.info(headers)

        post_data = json.dumps(data)

        uri = 'https://' + self.ip_address + urlsuffix
        logger.info(uri)

        try:
            post_response = requests.post(url=uri, verify=False, headers=headers, cookies=cookie, data=post_data)
            return convert_to_json(body=post_response.text)
        except requests.exceptions.RequestException as e:
            logger.error("Error:\n",e)
        return False

    def get_system_info(self):
        sys_info = self.https_get(urlsuffix='/api/instances/remoteSystem/RS_0?fields=id,name,serialNumber,health')
        return sys_info['content']


class VPLEX:
    def __init__(self, ip_address, username, password):
        self.ip_address = ip_address
        self.username = username
        self.password = password
        self.login_credentials = username + '@' + ip_address
        self.shell_prompt = '^.*~>'
        self.cli_prompt = '^.*:/>'
        self.model = self.set_vplex_model()

    # Common Unitilities
    def https_get(self, urlsuffix):
        url = 'https://' + str(self.ip_address) + urlsuffix
        logger.info('Connect to : ' + url)
        try:
            request_body = requests.get(url, auth=(self.username, self.password), verify=False)
        except ValueError:
            logger.error('>>> Error occurred during parsing json. VPLEX returned not a JSON value.')
            traceback.print_exc()
        except:
            logger.error('>>> URLError occurred. Please check the address or suffix you specified.')
            traceback.print_exc()
        else:
            return convert_to_json(body=request_body.text)

    def https_post(self, urlsuffix, data):
        url = 'https://' + str(self.ip_address) + urlsuffix
        logger.info('Connect to : ' + url)
        logger.info('POST Data : ' + data)
        try:
            time.sleep(3)
            request_body = requests.post(url, auth=(self.username, self.password), verify=False, data=data)
        except ValueError:
            logger.error('>>> Error occurred during parsing json. VPLEX returned not a JSON value.')
            traceback.print_exc()
        except:
            logger.error('>>> URLError occurred. Please check the address or suffix you specified.')
            traceback.print_exc()
        else:
            return convert_to_json(body=request_body.text)

    def confirm_vplex_serial_number(self, expect_serial_number):
        logger.info('Checking VPLEX S/N is same as expected or not.')
        actual_serial_number = self.https_get(urlsuffix='/vplex/clusters/cluster-1?top-level-assembly')

        if actual_serial_number['response']['context'][0]['attributes'][0]['value'] == expect_serial_number:
            return True
        else:
            return False
    
    def get_geosynchrony_version(self):
        geosync_version = self.https_post(urlsuffix='/vplex/version', data='{\"args\":\"\"}')['response']['custom-data']
        for line in geosync_version.splitlines():
            if 'Product Version' in line:
                return line.split()[2]
    
    def set_vplex_model(self):
        geosync_version = self.get_geosynchrony_version()
        if geosync_version.split('.')[0] == '6':
            model = 'VS6'
        else:
            model = 'VS2'
        return model

    def drill_down(self, object_name):
        context = self.check_vplex_context(object_name)
        if context == 'local-devices':
            data = '{\"args\":\"--device ' + object_name + '\"}'
        elif context == 'virtual-volumes':
            data = '{\"args\":\"--virtual-volume ' + object_name + '\"}'
        elif context == 'storage-views':
            data = '{\"args\":\"--storage-view ' + object_name + '\"}'
        else:
            data = ''

        uri = '/vplex/drill-down'
        response = self.https_post(urlsuffix=uri, data=data)

        return response

    def show_use_hierarchy(self, object_name):
        context = self.check_vplex_context(object_name)

        if (context == 'local-devices') or (context == 'virtual-volumes'):
            data = '{\"args\":\"--targets /clusters/cluster-1/' + context + '/' + object_name + '\"}'
        elif (context == 'storage-volumes') or (context == 'extents'):
            data = '{\"args\":\"--targets /clusters/cluster-1/storage-elements/' + context + '/' + object_name + '\"}'
        elif context == 'logical-units':
            data = '{\"args\":\"--targets /clusters/cluster-1/storage-elements/storage-arrays/*/' + context + '/' + object_name + '\"}'
        else:
            data = ''
        uri = '/vplex/show-use-hierarchy'
        response = self.https_post(urlsuffix=uri, data=data)

        return response

    # extents
    @staticmethod
    def set_extent_name(volume_name):
        return 'extent_' + volume_name + '_1'
    
    # local-devices
    @staticmethod
    def set_local_device_name(volume_name):
        return 'device_' + volume_name + '_1'

    # virtual-volumes
    @staticmethod
    def set_virtual_volume_name(volume_name):
        return 'device_' + volume_name + '_1_vol'
        
    @staticmethod
    def check_vplex_context(object_name):        
        if (object_name[:7] == 'device_') and (object_name[-6:] == '_1_vol'):
            return 'virtual-volumes'
        elif (object_name[:7] == 'device_') and (object_name[-2:] == '_1'):
            return 'local-devices'
        elif (object_name[:7] == 'extent_') and (object_name[-2:] == '_1'):
            return 'extents'
        elif object_name[:3] == 'VPD':
            return 'logical-units'
        else:
            return 'storage-volumes'

        # Exception handling
        if 'SV_' in object_name:
            return 'storage-views'
        elif '_HBA' in object_name:
            return 'initiator-ports'
        elif (object_name[:1] == 'P') and ('FC' in object_name[-4:]):
            return 'ports'
        else:
            return ''


class MDS:
    def __init__(self, ip_address, username, password):
        self.ip_address = ip_address
        self.username = username
        self.password = password
        self.login_credentials = username + '@' + ip_address
        self.await_prompt = '^.*#'
        self.config_mode_prompt = '^.*\(config\)#'
        self.device_alias_prompt = '^.*\(config-device-alias-db\)#'
        self.zone_prompt = '^.*\(config-zone\)#'
        self.zoneset_prompt = '^.*\(config-zoneset\)#'

    def send_show_command(self, cmd):
        output = pexpect.spawn('ssh ' + self.login_credentials)
        output.expect('Password:')
        output.sendline(self.password)
        output.expect(self.await_prompt)
        output.sendline('terminal length 0')
        output.expect(self.await_prompt)
        logger.debug('Logged in complete, set terminal length unlimited.')

        logger.debug('Runnnig command : ' + cmd)
        output.sendline(cmd)
        output.expect(self.await_prompt)
        if 'Invalid' in output.after:
            logger.error('Failed to run command')
            return []
        else:
            # return spawned output with removing head/tail elements
            stdout = output.after.splitlines()
            return stdout[2:len(stdout)-2]

    def send_command_config_mode(self, cmd):
        output = pexpect.spawn('ssh ' + self.login_credentials)
        output.expect('Password:')
        output.sendline(self.password)
        output.expect(self.await_prompt)
        output.sendline('terminal length 0')
        output.expect(self.await_prompt)
        logger.debug('Logged in complete, set terminal length unlimited.')

        output.sendline('configure terminal')
        # Enter configuration commands, one per line.
        output.expect(self.await_prompt)
        if 'Invalid' in output.after:
            logger.error('Failed to enter configuration mode.')
        else:
            logger.debug('Now you are in configuration mode on target system.')
            logger.debug('Execute configuration command : ' + cmd)
            output.sendline(cmd)
            output.expect(self.config_mode_prompt)
            if 'Invalid' in output.after:
                logger.error('Stdout on MDS showed as `Invalid command`. Failed to run command on configuration mode.')
                return []
            else:
                logger.debug('Successfully run command on configuration mode.')
                # return spawned output with removing head/tail elements
                stdout = output.after.splitlines()
                return stdout[2:len(stdout)-2]

    def confirm_mds_serial_number(self, expect_serial_number):
        logger.info('Checking MDS S/N is same as expected or not.')
        actual_serial_number = self.send_show_command(cmd='show license host-id')[0]

        if expect_serial_number in actual_serial_number:
            return True
        else:
            return False

    def set_target_zone_names(self, server_pwwn, storage_pwwn_1, storage_pwwn_2):
        def search_alias_by_pwwn(from_db, pwwn):
            line = ''
            for alias in from_db:
                if pwwn in alias:
                    line = alias
                    break
                else:
                    pass
                    # logger.debug('Not found.')
            if line != '':
                return line.split()[2]
            else:
                return ''

        device_aliases = self.send_show_command(cmd='show device-alias database')[:-2]
        server_alias = search_alias_by_pwwn(from_db=device_aliases, pwwn=server_pwwn)
        if server_alias == '':
            return []
        else:
            primary_vplex_port_alias = search_alias_by_pwwn(from_db=device_aliases, pwwn=storage_pwwn_1)
            if primary_vplex_port_alias == '':
                return []
            zone_name_primary = server_alias + '_' + primary_vplex_port_alias
            # logger.debug('--- Primary zone name : ' + zone_name_primary)
            # logger.debug('First zone member : ' + server_pwwn)
            # logger.debug('Second zone member : ' + storage_pwwn_1)
            secondary_vplex_port_alias = search_alias_by_pwwn(from_db=device_aliases, pwwn=storage_pwwn_2)
            if secondary_vplex_port_alias == '':
                return []
            zone_name_secondary = server_alias + '_' + secondary_vplex_port_alias
            # logger.debug('--- Secondary zone name : ' + zone_name_secondary)
            # logger.debug('First zone member : ' + server_pwwn)
            # logger.debug('Second zone member : ' + storage_pwwn_2)
            return [zone_name_primary, zone_name_secondary]

    def get_zones_from_zoneset(self, primary_vsan_id, is_active_zone):
        if is_active_zone:
            query_cmd_zones = 'show zoneset brief active vsan ' + primary_vsan_id + ' |grep zone |grep -v zoneset'
        else:
            query_cmd_zones = 'show zoneset brief vsan ' + primary_vsan_id + ' |grep zone |grep -v zoneset'

        stdout_zones = self.send_show_command(cmd=query_cmd_zones)
        # Return inverted list of zones, since acceralate searching time.
        return stdout_zones[::-1]

    @staticmethod
    def search_zone(zonelist, zonename):
        for zone in zonelist:
            if zonename in zone:
                return True
            else:
                pass
        return False