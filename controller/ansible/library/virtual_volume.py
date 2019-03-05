from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.cmnlib import VPLEX
from ansible.module_utils.cmnlib import Integrator

import logging
import os

logger = logging.getLogger(__name__)


def get_virtual_volume_info(vplex, name, is_all):
    if is_all:
        uri = '/vplex/clusters/cluster-1/virtual-volumes/'
    else:
        virtual_volume_name = vplex.set_virtual_volume_name(volume_name=name)
        uri = '/vplex/clusters/cluster-1/virtual-volumes/' + virtual_volume_name
    response = vplex.https_get(urlsuffix=uri)
    logger.info(response)
    return response


def create_virtual_volume(vplex, volume_name):
    local_device_name = vplex.set_local_device_name(volume_name=volume_name)
    uri = '/vplex/virtual-volume+create'
    # -d '{"args":"--device device_claim_by_ansible_1"}'
    data = '{\"args\":\"--device ' + local_device_name + '\"}'
    response = vplex.https_post(urlsuffix=uri, data=data)
    logger.info(response)
    return response

def expand_virtual_volume(vplex, volume_name):
    virtual_volume_name = vplex.set_virtual_volume_name(volume_name=volume_name)
    uri = '/vplex/virtual-volume+expand'
    # -d '{"args":"--device device_claim_by_ansible_1"}'
    data = '{\"args\":\"-v ' + virtual_volume_name + ' -f''\"}'
    response = vplex.https_post(urlsuffix=uri, data=data)
    logger.info(response)
    return response


def main():
    log_directory = "./logs"
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)

    _detail_formatting = "%(asctime)s : %(name)s - %(levelname)s : %(message)s"
    logging.basicConfig(
        level=logging.DEBUG,
        format=_detail_formatting,
        filename=log_directory + "/ansible-vplex.log"
    )
    logging.getLogger("modules").setLevel(level=logging.DEBUG)
    console = logging.StreamHandler()
    console_formatter = logging.Formatter("%(asctime)s : %(message)s")
    console.setFormatter(console_formatter)
    console.setLevel(logging.INFO)
    logging.getLogger("modules").addHandler(console)

    logger = logging.getLogger(__name__)
    logging.getLogger(__name__).addHandler(console)

    logger.info(">>>>>>>>>> Starting ansible-vplex module: virtual-volumes")

    # Get parameters from playbook
    argument_spec = {"target_vplex_name": dict(type="str", required=True),
                     "volume_name": dict(type="str", required=True)}

    module = AnsibleModule(argument_spec, supports_check_mode=True)

    target_vplex_name = module.params['target_vplex_name']
    logger.info('Operation to ' + target_vplex_name)

    fd = Integrator()
    configuration = fd.return_device_info(target=target_vplex_name)
    logger.info(configuration)

    ip_address = configuration['credentials'][0]['ip_address']
    username = configuration['credentials'][0]['username']
    password = configuration['credentials'][0]['password']
    serial_number = configuration['serial_number']

    volume_name = module.params["volume_name"]

    logger.info('------- Instantiate VPLEX to handle...')
    vplex = VPLEX(ip_address=ip_address, username=username, password=password)

    # 1. Check VPLEX S/N
    # --- if S/N differs from expected, exit the program
    if not vplex.confirm_vplex_serial_number(expect_serial_number=serial_number):
        logger.error('Target system S/N and expected ones are different. Exit the module wihtout any operations.')
        module.exit_json(changed=False)
    # --- if same as expected, proceed to play


    # Confirm that virtual-volume to create does not exist
    logger.info('------- Getting current virtual-volumes information...')
    virtual_volumes_list_all = get_virtual_volume_info(vplex=vplex, name=volume_name, is_all=True)
    logger.info(virtual_volumes_list_all)







    virtual_volumes = []
    for virtual_volume in virtual_volumes_list_all['response']['context'][0]['children']:
        virtual_volumes.append(virtual_volume['name'])

    target_virtual_volume_name = vplex.set_virtual_volume_name(volume_name=volume_name)
    if target_virtual_volume_name in virtual_volumes:
        logger.error('Name duplication occured. Target virtual-volume name [ ' + target_virtual_volume_name + ' ] has already configured on VPLEX.')
        logger.error('Exit the module without any operations.')
        # module.exit_json(changed=False)

        logger.info('kokomadeitteru?')
        # uri2 = '/vplex/clusters/cluster-1/virtual-volumes/device_ansible_RRR_1_1_vol/'
        # uri2 = '/vplex/clusters/cluster-1/virtual-volumes/\"{0}\"'['response']['context']['attributes'].format(volume_name)
        # uri2 = '/vplex/clusters/cluster-1/virtual-volumes?filter=name%20eq%20\"{0}\"'.format(volume_name)
        uri2 = '/vplex/clusters/cluster-1/virtual-volumes/' + target_virtual_volume_name
        test = vplex.https_get(urlsuffix=uri2)
        # logger.info(test)
        expandable_list = test['response']['context'][0]['attributes'][6]['value']
        logger.info(expandable_list)
        logger.info('kokomadeitteru??')


        if expandable_list == '0B' :
            logger.info('kokomadeitteru???????')
            logger.error('Do Not Expand')
            module.exit_json(changed=False)
        else:
            logger.info('------- Expand virtual-volume')
            try:
                expand_virtual_volume(vplex=vplex, volume_name=volume_name)
                logger.info('------- Get virtual-volume information by name')
                get_virtual_volume_info(vplex=vplex, name=volume_name, is_all=False)
            except:
                logger.error('Failed to expand virtual-volume')
                module.fail_json(msg='Failed to expand virtual-volume')
            else:
                logger.info('Successfully expand virtual-volume.')
                logger.info('------- Drill-down virtual-volume expanded')
                logger.debug(vplex.drill_down(object_name=target_virtual_volume_name))
                logger.info('------- Check assignment from virtual-volume side')
                logger.debug(vplex.show_use_hierarchy(object_name=target_virtual_volume_name))
                module.exit_json(changed=True)

    else:
        logger.info('------- Create virtual-volume from local-device')
        logger.info('Virtual-volume name to be created : ' + target_virtual_volume_name)
        logger.info('Local-device to be converted to virtual-volume : ' + vplex.set_local_device_name(volume_name=volume_name))
        try:
            create_virtual_volume(vplex=vplex, volume_name=volume_name)
            logger.info('------- Get virtual-volume information by name')
            get_virtual_volume_info(vplex=vplex, name=volume_name, is_all=False)
        except:
            logger.error('Failed to create virtual-volume')
            module.fail_json(msg='Failed to create virtual-volume from extent...')
        else:
            logger.info('Successfully create virtual-volume from extent.')

            logger.info('------- Drill-down virtual-volume created')
            logger.debug(vplex.drill_down(object_name=target_virtual_volume_name))

            logger.info('------- Check assignment from virtual-volume side')
            logger.debug(vplex.show_use_hierarchy(object_name=target_virtual_volume_name))

            module.exit_json(changed=True)


if __name__ == "__main__":
    main()
