import json
import requests
import urllib.parse
import yaml
import toml
import dateutil.parser
import re
import os

from const import (
    config_toml_file_name,
    required_config_keys,
    issue_display_keys,
    display_key_len,
    queue_file_name,
)


req = requests.models.PreparedRequest()

jira_instance_url = None
jira_request_headers = None
queries_definition_file = None
result_files_dir = None


def init_lib():
    get_user_config()

def get_jira_data(url, headers = None):
    if headers is None:
        resp = requests.get(url, allow_redirects=True)
    else:
        resp = requests.get(url, headers=headers, allow_redirects=True)
    return json.loads(resp.content)

def get_jira_issue(jira_issue):
    url = urllib.parse.urljoin(jira_instance_url, f'/rest/api/2/issue/{jira_issue}')
    return JiraIssue(get_jira_data(url, jira_request_headers))

def search_issues(jql, *, maxResults = -1, startAt = None):
    data_url = urllib.parse.urljoin(jira_instance_url, '/rest/api/2/search')
    queryparams = {
        'jql': jql,
        'maxResults': maxResults,
    }
    if startAt is not None:
        queryparams['startAt'] = startAt
    req.prepare_url(data_url, queryparams)
    resp = requests.get(req.url, headers=jira_request_headers, allow_redirects=True)
    return json.loads(resp.content)

def get_user_config():
    global jira_instance_url, jira_request_headers, queries_definition_file, result_files_dir
    user_config = toml.loads(open(config_toml_file_name).read())
    for required_key in required_config_keys:
        assert required_key in user_config, f"Key missing from {config_toml_file_name}: {required_key}"
    jira_instance_url = user_config["jira_instance_url"]
    jira_request_headers = {
        'Authorization': f'Basic {open(user_config["jira_key_file"]).read().strip()}',
        'Content-Type': 'application/json',
    }
    queries_definition_file = user_config["queries_definition_file"]
    result_files_dir = user_config["result_files_dir"]
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

def issue_details(issue, *, prefix = ''):
    return f'\n{prefix}'.join(f"{display_key:{display_key_len}} : {getattr(issue, key)}" for key, display_key in issue_display_keys)

def issues_details(issues):
    content = ''
    for issue in issues.to_list():
        content += f"{issue.key}\n    {issue_details(issue, prefix='    ')}\n"
    return content

def write_issues(filename, issues):
    with open(os.path.join(result_files_dir, f"{filename}.txt"), 'w+') as txtfile:
        txtfile.write(issues_details(issues))

def import_core_data_of_issue(issue_text):
    core_data = dict()
    lines = [line.strip() for line in issue_text.split('\n')]
    core_data['key'] = lines[0]
    for line in lines[1:]:
        if len(line.strip()) == 0:
            continue
        display_key, value = [item.strip() for item in line.split(':', 1)]
        key = [item[0] for item in issue_display_keys if item[1] == display_key][0]
        core_data[key] = value
    return core_data

def import_core_data_sets(text):
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

def update_queue(query_title, updated_issues):
    queue_items = [f"{query_title} -- {str(issue)}" for key, issue in updated_issues.items()]
    if len(queue_items) > 0:
        with open(os.path.join(result_files_dir, queue_file_name), 'a+') as queuefile:
            queuefile.write('\n'.join(queue_items) + '\n')

def print_queue():
    queue_file_path = os.path.join(result_files_dir, queue_file_name)
    queue_content = ''
    if os.path.isfile(queue_file_path):
        queue_content = open(queue_file_path).read().strip()
    if len(queue_content) > 0:
        print(queue_content)
    else:
        print("Queue is empty")


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
        fields = issue_obj['fields']
        self.data = {
            'key': issue_obj['key'].strip(),
            'title': fields['summary'].strip(),
            'type': fields['issuetype']['name'].strip(),
            'assignee': fields['assignee']['name'].strip(),
            'status': fields['status']['name'].strip(),
            'resolution': fields['resolution']['name'].strip() if fields['resolution'] is not None else '',
            'target_version': (fields['customfield_13621'] or '').strip(),
            'git_branches': re.sub(r'\s+', ' ', fields['customfield_11207'] or '').strip(),
            'creator': fields['creator']['name'].strip(),
            'created': dateutil.parser.parse(fields['created']),
            'created_str': dateutil.parser.parse(fields['created']).strftime('%m-%b-%Y'),
            'labels': fields['labels'],
            'labels_str': f"{', '.join(label.strip() for label in fields['labels'])}",
            'description': re.sub(r'\s+', ' ', fields['description'].strip()),
        }
        self.core_data = {key: self.data[key] for key, value in issue_display_keys}
        self.core_data['key'] = self.data['key']

    def __getattr__(self, attr):
        if attr in self.data:
            return self.data[attr]
        else:
            raise KeyError(attr)

    def __str__(self):
        return f"{self.key} - {self.title}"


class JiraIssues(dict):

    def __init__(self, issues_list):
        for issue_obj in issues_list:
            issue = JiraIssue(issue_obj)
            self[issue.key] = issue

    def __str__(self):
        return '\n'.join(str(issue) for issue in self.values())

    def to_list(self):
        return sorted(self.values(), key=lambda issue: issue.key, reverse=True)
