defaults = {
    'coredns': {
        'url': 'https://github.com/coredns/coredns/releases/download/v1.14.2/coredns_1.14.2_linux_amd64.tgz',
        'sha256_checksum': '2f08896df9d28ea0cd2294037e6d66e82f996b504e4901b791be8a3ae042029b',
        'sha1_checksum': '6cb3c83a39ab3349e52058081c39897c4b512e34',
    }
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
                'name_servers': server_config.get('name_servers', {}),
                'notify': server_config.get('notify', []),
                'config': server_config.get('config', {}),
                'soa':  server_config.get('soa', {}),
                'acme': server_config.get('acme', {}),
            }

            if zone_config.get('use_template_records', False):
                merged[name]['zones'][zone]['records'] = server_config.get('template_records', {})

    return {
        'coredns': {
            'servers': merged,
        },
    }
