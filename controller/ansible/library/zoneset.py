from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.mds import MDS
from ansible.module_utils.common import Integrator

import logging
import os
import pexpect

logger = logging.getLogger(__name__)


def add_zone_member_to_zoneset(mds, enter_cmd, target_zones):
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

    output.sendline(enter_cmd[0])
    output.expect(mds.zoneset_prompt)
    if 'Invalid' in output.after:
        logger.error('Failed to enter zoneset mode. Please check zoneset_name in group_vars/all.yml and retry it.')
        return False
    logger.debug('Terminal changed successfully. Now you are in config-zoneset mode with target system.')

    if type(target_zones) is list:
        for zone in target_zones:
            cmd_add_zone = 'member ' + zone
            logger.debug('Runnnig command : ' + cmd_add_zone)
            output.sendline(cmd_add_zone)
            output.expect(mds.zoneset_prompt)
            if 'Invalid' in output.after:
                logger.error('Failed to add member to zoneset. Please check provided parameters in group_vars/all.yml and retry it.')
                return False
            logger.debug('Zone [ ' + zone +' ] added to zoneset.')
    elif type(target_zones) is str:
        cmd_add_zone = 'member ' + target_zones
        logger.debug('Runnnig command : ' + cmd_add_zone)
        output.sendline(cmd_add_zone)
        output.expect(mds.zoneset_prompt)
        if 'Invalid' in output.after:
            logger.error('Failed to add member to zoneset. Please check provided parameters in group_vars/all.yml and retry it.')
            return False
        logger.debug('Zone [ ' + target_zones +' ] added to zoneset.')

    output.sendline('end')
    output.expect(mds.await_prompt)
    return True


def activate_zoneset(mds, zoneset_name, vsan_id):
    cmd_activate = 'zoneset activate name ' + zoneset_name + ' vsan ' + vsan_id
    configred_zoneset = mds.send_command_config_mode(cmd=cmd_activate)[0]
    if configred_zoneset != 'Zoneset activation initiated. check zone status':
        return False
    else:
        return True


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

    logger.info(">>>>>>>>>> Starting ansible-mds module: zoneset")

    # Get parameters from playbook
    argument_spec = {"target_switch": dict(type="str", required=True),
                     "vsan_id": dict(type="str", required=True),
                     "zoneset_name": dict(type="str", required=True),
                     "server_side_pwwn": dict(type="str", required=True),
                     "target_vplex": dict(type="str", required=True)}

    module = AnsibleModule(argument_spec, supports_check_mode=True)

    target_switch = module.params['target_switch']
    logger.info('Operation to ' + target_switch)

    fd = Integrator()
    configuration = fd.return_device_info(target=target_switch)
    logger.info(configuration)

    ip_address = configuration['credentials'][0]['ip_address']
    username = configuration['credentials'][0]['username']
    password = configuration['credentials'][0]['password']
    primary_switch_serial_number = configuration['serial_number']

    vsan_id = module.params['vsan_id']
    zoneset_name = module.params['zoneset_name']
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
    target_zones = mds.set_target_zone_names(server_pwwn=server_side_pwwn,storage_pwwn_1=primary_frontend_port_0_wwn, storage_pwwn_2=secondary_frontend_port_0_wwn)
    if len(target_zones) == 0:
        logger.error('Device-aliases are currently configured properly.')
        logger.error('Device-aliases for VPLEX-size and server-size should be configured properly to start zoning and activation.')
        logger.error('Please check manually and retry it.')
        module.exit_json(changed=False)
    else:
        logger.info('------- Validate zoneset on remote target is same as expected')
        query_cmd_zoneset = 'show zoneset active vsan ' + vsan_id + ' |grep zoneset'
        # target_zoneset === 'zoneset name Fixed_TSLAB_Zoneset_VSAN2 vsan 2'
        target_zoneset = mds.send_show_command(cmd=query_cmd_zoneset)

        if zoneset_name != target_zoneset[0].split()[2]:
            logger.error('Expected zoneset name differs from current active one. Check `zoneset_name` in group_vars/all.yml and retry it.')
            module.exit_json(changed=False)

        logger.info('------- Validating zones are truly exist in the remote system or not...')
        all_zones_on_target = mds.send_show_command(cmd='show zone vsan ' + vsan_id + ' |grep zone')
        if not mds.search_zone(zonelist=all_zones_on_target, zonename=target_zones[0]) or not mds.search_zone(zonelist=all_zones_on_target, zonename=target_zones[1]):
            logger.error('Some zones does not configured properly on target system.')
            logger.error('Please check the configuration and retry it.')
            module.exit_json(changed=False)


        logger.info('All zones are properly created to target system and start to add/activate them.')
        logger.info('Canditates zones to be activated : ' + str(target_zones))
        logger.info('Zoneset to be activated : ' + zoneset_name)

        logger.info('------- Getting zones in active zoneset on remote system')
        active_zones = mds.get_zones_from_zoneset(primary_vsan_id=vsan_id, is_active_zone=True)

        # 1. Case if both zone are already in active zoneset
        if mds.search_zone(zonelist=active_zones, zonename=target_zones[0]) and mds.search_zone(zonelist=active_zones, zonename=target_zones[1]):
            # TODO: Add logics case if zones are activated but not in defined zone(Removed)
            logger.error('Both target zones are already in active zoneset. Need not to activate zoneset.')
            logger.error('Nothing to do in this step, exit the module without any operation.')
            module.exit_json(changed=False)

        # 2. Case if one of zones is not in active zoneset
        elif mds.search_zone(zonelist=active_zones, zonename=target_zones[0]) or mds.search_zone(zonelist=active_zones, zonename=target_zones[1]):
            if mds.search_zone(zonelist=active_zones, zonename=target_zones[0]):
                logger.warning('Zone [ ' + target_zones[0] + ' ] has already in active zoneset.')
                logger.warning('But zone [ ' + target_zones[1] + ' ] is not in active zoneset. Add and activate it.')
                # added and activate zones[1]
                if add_zone_member_to_zoneset(mds=mds, enter_cmd=target_zoneset, target_zones=target_zones[1]):
                    logger.info('Since, successfully added members to zoneset, starting zoneset activation.')
                    if activate_zoneset(mds=mds, zoneset_name=zoneset_name, vsan_id=vsan_id):
                        logger.info('Successfully activated zoneset.')
                        logger.info('Activated zones to change: ' + target_zones[1])
                        module.exit_json(changed=True)
                    else:
                        logger.error('Failed to activation. Notice that zone [ ' + target_zones[1] + ' ] had already added to zoneset unexpectedly.')
                        logger.error('Do not forget to re-confiugre manualy if needed.')
                        module.exit_json(changed=True)
                else:
                    # zonset add failure
                    logger.error('Failed to add member to zoneset. Exit the modules, since zoneset activation might be risk for another zones.')
                    module.exit_json(changed=False)
            # elif mds.search_zone(zonelist=active_zones, zonename=target_zones[1])
            else:
                logger.warning('Zone [ ' + target_zones[1] + ' ] has already in active zoneset.')
                logger.warning('But zone [ ' + target_zones[0] + ' ] is not in active zoneset. Add and activate it.')
                # added and activate zones[0]
                if add_zone_member_to_zoneset(mds=mds, enter_cmd=target_zoneset, target_zones=target_zones[0]):
                    logger.info('Since, successfully added members to zoneset, starting zoneset activation.')
                    if activate_zoneset(mds=mds, zoneset_name=zoneset_name, vsan_id=vsan_id):
                        logger.info('Successfully activated zoneset.')
                        logger.info('Activated zones to change: ' + target_zones[0])
                        module.exit_json(changed=True)
                    else:
                        logger.error('Failed to activation. Notice that zone [ ' + target_zones[0] + ' ] had already added to zoneset unexpectedly.')
                        logger.error('Do not forget to re-confiugre manualy if needed.')
                        module.exit_json(changed=True)
                else:
                    # zonset add failure
                    logger.error('Failed to add member to zoneset. Exit the modules, since zoneset activation might be risk for another zones.')
                    module.exit_json(changed=False)

        # 3. Case if both zones are not in active zoneset
        else:
            logger.info('Both zones  ' + str(target_zones) + ' are not in active zoneset.')
            logger.info('------- Getting zones in defined zoneset on remote system')
            defined_zones = mds.get_zones_from_zoneset(primary_vsan_id=vsan_id, is_active_zone=False)

            # search target zone with intverted defined zones list
            if mds.search_zone(zonelist=defined_zones, zonename=target_zones[0]):
                logger.warning('Zone [ ' + target_zones[0] + ' ] has already added to zoneset.')
                
                if mds.search_zone(zonelist=defined_zones, zonename=target_zones[1]):
                    logger.warning('Zone [ ' + target_zones[1] + ' ] has also already added to zoneset.')
                    logger.info('Both zones are added properly to zoneset. Execute zoneset activation only.')
                    if activate_zoneset(mds=mds, zoneset_name=zoneset_name, vsan_id=vsan_id):
                        logger.info('Successfully activated zoneset.')
                        logger.info('Activated zones : ' + str(target_zones))
                        module.exit_json(changed=True)
                    else:
                        logger.error('Failed to activation.')
                        module.exit_json(changed=False)
                else:
                    # Case target_zones[0] exists, but target_zones[1] doesn't in zoneset
                    logger.warning('Zone [ ' + target_zones[1] + ' ] does not added to zoneset.')
                    logger.warning('For activation, Zone [ ' + target_zones[1] + ' ] would be added to zoneset [ ' + zoneset_name + ' ].')

                    if add_zone_member_to_zoneset(mds=mds, enter_cmd=target_zoneset, target_zones=target_zones[1]):
                        logger.info('Since, successfully added members to zoneset, starting zoneset activation.')
                        if activate_zoneset(mds=mds, zoneset_name=zoneset_name, vsan_id=vsan_id):
                            logger.info('Successfully activated zoneset.')
                            logger.info('Activated zones to change: ' + target_zones[1])
                            module.exit_json(changed=True)
                        else:
                            logger.error('Failed to activation. Notice that zone [ ' + target_zones[1] + ' ] had already added to zoneset unexpectedly.')
                            logger.error('Do not forget to re-confiugre manualy if needed.')
                            module.exit_json(changed=True)
                    else:
                        # zonset add failure
                        logger.error('Failed to add member to zoneset. Exit the modules, since zoneset activation might be risk for another zones.')
                        module.exit_json(changed=False)

            else:
                # Case target_zones[0] does not exist, but target_zones[1] exists in zoneset
                if mds.search_zone(zonelist=defined_zones, zonename=target_zones[1]):
                    logger.warning('Zone [ ' + target_zones[0] + ' ] does not added to zoneset.')
                    logger.warning('For activation, Zone [ ' + target_zones[0] + ' ] would be added to zoneset [ ' + zoneset_name + ' ].')

                    if add_zone_member_to_zoneset(mds=mds, enter_cmd=target_zoneset, target_zones=target_zones[0]):
                        logger.info('Successfully added members to zoneset. Execute zoneset activation.')
                        if activate_zoneset(mds=mds, zoneset_name=zoneset_name, vsan_id=vsan_id):
                            logger.info('Successfully activated zoneset.')
                            logger.info('Activated zones to change: ' + target_zones[0])
                            module.exit_json(changed=True)
                        else:
                            logger.error('Failed to activation. Notice that zone [ ' + target_zones[0] + ' ] had added to zoneset unexpectedly.')
                            logger.error('Do not forget to re-confiugre manualy if needed.')
                            module.exit_json(changed=True)
                    else:
                        # zonset add failure
                        logger.error('Failed to add member to zoneset. Exit the modules, since zoneset activation might be risk another zones.')
                        module.exit_json(changed=False)
                        
                else:
                    # Case target_zones[0] does not exist, and target_zones[1] does not.
                    logger.warning('Zone [ ' + target_zones[1] + ' ] also does not added to zoneset.')
                    logger.warning('Both zones ' + str(target_zones) + ' would be added to [ ' + zoneset_name + ' ]')

                    # Add zones to zoneset at once
                    if add_zone_member_to_zoneset(mds=mds, enter_cmd=target_zoneset, target_zones=target_zones):
                        logger.info('Successfully added members to zoneset. Execute zoneset activation.')
                        if activate_zoneset(mds=mds, zoneset_name=zoneset_name, vsan_id=vsan_id):
                            logger.info('Successfully activated zoneset.')
                            logger.info('Activated zones : ' + str(target_zones))
                            module.exit_json(changed=True)
                        else:
                            logger.error('Failed to activation. Notice that zones  ' + target_zones + '  have added to zoneset unexpectedly.')
                            logger.error('Do not forget to re-confiugre manualy if needed.')
                            module.exit_json(changed=True)
                    else:
                        # zoneset add failure
                        logger.error('Part of zones failed to add as member to zoneset. Exit the modules, since zoneset activation might mis-configure another zones.')
                        module.exit_json(changed=False)


if __name__ == "__main__":
    main()
