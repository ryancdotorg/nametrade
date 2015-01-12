#!/usr/bin/env python
# vim: sw=4 ts=4 et ai si bg=dark

import os
import sys
import time

import argparse

from binascii import hexlify, unhexlify
from base64 import b64encode as b64e, b64decode as b64d

from bitcoin import *
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException

### OPCODES - just the ones we need
OP_NAME_UPDATE = 3
OP_2DROP = 109
OP_DROP = 117
OP_DUP = 118
OP_HASH160 = 169
OP_EQUALVERIFY = 136
OP_CHECKSIG = 172

class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self

_nt = {}

def print_stderr(s):
    # escape characters to clear the rest of the line
    sys.stderr.write('\033[0G%s\033[0K\n' % s)

# look for the config file in default locations
def defaultconf():
    home = os.path.expanduser('~')
    # XXX where should we be looking for Windows/OS X?
    for namecoin in ['.namecoin', 'namecoin', 'Namecoin', 'NameCoin']:
        for conf in ['namecoin.conf', 'bitcoin.conf']:
            config = os.path.join(home, namecoin, conf)
            if os.path.isfile(config):
                return config
    return None

def asp_from_config(filename=None):
    if filename is None:
        filename = defaultconf()
    rpcport = '8332'
    rpcconn = '127.0.0.1'
    rpcuser = None
    rpcpass = None
    with open(filename, 'r') as f:
        for line in f:
            (key, val) = line.rstrip().replace(' ', '').split('=')
            if key == 'rpcuser':
                rpcuser = val
            elif key == 'rpcpassword':
                rpcpass = val
            elif key == 'rpcport':
                rpcport = val
            elif key == 'rpcconnect':
                rpcconn = val
        f.close()
    if rpcuser is not None and rpcpass is not None:
        rpcurl = 'http://%s:%s@%s:%s' % (rpcuser, rpcpass, rpcconn, rpcport)
        #print_stderr('RPC server: %s' % rpcurl)
        _nt['rpc'] = AuthServiceProxy(rpcurl)
        return _nt['rpc']

def getoutputscript(txid, i):
    return deserialize(_nt['rpc'].getrawtransaction(txid))['outs'][i]['script']

def encode_offer(tx, desc=None):
    b64tx = b64e(unhexlify(tx))
    encoded = "----- BEGIN NAMETRADE OFFER -----\n"
    if desc:
        encoded += "# Description %s\n\n" % desc
    for i in xrange(0, len(b64tx), 64):
        enocded += b64tx[i:64]
    encoded += "----- END NAMETRADE OFFER -----\n"
    return encoded

def name_update_to_script(name, data, addr):
    return serialize_script([
        OP_NAME_UPDATE,
        hexlify(name),
        hexlify(data),
        OP_2DROP, OP_DROP,
        OP_DUP, OP_HASH160,
        b58check_to_hex(addr),
        OP_EQUALVERIFY, OP_CHECKSIG
    ])

def script_to_name_update(script):
    # XXX for now be strict about format
    opcodes = deserialize_script(script)
    name = unhexlify(opcodes[1])
    data = unhexlify(opcodes[2])
    addr = hex_to_b58check(opcodes[7])
    if script == name_update_to_script(name, data, addr):
        return AttrDict({'name':name, 'data':data, 'address':addr})
    else:
        raise ValueError("Malformed NAME_UPDATE script.")

def build_buy_offer(txid, vout, name, data, addr):
    txin = "%s:%u" % (txid, vout)
    # we need the name's last transaction to figure out the amount
    last = get_last_output(name)
    # generate a name_update script transfering the name to us
    script = name_update_to_script(name, data, addr)
    txout = {'value': int(last.amount*1e8), 'script': script}
    # build transaction
    tx_obj = deserialize(mktx(txin, txout))
    # mark it as a name transaction
    tx_obj['version'] = 0x7100
    # serialize for signing
    tx = serialize(tx_obj)
    return tx

def build_sell_offer(txid, vout, addr, amount):
    txin = "%s:%u" % (txid, vout)
    txout = {'value': int(amount*1e8), 'address': addr}
    # build transaction
    tx_obj = deserialize(mktx(txin, txout))
    # mark it as a name transaction
    tx_obj['version'] = 0x7100
    # serialize for signing (output script is fine)
    tx = serialize(tx_obj)
    return tx

def get_key_for_output(txid, vout):
    # XXX this will need to be smarter eventually to handle multisig
    addr = _nt['rpc'].getrawtransaction(txid, 1)['vout'][vout]['scriptPubKey']['addresses'][0]
    return _nt['rpc'].dumpprivkey(addr)

def get_last_output(name):
    history = filter(lambda x: 'expired' not in x, _nt['rpc'].name_history(name))
    txid = sorted(history, key=lambda x: x['expires_in'], reverse=True)[0]['txid']
    # we still need the vout
    for output in _nt['rpc'].getrawtransaction(txid, 1)['vout']:
        if 'nameOp' in output['scriptPubKey']:
            if output['scriptPubKey']['nameOp']['name'] == name:
                return AttrDict({
                    'txid': txid,
                    'vout': output['n'],
                    'amount': output['value']
                })
    raise ValueError("Could not find last output for '%s'!" % name)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='NameTrader')
    parser.add_argument('-c', '--config', type=str,
            dest='config',
            metavar='FILE',
            help='config file location')
    parser.add_argument('-o', '--offer', type=str,
            dest='infile',
            metavar='FILE',
            help='read offer from FILE')
    parser.add_argument('-b', '--buy', type=str,
            dest='buy',
            metavar='NAME',
            help='name to prepare a buy offer for')
    parser.add_argument('-s', '--sell', type=str,
            dest='sell',
            metavar='NAME',
            help='name to prepare a sell offer for')
    parser.add_argument('-a', '--amount', type=float,
            metavar='AMOUNT',
            help='amount of the offer in NMC')

    args = parser.parse_args();

    # set up namecoin rpc
    if args.config:
        rpc = asp_from_config(args.config)
    else:
        config = defaultconf()
        if config:
            print_stderr("Using config file '%s'" % config)
            rpc = asp_from_config(config)
        else:
            sys.exit("Could not find config file, try specifying it with -c")

    if args.buy and args.sell:
        sys.exit("An offer cannot be to both buy and sell.")

    # TODO - main program
    sys.exit(0)
