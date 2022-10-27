#!/usr/bin/env python3

import sys
import psij
import json
import time
import requests
import websocket
import threading

url = sys.argv[1].rstrip('/')
rep = requests.get('%s/executor/local' % url)
cid = str(rep.json())

print('cid: %s' % rep.json())


def hello(cid: str):
    ws_url = url.replace('http', 'ws')
    print(ws_url)
    ws = websocket.create_connection(ws_url + '/ws/' + cid)
    print('ws: ', ws)
    while True:
        msg = json.loads(ws.recv())
        print('==>', msg)


print('before ws')
t = threading.Thread(target=hello, args=[cid])
t.daemon = True
t.start()
print('after ws')

spec = psij.Export().to_dict(psij.JobSpec(executable='/bin/date'))
rep = requests.put('%s/%s' % (url, cid), json=spec)
jid = rep.json()
print('=== submit: %s' % jid)

spec = psij.Export().to_dict(psij.JobSpec(executable='/bin/sleep', arguments=['3']))
rep = requests.put('%s/%s' % (url, cid), json=spec)
jid = rep.json()
print('=== submit: %s' % jid)

rep = requests.get('%s/%s/jobs' % (url, cid))
print('=== list: %s' % rep.json())

rep = requests.delete('%s/%s/%s' % (url, cid, jid))
print('=== del: %s' % rep.json())

rep = requests.get('%s/%s/jobs' % (url, cid))
print('=== list: %s' % rep.json())

time.sleep(2)

