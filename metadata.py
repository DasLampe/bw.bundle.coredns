from bundlewrap.utils.dicts import merge_dict

defaults = {
}

@metadata_reactor
def add_iptables_rule(metadata):
    if not node.has_bundle("iptables"):
        raise DoNotRunAgain

    interfaces = ['main_interface']

    meta_tables = {}
    for interface in interfaces:
        meta_tables += repo.libs.iptables.accept().chain('INPUT').input(interface).tcp().dest_port(53)
        meta_tables += repo.libs.iptables.accept().chain('INPUT').input(interface).udp().dest_port(53)

    return meta_tables

@metadata_reactor.provides('coredns/servers',)
def merge_server_and_zone_config(metadata):
    merged= {}

    for name, server_config in metadata.get('coredns/servers', {}).items():
        merged[name] = {
            'zones': {}
        }
        for zone, zone_config in server_config.get('zones', {}).items():
            merged[name]['zones'][zone] = {
                'name_servers': merge_dict(zone_config.get('name_servers', {}), server_config.get('name_servers', {})),
                'notify': merge_dict(zone_config.get('notify', []), server_config.get('notify', [])),
                'config': merge_dict(zone_config.get('config', {}), server_config.get('config', {})),
                'soa': merge_dict(zone_config.get('soa', {}), server_config.get('soa', {}))
            }

            if zone_config.get('use_template_records', False):
                merged[name]['zones'][zone]['records'] = merge_dict(zone_config.get('records', {}), server_config.get('template_records', {}))

    return {
        'coredns': {
            'servers': merged,
        },
    }
