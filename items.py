import os
import re
from shlex import quote

def add_to_list_or_create(ilist: dict, list_key: str, value: dict):
    if list_key not in ilist:
        ilist[list_key] = []

    ilist[list_key] += [value,]

def add_dot(url):
    if not url.endswith('.'):
        url += '.'

    return url

config = node.metadata.get('coredns', {})

defaultDir = config.get('defaultDir', '/etc/coredns')
owner = config.get('owner', 'coredns')
group = config.get('group', 'coredns')

files = {
    '/etc/systemd/system/coredns.service': {
        'source': 'etc/systemd/system/coredns.service.j2',
        'content_type': 'jinja2',
        'context': {
            'user': owner,
            'dir': defaultDir,
        }
    },
}
directories = {}
symlinks = {
    '/usr/bin/coredns': {
        'target': '/opt/coredns/coredns',
    },
}
svc_systemd = {
    'coredns.service': {
        'running': True,
        'enabled': True,
        'needs': [
            'zonefiles:',
            'file:/etc/systemd/system/coredns.service',
            f'file:{defaultDir}/Corefile',
            'file:/opt/coredns/coredns',
        ]
    }
}
zonefiles = {} # Special item

users = {
    owner: {
        'home': defaultDir,
    }
}

servers = {}
for name, server_config in config.get('servers', {}).items():
    if not server_config.get('enabled', True):
        continue
    zoneDir = server_config.get('zonefile_dir', f'{defaultDir}/zones/{name}')
    directories[zoneDir] = {
        'owner': owner,
        'group': group,
    }

    # Gather zonesfiles
    for zone, zone_config in server_config.get('zones', {}).items():
        if not zone.rstrip('.') or not zone_config.get('enabled', True):
            continue

        # create ns records we add a . to the end of every domain, since we assume they are absolute
        ns_records = []
        for ns in zone_config.get('name_servers', []):
            ns_records += [{'ttl': 86400, 'type': 'NS', 'value': add_dot(ns)}, ]

        zonefiles[f'{name}_{zone}'] = {
            'zone_name': zone,
            'soa': {
                'nameserver': zone_config.get('name_servers', [''])[0],
                'postmaster': zone_config.get('soa', {}).get('hostmaster', 'hostmaster@example.org'),
                'refresh': zone_config.get('soa', {}).get('refresh', 14400),
                'retry': zone_config.get('soa', {}).get('retry', 7200),
                'expire': zone_config.get('soa', {}).get('expire', 604800),
                'minimum': zone_config.get('soa', {}).get('minimum', 14400),
            },
            'records': {
                '': ns_records,
            },
            'default_ttl': zone_config.get('default_ttl', 300),
            'zonefile_directory': zoneDir,
            'zonefile_filename': f'db.{zone}', # Be compatible with powerdns zonefile item,
            'needs': [
                f'directory:{zoneDir}',
            ],
        }

        if zone_config.get('zone_type') == 'group':
            if 'group' not in zone_config:
                raise BundleError("zone_type is group, but no group defined")

            for group_node in sorted(repo.nodes_in_group(zone_config.get('group'))):
                for interface, interface_config in zone_config.get('interfaces', {}).items():
                    ip = group_node.metadata.get('interfaces', {})\
                        .get(interface, {})\
                        .get('ip_addresses', [None, ])[0]

                    # Remove Zone in hostname
                    group_node_name = re.sub(f"[.]{zone.replace('.', '[.]')}$", '', group_node.hostname)

                    if ip:
                        add_to_list_or_create(
                            zonefiles[f'{name}_{zone}']['records'],
                            f'{interface}.{group_node_name}',
                            {'type': 'A', 'value': ip}
                        )

                        if interface_config.get('cname', False):
                            add_to_list_or_create(
                                zonefiles[f'{name}_{zone}']['records'],
                                group_node_name,
                                {
                                    'type': 'CNAME',
                                    'value': f'{interface}.{group_node_name}',
                                },
                            )

        extra_records = zone_config.get('records', {})
        for rr_name, items in sorted(extra_records.items()):
            for item in items:
                add_to_list_or_create(
                    zonefiles[f'{name}_{zone}']['records'],
                    rr_name,
                    item,
                ),

    servers[name] = {
        'port': server_config.get('port'),
        'zones': server_config.get('zones', {}),
    }

files[f'{defaultDir}/Corefile'] = {
    'source': 'etc/coredns/Corefile.j2',
    'content_type': 'jinja2',
    'context': {
        'defaultDir': defaultDir,
        'snippets': config.get('snippets', {}),
        'servers': servers,
    },
    'owner': owner,
    'group': group,
    'needs': [
        'zonefiles:',
    ],
    'triggers': [
        'svc_systemd:coredns.service:restart',
    ]
}

if config.get('url', '').startswith('local:'):
    files['/opt/coredns/coredns'] = {
        'source': config.get('url').replace('local:', ''),
        'content_type': 'binary',
        'mode': '0555',
        'owner': owner,
        'group': group,
    }
else:
    files['/opt/coredns/coredns'] = {
        'source': config.get('url', ''),
        'content_type': 'download',
        'mode': '0555',
        'owner': owner,
        'group': group,
    }
