from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.cmnlib import VPLEX
from ansible.module_utils.cmnlib import Integrator

import logging
import os
import pexpect

logger = logging.getLogger(__name__)


def get_initiator_port_info(vplex, is_all, name):
    if is_all:
        uri = '/vplex/clusters/cluster-1/exports/initiator-ports/*'
    else:
        uri = '/vplex/clusters/cluster-1/exports/initiator-ports/' + name
    response = vplex.https_get(urlsuffix=uri)
    # logger.info(response)
    return response


def register_initiator_port(vplex, initiator_port_name, wwpn, wwnn):
    cmd = 'export initiator-port register --cluster cluster-1 --initiator-port ' + initiator_port_name + ' --type default --port ' + wwpn + '|' + wwnn
 
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

    logger.debug('>>> Registering initiator-port')
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

    logger.info(">>>>>>>>>> Starting ansible-vplex module: initiator-ports")

    # Get parameters from playbook
    argument_spec = {"target_vplex_name": dict(type="str", required=True),
                     "target_server_name": dict(type="str", required=True),
                     "primary_initiator_pwwn": dict(type="str", required=True),
                     "primary_initiator_nwwn": dict(type="str", required=True),
                     "secondary_initiator_pwwn": dict(type="str", required=True),
                     "secondary_initiator_nwwn": dict(type="str", required=True)}

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
    primary_initiator_pwwn = '0x' + module.params['primary_initiator_pwwn'].replace(":", "").lower()
    primary_initiator_nwwn = '0x' + module.params['primary_initiator_nwwn'].replace(":", "").lower()
    secondary_initiator_pwwn =  '0x' + module.params['secondary_initiator_pwwn'].replace(":", "").lower()
    secondary_initiator_nwwn =  '0x' + module.params['secondary_initiator_nwwn'].replace(":", "").lower()

    logger.info('------- Instantiate VPLEX to handle...')
    vplex = VPLEX(ip_address=ip_address, username=username, password=password)

    # 1. Check VPLEX S/N
    # --- if S/N differs from expected, exit the program
    if not vplex.confirm_vplex_serial_number(expect_serial_number=serial_number):
        logger.error('Target system S/N and expected ones are different. Exis the module wihtout any operations.')
        module.exit_json(changed=False)
    # --- if same as expected, proceed to play

    # 2. Confirm fabric exposure of expected PWWN from VPLEX
    logger.info('------- Getting initator-ports list currently visible from VPLEX')
    initiator_port_list_all = get_initiator_port_info(vplex=vplex, is_all=True, name=target_server_name)
    # logger.info(initiator_port_list_all)

    initiator_ports = []
    for initiator in initiator_port_list_all['response']['context']:
        initiator_pwwn = initiator['attributes'][2]['value']
        initiator_ports.append(initiator_pwwn)
    # --- if pwwn have not logged in, exit the modules
    if (primary_initiator_pwwn or secondary_initiator_pwwn) not in initiator_ports:
        logger.error('WWPN of target server does not be exposed from VPLEX side.')
        logger.warning('Check zoning on FC-Switches/masking on backend storages, or try again after array re-discovery on VPLEX.')
        module.exit_json(changed=False)
    # --- if pwwns have already logged in, proceed to play

    # 3. Check initiator-port name duplication
    initiator_names = []
    for initiator in initiator_port_list_all['response']['context']:
        initiator_name = initiator['attributes'][0]['value']
        initiator_names.append(initiator_name)

    if ((target_server_name + '_HBA0') in initiator_names) and ((target_server_name + '_HBA1') in initiator_names):
        logger.warning('Initiator-port name of target server have already configured on VPLEX.')
        logger.warning('Target server seems to be already configured on VPLEX.')
        logger.warning('Exit the module without any operations.')
        module.exit_json(changed=False)
    # --- if no name duplication, start to register operations

    # 4. Register initiator-ports
    logger.info('------- PWWN of initiator-ports to be registered')
    logger.info('Primary initiator-port [ ' + target_server_name + '_HBA0 ] ')
    logger.info('Primary PWWN: ' + primary_initiator_pwwn)
    logger.info('Primary NWWN: ' + primary_initiator_nwwn)
    logger.info('---')
    logger.info('Secondary initiator-port [ ' + target_server_name + '_HBA1 ] ')
    logger.info('Secondary PWWN: ' + secondary_initiator_pwwn)
    logger.info('Secondary NWWN: ' + secondary_initiator_nwwn)

    logger.info('------- Register primary initiator-port')
    register_initiator_port(vplex=vplex, initiator_port_name=target_server_name+'_HBA0', wwpn=primary_initiator_pwwn, wwnn=primary_initiator_nwwn)
    logger.info('Primary initiator-port info : ' + str(get_initiator_port_info(vplex=vplex, is_all=False, name=target_server_name+'_HBA0')))

    logger.info('------- Register secondary initiator-port')
    register_initiator_port(vplex=vplex, initiator_port_name=target_server_name+'_HBA1', wwpn=secondary_initiator_pwwn, wwnn=secondary_initiator_nwwn)
    logger.info('Secondary initiator-port info : ' + str(get_initiator_port_info(vplex=vplex, is_all=False, name=target_server_name+'_HBA1')))

    module.exit_json(changed=True)


if __name__ == "__main__":
    main()
