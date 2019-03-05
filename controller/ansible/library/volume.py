from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.cmnlib import Unity
from ansible.module_utils.cmnlib import Integrator

import logging
import os

logger = logging.getLogger(__name__)



def get_id_from_name(find_maplist, keyname):
    # peer should be expected as {pool_id: pool_name}
    for peer in find_maplist:
        for k, v in peer.items():
            if keyname in v:
                return k
def main():
    # logging setup
    log_directory = "./logs"
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)

    _detail_formatting = "%(asctime)s : %(name)s - %(levelname)s : %(message)s"
    logging.basicConfig(
        level=logging.DEBUG,
        format=_detail_formatting,
        filename=log_directory + "/ansible-unity.log"
    )
    logging.getLogger("modules").setLevel(level=logging.DEBUG)
    console = logging.StreamHandler()
    console_formatter = logging.Formatter("%(asctime)s : %(message)s")
    console.setFormatter(console_formatter)
    console.setLevel(logging.INFO)
    logging.getLogger("modules").addHandler(console)

    logger = logging.getLogger(__name__)
    logging.getLogger(__name__).addHandler(console)

    logger.info(">>>>>>>>>> Starting ansible-unity module: volumes")

    # Get parameters from playbook
    argument_spec = {"storage_name": dict(type="str", required=True),
                     "volume_name": dict(type="str", required=True),
                     "volume_size_gb": dict(type="int", required=True),
                     "is_thin_enabled": dict(type="bool", required=True),
                     "target_pool_name": dict(type="str", required=True),
                     "target_host": dict(type="str", required=True)
                     }

    module = AnsibleModule(argument_spec, supports_check_mode=True)

    target_storage = module.params['storage_name']
    logger.info('Operation to ' + target_storage)

    fd = Integrator()
    configuration = fd.return_device_info(target=target_storage)
    logger.info(configuration)

    ip_address = configuration['credentials'][0]['ip_address']
    username = configuration['credentials'][0]['username']
    password = configuration['credentials'][0]['password']
    serial_no = configuration['serial_number']

    volume_name = module.params["volume_name"]
    volume_size_gb = module.params["volume_size_gb"]
    is_thin_enabled = module.params["is_thin_enabled"]

    logger.info('------- Instantiate Unity to handle...')
    unity = Unity(ip_address=ip_address, username=username, password=password)

    # TODO: add method to find host_id from variables target_host
    target_host = module.params["target_host"]
    target_pool_name = module.params["target_pool_name"]

    # 1. Check S/N
    logger.info('------- Getting remote system information')
    remote_sys = unity.get_system_info()
    # --- if S/N differs from expected, exit the program
    if remote_sys['serialNumber'] != serial_no:
        logger.info(remote_sys)
        logger.error('Remote system S/N differs from expected one. Exit the module without operations.')
        module.exit_json(changed=False)
    # --- if not, proceed to playbook

    # 2. Get mapping of pool_id and pool_name
    logger.info('------- Getting mapping list between pool_id and pool_name...')
    pool_mapping_list = []
    for content in unity.https_get(urlsuffix='/api/types/pool/instances?compact=True&fields=id,name')['entries']:
        pool_mapping_list.append({content['content']['id']: content['content']['name']})
    pool_list = []
    for p in pool_mapping_list:
        for k, v in p.items():
            pool_list.append(v)

    # Check provided storage_pool_name exists or not
    if target_pool_name not in pool_list:
        logger.error('Provided storage pool name not found on remote system.')
        logger.error('Provided pool seems wrong. Check group_vars/all.yml and retry it.')
        module.exit_json(changed=False)
    # --- if correct, proceed to playbook
    # Find Pool ID from user-specified pool name
    target_pool_id = get_id_from_name(pool_mapping_list, module.params["target_pool_name"])
    logger.info('StoragePool ID in which target LUN create:  ' + target_pool_id)
    uri = '/api/instances/pool/' + target_pool_id + '?compact=True&fields=id,name,health,sizeFree,sizeTotal,sizeUsed,sizeSubscribed'
    target_pool_info = unity.https_get(urlsuffix=uri)
    logger.info('Pool information where LUN to be created.')
    logger.info(target_pool_info['content'])


    # 2. Get mapping of host_id and host_name
    logger.info('------- Getting mapping list between host_id and host_name...')
    host_mapping_list = []
    for content in unity.https_get(urlsuffix='/api/types/host/instances?compact=True&fields=id,name')['entries']:
        host_mapping_list.append({content['content']['id']: content['content']['name']})
    host_list = []
    for h in host_mapping_list:
        for k, v in h.items():
            host_list.append(v)
    # logger.info(host_list)
    # Check provided storage_pool_name exists or not
    if target_host not in host_list:
        logger.error('Provided host name not found on remote system.')
        logger.error('Provided host seems wrong. Check group_vars/all.yml and retry it.')
        module.exit_json(changed=False)
    # --- if correct, proceed to playbook
    # Find Host ID from user-specified pool name
    target_host_id = get_id_from_name(host_mapping_list, module.params["target_host"])
    logger.info('Host ID in which target LUN create:  ' + target_host_id)
    uri = '/api/instances/host/' + target_host_id + '?compact=True&fields=id,name,health,fcHostInitiators,hostLUNs,hostUUID'
    target_host_info = unity.https_get(urlsuffix=uri)
    logger.info('Host information which has LUN mappings')
    logger.info(target_host_info['content'])


    # 3. Check lun name duplication
    logger.info('------- Getting mapping list between host_id and host_name...')
    volume_mapping_list = []
    for content in unity.https_get(urlsuffix='/api/types/lun/instances?compact=True&fields=id,name')['entries']:
        volume_mapping_list.append({content['content']['id']: content['content']['name']})
    volume_list = []
    for h in volume_mapping_list:
        for k, v in h.items():
            volume_list.append(v)
    # Check provided volume_name exists or not
    if volume_name in volume_list:
        logger.error('Provided LUN name have already existed on target system. Check group_vars/all.yml and retry it.')
        # Get WWN of already existing LUN
        urisuffix = '/api/types/lun/instances?filter=name%20eq%20\"{0}\"&fields=id,name,sizeTotal,sizeUsed,sizeAllocated,isThinEnabled,pool,wwn,hostAccess'.format(volume_name)
        target_lun_info = unity.https_get(urlsuffix=urisuffix)
        target_volume_volid = target_lun_info['entries'][0]['content']['id']
        logger.info('LUN information already existing : ' + str(target_lun_info['entries'][0]['content']))
        target_volume_id = target_lun_info['entries'][0]['content']['wwn']
        volume_id = {"volume_id": target_volume_id}
        # logger.info(target_lun_info['entries'][0]['content']['sizeTotal'])

        if volume_size_gb*1024*1024*1024 > target_lun_info['entries'][0]['content']['sizeTotal']:
            logger.info(target_lun_info['entries'][0]['content']['sizeTotal'])

            # Post
            # --- if exsits the expected size, start to expand LUN
            post_data = {'name': volume_name,
                                'lunParameters': {
                                    'size': volume_size_gb * 1024 * 1024 * 1024}
                             }
            logger.info('LUN parameters to be expanded : ' + str(post_data))
            urlpattern = '/api/instances/storageResource/{0}/action/modifyLun'.format(target_volume_volid)
            logger.info(urlpattern)
            try:
                logger.info('Posting data to expand LUN.')
                unity.https_post(urlsuffix=urlpattern, data=post_data)
            except:
                logger.error('Failed to expand LUN on Unity with POST request.')
                module.fail_json(msg='Tried to expand LUN but failed to operate.')
            else:
                logger.info('Successfully expand LUN on Unity.')
                module.exit_json(changed=False, ansible_facts=volume_id)
        else:
            logger.info('Do Nothing')
            module.exit_json(changed=False, ansible_facts=volume_id)

    # --- if not exists the expected name, start to create LUN
    post_data = {'name': volume_name,
                 'lunParameters': {
                     'pool':{'id': target_pool_id},
                     'size': volume_size_gb*1024*1024*1024,
                     'isThinEnabled': is_thin_enabled,
                     'hostAccess':[{"host": {"id": target_host_id},
                                    "accessMask": 1}]
                                   }
                }
    logger.info('LUN parameters to be created : ' + str(post_data))
    try:
        logger.info('Posting data to create LUN.')
        unity.https_post(urlsuffix='/api/types/storageResource/action/createLun', data=post_data)
    except:
        logger.error('Failed to create LUN on Unity with POST request.')
        module.fail_json(msg='Tried to create LUN but failed to operate.')
    else:
        logger.info('Successfully create LUN on Unity.')
        # Get WWN of created LUN
        urisuffix = '/api/types/lun/instances?filter=name%20eq%20\"{0}\"&fields=id,name,sizeTotal,sizeUsed,sizeAllocated,isThinEnabled,pool,wwn,hostAccess'.format(volume_name)
        target_lun_info = unity.https_get(urlsuffix=urisuffix)
        logger.info('LUN information newly created : ' + str(target_lun_info['entries'][0]['content']))
        target_volume_id = 'VPD83T3:' + target_lun_info['entries'][0]['content']['wwn'].replace(':','').lower()
        # target_volume_id = 'VPD83T3:60000970000294901370533031314645'
        volume_id = {"volume_id": target_volume_id}

        # 4. exit custom module
        module.exit_json(changed=True, ansible_facts=volume_id)


if __name__ == "__main__":
    main()