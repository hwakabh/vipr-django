from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.mds import MDS
from ansible.module_utils.common import Integrator

import logging
import os
import pexpect

logger = logging.getLogger(__name__)


def get_zones(mds, primary_vsan_id):
    query_cmd_zones = 'show zone vsan ' + primary_vsan_id + ' |grep zone'
    all_zones = mds.send_show_command(cmd=query_cmd_zones)

    # Return inverted list of zones, since acceralate searching time.
    return all_zones[::-1]


def create_zone(mds, zonename, server_wwn, storage_pwwn, vsan_id):
    cmd_create = 'zone name ' + zonename + ' vsan ' + vsan_id
    cmd_add_sv = 'member pwwn ' + server_wwn
    cmd_add_st = 'member pwwn ' + storage_pwwn

    output = pexpect.spawn('ssh ' + mds.login_credentials)
    output.expect('Password:')
    output.sendline(mds.password)
    output.expect(mds.await_prompt)
    output.sendline('terminal length 0')
    output.expect(mds.await_prompt)
    logger.debug('Logged in complete, set terminal length unlimited.')

    output.sendline('configure terminal')
    output.expect(mds.config_mode_prompt)
    logger.debug('Now you are in configuration mode with target system.')

    output.sendline(cmd_create)
    output.expect(mds.zone_prompt)
    if 'Invalid' in output.after:
        logger.error('Failed to create zone. Please check provided name or wwn in group_vars/all.yml and retry it.')
    logger.debug('Create zone success. Now you are in config-zone mode with target system.')

    logger.debug('Runnnig command : ' + cmd_create)
    output.sendline(cmd_add_sv)
    output.expect(mds.zone_prompt)
    if 'Invalid' in output.after:
        logger.error('Failed to add member to zone. Please check provided wwn in group_vars/all.yml and retry it.')
    logger.debug('First member added to zone.')

    output.sendline(cmd_add_st)
    output.expect(mds.zone_prompt)
    if 'Invalid' in output.after:
        logger.error('Failed to add second member to zone. Please check provided wwn in group_vars/all.yml and retry it.')
        logger.error('The zone partly created would be remained on the system. Do not forget to remove it.')
    logger.debug('Second member added to zone.')
    logger.info('Successfully create zone [ ' + zonename + ' ]')
    output.sendline('end')
    output.expect(mds.await_prompt)


def main():
    log_directory = "./logs"
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)

    _detail_formatting = "%(asctime)s : %(name)s - %(levelname)s : %(message)s"
    logging.basicConfig(
        level=logging.DEBUG,
        format=_detail_formatting,
        filename=log_directory + "/ansible-mds.log"
    )
    logging.getLogger("modules").setLevel(level=logging.DEBUG)
    console = logging.StreamHandler()
    console_formatter = logging.Formatter("%(asctime)s : %(message)s")
    console.setFormatter(console_formatter)
    console.setLevel(logging.INFO)
    logging.getLogger("modules").addHandler(console)

    logger = logging.getLogger(__name__)
    logging.getLogger(__name__).addHandler(console)

    logger.info(">>>>>>>>>> Starting ansible-mds module: zone")

    # Get parameters from playbook
    argument_spec = {"target_switch": dict(type="str", required=True),
                     "vsan_id": dict(type="str", required=True),
                     "server_side_pwwn": dict(type="str", required=True),
                     "target_vplex": dict(type="str", required=True)}

    module = AnsibleModule(argument_spec, supports_check_mode=True)

    target_switch = module.params['target_switch']
    target_vplex = module.params['target_vplex']
    logger.info('Operation to ' + target_switch + ' and ' + target_vplex)

    fd = Integrator()
    configuration = fd.return_device_info(target=target_switch)
    logger.info(configuration)

    ip_address = configuration['credentials'][0]['ip_address']
    username = configuration['credentials'][0]['username']
    password = configuration['credentials'][0]['password']
    primary_switch_serial_number = configuration['serial_number']

    vsan_id = module.params['vsan_id']
    # wwpn for zoning
    vplex_fe_ports = fd.find_vplex_fe_port_by_mds(sitename=configuration['location'], mds_name=target_switch, vsanid=vsan_id)

    server_side_pwwn = module.params['server_side_pwwn'].lower()
    primary_frontend_port_0_wwn = vplex_fe_ports[0]['pwwn']
    secondary_frontend_port_0_wwn = vplex_fe_ports[1]['pwwn']

    logger.info('------- Instantiate MDS to handle')
    mds = MDS(ip_address=ip_address, username=username, password=password)

    # --- if S/N differs from expected, exit the program
    if not mds.confirm_mds_serial_number(expect_serial_number=primary_switch_serial_number):
        logger.error('Target system S/N and expected ones are different. Exis the module wihtout any operations.')
        module.exit_json(changed=False)
    # --- if same as expected, proceed to play

    logger.info('------- Collecting paramters to use with zoning')
    # If could not find device-alias to use zones, exit the module(Pre-Check fails)
    target_zones = mds.set_target_zone_names(server_pwwn=server_side_pwwn, storage_pwwn_1=primary_frontend_port_0_wwn, storage_pwwn_2=secondary_frontend_port_0_wwn)
    if len(target_zones) == 0:
        logger.error('Some configurations to need for zoning are missing.')
        logger.error('Device-aliases for VPLEX-size and server-size should be configured properly to start zoning. Please check manually and retry it.')
        module.exit_json(changed=False)
    else:
        logger.info('Preparation for zoning done. Zones to be created : ' + str(target_zones))

        logger.info('------- Getting zones on target system')
        all_zones = get_zones(mds=mds, primary_vsan_id=vsan_id)

        if mds.search_zone(zonelist=all_zones, zonename=target_zones[0]):
            logger.warning('First zone to be created already configured, checking second one...')
            if mds.search_zone(zonelist=all_zones, zonename=target_zones[1]):
                logger.warning('Second zone to be created already configured.')
                logger.error('Both zones already exist. Exit the module without any operation.')
                module.exit_json(changed=False)
            else:
                logger.warning('------- Started to create reate only secondary zone.')
                create_zone(mds=mds, zonename=target_zones[1], server_wwn=server_side_pwwn, storage_pwwn=secondary_frontend_port_0_wwn, vsan_id=vsan_id)
                module.exit_json(changed=True)
        else:
            logger.info('------- First zone does not exist in target system, create it.')
            create_zone(mds=mds, zonename=target_zones[0], server_wwn=server_side_pwwn, storage_pwwn=primary_frontend_port_0_wwn, vsan_id=vsan_id)

            if mds.search_zone(zonelist=all_zones, zonename=target_zones[1]):
                logger.warning('Secondary zone have already existed. Nothing to do for second zone.')
                module.exit_json(changed=True)
            else:
                logger.info('------- Secondary zone also does not exist, create it.')
                create_zone(mds=mds, zonename=target_zones[1], server_wwn=server_side_pwwn, storage_pwwn=secondary_frontend_port_0_wwn, vsan_id=vsan_id)
                module.exit_json(changed=True)


if __name__ == "__main__":
    main()
