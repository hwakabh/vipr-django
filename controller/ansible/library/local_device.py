from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.cmnlib import VPLEX
from ansible.module_utils.cmnlib import Integrator

import logging
import os

logger = logging.getLogger(__name__)


def get_local_device_info(vplex, name, is_all):
    if is_all:
        uri = '/vplex/clusters/cluster-1/devices'
    else:
        local_device_name = vplex.set_local_device_name(volume_name=name)
        uri = '/vplex/clusters/cluster-1/devices/' + local_device_name
    response = vplex.https_get(urlsuffix=uri)
    # logger.info(response)
    return response


def create_local_device(vplex, volume_name):
    extent_name = vplex.set_extent_name(volume_name=volume_name)
    local_device_name = vplex.set_local_device_name(volume_name=volume_name)
    uri = '/vplex/local-device+create'
    data = '{\"args\":\"--name ' + local_device_name + ' --geometry raid-0 --extents ' + extent_name + ' --force\"}'
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

    logger.info(">>>>>>>>>> Starting ansible-vplex module: local-devices")

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

    # Confirm that local-device to create does not exist
    logger.info('------- Getting current local-devices information...')
    local_device_list_all = get_local_device_info(vplex=vplex, name=volume_name, is_all=True)
    local_devices = []
    for local_device in local_device_list_all['response']['context'][0]['children']:
        local_devices.append(local_device['name'])

    target_local_device_name = vplex.set_local_device_name(volume_name=volume_name)
    if target_local_device_name in local_devices:
        logger.error('Name duplication occured. Target local-device name [ ' + target_local_device_name + ' ] has already configured on VPLEX.')
        logger.error('Exit the module without any operations.')
        module.exit_json(changed=False)
    else:
        logger.info('------- Create local-device from extent')
        logger.info('Local-device name to be created : ' + target_local_device_name)
        logger.info('Extent to be converted to local-device : ' + vplex.set_extent_name(volume_name=volume_name))
        try:
            create_local_device(vplex=vplex, volume_name=volume_name)
            logger.info('------- Get local-device information by name')
            get_local_device_info(vplex=vplex, name=volume_name, is_all=False)
        except:
            logger.error('Failed to create local-device')
            module.fail_json(msg='Failed to create local-device from extent...')
        else:
            logger.info('Successfully create local-device from extent.')
            module.exit_json(changed=True)


if __name__ == "__main__":
    main()
