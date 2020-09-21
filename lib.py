import json
import requests
import urllib.parse
import yaml
import toml
import dateutil.parser
import re
import os
import sys
import subprocess
import platform

from const import (
    config_toml_file_name,
    required_config_keys,
    issue_display_keys,
    display_key_len,
    queue_file_name,
    request_timeout_seconds,
)


req = requests.models.PreparedRequest()

jira_instance_url = None
jira_request_headers = None
queries_definition_file = None
result_files_dir = None
alert_sound_file = None


class ANSIColors(object):

    reset = '\u001b[0m'

    black = '\u001b[30m'
    red = '\u001b[31m'
    green = '\u001b[32m'
    yellow = '\u001b[33m'
    blue = '\u001b[34m'
    magenta = '\u001b[35m'
    cyan = '\u001b[36m'
    white = '\u001b[37m'

    l_black = '\u001b[30;1m'
    l_red = '\u001b[31;1m'
    l_green = '\u001b[32;1m'
    l_yellow = '\u001b[33;1m'
    l_blue = '\u001b[34;1m'
    l_magenta = '\u001b[35;1m'
    l_cyan = '\u001b[36;1m'
    l_white = '\u001b[37;1m'


class JiraIssue(object):

    def __init__(self, issue_obj):
        self.raw_data = issue_obj
        if 'fields' in issue_obj:
            fields = issue_obj['fields']
            self.data = {
                'key': (issue_obj['key'] or '').strip(),
                'title': (fields['summary'] or '').strip(),
                'type': (fields['issuetype']['name'] or '').strip(),
                'assignee': (fields['assignee']['name'] or '').strip() if fields['assignee'] is not None else '',
                'status': (fields['status']['name'] or '').strip(),
                'resolution': (fields['resolution']['name'] or '').strip() if fields['resolution'] is not None else '',
                'target_version': (fields['customfield_13621'] or '').strip(),
                'git_branches': re.sub(r'\s+', ' ', fields['customfield_11207'] or '').strip(),
                'creator': (fields['creator']['name'] or '').strip(),
                'created': dateutil.parser.parse(fields['created']),
                'created_str': dateutil.parser.parse(fields['created']).strftime('%m-%b-%Y'),
                'labels': sorted(fields['labels']),
                'labels_str': f"{', '.join(label.strip() for label in fields['labels'])}",
                'description': re.sub(r'\s+', ' ', (fields['description'] or '').strip()),
            }
            self.core_data = {key: self.data[key] for key, value in issue_display_keys}
            self.core_data['key'] = self.data['key']
        else:
            self.data = self.core_data = issue_obj

    def __getattr__(self, attr):
        if attr in self.data:
            return self.data[attr]
        elif attr in self.core_data:
            return self.core_data[attr]
        else:
            raise KeyError(attr)

    def __str__(self):
        return f"{self.key} - {self.title}"

    def details(self, *, format = None, prefix = ''):
        if format == 'short':
            return str(self)
        elif format == 'long':
            return f'\n{prefix}'.join(f"{display_key:{display_key_len}} : {getattr(self, key)}" for key, display_key in issue_display_keys)
        else:
            return f"{self.key} - {self.title}\n  {self.assignee or 'unassigned'} | {self.status}"


class JiraIssues(dict):

    def __init__(self, issues_data):
        assert isinstance(issues_data, (list, dict)), f"Unrecognised issues data: {issues_data}"
        if isinstance(issues_data, list):
            for issue_obj in issues_data:
                issue = JiraIssue(issue_obj)
                self[issue.key] = issue
        else:
            for issue_key, issue_dict in issues_data.items():
                full_issue_dict = dict(issue_dict)
                full_issue_dict.update({'key': issue_key})
                issue = JiraIssue(full_issue_dict)
                self[issue.key] = issue

    def __str__(self):
        return '\n'.join(str(issue) for issue in self.values())

    def to_list(self):
        return sorted(self.values(), key=lambda issue: issue.key, reverse=True)

    def details(self, *, format = None):
        if format == 'long':
            return ''.join(f"{issue.key}\n    {issue.details(format=format, prefix='    ')}\n" for issue in self.to_list())
        else:
            return '\n'.join(issue.details(format=format) for issue in self.to_list())


def init_lib():
    get_user_config()

def get_jira_data(url, headers = None):
    try:
        if headers is None:
            resp = requests.get(url, allow_redirects=True, timeout=request_timeout_seconds)
        else:
            resp = requests.get(url, headers=headers, allow_redirects=True, timeout=request_timeout_seconds)
    except Exception as e:
        raise AssertionError(str(e))
    except KeyboardInterrupt:
        raise AssertionError()
    try:
        response_json = json.loads(resp.content)
    except:
        raise AssertionError(f"Error while loading json:\n{resp.content}")
    if 'errorMessages' in response_json:
        raise AssertionError(f"Error: {', '.join(response_json.get('errorMessages', ('unspecified', )))}")
    return response_json

def search_issues(jql, *, maxResults = -1, startAt = None):
    url = urllib.parse.urljoin(jira_instance_url, '/rest/api/2/search')
    queryparams = {
        'jql': jql,
        'maxResults': maxResults,
    }
    if startAt is not None:
        queryparams['startAt'] = startAt
    req.prepare_url(url, queryparams)
    return get_jira_data(req.url, headers=jira_request_headers)

def get_jira_issues(jira_issue_refs):
    return search_issues(f"key in ({', '.join(jira_issue_refs)})")

def get_user_config():
    global jira_instance_url, jira_request_headers, queries_definition_file, result_files_dir, alert_sound_file
    assert os.path.isfile(config_toml_file_name), f"Config file '{config_toml_file_name}' not found"
    user_config = toml.loads(open(config_toml_file_name).read())
    for required_key in required_config_keys:
        assert required_key in user_config, f"Key missing from {config_toml_file_name}: {required_key}"
    jira_instance_url = user_config["jira_instance_url"]
    key_file_path = user_config["jira_key_file"]
    assert os.path.isfile(key_file_path), f"Key file '{key_file_path}' not found"
    jira_request_headers = {
        'Authorization': f'Basic {open(key_file_path).read().strip()}',
        'Content-Type': 'application/json',
    }
    queries_definition_file = user_config["queries_definition_file"]
    result_files_dir = user_config["result_files_dir"]
    alert_sound_file = user_config["alert_sound_file"]
    if not os.path.isdir(result_files_dir):
        os.mkdir(result_files_dir)
    return user_config

def get_queries():
    get_user_config()
    queries = yaml.safe_load(open(queries_definition_file).read())
    return queries

def get_query(query_name):
    queries = [(key, value) for key, value in get_queries().items() if value['name'] == query_name]
    assert len(queries) > 0, f"Command '{query_name}' not found in '{queries_definition_file}'"
    assert len(queries) <= 1, f"Duplicate command '{query_name}' found in '{queries_definition_file}'"
    return queries[0][0], queries[0][1]['jql']

def get_all_query_names():
    return tuple(value['name'] for value in get_queries().values())

def write_issues(filename, issues):
    with open(os.path.join(result_files_dir, f"{filename}.txt"), 'w+') as txtfile:
        txtfile.write(issues.details(format='long'))

def import_core_data_of_issue(issue_text):
    core_data = dict()
    lines = [line.strip() for line in issue_text.split('\n')]
    core_data['key'] = lines[0]
    for line in lines[1:]:
        if len(line.strip()) == 0:
            continue
        display_key, value = [item.strip() for item in line.split(':', 1)]
        keys = [item[0] for item in issue_display_keys if item[1] == display_key]
        assert len(keys) > 0, f"Field '{display_key}' not recognised for issue {core_data['key']}"
        core_data[keys[0]] = value
    return core_data

def import_core_data_sets(text):
    if text.strip() == '':
        return dict()
    core_data_sets = dict()
    for issue_text in re.split(r'\n(?=\S)', text):
        core_data = import_core_data_of_issue(issue_text)
        core_data_sets[core_data['key']] = core_data
    return core_data_sets

def get_stored_core_data_for_query(query_name):
    query_title, jql = get_query(query_name)
    query_file_path = os.path.join(result_files_dir, f"{query_title}.txt")
    text = ''
    if os.path.isfile(query_file_path):
        text = open(query_file_path).read()
    return import_core_data_sets(text)

def get_updated_issues(issues, stored_data_set):
    updated_issues = dict()
    for key, issue in issues.items():
        if key not in stored_data_set or stored_data_set[key] != issue.core_data:
            updated_issues[key] = issue
    return updated_issues

def write_queue(queue_lines, *, append = False):
    file_mode = 'a+' if append is True else 'w+'
    if file_mode == 'w+' or len(queue_lines) > 0:
        with open(os.path.join(result_files_dir, queue_file_name), file_mode) as queuefile:
            if len(queue_lines) > 0:
                queuefile.write('\n'.join(queue_lines) + '\n')
            else:
                queuefile.write('')

def update_queue(query_title, updated_issues):
    queue_items = [f"{query_title} -- {str(issue)}" for key, issue in updated_issues.items()]
    write_queue(queue_items, append=True)

def load_queue():
    queue_file_path = os.path.join(result_files_dir, queue_file_name)
    queue_content = ''
    if os.path.isfile(queue_file_path):
        queue_content = open(queue_file_path).read().strip()
    return queue_content

def step_through_queue():
    queue_lines = [line.strip() for line in load_queue().split('\n') if len(line.strip()) > 0]
    if len(queue_lines) > 0:
        remaining_lines = list()
        resp = None
        for line in queue_lines:
            if resp != 'all skipped':
                resp = None
            while resp not in ('', 's', 'd', 'q', 'all skipped'):
                resp = input(f"{line}  |  S(kip) d(one) q(uit) > ").lower()
            if resp in ('', 's', 'q', 'all skipped'):
                remaining_lines.append(line)
            if resp == 'q':
                resp = 'all skipped'
            elif resp == 'd':
                pass
        write_queue(remaining_lines)
    else:
        print("Queue is empty")

def print_queue():
    queue_content = load_queue()
    if len(queue_content) > 0:
        print(queue_content)
    else:
        print("Queue is empty")

def normalise_issue_ref(issue_ref):
    return re.sub(r"([a-zA-z])(?=\d)", r"\1-", issue_ref).upper()

def show_help():
    sys.stdout.write(help_text)

def get_format_option(quickparse):
    format = None
    for option in quickparse.options:
        if option == '--short':
            format == 'short'
        elif option == '--long':
            format == 'long'
    return format

def play_sound(filename):
    if 'linux' in platform.system().lower():
        p = subprocess.Popen(['aplay', os.path.join(os.getcwd(), filename)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    else:
        p = subprocess.Popen(['afplay', os.path.join(os.getcwd(), filename)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    output, err = p.communicate()

def sound_alert_if_queue_not_empty():
    queue_file_path = os.path.join(result_files_dir, queue_file_name)
    if os.path.isfile(queue_file_path):
        queue_items = [line for line in open(queue_file_path).read().strip().split('\n') if len(line.strip()) > 0]
        if len(queue_items) > 0:
            if os.path.isfile(alert_sound_file):
                play_sound('finealert.wav')
            elif alert_sound_file:
                print(f"Alert sound file not found: {alert_sound_file}")
            print(f"Queue length: {len(queue_items)}")
        else:
            print("Queue is empty")
    else:
        print("Queue is empty")
