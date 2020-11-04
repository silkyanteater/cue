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

from const import *


req = requests.models.PreparedRequest()

jira_instance_url = None
jira_request_headers = None
queries_definition_file = None
result_files_dir = None
alert_sound_file = None
all_issues_file = None
all_issues_cache = None


class JiraIssue(object):

    def __init__(self, issue_obj):
        if 'fields' in issue_obj:
            self.raw_data = issue_obj
            fields = issue_obj['fields']
            sprints = list()
            for sprint in (fields['customfield_10104'] or tuple()):
                hit = sprint_re.search(sprint)
                if hit is not None:
                    sprints.append(hit.group())
            assert fields['project']['key'] == 'UI', f"Can't process a non-UI ticket, found '{fields['project']['key']}'"
            self.data = {
                'key': issue_obj['key'],
                'url': urllib.parse.urljoin(jira_instance_url, f"/browse/{issue_obj['key']}"),
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
                'updated': dateutil.parser.parse(fields['updated']),
                'updated_str': dateutil.parser.parse(fields['updated']).strftime('%m-%b-%Y'),
                'labels': sorted(fields['labels']),
                'labels_str': f"{', '.join(label.strip() for label in fields['labels'])}",
                'description': re.sub(r'\s+', ' ', (fields['description'] or '').strip()),
                'time_spent': fields['timespent'],
                'time_spent_str': f"{fields['timespent'] // 3600}:{(fields['timespent'] % 3600) // 60:02}" if fields['timespent'] is not None else "",
                'estimate': fields['timeestimate'],
                'estimate_str': f"{fields['timeestimate'] // 3600}:{(fields['timeestimate'] % 3600) // 60:02}" if fields['timeestimate'] is not None else "",
                'original_estimate': fields['timeoriginalestimate'],
                'original_estimate_str': f"{fields['timeoriginalestimate'] // 3600}:{(fields['timeoriginalestimate'] % 3600) // 60:02}" if fields['timeoriginalestimate'] is not None else "",
                'progress': fields['progress'],
                'project': (fields['customfield_13613'] or '').strip(),
                'fr': (fields['customfield_13611'] or '').strip(),
                'epic': (fields['customfield_10100'] or '').strip(),
                'story_points': str(fields['customfield_10106'] or ''),
                'sprints': sprints,
                'last_sprint': sprints[-1] if len(sprints) > 0 else '',
                'sprints_str': ', '.join(sprints),
                'parent': fields.get('parent', dict()).get('key', ''),
            }
            # TODO: add progress status, attachments
            # TODO: add a field as how old the data is
            # TODO: process non-UI tickets
            # TODO: parent issue doesn't come up for sub-tasks
            self.core_data = {key: self.data[key] for key, value in issue_display_keys}
            self.core_data['key'] = self.data['key']
        else:
            self.raw_data = self.core_data = dict(issue_obj)
            data = dict(issue_obj)
            data['sprints'] = [sprint.strip() for sprint in data['sprints_str'].split(',')]
            data['last_sprint'] = data['sprints'][-1] if len(data['sprints']) > 0 else ''
            self.data = data

    def __getattr__(self, attr):
        if attr in self.data:
            return self.data[attr]
        elif attr in self.core_data:
            return self.core_data[attr]
        else:
            raise KeyError(attr)

    def __str__(self):
        return f"{self.key} - {self.title}"

    def _get_formatted_fields(self, fields_definition, *, add_colors = True, add_empty = True, centered = True, expand_links = True, align_field_separator = False):

        def render_field(color, field_str, width, *, add_colors = True, centered = True):
            if centered:
                if add_colors and color is not None:
                    return f"{color}{field_str:^{width}}{CLR.reset}" if width > 0 else ''
                else:
                    return f"{field_str:^{width}}" if width > 0 else ''
            else:
                if add_colors and color is not None:
                    return f"{color}{field_str:{width}}{CLR.reset}" if width > 0 else ''
                else:
                    return f"{field_str:{width}}" if width > 0 else ''

        formatted_fields = list()
        for fields in fields_definition:
            if len(fields) == 4:
                key, width, default, color = fields
                insert_field_name = False
            elif len(fields) == 5:
                key, width, default, color, field_name_color = fields
                insert_field_name = True
            else:
                raise AssertionError(f"Field definition item is invalid: {fields}")
            attr = getattr(self, key)
            if not add_empty and not attr:
                continue
            attr = expand_issue_link(attr) if expand_links is True else attr
            _width = width if width > 0 else len(attr)
            field_str = ellipsis(attr, _width) if attr else default
            if add_colors is True and isinstance(color, (tuple, list)):
                default_color, color_switchers = color
                formatted_field = render_field(default_color, field_str, _width, add_colors=add_colors, centered=centered)
                for after_this, color_to_switch in color_switchers.items():
                    switch_position = formatted_field.find(after_this)
                    if switch_position >= 0:
                        insert_at_index = switch_position + len(after_this)
                        formatted_field = formatted_field[:insert_at_index] + color_to_switch + formatted_field[insert_at_index:]
            else:
                formatted_field = render_field(color, field_str, _width, add_colors=add_colors, centered=centered)
            if insert_field_name:
                field_name = [item[1] for item in issue_display_keys if item[0] == key][0]
                if align_field_separator is True:
                    if add_colors is False or field_name_color is None:
                        formatted_field = f"{field_name:>{display_key_len}}: {formatted_field}"
                    else:
                        formatted_field = f"{field_name_color}{field_name:>{display_key_len}}{CLR.reset}: {formatted_field}"
                else:
                    if add_colors is False or field_name_color is None:
                        formatted_field = f"{field_name}: {formatted_field}"
                    else:
                        formatted_field = f"{field_name_color}{field_name}{CLR.reset}: {formatted_field}"
            formatted_fields.append(formatted_field)
        return formatted_fields

    def format_oneline(self, add_colors = True):
        return f"{issue_fields_oneline_separator.join(self._get_formatted_fields(issue_fields_oneline, add_colors=add_colors, centered=False))}"

    def format_compact(self, add_colors = True):
        # TODO: show epic parent links
        format_str = f"{issue_fields_compact_head_separator.join(self._get_formatted_fields(issue_fields_compact_head, add_colors=add_colors, centered=False))}"
        for conditional_row in self._get_formatted_fields(issue_fields_compact_conditional_rows, add_colors=add_colors, add_empty=False, centered=False):
            format_str += f"\n  {conditional_row}"
        body_str = issue_fields_compact_body_separator.join(self._get_formatted_fields(issue_fields_compact_body, add_colors=add_colors))
        body_str = f"{issue_fields_compact_body_separator}{body_str}{issue_fields_compact_body_separator}".strip()
        format_str += f"\n  {body_str}"
        return format_str

    def format_long(self, *, add_colors = True, expand_links = True, align_field_separator = False):
        used_indentation = '' if align_field_separator is True else ' '*issue_fields_long_indent
        if add_colors is True:
            format_str = f"{issue_fields_long_key_color}{self.key}{CLR.reset}\n{used_indentation}"
        else:
            format_str = f"{self.key}\n{used_indentation}"
        format_str += ('\n' + used_indentation).join(self._get_formatted_fields(issue_fields_long, add_colors=add_colors, expand_links=expand_links, centered=False, align_field_separator=align_field_separator))
        return format_str

    def format(self, *, variant = None, add_colors = True, expand_links = True, align_field_separator = False):
        if variant == 'oneline':
            return self.format_oneline(add_colors=add_colors)
        elif variant == 'long':
            return self.format_long(add_colors=add_colors, expand_links=expand_links, align_field_separator=align_field_separator)
        else:
            return self.format_compact(add_colors=add_colors)


class JiraIssues(dict):

    def __init__(self, issues_data = None):
        super().__init__()
        if issues_data is None:
            return
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
        return sorted(self.values(), key=lambda issue: int(issue.key.split('-')[1]))

    def format(self, *, variant = None, add_colors = True, expand_links = True, add_separator_to_multiline = True, align_field_separator = False):
        if variant == 'oneline':
            return '\n'.join(issue.format(variant=variant, add_colors=add_colors, expand_links=expand_links) for issue in self.to_list())
        else:
            formatted_issues = tuple(issue.format(variant=variant, add_colors=add_colors, expand_links=expand_links, align_field_separator=align_field_separator) for issue in self.to_list())
            if add_separator_to_multiline is True and issue_fields_vertical_separator:
                if add_colors is True and issue_fields_vertical_separator_color is not None:
                    separator = f"{issue_fields_vertical_separator_color}{issue_fields_vertical_separator}{CLR.reset}"
                else:
                    separator = issue_fields_vertical_separator
                return separator + '\n' + f"\n{separator}\n".join(formatted_issues) + '\n' + separator
            else:
                return '\n'.join(formatted_issues)

    def filter(self, issure_refs):
        keys_to_remove = list()
        for key in self.keys():
            if key not in issure_refs:
                keys_to_remove.append(key)
        for key in keys_to_remove:
            del self[key]
        return self

    def update(self, issues):
        assert isinstance(issues, type(self)), f"JiraIssues type expected"
        for key, value in issues.items():
            self[key] = value
        return self


def init_lib():
    get_user_config()

def get_jira_data(url, *, query_params = None, headers = None):
    query_params = dict(query_params)
    query_params.update({'fields': ','.join(requested_issue_fields)})
    req.prepare_url(url, query_params)
    try:
        print(f"Sending request: {req.url}")
        resp = requests.get(url, params=query_params, headers=headers, allow_redirects=True, timeout=request_timeout_seconds)
    except Exception as e:
        raise AssertionError(str(e))
    except KeyboardInterrupt:
        raise AssertionError()
    if resp.status_code != 200:
        if resp.headers.get('X-Seraph-LoginReason') == 'AUTHENTICATED_FAILED':
            raise AssertionError(f"HTTP Error: {resp.status_code} - {requests.status_codes._codes.get(resp.status_code, ['N/A'])[0]} > check login credentials")
        elif resp.headers.get('X-Seraph-LoginReason') == 'AUTHENTICATION_DENIED':
            raise AssertionError(f"HTTP Error: {resp.status_code} - {requests.status_codes._codes.get(resp.status_code, ['N/A'])[0]} > try a browser login, captcha authentication may have been triggered")
        else:
            raise AssertionError(f"HTTP Error: {resp.status_code} - {requests.status_codes._codes.get(resp.status_code, ['N/A'])[0]}")
    try:
        response_json = json.loads(resp.content)
    except Exception as e:
        raise AssertionError(f"Error while loading json: {e}")
    if 'errorMessages' in response_json:
        raise AssertionError(f"Error: {', '.join(response_json.get('errorMessages', ('unspecified', )))}")
    return response_json

def search_issues(jql, *, maxResults = -1, startAt = None):
    # TODO: limit maxResults
    url = urllib.parse.urljoin(jira_instance_url, '/rest/api/2/search')
    query_params = {
        'jql': jql,
        'maxResults': maxResults,
    }
    if startAt is not None:
        query_params['startAt'] = startAt
    issues = JiraIssues(get_jira_data(url, query_params=query_params, headers=jira_request_headers)['issues'])
    update_all_issues_cache(issues)
    return issues

def get_jira_issues(jira_issue_refs):
    return search_issues(f"key in ({', '.join(jira_issue_refs)})")

def get_user_config():
    global jira_instance_url, jira_request_headers, queries_definition_file, result_files_dir, alert_sound_file, all_issues_file
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
    all_issues_file = user_config["all_issues_file"]
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

def get_active_query_names():
    return tuple(value['name'] for value in get_queries().values() if value.get('passive', False) is not True)

def write_issues(filename, issues):
    with open(os.path.join(result_files_dir, f"{filename}.txt"), 'w+') as txtfile:
        txtfile.write(issues.format(variant='long', add_colors=False, expand_links=False, add_separator_to_multiline = False))

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

def get_stored_issues_for_query(query_name):
    query_title, jql = get_query(query_name)
    query_file_path = os.path.join(result_files_dir, f"{query_title}.txt")
    text = ''
    if os.path.isfile(query_file_path):
        text = open(query_file_path).read()
    return JiraIssues(import_core_data_sets(text))

def load_all_issues_cache():
    global all_issues_cache
    if all_issues_cache is None:
        all_issues_file_path = os.path.join(result_files_dir, all_issues_file)
        text = ''
        if os.path.isfile(all_issues_file_path):
            text = open(all_issues_file_path).read()
        all_issues_cache = JiraIssues(import_core_data_sets(text))
    return all_issues_cache

def update_all_issues_cache(issues):
    all_issues_cache = load_all_issues_cache().update(issues)
    with open(os.path.join(result_files_dir, all_issues_file), 'w+') as txtfile:
        txtfile.write(all_issues_cache.format(variant='long', add_colors=False, expand_links=False, add_separator_to_multiline = False))

def get_updated_issues(issues, stored_issues):
    updated_issues = dict()
    for key, issue in issues.items():
        if key not in stored_issues or stored_issues[key].core_data != issue.core_data:
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

def convert_to_issue_ref(ref):
    issue_ref = re.sub(r"([a-zA-Z])(?=\d)", r"\1-", str(ref)).upper()
    if digits_re.match(issue_ref):
        issue_ref = "UI-" + issue_ref
    return issue_ref

def show_help():
    sys.stdout.write(help_text)

def get_format_option(quickparse):
    format = default_listing_format
    for option in quickparse.options:
        if option == '--oneline':
            format = 'oneline'
        elif option == '--compact':
            format = 'compact'
        elif option == '--long':
            format = 'long'
    return format

def play_sound(filename):
    if 'linux' in platform.system().lower():
        p = subprocess.Popen(['aplay', os.path.join(os.getcwd(), filename)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    else:
        p = subprocess.Popen(['afplay', os.path.join(os.getcwd(), filename)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    output, err = p.communicate()

def show_system_notification(message):
    os.system(f"notify-send '{message}'")

def alert_if_queue_not_empty():
    queue_file_path = os.path.join(result_files_dir, queue_file_name)
    if os.path.isfile(queue_file_path):
        queue_items = [line for line in open(queue_file_path).read().strip().split('\n') if len(line.strip()) > 0]
        if len(queue_items) > 0:
            if QUEUE_ALERT_PLAY_SOUND:
                if os.path.isfile(alert_sound_file):
                    play_sound('finealert.wav')
                elif alert_sound_file:
                    print(f"Alert sound file not found: {alert_sound_file}")
            if QUEUE_ALERT_SHOW_SYSTEM_NOTIFICATION:
                show_system_notification('\n'.join(queue_items))
            print(f"Queue length: {len(queue_items)}")
        else:
            print("Queue is empty")
    else:
        print("Queue is empty")

def ellipsis(string, length):
    if len(string) <= length or length <= 0:
        return string
    else:
        return f"{string[:length-1]}…"

def expand_issue_link(field):
    if issue_ref_re.match(field) is not None:
        issues_cache = load_all_issues_cache()
        if field in issues_cache:
            return f"{field} - {issues_cache[field].title}"
    return field

def add_extra_params(jql, quickparse):
    required_param_count = jql.count('%s')
    if required_param_count > 0:
        assert '--extra' in quickparse.options, f"Expected {required_param_count} extra parameters to substitute"
        extra_params = quickparse.options['--extra'].split(',')
        assert required_param_count == len(extra_params), f"Expected {required_param_count} extra parameters to substitute and got {len(extra_params)}"
        for extra_param in extra_params:
            jql = jql.replace('%s', convert_to_issue_ref(extra_param), 1)
        return jql
    else:
        assert '--extra' not in quickparse.options, f"No extra parameters required, got: {quickparse.options['--extra']}"
        return jql
