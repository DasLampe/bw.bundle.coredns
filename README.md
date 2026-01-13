# CoreDNS via Bundlewrap

## Config Example
```python
metadata = {
    'snippets': {
        'internalView': [
            'view internal {',
                "expr (incidr(client_ip(), '127.1.0.0/24'))",
            '}',
        ],
    },
    'servers': {
        'internal': {
            'port': '5353',
            'notify': [
              '127.0.0.2'
            ],
            'config': [
                'import internalView',
                'errors',
            ],
            'name_servers': ['ns1.example.org', 'ns2.example.org'],
            'soa': {
                'hostmaster': 'hostmaster@example.org',
            },
            'template_records': {
                'bar': [
                    {
                        'type': 'CNAME',
                        'value': 'baz',
                    },
                ],
            },
            'zones': {
                'home.example.org': {
                    'name_servers': atomic(['ns1.example.com', 'ns3.example.org']),
                    'zone_type': 'group',
                    'group': 'home',
                    'interfaces': {
                        'eth0': {
                            'cname': True,
                        },
                    },
                    'records': {
                        'foo': [
                            {
                                'type': 'A',
                                'value': '127.0.0.1',
                            },
                        ],
                    },
                },
                'lab.example.org': {
                    'use_template_records': True,
                    'zone_type': 'group',
                    'group': 'lab',
                    'interfaces': {
                        'eth0': {
                            'cname': True,
                        },
                    },
                },
            },
        },
    },
}
```
