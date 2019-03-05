import subprocess
import yaml
import logging
import os

logger = logging.getLogger('django')
path_prefix = os.getcwd() + '/'


def get_device_mismatch_check(data):
    connect_device_filename = path_prefix + 'controller/ansible/group_vars/devices_examples.yml'
    with open(connect_device_filename, 'r') as cdf:
        c = cdf.read()
    configs = yaml.safe_load(c)

    input_vplex = data['vplex_name'].lower()
    input_mds1 = data['primary_mds_switch'].lower()
    input_mds2 = data['secondary_mds_switch'].lower()

    # TODO: added error handling case if not found.
    connect_device = configs[input_vplex.replace('#','_')]['connect_devices']
    is_found_mds1 = False
    is_found_mds2 = False
    if input_mds1.replace('#', '_') in connect_device:
        is_found_mds1 = True
    else:
        pass
    if input_mds2.replace('#', '_') in connect_device:
        is_found_mds2 = True
    else:
        pass
    return is_found_mds1, is_found_mds2


def kick_command_from_django(cmd):
    ansible_result = ''
    try:
        ansible_result = subprocess.run(cmd, shell=True, check=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True)
    except subprocess.CalledProcessError:
        logger.error('Failed to run command [ ' + cmd + ' ]')
        return 1, '', 'Failed to kick command from Django... \nLogs of ansible modules are in residency/ansible/logs/*.log'
    except:
        return 1, '', 'Module Failed...'
    else:
        return ansible_result.returncode, ansible_result.stdout, ansible_result.stderr


def query_wwns_with_hostname(servername):
    # MongoDB setup
    from pymongo import MongoClient
    mongo_ip = 'localhost'
    mongo_port = 27017
    mc = MongoClient(mongo_ip, mongo_port)
    mdb = mc['mind_django']
    mongo_rt = mdb['servers'].find({"hostname": servername})
    for rt in mongo_rt:
        if rt:
            return rt['wwns']
        else:
            return []


def query_wwnn_by_wwpn(wwpn):
    # MongoDB setup
    from pymongo import MongoClient
    mongo_ip = 'localhost'
    mongo_port = 27017
    mc = MongoClient(mongo_ip, mongo_port)
    mdb = mc['mind_django']
    mongo_rt = mdb['mds_interfaces'].find({"wwpn": wwpn})
    for rt in mongo_rt:
        print(rt)


def modify_ansible_conf_file(user_input):
    # get user input
    logger.info('Values to be overwritten in default residency/ansible/group_vars/all.yml')
    logger.info('   server_name :' + str(user_input['server_name']))
    # logger.info('   wwpn_1 : ' + str(user_input['wwpn_1']))
    # logger.info('   wwpn_2 :' + str(user_input['wwpn_2']))
    logger.info('   backend_array :' + str(user_input['backend_array_name']))
    logger.info('   storage_pool : ' + str(user_input['backend_storagepool_name']))
    logger.info('   vplex_name :' + str(user_input['vplex_name']))
    logger.info('   primary_switch :' + str(user_input['primary_mds_switch']))
    logger.info('   secondary_switch :' + str(user_input['secondary_mds_switch']))
    logger.info('   lun_name : ' + str(user_input['lun_name_on_backend']))
    logger.info('   lun_size : ' + str(user_input['lun_size']))
    logger.info('   hlu : ' + str(user_input['hlu_on_vplex']))
    # logger.info('   message : ' + str(user_input['message']))

    # open files to read
    rf = open(path_prefix + 'controller/ansible/group_vars/all.yml', 'r+')
    data = yaml.load(rf)
    rf.close()
    logger.info('Configured parameters for ansible-playbook BEFORE making modifications.')
    logger.info(data)

    if user_input['wwpn_1'] == '' or user_input['wwpn_2'] == '':
        logger.warning('--->>> User omitted optional parameters, WWPN_1 and WWPN_2. Starting to search them from MongoDB...')
        wwns = query_wwns_with_hostname(servername=user_input['server_name'])
        if wwns:
            logger.info('Found WWPNs with key [ {0} ] of servername: [ {1} ]'.format(str(user_input['server_name']), str(wwns)))
            data['server']['hbas']['primary']['pwwn'] = wwns['wwpns'][0]
            data['server']['hbas']['secondary']['pwwn'] = wwns['wwpns'][1]
            data['server']['hbas']['primary']['nwwn'] = wwns['wwnns'][0]
            data['server']['hbas']['secondary']['nwwn'] = wwns['wwnns'][1]
        else:
            logger.warning('WWPNs not found in MongoDB.')
            #TODO: Case if user expect correct servername with wrong ones, handle the case
    else:
        data['server']['hbas']['primary']['pwwn'] = str(user_input['wwpn_1'])
        data['server']['hbas']['secondary']['pwwn'] = str(user_input['wwpn_2'])
        data['server']['hbas']['primary']['nwwn'] = query_wwnn_by_wwpn(wwpn=str(user_input['wwpn_1']))
        data['server']['hbas']['secondary']['nwwn'] = query_wwnn_by_wwpn(wwpn=str(user_input['wwpn_2']))

    # modifiy configuration data as Python variables
    data['server']['hostname'] = str(user_input['server_name'])
    data['backend_storage_name'] = str(user_input['backend_array_name'])
    data['volume']['storage_pool'] = str(user_input['backend_storagepool_name'])
    data['volume']['mapping_host'] = str(user_input['vplex_name'])
    data['switches']['primary']['switch_name'] = str(user_input['primary_mds_switch'])
    data['switches']['secondary']['switch_name'] = str(user_input['secondary_mds_switch'])
    data['volume']['name'] = str(user_input['lun_name_on_backend'])
    data['volume']['size'] = str(user_input['lun_size'])
    data['volume']['hlu'] = str(user_input['hlu_on_vplex'])
    # Required==False lables
    for key in user_input.keys():
        if 'is_thin' in key:
            data['volume']['is_thin'] = str(user_input['thin_volume_or_not'])

    # overwrite ansible configs with user input values
    wf = open(path_prefix + 'controller/ansible/group_vars/all.yml', 'w')
    yaml.dump(data, wf)
    wf.close()

    logger.info('controller/group_vars/all.yml AFTER replacing with user input values')
    logger.info(data)

    return data


def parse_confirm_data(modified_data):
    server_info = []
    storage_info = []
    switch_info = []

    # Generate rendered data for servers
    server_info.append('>>> Servers to be configured: ')
    server_info.append('\tserver name: ' + modified_data['server']['hostname'])
    server_info.append('\tserver pwwn 1: ' + modified_data['server']['hbas']['primary']['pwwn'])
    server_info.append('\tserver pwwn 2: ' + modified_data['server']['hbas']['secondary']['pwwn'])
    # Generate rendered data for volumes
    storage_info.append('>>> Volumes to be provisioned: ')
    storage_info.append('\tvolume name: ' + modified_data['volume']['name'] + ' (isThin: ' + str(modified_data['volume']['is_thin']) + ' )')
    storage_info.append('\tfrom pool: ' + modified_data['volume']['storage_pool'])
    storage_info.append('\thlu: ' + modified_data['volume']['hlu'])
    # Generate rendered data for switches
    switch_info.append('>>> Switches to be configured: ')
    switch_info.append('\tPrimary Switch: ' + modified_data['switches']['primary']['switch_name'])
    switch_info.append('\tSecondary Switch: ' + modified_data['switches']['secondary']['switch_name'])

    return server_info, storage_info, switch_info