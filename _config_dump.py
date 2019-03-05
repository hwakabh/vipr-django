import json
import requests
import yaml
import os
import ast
import logging
import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(InsecureRequestWarning)
from pymongo import MongoClient
from storops import VNXSystem
from storops import UnitySystem
from storops import exception
import pexpect

logger = logging.getLogger('django')

#mongo_url = 'mongodb://10.118.37.180:27017/'
mongo_ip = 'localhost'
mongo_port = 27017
mongo_dbname = 'vipr_django'

# Instantiate Mongo client and get database instance
mc = MongoClient(mongo_ip, mongo_port)
# mc = MongoClient(mongo_url)
mdb = mc[mongo_dbname]
# Get collection list(returned as dictionary)
mcollections = mdb.collection_names(include_system_collections=False)
if mcollections:
    print('>>> Current list of collections on databse : ')
    print(mcollections)
    print('')

    # Remove current configuration
    print('>>> Truncate all collections for refreshing data: ')
    for collection in mcollections:
        print('--->>> Deleting collection ' + collection + ' ....')
        mdb[collection].drop()
    print('')
else:
    print('>>> Currently no collection/document on MongoDB.')


def send_show_command(ipaddr, username, password, cmd):
    await_prompt = '^.*#'
    output = pexpect.spawn('ssh {0}@{1}'.format(username, ipaddr))
    output.expect('Password:')
    output.sendline(password)
    output.expect(await_prompt)
    output.sendline('terminal length 0')
    output.expect(await_prompt)
    print('Logged in complete, set terminal length unlimited.')

    print('Runnnig command : ' + cmd)
    output.sendline(cmd)
    output.expect(await_prompt)
    if 'Invalid' in str(output.after):
        logger.error('Failed to run command')
        return []
    else:
        # return spawned output with removing head/tail elements
        stdout = output.after.splitlines()
        return stdout[2:len(stdout)-2]


def get_mds_config(target_mdses):
    for mds in target_mdses:
        mds_ip = mds['credentials'][0]['ip_address']
        mds_username = mds['credentials'][0]['username']
        mds_password = mds['credentials'][0]['password']
        print('>>> Start to gather configs on MDS ... {0}'.format(mds['name']))
        # Getting flogi mapping (interface number <---> end-device WWPN)
        zone_lists = send_show_command(mds_ip, mds_username, mds_password, cmd='show flogi database')
        for line in zone_lists:
            strline = str(line)[1:].replace('\'','').split()
            # print(strline)
            if len(strline) == 5:
                doc = {
                    'fcint': strline[0],
                    'wwpn': strline[3],
                    'wwnn': strline[4]
                }
                # interface_info = {strline[0] : [strline[3],strline[4]]}
                print('loading config to MongoDB documents : ' + strline[0])
                mdb['mds_interfaces'].insert_one(doc)
        print('')


def get_unity_config(target_unities):
    for unity in target_unities:
        unity_ip = unity['credentials'][0]['ip_address']
        unity_username = unity['credentials'][0]['username']
        unity_password = unity['credentials'][0]['password']
        print('>>> Start to gather configs on VNX ...')
        unity = UnitySystem(unity_ip, unity_username, unity_password)

        print('--->>> Unity System')
        unity_system = json.loads(str(unity))['UnitySystem']
        print('loading config to MongoDB documents : ' + unity_system['name'])
        mdb['backend_arrays'].insert_one(unity_system)
        print('')

        print('--->>> StoragePools on Unity')
        unity_pools = json.loads(str(unity.get_pool()))['UnityPoolList']
        for pool in unity_pools:
            # Add label to determine which Unity has its pool
            pool['UnityPool']['unity_label'] = unity_system['serial_number']
            print('loading config to MongoDB documents : ' + pool['UnityPool']['name'])
            mdb['storage_pools'].insert_one(pool)
        print('')

        print('--->>> LUNs on Unity')
        lun_list = json.loads(str(unity.get_lun()))['UnityLunList']
        for lun in lun_list:
            # Add label to determine which Unity has its lun
            lun['UnityLun']['unity_label'] = unity_system['serial_number']
            print('loading config to MongoDB documents : ' + lun['UnityLun']['name'])
            mdb['luns'].insert_one(lun)
        print('')

        print('--->>> Hosts on Unity')
        hosts = json.loads(str(unity.get_host()))['UnityHostList']
        for host in hosts:
            # Add label to determine which Unity has its host
            host['UnityHost']['unity_label'] = unity_system['serial_number']
            print('loading config to MongoDB documents : ' + host['UnityHost']['name'])
            mdb['hosts'].insert_one(host)

        print('--->>> SP Ports')
        sp_ports = json.loads(str(unity.get_fc_port()))['UnityFcPortList']
        for sp_port in sp_ports:
            sp_port['UnityFcPort']['unity_label'] = unity_system['serial_number']
            print('loading config to MongoDB documents : ' + sp_port['UnityFcPort']['name'])
            mdb['spports'].insert_one(sp_port)

        print('>>> All the configurations dumpped : ' + unity_system['name'])


def get_vnx_config(target_vnxs):
    for vnx in target_vnxs:
        vnx_ip = vnx['credentials'][0]['ip_address']
        vnx_username = vnx['credentials'][0]['username']
        vnx_password = vnx['credentials'][0]['password'] 
        # store array general information to MongoDB
        print('>>> Start to gather configs on VNX ...')
        vnx = VNXSystem(vnx_ip, vnx_username, vnx_password)

        print('--->>> VNX System')
        vnx_system = json.loads(str(vnx))['VNXSystem']
        print('loading config to MongoDB documents : ' + vnx_system['name'])
        mdb['backend_arrays'].insert_one(vnx_system)
        print('')

        print('--->>> StoragePools on VNX')
        vnx_pools = json.loads(str(vnx.get_pool()))['VNXPoolList']
        for pool in vnx_pools:
            # Add label to determine which VNX has its pool
            pool['VNXPool']['vnx_label'] = vnx_system['serial']
            print('loading config to MongoDB documents : ' + pool['VNXPool']['name'])
            mdb['storage_pools'].insert_one(pool)

            print('--->>> LUNs on Pool :' + pool['VNXPool']['name'])
            pool_lun_list = pool['VNXPool']['luns']
            for alu in pool_lun_list:
                lun = json.loads(str(vnx.get_lun(lun_id=alu)))
                # Add label to determine which VNX has its pool
                lun['VNXLun']['vnx_label'] = vnx_system['serial']
                lun['VNXLun']['storage_pool_name'] = pool['VNXPool']['name']
                lun['VNXLun']['storage_pool_id'] = pool['VNXPool']['pool_id']
                print('loading config to MongoDB documents : ' + lun['VNXLun']['name'])
                mdb['luns'].insert_one(lun)
        print('')

        print('--->>> Hosts')
        hosts = json.loads(str(vnx.get_host()))['VNXHostList']
        for host in hosts:
            # Add label to determine which VNX has its host
            host['VNXHost']['vnx_label'] = vnx_system['serial']
            print('loading config to MongoDB documents : ' + host['VNXHost']['name'])
            mdb['hosts'].insert_one(host)
        print('')

        print('--->>> StorageGroups')
        storage_groups = json.loads(str(vnx.get_sg()))['VNXStorageGroupList']
        for sg in storage_groups:
            # Add label to determine which VNX has its host
            sg['VNXStorageGroup']['vnx_label'] = vnx_system['serial']
            print('loading config to MongoDB documents : ' + sg['VNXStorageGroup']['name'])
            mdb['storagegroups'].insert_one(sg)
        print('')

        print('--->>> SP Ports')
        sp_ports = json.loads(str(vnx.get_sp_port()))['VNXSPPortList']
        for sp_port in sp_ports:
            # add label to determine which VNX has its oprts
            sp_port['VNXSPPort']['vnx_label'] = vnx_system['serial']
            print('loading config to MongoDB documents : ' + sp_port['VNXSPPort']['sp'])
            mdb['spports'].insert_one(sp_port)
        print('')

        print('>>> All the configurations dumpped : ' + vnx_system['name'])


def get_vplex_config(target_vplexs):
    for vplex in target_vplexs:
        vplex_ip = vplex['credentials'][0]['ip_address']
        vplex_username = vplex['credentials'][0]['username']
        vplex_password = vplex['credentials'][0]['password']

        # collection name, urisuffix, index of name in GET response
        collection_list = [
            ('logical_volumes', '/clusters/cluster-1/storage-elements/storage-arrays/*/logical-units/', 5),
            ('storage_arrays', '/clusters/cluster-1/storage-elements/storage-arrays/', 4),
            ('storage_volumes', '/clusters/cluster-1/storage-elements/storage-volumes/', 12),
            ('extents', '/clusters/cluster-1/storage-elements/extents/', 11),
            ('local_devices', '/clusters/cluster-1/devices/', 10),
            ('virtual_volumes', '/clusters/cluster-1/virtual-volumes/', 12),
            ('initiator_ports', '/clusters/cluster-1/exports/initiator-ports/', 0),
            ('ports', '/clusters/cluster-1/exports/ports/', 6),
            ('storage_views', '/clusters/cluster-1/exports/storage-views/', 3),
            ('system_volumes', '/clusters/cluster-1/system-volumes/*/components/', 11),
            ('directors', '/engines/*/directors/', 18),
        ]

        print('>>> Start to gather configs on VPLEX ...' + vplex['name'])
        urlprefix = 'https://{0}/vplex'.format(vplex_ip)

        for obj in collection_list:
            print('--->>> Getting config of ' + obj[0] + ' ...')
            url = urlprefix + obj[1] + '*'
            print('REST-API Endpoint: ' + url)
            get_res = requests.get(url, auth=(vplex_username, vplex_password), verify=False)
            json_data = json.loads(get_res.text)['response']['context']
            for d in json_data:
                print('loading config to MongoDB collection ' + obj[0]+' : ' + d['attributes'][obj[2]]['value'])
                mdb[obj[0]].insert_one(d)
            print('')

        print('>>> Retrieving use-hierarchy of virtual-volumes to ...' + vplex['name'])
        url = urlprefix + '/show-use-hierarchy'
        data = '{\"args\":\"--targets /clusters/cluster-1/virtual-volumes/*' + '\"}'
        print('REST-API Endpoint: ' + url)
        print('Request Data to post: ' + str(data))
        post_res = requests.post(url, auth=(vplex_username, vplex_password), data=data, verify=False)
        try:
            hierarchies = json.loads(post_res.text)['response']['custom-data'].split('\n\n')
        except:
            logger.error('Failed to collect hierarchy config, seems to be taken too much time to get API response.')
        else:
            for h in hierarchies:
                # Replace raw string to handle as dictonary
                docstr = repr(h).replace(r'\x1b[0m', '').replace(r'\x1b[1;32m', '').replace(r'\x1b[33m','').replace(r'\x1b[1m','"').replace(r'\n','",').replace(': ', '": "')
                docdict = docstr.replace("\'\"", "{\"").replace("\'", "\"}").replace(' ','')
                if docdict[-3:] == ',\"}':
                    docdict = docdict[:-3]
                    docdict += '}'
                if docdict[:3] == '{\",':
                    docdict = '{' + docdict[3:]
                # Case if virtual-volumes are on data-migration status
                if docdict.count('local-device') != 1:
                    print('Virtual-volume has multiple local-devices. Skipped storing data to mongoDB.')
                    pass
                else:
                    if docdict.count('storage-view') >= 2:
                        print('Virtual-voume has been associated multiple storage-views. Skipping data to mongoDB.')
                        pass
                    else:
                        print('loading config to MongoDB collection ...')
                        mdb['vv_use_hierarchy'].insert_one(ast.literal_eval(docdict))

        print('>>> All the configurations dumpped : ' + vplex['name'])


def get_host_config():
    print('--->>> Start gathering masking info on VPLEX ...')
    storage_views = mdb['storage_views'].find()
    for sv in storage_views:
        host_data = {}
        print('--->>> Getting WWPN info for server [ {0} ] ...'.format(sv['attributes'][3]['value']))
        host_data['hostname'] = sv['attributes'][3]['value']
        wwpns = []
        wwnns = []
        for i in sv['attributes'][2]['value']:
            wwn = mdb['initiator_ports'].find({"attributes.0.value": i})
            for w in wwn:
                # Getting WWPN of server
                wwpn_bf = w['attributes'][2]['value'].replace('0x','') 
                pli = [(i + j) for (i, j) in zip(wwpn_bf[::2], wwpn_bf[1::2])]
                wwpn = ':'.join(pli)
                wwpns.append(wwpn)

                # Getting WWNN of server
                wwnn_bf = w['attributes'][1]['value'].replace('0x','')
                nli = [(i + j) for (i, j) in zip(wwnn_bf[::2], wwnn_bf[1::2])]
                wwnn = ':'.join(nli)
                wwnns.append(wwnn)

        host_data['wwns'] = {'wwpns': wwpns, 'wwnns': wwnns}
        print('Inserting data of server [ {0} ] ...'.format(sv['attributes'][3]['value']))
        mdb['servers'].insert_one(host_data)


if __name__ == '__main__':
    target_vnxs = []
    target_unities = []
    target_vplexs = []
    target_mdses = []
    sites = ['examples',]

    for sitename in sites:
        # Load YAML to determine target device
        path = os.path.dirname(os.path.abspath(__name__))
        joined_path = os.path.join(path, 'controller/ansible/group_vars/devices_' + sitename + '.yml')
        data_path = os.path.normpath(joined_path)
        with open(data_path, 'r') as uc:
            c = uc.read()
        conf = yaml.safe_load(c)

        for k, v in conf.items():
            if 'vnx' in k:
                target_vnxs.append(v)
            elif 'vplex' in k:
                target_vplexs.append(v)
            elif 'unity' in k:
                target_unities.append(v)
            elif 'mds' in k:
                target_mdses.append(v)

    print('===>>>>>> Start to dumping storage configurations ...')
    get_vplex_config(target_vplexs)
    print('')
    print('')
    get_unity_config(target_unities)
    print('')
    print('')
    get_mds_config(target_mdses)
    print('')
    print('')
    # get_vnx_config(target_vnxs)
    # print('')
    print('===>>>>>> All the storage configurations dumpped.')
    print('')
    print('')
    print('===>>>>>> Start to dumping server configurations ...')
    print('')
    get_host_config()
    print('')
    print('===>>>>>> All the server configurations dumpped.')
