import json
import requests
import urllib.parse
import yaml
import toml
import dateutil.parser
import re
import os

req = requests.models.PreparedRequest()

config_toml_file_path = 'config.toml'

required_config_keys = (
    'jira_instance_url',
    'jira_key_file',
    'queries_definition_file',
    'result_files_dir',
)

jira_instance_url = None
jira_request_headers = None
queries_definition_file = None
result_files_dir = None


def init_lib():
    get_user_config()

def _get_jira_data(url, headers = None):
    if headers is None:
        resp = requests.get(url, allow_redirects=True)
    else:
        resp = requests.get(url, headers=headers, allow_redirects=True)
    return json.loads(resp.content)

def get_jira_issue(jira_issue):
    url = urllib.parse.urljoin(jira_instance_url, f'/rest/api/2/issue/{jira_issue}')
    return _get_jira_data(url, jira_request_headers)

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
    user_config = toml.loads(open(config_toml_file_path).read())
    for required_key in required_config_keys:
        assert required_key in user_config, f"Key missing from {config_toml_file_path}: {required_key}"
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

def _get_queries():
    get_user_config()
    queries = yaml.safe_load(open(queries_definition_file).read())
    return queries

def get_command(command):
    commands = [(key, value) for key, value in _get_queries().items() if value['command'] == command]
    assert len(commands) > 0, f"Command '{command}' not found in '{queries_definition_file}'"
    assert len(commands) <= 1, f"Duplicate command '{command}' found in '{queries_definition_file}'"
    return commands[0][0], commands[0][1]['jql']

def write_issues(filename, issues):
    with open(os.path.join(result_files_dir, f"{filename}.yaml"), 'w+') as yamlfile:
        yaml.safe_dump(issues.normalise(), yamlfile, explicit_start=True, default_style='\"', width=4096)


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
        self.issue_obj = issue_obj

    def __str__(self):
        return f"{self.key()} - {self.title()}"

    def key(self):
        return self.issue_obj['key']

    def title(self):
        return self.issue_obj['fields']['summary']

    def assignee(self):
        return self.issue_obj['fields']['assignee']['name']

    def status(self):
        return self.issue_obj['fields']['status']['name']

    def resolution(self):
        return self.issue_obj['fields']['resolution']

    def labels(self):
        return self.issue_obj['fields']['labels']

    def issue_type(self):
        return self.issue_obj['fields']['issuetype']['name']

    def description(self):
        return re.sub(r'\s+', ' ', self.issue_obj['fields']['description'])

    def git_branches(self):
        return re.sub(r'\s+', ' ', self.issue_obj['fields']['customfield_11207'])

    def creator(self):
        return self.issue_obj['fields']['creator']['name']

    def created(self):
        return dateutil.parser.parse(self.issue_obj['fields']['created'])

    def normalise(self):
        return {
            'key': self.key(),
            'title': self.title(),
            'assignee': self.assignee(),
            'status': self.status(),
            'resolution': self.resolution(),
            'labels': self.labels(),
            'type': self.issue_type(),
            'description': self.description(),
            'GIT branches': self.git_branches(),
            'created': self.created().strftime('%m-%b-%Y'),
        }


class JiraIssues(dict):

    def __init__(self, issues_list):
        for issue_obj in issues_list:
            issue = JiraIssue(issue_obj)
            self[issue.key()] = issue

    def __str__(self):
        return '\n'.join(str(issue) for issue in self.values())

    def to_list(self):
        return sorted(self.values(), key=lambda issue: issue.key(), reverse=True)

    def normalise(self):
        return {issue.key(): issue.normalise() for issue in self.to_list()}
