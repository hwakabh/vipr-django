from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.mds import MDS
from ansible.module_utils.common import Integrator

import logging
import os
import pexpect

logger = logging.getLogger(__name__)


def add_device_alias(mds, device_alias, pwwn):
    cmd = 'device-alias name ' + device_alias + ' pwwn ' + pwwn

    logger.debug('>>> Attempt to login MDS Switch...')
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

    output.sendline('device-alias database')
    output.expect(mds.device_alias_prompt)
    logger.debug('Now you are in config-device-alias-db mode with target system.')

    logger.debug('Runnnig command : ' + cmd)
    output.sendline(cmd)
    output.expect('(Device Alias already present)|(' + mds.device_alias_prompt + ')')
    if output.after == 'Device Alias already present':
        logger.error('Failed to add device-alias database. Provided device-alias has currently pending status.')
    else:
        logger.debug('Added device-alias successful. Note that device-alias database has not commited yet.')
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

    logger.info(">>>>>>>>>> Starting ansible-mds module: device-alias")

    # Get parameters from playbook
    argument_spec = {"target_switch": dict(type="str", required=True),
                     "target_server_name": dict(type="str", required=True),
                     "alias_name": dict(type="str", required=True),
                     "server_side_pwwn": dict(type="str", required=True)}

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
    target_server_name = module.params['target_server_name']
    alias_name = module.params['alias_name']
    server_side_pwwn = module.params['server_side_pwwn'].lower()

    logger.info('------- Instantiate MDS to handle')
    mds = MDS(ip_address=ip_address, username=username, password=password)

    # --- if S/N differs from expected, exit the program
    if not mds.confirm_mds_serial_number(expect_serial_number=primary_switch_serial_number):
        logger.error('Target system S/N and expected ones are different. Exis the module wihtout any operations.')
        module.exit_json(changed=False)
    # --- if same as expected, proceed to play

    logger.info('------- Getting active device-alias')
    device_aliases = mds.send_show_command(cmd='show device-alias database')[:-2]

    logger.info('------- Checking duplication of name/PWWN in device-alias database')
    for alias in device_aliases:
        if ('some_hostname' in alias) or (server_side_pwwn in alias):
            logger.error('Seems that device-alias already configured. Exit the module without any operations.')
            module.exit_json(changed=False)
        else:
            pass
            # logger.debug('Proceed to Play')

    logger.info('---- Checking device-alias diff exist or not')
    alias_diffs = mds.send_show_command(cmd='show device-alias pending-diff')
    if alias_diffs[0] != 'There are no pending changes':
        logger.warning('There are some pending alias.' + str(alias_diffs))
        if len(alias_diffs) >= 2:
            logger.error('There is another device-alias with pending-status.')
            logger.error('Since this might be triggered mis-configurations, exit the modules without any operations.')
            module.exit_json(changed=False)
        elif len(alias_diffs) == 1:
            if (target_server_name in alias_diffs[0]) or (server_side_pwwn in alias_diffs[0]):
                logger.warning('Device-alias of target server has already configred and currently been pending status.')
                logger.warning('Start to commit it.')
                mds.send_command_config_mode(cmd='device-alias commit')
                module.exit_json(changed=True)
            else:
                logger.error('Pending alias is not the same as expected one.')
                logger.error('Since this might be triggered mis-configurations, exit the modules without any operations.')
                module.exit_json(changed=False)
    else:
        logger.info('There is no pending alias on database. Start to register device-alias.')

        logger.info('---- Adding device-alias on MDS Switch')
        add_device_alias(mds=mds, device_alias=alias_name, pwwn=server_side_pwwn)

        logger.info('---- Commit registered device-alias on MDS Switch')
        mds.send_command_config_mode(cmd='device-alias commit')

        module.exit_json(changed=True)


if __name__ == "__main__":
    main()
