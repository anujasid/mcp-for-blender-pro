import json


def decode(text):
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0]
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError('Expected a JSON object')
    return result


def run(session, request, team):
    managers = [a for a in team if a.kind == 'manager']
    reviewers = [a for a in team if a.kind == 'reviewer']
    workers = {a.id: a for a in team if a.kind == 'worker'}
    if len(managers) != 1 or not reviewers or not workers:
        raise ValueError('Team needs exactly one manager, at least one worker and one reviewer')
    manager = managers[0]
    roster = [{'id': a.id, 'role': a.role, 'instructions': a.instructions} for a in workers.values()]
    session.status = manager.name + ': assigning tasks'
    plan = decode(session._run_agent(manager,
        'User request: ' + request + '\nWorkers: ' + json.dumps(roster) +
        '\nInspect the scene if necessary. Return only JSON: {"tasks":[{"id":"t1","worker":"worker id","goal":"specific task","acceptance":"verifiable criteria"}]}. '
        'Use 1 to 12 tasks in dependency order. Do not do worker tasks.', read_only=True))
    tasks = plan.get('tasks')
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 12:
        raise ValueError('Manager must assign 1 to 12 tasks')
    ids = set()
    for task in tasks:
        if not isinstance(task, dict) or not all(isinstance(task.get(k), str) and task[k].strip() for k in ['id', 'worker', 'goal', 'acceptance']):
            raise ValueError('Manager returned an invalid task')
        if task['id'] in ids or task['worker'] not in workers:
            raise ValueError('Duplicate task ID or unknown worker')
        ids.add(task['id'])
    session.tasks = [dict(task, status='queued', attempts=0, feedback='') for task in tasks]
    results = []
    for task in session.tasks:
        worker = workers[task['worker']]
        for attempt in range(2):
            if session.cancelled.is_set():
                task['status'] = 'cancelled'
                return
            task.update(status='working', attempts=attempt + 1)
            session.status = worker.name + ': ' + task['goal']
            prompt = json.dumps({'request': request, 'task': task, 'completed_tasks': results}, ensure_ascii=False)
            output = session._run_agent(worker, prompt)
            task['status'] = 'reviewing'
            feedback = []
            for reviewer in reviewers:
                if session.cancelled.is_set():
                    task['status'] = 'cancelled'
                    return
                session.status = reviewer.name + ': checking ' + task['id']
                verdict = decode(session._run_agent(reviewer,
                    prompt + '\nWorker report: ' + output +
                    '\nIndependently inspect Blender with read-only tools. Check acceptance criteria. '
                    'Return only JSON {"verdict":"APPROVED" or "BLOCK","findings":"evidence and specific corrections"}.', read_only=True))
                if verdict.get('verdict') not in {'APPROVED', 'BLOCK'} or not isinstance(verdict.get('findings'), str):
                    raise ValueError('Reviewer returned an invalid verdict')
                session.transcript.append(('review', reviewer.name + ': ' + json.dumps(verdict, ensure_ascii=False)))
                if verdict['verdict'] == 'BLOCK':
                    feedback.append(verdict['findings'])
            if not feedback:
                task['status'] = 'approved'
                results.append({'id': task['id'], 'result': output})
                break
            task['feedback'] = '\n'.join(feedback)
            task['status'] = 'rework' if attempt == 0 else 'blocked'
            if attempt == 1:
                raise RuntimeError('Review blocked task ' + task['id'] + ': ' + task['feedback'])
            session.transcript.append(('review', 'Returned to ' + worker.name + ': ' + task['feedback']))
    session.status = manager.name + ': final report'
    session._run_agent(manager, 'Summarize verified results for the user. Original request: ' + request +
                       '\nApproved tasks: ' + json.dumps(results, ensure_ascii=False), read_only=True)
