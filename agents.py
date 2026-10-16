import json
import threading
from dataclasses import asdict, dataclass

from .core import util


@dataclass
class Agent:
    id: str
    name: str
    role: str
    instructions: str
    provider: str = ''
    model: str = ''
    parent: str = ''
    enabled: bool = True
    kind: str = 'worker'


DEFAULT = [
    Agent('director', 'Director', 'Creative Director', 'Break the request into tasks with acceptance criteria.', kind='manager'),
    Agent('scene', 'Scene Builder', 'Modeling and scene assembly', 'Create and arrange geometry, cameras and lights.', parent='director'),
    Agent('lookdev', 'Look Developer', 'Materials and lighting', 'Improve materials, color, lighting and presentation.', parent='director'),
    Agent('reviewer', 'Reviewer', 'Quality control', 'Inspect the scene and report concrete problems or improvements.', parent='director', kind='reviewer'),
]
lock = threading.RLock()
_agents = {}


def _load():
    global _agents
    prefs = util.prefs()
    raw = prefs.agent_team_json if prefs else ''
    try:
        values = json.loads(raw) if raw else [asdict(agent) for agent in DEFAULT]
        loaded = {value['id']: Agent(**value) for value in values}
        for value in values:
            if 'kind' not in value and value['id'] in {'director', 'reviewer'}:
                loaded[value['id']].kind = 'manager' if value['id'] == 'director' else 'reviewer'
        validate(loaded)
        _agents = loaded
    except Exception:
        _agents = {agent.id: agent for agent in DEFAULT}


def all_agents():
    with lock:
        if not _agents:
            _load()
        return [Agent(**asdict(agent)) for agent in _agents.values()]


def save(values=None):
    global _agents
    with lock:
        if values is not None:
            validate(values)
            _agents = dict(values)
        prefs = util.prefs()
        if prefs:
            prefs.agent_team_json = json.dumps([asdict(agent) for agent in _agents.values()], ensure_ascii=False)


def validate(values):
    if not values:
        raise ValueError('Team needs at least one agent')
    for key, agent in values.items():
        if agent.kind not in {'manager', 'worker', 'reviewer'}:
            raise ValueError('Unknown agent kind')
        if key != agent.id or not agent.name.strip() or not agent.role.strip():
            raise ValueError('Every agent needs a unique id, name and role')
        if agent.parent == agent.id:
            raise ValueError(f'Agent {agent.name} cannot report to itself')
        if agent.parent and agent.parent not in values:
            raise ValueError(f'Parent {agent.parent} does not exist')
    for key in values:
        seen = set()
        current = key
        while current:
            if current in seen:
                raise ValueError('Team hierarchy contains a cycle')
            seen.add(current)
            current = values[current].parent


def update(value):
    with lock:
        values = {agent.id: agent for agent in all_agents()}
        if value['id'] not in values:
            values[value['id']] = Agent(value['id'], value['name'], value['role'], value.get('instructions', ''), value.get('provider', ''), value.get('model', ''), value.get('parent', ''), value.get('enabled', True))
        else:
            values[value['id']] = Agent(value['id'], value['name'], value['role'], value.get('instructions', ''), value.get('provider', ''), value.get('model', ''), value.get('parent', ''), value.get('enabled', True))
        values[value['id']].kind = value.get('kind', 'worker')
        save(values)


def remove(agent_id):
    with lock:
        values = {agent.id: agent for agent in all_agents()}
        if agent_id not in values:
            return
        for agent in values.values():
            if agent.parent == agent_id:
                agent.parent = values[agent_id].parent
        del values[agent_id]
        save(values)


def chain():
    all_values = {agent.id: agent for agent in all_agents()}
    validate(all_values)
    values = {key: agent for key, agent in all_values.items() if agent.enabled}
    ordered = []
    def visit(agent):
        if agent.enabled:
            ordered.append(agent)
        for child in all_values.values():
            if child.parent == agent.id:
                visit(child)
    roots = [agent for agent in all_values.values() if not agent.parent]
    for root in roots:
        visit(root)
    if not ordered:
        raise ValueError('Enable at least one agent')
    return ordered
