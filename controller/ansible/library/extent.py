from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.cmnlib import VPLEX
from ansible.module_utils.cmnlib import Integrator

import logging
import os

logger = logging.getLogger(__name__)


def get_extent_info(vplex, name, is_all):
    if is_all:
        uri = '/vplex/clusters/cluster-1/storage-elements/extents'
    else:
        extent_name = vplex.set_extent_name(volume_name=name)
        uri = '/vplex/clusters/cluster-1/storage-elements/extents/' + extent_name
    response = vplex.https_get(urlsuffix=uri)
    # logger.info(response)
    return response


def create_extent(vplex, volume_name):
    uri = '/vplex/extent+create'
    data = '{\"args\":\" --storage-volumes ' + volume_name + '\"}'
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

    logger.info(">>>>>>>>>> Starting ansible-vplex module: extents")

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

    # Confirm that extents to create does not exist
    logger.info('------- Getting current extents information...')
    extents_list_all = get_extent_info(vplex=vplex, name=volume_name, is_all=True)
    extents = []
    for extent in extents_list_all['response']['context'][0]['children']:
        extents.append(extent['name'])

    target_extent_name = vplex.set_extent_name(volume_name=volume_name)

    if target_extent_name in extents:
        logger.error('Name duplication occured. Target extent [ ' + target_extent_name + ' ] has already configured on VPLEX.')
        logger.error('Exit the module without any operations.')
        module.exit_json(changed=False)
    else:
        logger.info('------- Create extent from storage-volume')
        logger.info('Extent name to be created : ' + target_extent_name)
        logger.info('Storage-volumes to be converted to extent : ' + volume_name)
        try:
            create_extent(vplex=vplex, volume_name=volume_name)
            # Confirm that extents to create does not exist
            logger.info('------- Get extent information by name')
            get_extent_info(vplex=vplex, name=volume_name, is_all=False)
        except:
            logger.error('Failed to create extent.')
            module.fail_json(msg='Failed to create extent from storage-volume...')
        else:
            logger.info('Successfully create extents from storage-volume.')
            module.exit_json(changed=True)


if __name__ == "__main__":
    main()
