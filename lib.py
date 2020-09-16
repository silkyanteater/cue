import json
import requests
import urllib.parse
import yaml
import toml
import dateutil.parser
import re
import os
from collections import OrderedDict

req = requests.models.PreparedRequest()

config_toml_file_path = 'config.toml'

required_config_keys = (
    'jira_instance_url',
    'jira_key_file',
    'queries_definition_file',
    'result_files_dir',
)

valid_commands = (
    'x',
    'c',
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
    return JiraIssue(_get_jira_data(url, jira_request_headers))

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

def get_query(query_name):
    queries = [(key, value) for key, value in _get_queries().items() if value['name'] == query_name]
    assert len(queries) > 0, f"Command '{query_name}' not found in '{queries_definition_file}'"
    assert len(queries) <= 1, f"Duplicate command '{query_name}' found in '{queries_definition_file}'"
    return queries[0][0], queries[0][1]['jql']

def issue_details(issue, *, prefix = ''):
    return f'\n{prefix}'.join(f"{key:14} : {value}" for key, value in issue.normalise().items())

def issues_details(issues):
    content = ''
    for issue in issues.to_list():
        content += f"{issue.key()}\n    {issue_details(issue, prefix='    ')}\n"
    return content

def write_issues(filename, issues):
    with open(os.path.join(result_files_dir, f"{filename}.txt"), 'w+') as txtfile:
        txtfile.write(issues_details(issues))
        # yaml.safe_dump(issues.normalise(), yamlfile, explicit_start=True, default_style='\"', width=4096)


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
        self.data = issue_obj

    def __str__(self):
        return f"{self.key()} - {self.title()}"

    def key(self):
        return self.data['key']

    def title(self):
        return self.data['fields']['summary']

    def assignee(self):
        return self.data['fields']['assignee']['name']

    def status(self):
        return self.data['fields']['status']['name']

    def resolution(self):
        res = self.data['fields']['resolution']
        return res['name'] if res is not None else ''

    def labels(self):
        return self.data['fields']['labels']

    def labels_str(self):
        return f"[{', '.join(label for label in self.labels())}]"

    def issue_type(self):
        return self.data['fields']['issuetype']['name']

    def description(self):
        return re.sub(r'\s+', ' ', self.data['fields']['description'])

    def git_branches(self):
        return re.sub(r'\s+', ' ', self.data['fields']['customfield_11207'] or '')

    def creator(self):
        return self.data['fields']['creator']['name']

    def created(self):
        return dateutil.parser.parse(self.data['fields']['created'])

    def target_version(self):
        return self.data['fields']['customfield_13621'] or ''

    def normalise(self):
        details = OrderedDict()
        # details['key'] = self.key()
        details['title'] = self.title()
        details['type'] = self.issue_type()
        details['assignee'] = self.assignee()
        details['status'] = self.status()
        details['resolution'] = self.resolution()
        details['target version'] = self.target_version()
        details['GIT branches'] = self.git_branches()
        details['created'] = self.created().strftime('%m-%b-%Y')
        details['labels'] = self.labels_str()
        # details['description'] = self.description()
        return details


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
