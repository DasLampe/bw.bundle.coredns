from bundlewrap.items import Item, ItemStatus
from bundlewrap.exceptions import BundleError
from bundlewrap.utils.text import mark_for_translation as _
import os
import datetime

try:
    import dns.zone
except ImportError:
    import sys
    sys.stderr.write("Requires dnspython module\nInstall with\n\npip3 install dnspython\n\n"
                     "If you still get this error, try renaming `/usr/local/lib/python3.6/site-packages/DNS` "
                     "to `/usr/local/lib/python3.6/site-packages/dns`. Upper to lowercase")
    sys.exit(1)

from tempfile import NamedTemporaryFile

from dns.rdtypes.ANY.NS import NS
from dns.rdtypes.IN.A import A
from dns.rdtypes.IN.AAAA import AAAA
from dns.rdtypes.ANY.CNAME import CNAME
from dns.rdtypes.IN.SRV import SRV
from dns.rdtypes.ANY.PTR import PTR
from dns.rdtypes.ANY.SOA import SOA
from dns.rdtypes.ANY.TXT import TXT
from dns.rdtypes.ANY.MX import MX

from dns.zone import NoSOA, NoNS

def split_txt_record(value: str, max_length:int=255 ) -> list[str]:
    return [value[i : i + max_length] for i in range(0, len(value.strip().strip('"')), max_length)]

allowed_records = {
    'NS': {
        'class': dns.rdataclass.IN,
        'type': dns.rdatatype.NS,
        'obj': lambda x: NS(dns.rdataclass.IN, dns.rdatatype.NS, to_name(x))
    },
    'A': {
        'class': dns.rdataclass.IN,
        'type': dns.rdatatype.A,
        'obj': lambda x: A(dns.rdataclass.IN, dns.rdatatype.A, x)
    },
    'AAAA': {
        'class': dns.rdataclass.IN,
        'type': dns.rdatatype.AAAA,
        'obj': lambda x: AAAA(dns.rdataclass.IN, dns.rdatatype.AAAA, x)
    },
    'CNAME': {
        'class': dns.rdataclass.IN,
        'type': dns.rdatatype.CNAME,
        'obj': lambda x: CNAME(dns.rdataclass.IN, dns.rdatatype.CNAME, to_name(x))
    },
    'SRV': {
        'class': dns.rdataclass.IN,
        'type': dns.rdatatype.SRV,
        'obj': lambda x: SRV(dns.rdataclass.IN, dns.rdatatype.SRV, x[0], x[1], x[2], to_name(x[3]))
    },
    'PTR': {
        'class': dns.rdataclass.IN,
        'type': dns.rdatatype.PTR,
        'obj': lambda x: PTR(dns.rdataclass.IN, dns.rdatatype.PTR, to_name(x))
    },
    'TXT': {
        'class': dns.rdataclass.IN,
        'type': dns.rdatatype.TXT,
        'obj': lambda x: TXT(dns.rdataclass.IN, dns.rdatatype.TXT, split_txt_record(x))
    },
    'MX': {
        'class': dns.rdataclass.IN,
        'type': dns.rdatatype.MX,
        'obj': lambda x: MX(dns.rdataclass.IN, dns.rdatatype.MX, int(x.get('preference', 10)), x.get('exchange'))
    },
}


def to_name(name):
    return dns.name.Name(name.split('.'))


def add_dot(url):
    if url[-1] != '.':
        url += '.'

    return url


def generate_zone(zone_name, attributes):
    zone = dns.zone.Zone(zone_name)

    serial = int('{0:%y%m%d%H%M}'.format(datetime.datetime.now()))
    mname = attributes['soa']['nameserver']
    rname = attributes['soa']['postmaster']
    refresh = attributes['soa'].get('refresh', 14400)
    retry = attributes['soa'].get('retry', 7200)
    expire = attributes['soa'].get('expire', 604800)
    minimum = attributes['soa'].get('minimum', 14400)

    default_ttl = int(attributes.get('default_ttl', 60))

    root = zone.get_node('@', create=True)
    rdset = root.get_rdataset(dns.rdataclass.IN, dns.rdatatype.SOA, create=True)
    soa = SOA(dns.rdataclass.IN, dns.rdatatype.SOA,
              to_name(mname), to_name(rname), serial, int(refresh), int(retry), int(expire), int(minimum)
              )
    rdset.add(soa, default_ttl)

    for node_name in attributes['records'].keys():
        node = zone.get_node(node_name, create=True)

        for r in attributes['records'][node_name]:
            if r['type'] not in allowed_records.keys():
                continue

            record_type = allowed_records[r['type']]
            rdset = node.get_rdataset(record_type['class'], record_type['type'], create=True)

            record = record_type['obj'](r['value'])
            ttl = r.get('ttl', default_ttl)
            rdset.add(record, ttl)

    return zone


def get_records_from_zone(zone, zone_name):
    records = []

    for node_name in zone:
        node = zone.get_node(str(node_name))
        for r in node:
            if r.match(dns.rdataclass.IN, dns.rdatatype.SOA, dns.rdatatype.NONE):
                # ignore SOA
                continue

            records += [r.to_text(node_name, origin=to_name(zone_name), relativize=True), ]

    return records


def get_soa_from_zone(zone, zone_name):
    _soa_rec = zone[zone_name].get_rdataset(dns.rdataclass.IN, dns.rdatatype.SOA)
    if not _soa_rec:
        # we have no soa, so create new file
        return None

    return list(_soa_rec)[0]


class ZoneFile(Item):
    """
    Generate BindZoneFiles.
    """
    BUNDLE_ATTRIBUTE_NAME = "zonefiles"
    NEEDS_STATIC = [
        "pkg_apt:",
        "pkg_pacman:",
        "pkg_yum:",
        "pkg_zypper:",
    ]
    ITEM_ATTRIBUTES = {
        'zone_name': None,
        'soa': None,
        'records': None,
        'default_ttl': None,
        'zonefile_directory': None,
        'zonefile_filename': None,
        'dynamic': None,
    }
    ITEM_TYPE_NAME = "zonefile"
    REQUIRED_ATTRIBUTES = ['soa', 'records']

    def __repr__(self):
        return f"<zonefile:{self.attributes.get('zone_name', self.name)}>"

    def fix(self, status):
        zone_name = add_dot(self.attributes.get('zone_name', self.name))
        remote_file_name = f"{self.attributes.get('zonefile_directory', '/var/lib/powerdns/zones')}/{self.attributes.get('zonefile_filename', self.name + '.zone')}"

        default_ttl = int(self.attributes.get('default_ttl', 60))

        zone = generate_zone(zone_name, self.attributes)
        # TODO: if dynamic only add missing

        # generate local tmp files
        tmp_file = NamedTemporaryFile(delete=False)
        header = f"$ORIGIN {zone_name}\n$TTL {default_ttl}\n\n"

        tmp_file.write(header.encode('utf-8'))
        zone.to_file(tmp_file)
        tmp_file.close()

        # upload files to node
        self.node.upload(tmp_file.name, remote_file_name, '444', 'root', 'root')

        # remove file
        os.unlink(tmp_file.name)

    # should look like this
    def cdict(self):
        zone_name = add_dot(self.attributes.get('zone_name', self.name))
        zone = generate_zone(zone_name, self.attributes)

        soa = get_soa_from_zone(zone, zone_name)
        records = get_records_from_zone(zone, zone_name)

        cdict = {
            'type': 'zonefile',
            'zone_name': zone_name,
            'soa_mname': str(soa.mname),
            'soa_rname': str(soa.rname),
            'soa_refresh': int(soa.refresh),
            'soa_retry': int(soa.retry),
            'soa_expire': int(soa.expire),
            'soa_minimum': int(soa.minimum),
            'records': sorted(records),
        }

        return cdict

    # real world
    def sdict(self):
        zone_name = add_dot(self.attributes.get('zone_name', self.name))
        remote_file_name = f"{self.attributes.get('zonefile_directory', '/var/lib/powerdns/zones')}/{self.attributes.get('zonefile_filename', self.name + '.zone')}"

        tmp_file = NamedTemporaryFile()

        res = self.node.run('test -f {}'.format(remote_file_name), may_fail=True)
        if res.return_code != 0:
            return None

        self.node.download(remote_file_name, tmp_file.name)
        try:
            zone = dns.zone.from_file(tmp_file.name, zone_name)
        except NoSOA:
            # file cannot be parsed, does not have a SOA
            return None
        except NoNS:
            # file cannot be parsed, does not have a NS
            return None

        tmp_file.close()

        if not zone:
            return None

        soa = get_soa_from_zone(zone, zone_name)
        records = get_records_from_zone(zone, zone_name)

        if not soa or not records:
            return None

        sdict = {
            'type': 'zonefile',
            'zone_name': zone_name,
            'soa_mname': str(soa.mname),
            'soa_rname': str(soa.rname),
            'soa_refresh': int(soa.refresh),
            'soa_retry': int(soa.retry),
            'soa_expire': int(soa.expire),
            'soa_minimum': int(soa.minimum),
            'records': sorted(records),
        }

        return sdict

    @classmethod
    def validate_attributes(cls, bundle, item_id, attributes):
        if 'nameserver' not in attributes['soa']:
            raise BundleError(_(
                "no Nameserver in SOA Record found {item_id} in bundle '{bundle.name}'"
            ))

        if 'postmaster' not in attributes['soa']:
            raise BundleError(_(
                f"no Postmaster in SOA Record found {item_id} in bundle '{bundle.name}'"
            ))

    def patch_attributes(self, attributes):
        if not attributes['soa']['nameserver'].endswith('.'):
            attributes['soa']['nameserver'] += '.'

        if not attributes['soa']['postmaster'][-1].endswith('.'):
            attributes['soa']['postmaster'] += '.'

        attributes['soa']['postmaster'] = attributes['soa']['postmaster'].replace('@', '.')

        if 'default_ttl' not in attributes:
            attributes['default_ttl'] = 60

        return attributes

    def display_dicts(self, cdict, sdict, keys):
        return (cdict, sdict, keys)

    def display_on_create(self, cdict):
        """
        Given a cdict as implemented above, modify it to better suit
        interactive presentation when an item is created. If there are
        any when_creating attributes, they will be added to the cdict
        before it is passed to this method.

        Implementing this method is optional.
        """
        return cdict
