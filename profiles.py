import json
import uuid

from .core import util

FIELDS = ('provider', 'model', 'custom_url', 'custom_protocol', 'ollama_url')


def records():
    return json.loads(util.prefs().connection_profiles or '[]')


def public_records():
    return [{k: v for k, v in row.items() if k != 'key'} for row in records()]


def save(name):
    prefs = util.prefs()
    if not name.strip():
        raise ValueError('Enter a profile name')
    rows = records()
    row = {'id': uuid.uuid4().hex, 'name': name.strip(), 'key': prefs.key_for(prefs.provider)}
    row.update({field: getattr(prefs, field) for field in FIELDS})
    rows.append(row)
    prefs.connection_profiles = json.dumps(rows, ensure_ascii=False)
    return row['id']


def activate(identifier):
    prefs = util.prefs()
    row = next((row for row in records() if row['id'] == identifier), None)
    if row is None:
        raise ValueError('Profile not found')
    prefs.provider = row['provider']
    for field in FIELDS[1:]:
        setattr(prefs, field, row[field])
    if row['provider'] != 'ollama':
        setattr(prefs, row['provider'] + '_key', row['key'])


def remove(identifier):
    util.prefs().connection_profiles = json.dumps([r for r in records() if r['id'] != identifier], ensure_ascii=False)
