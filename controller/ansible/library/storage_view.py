from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.cmnlib import VPLEX
from ansible.module_utils.cmnlib import Integrator

import logging
import os
import pexpect

logger = logging.getLogger(__name__)

# VPLEX API to get storage-view info
# /vplex/clusters/cluster-1/exports/storage-views/
# /vplex/clusters/cluster-1/exports/storage-views/*
#     initiator-ports info masked GET_RESPONSE['response']['context'][X]['attributes'][2]['value']
#     storage-view name GET_RESPONSE['response']['context'][X]['attributes'][3]['value']
#     virtual-volume info masked GET_RESPONSE['response']['context'][X]['attributes'][7]['value']

def get_storage_view_info(vplex, name, is_all):
    if is_all:
        uri = '/vplex/clusters/cluster-1/exports/storage-views/'
    else:
        uri = '/vplex/clusters/cluster-1/exports/storage-views/SV_' + name
    response = vplex.https_get(urlsuffix=uri)
    return response


def create_storage_view(vplex, name, vplex_ports):
    ports = ''
    for port in vplex_ports:
        ports += port + ','
    ports = ports[:-1]
    logger.debug(ports)
    cmd = 'export storage-view create --cluster cluster-1 --name SV_' + name + ' --ports ' + ports

    logger.debug('>>> Attempt to login vplex-shell...')
    output = pexpect.spawn('ssh ' + vplex.login_credentials)
    output.expect('Password:')
    output.sendline(vplex.password)
    output.expect(vplex.shell_prompt)
    logger.debug('Sucessfully logged in to vplex-shell.')

    if vplex.model == 'VS6':
        logger.debug('>>> Trying to login VPLEX-CLI terminal...')
        output.sendline('vplexcli')
        output.expect(vplex.cli_prompt)
        logger.debug('Logged into vplexcli done.')

    elif vplex.model == 'VS2':
        logger.debug('>>> Trying to login VPLEX-CLI terminal...')
        output.sendline('vplexcli')
        output.expect('Enter User Name: ')
        output.sendline(vplex.username)
        output.expect('Password:')
        output.sendline(vplex.password)
        output.expect(vplex.cli_prompt)
        logger.debug('Logged into vplexcli done.')

    logger.debug('>>> Creating storage-view')
    logger.debug('Runnnig vplex command : ' + cmd)
    output.sendline(cmd)
    output.expect(vplex.cli_prompt)


def map_initiator_ports_to_storage_view(vplex, server_name):
    cmd = 'export storage-view addinitiatorport --view SV_' + server_name + ' --initiator-ports ' + server_name

    logger.debug('>>> Attempt to login vplex-shell...')
    output = pexpect.spawn('ssh ' + vplex.login_credentials)
    output.expect('Password:')
    output.sendline(vplex.password)
    output.expect(vplex.shell_prompt)
    logger.debug('Sucessfully logged in to vplex-shell.')

    if vplex.model == 'VS6':
        logger.debug('>>> Trying to login VPLEX-CLI terminal...')
        output.sendline('vplexcli')
        output.expect(vplex.cli_prompt)
        logger.debug('Logged into vplexcli done.')

    elif vplex.model == 'VS2':
        logger.debug('>>> Trying to login VPLEX-CLI terminal...')
        output.sendline('vplexcli')
        output.expect('Enter User Name: ')
        output.sendline(vplex.username)
        output.expect('Password:')
        output.sendline(vplex.password)
        output.expect(vplex.cli_prompt)
        logger.debug('Logged into vplexcli done.')

    logger.debug('>>> Adding Primary initiator-port to storage-view')
    logger.info('Target storage-view : SV_' + server_name)
    logger.info('Target initiator-port : ' + server_name + '_HBA0')
    logger.debug('Runnnig vplex command : ' + cmd + '_HBA0')
    output.sendline(cmd + '_HBA0')
    output.expect(vplex.cli_prompt)

    logger.debug('>>> Adding Secondary initiator-port to storage-view')
    logger.info('Target storage-view : SV_' + server_name)
    logger.info('Target initiator-port : ' + server_name + '_HBA1')
    logger.debug('Runnnig vplex command : ' + cmd + '_HBA1')
    output.sendline(cmd + '_HBA1')
    output.expect(vplex.cli_prompt)


def add_virtual_volume_to_storage_view(vplex, server_name, volume_name, hlu):
    cmd = 'export storage-view addvirtualvolume --view SV_' + server_name + ' --virtual-volumes (' + hlu + ',' + volume_name + ')'

    logger.debug('>>> Attempt to login vplex-shell...')
    output = pexpect.spawn('ssh ' + vplex.login_credentials)
    output.expect('Password:')
    output.sendline(vplex.password)
    output.expect(vplex.shell_prompt)
    logger.debug('Sucessfully logged in to vplex-shell.')

    if vplex.model == 'VS6':
        logger.debug('>>> Trying to login VPLEX-CLI terminal...')
        output.sendline('vplexcli')
        output.expect(vplex.cli_prompt)
        logger.debug('Logged into vplexcli done.')

    elif vplex.model == 'VS2':
        logger.debug('>>> Trying to login VPLEX-CLI terminal...')
        output.sendline('vplexcli')
        output.expect('Enter User Name: ')
        output.sendline(vplex.username)
        output.expect('Password:')
        output.sendline(vplex.password)
        output.expect(vplex.cli_prompt)
        logger.debug('Logged into vplexcli done.')

    logger.debug('>>> Adding virtual-volume to storage-view')
    logger.info('Target storage-view : SV_' + server_name)
    logger.info('Target virtual-volume : ' + volume_name)
    logger.info('HLU : ' + hlu)
    logger.debug('Runnnig vplex command : ' + cmd)
    output.sendline(cmd)
    output.expect(vplex.cli_prompt)


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

    logger.info(">>>>>>>>>> Starting ansible-vplex module: storage-views")

    # Get parameters from playbook
    argument_spec = {"target_vplex_name": dict(type="str", required=True),
                     "target_server_name": dict(type="str", required=True),
                     "primary_frontend_port_0_name": dict(type="str", required=True),
                     "secondary_frontend_port_0_name": dict(type="str", required=True),
                     "primary_frontend_port_1_name": dict(type="str", required=True),
                     "secondary_frontend_port_1_name": dict(type="str", required=True),
                     "volume_name": dict(type="str", required=True),
                     "host_volume_number": dict(type="str", required=True)}

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

    target_server_name = module.params['target_server_name']
    primary_frontend_port_0_name = module.params['primary_frontend_port_0_name']
    secondary_frontend_port_0_name = module.params['secondary_frontend_port_0_name']
    primary_frontend_port_1_name = module.params['primary_frontend_port_1_name']
    secondary_frontend_port_1_name = module.params['secondary_frontend_port_1_name']
    volume_name = module.params["volume_name"]
    host_volume_number = module.params["host_volume_number"]

    logger.info('------- Instantiate VPLEX to handle...')
    vplex = VPLEX(ip_address=ip_address, username=username, password=password)

    # 1. Check VPLEX S/N
    # --- if S/N differs from expected, exit the program
    if not vplex.confirm_vplex_serial_number(expect_serial_number=serial_number):
        logger.error('Target system S/N and expected ones are different. Exis the module wihtout any operations.')
        module.exit_json(changed=False)
    # --- if same as expected, proceed to play

    # 1. Check storage-view exists
    logger.info('------- Getting storage-view lists')
    storage_view_list_all = get_storage_view_info(vplex=vplex, name=target_server_name, is_all=True)
    storage_views = []
    for view_name in storage_view_list_all['response']['context'][0]['children']:
        storage_views.append(view_name['name'])
    
    # --- if not configured storage-view, create it.
    if "SV_" + target_server_name not in storage_views:
    # if 'test' in storage_views:
        logger.info('Seems that provivded server would be newly implemented. Start to create storage-view.')
        logger.info('------- Creating storage-view')
        vplex_fe_ports = [primary_frontend_port_0_name, secondary_frontend_port_0_name, primary_frontend_port_1_name, secondary_frontend_port_1_name]
        logger.info('VPLEX FE-Ports to be added to new storage-view: ' + str(vplex_fe_ports))
        try:
            create_storage_view(vplex=vplex, name=target_server_name, vplex_ports=vplex_fe_ports)
        except:
            logger.error('Failed to create storage-view.')
            module.fail_json(msg='Failed to create storage-view.')
        else:
            logger.info('Successfully create storage-view.')

        try:
            logger.info('------- Mapping initiator-ports to storage-view')
            map_initiator_ports_to_storage_view(vplex=vplex, server_name=target_server_name)
        except:
            logger.error('Failed to add initiator-ports to storage-view.')
            module.fail_json(msg='Failed to add initiator-ports to storage-view.')
        else:
            logger.info('Successfully added initiator-port to storage-view.')

        try:
            logger.info('------- Add virtual-volumes to storage-view')
            target_virtual_volume_name = vplex.set_virtual_volume_name(volume_name=volume_name)        
            add_virtual_volume_to_storage_view(vplex=vplex, server_name=target_server_name, volume_name=target_virtual_volume_name, hlu=host_volume_number)
        except:
            logger.error('Failed to add virtual-volumes to storage-view.')
            module.fail_json(msg='Failed to add virtual-volumes to storage-view.')
        else:
            logger.info('Successfully added initiator-port to storage-view.')

        logger.info('All tasks for volume masking to servers done. End modules.')
        module.exit_json(changed=True)

    # --- if storage-view already exists, switched to operate adding virtual-volumes to storage-view
    else:
        logger.warning('Provided storage-view name have already existed on VPLEX.')
        logger.warning('Storege-view of target server seems to be already configured.')

        logger.info('Target storage-view name: SV_' + target_server_name)
        # logger.info('Target storage-view info: ' + str(get_storage_view_info(vplex=vplex, name=target_server_name, is_all=False)))
        virutal_volumes_in_view_all = get_storage_view_info(vplex=vplex, name=target_server_name, is_all=False)['response']['context'][0]['attributes'][7]['value']
        virutal_volumes_in_view = []
        for virtual_volume in virutal_volumes_in_view_all:
            virutal_volumes_in_view.append(virtual_volume.split(',')[1])

        # Check virtual-volumes exists in storage-views
        target_virtual_volume_name = vplex.set_virtual_volume_name(volume_name=volume_name)
        if target_virtual_volume_name in virutal_volumes_in_view:
            logger.error('Target virtual-volume [ ' + target_virtual_volume_name + ' ] have already masked in target storage-view.')
            logger.error('Exit the module without any operations.')
            module.exit_json(changed=False)
        else:
            logger.info('Target virtual-volume is currently not masked to storage-view.')
            logger.info('Start to assign virutal-volumes to storage-view.')

            try:
                logger.info('------- Add virtual-volumes to storage-view')
                add_virtual_volume_to_storage_view(vplex=vplex, server_name=target_server_name, volume_name=target_virtual_volume_name, hlu=host_volume_number)
            except:
                logger.error('Failed to add virtual-volumes to existing storage-view.')
                module.fail_json(msg='Failed to add virtual-volumes to existing storage-view.')
            else:
                logger.info('Successfuly add virtual-volumes to existing storage-view.')
                logger.info('All tasks for existing storage-view done. End modules.')
                module.exit_json(changed=True)


if __name__ == "__main__":
    main()
