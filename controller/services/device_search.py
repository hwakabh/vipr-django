import json
import logging
import re
from pymongo import MongoClient

logger = logging.getLogger('django')

#mongo_url = 'mongodb://10.118.37.180:27017/'
mongo_ip = 'localhost'
mongo_port = 27017
mongo_dbname = 'vipr_django'

# Instantiate Mongo client and get database instance
mc = MongoClient(mongo_ip, mongo_port)
# mc = MongoClient(mongo_url)
mdb = mc[mongo_dbname]


def get_storage_view_from_mongo(user_input):
    keystr = ''
    find_result = []
    logger.info('Searching storage-view withing mongodb...')
    logger.debug('Quering to monogodb database [ mind_django ]')
    logger.debug('Quering to monogodb collections [ storage_views ]')

    # case if user provide server pwwn (## TO be implemented)
    if (len(user_input) == 23) and (':' in user_input):
        logger.info('User provided WWN as keyword, swithching mongodb collections to [ initiator_ports ]...')
        # parse user input with vplex context
        keystr = '0x' + user_input.replace(':','')
        logger.info('Search [ ' + keystr + ' ] within collection [ initiator_ports ] ...')
        mongo_result = mdb['initiator_ports'].find({"attributes.2.value": keystr})
        return mongo_result
    # case if user provide server name
    else:
        mongo_result_views = mdb['storage_views'].find()

        for storage_view in mongo_result_views:
            if user_input in storage_view['attributes'][3]['value']:
                logger.info('[ ' + storage_view['attributes'][3]['value'] + ' ] found in MongoDB collection [ storage_view ] !!')
                find_result.append(storage_view)
            else:
                pass

        logger.info('Searching virtual-volumes within storage-views ...')

        for storage_view in find_result:
            virtual_volume_mappings = []
            del storage_view['_id']
            if len(storage_view['attributes'][7]['value']) != 0:
                logger.info(str(len(storage_view['attributes'][7]['value'])) + ' virtual-volume(s) are found in storage-view [ ' +  storage_view['attributes'][3]['value'] + ' ].')

                for virtual_volume in storage_view['attributes'][7]['value']:
                    vv_name = virtual_volume.split(',')[1]

                    logger.info('Getting backend array info of virtual-volume [ ' + vv_name + ' ].')
                    logger.info('Searching from [ vv_use_hierarchy ] results with key ' + vv_name)
                    for volume_map in mdb['vv_use_hierarchy'].find({"virtual-volume": {'$regex': re.compile(vv_name, re.I)}}):
                        del volume_map['_id']
                        virtual_volume_mappings.append(volume_map)

                # add virtual-volume use-hierarchy to storage-view information
                for i, vol_map in enumerate(virtual_volume_mappings):
                    storage_view['attributes'][7]['value'][i] = {}
                    storage_view['attributes'][7]['value'][i]['storage_view'] = vol_map['storage-view']
                    storage_view['attributes'][7]['value'][i]['virtual_volume'] = vol_map['virtual-volume']
                    storage_view['attributes'][7]['value'][i]['local_device'] = vol_map['local-device']
                    storage_view['attributes'][7]['value'][i]['extent'] = vol_map['extent']
                    storage_view['attributes'][7]['value'][i]['storage_volume'] = vol_map['storage-volume']
                    storage_view['attributes'][7]['value'][i]['logical_unit'] = vol_map['logical-unit']
                    storage_view['attributes'][7]['value'][i]['storage_array'] = vol_map['storage-array']

            else:
                logger.info('No virtual-volume are assigned to storage-view [ ' + storage_view['attributes'][3]['value'] + ' ].')

        return find_result
