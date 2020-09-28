class CLR(object):

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


config_toml_file_name = 'config.toml'

required_config_keys = (
    'jira_instance_url',
    'jira_key_file',
    'queries_definition_file',
    'result_files_dir',
    'alert_sound_file',
    'all_issues_file',
)

issue_display_keys = (
    ('title', 'Title'),
    ('assignee', 'Assignee'),
    ('status', 'Status'),
    ('type', 'Type'),
    ('parent', 'Parent'),
    ('epic', 'Epic'),
    ('story_points', 'Story points'),
    ('sprints_str', 'Sprints'),
    ('resolution', 'Resolution'),
    ('target_version', 'Target version'),
    ('git_branches', 'Git branches'),
    ('created_str', 'Created'),
    ('labels_str', 'Labels'),
    ('time_spent_str', 'Time spent'),
    ('original_estimate_str', 'Estimate'),
)
display_key_len = max(len(item[1]) for item in issue_display_keys)

issue_fields_compact_head = (
    ('key', 7, '', CLR.l_yellow),
    ('title', 125, '', CLR.l_white),
)
issue_fields_compact_head_separator = ' - '
issue_fields_compact_parent = (125, '', CLR.l_cyan)
issue_fields_compact_epic = (125, '', CLR.l_cyan)
issue_fields_compact_body = (
    ('assignee', 16, 'unassigned', CLR.green),
    ('type', 8, '', CLR.l_blue),
    ('status', 21, '', CLR.l_red),
    ('resolution', 10, 'unresolved', CLR.l_black),
    ('last_sprint', 7, 'backlog', CLR.cyan),
    ('target_version', 9, 'no target', CLR.magenta),
    ('time_spent_str', 7, '0', CLR.l_yellow),
    ('original_estimate_str', 7, '0', CLR.l_magenta),
    ('git_branches', 77, '', CLR.cyan),
)
issue_fields_compact_body_separator = ' | '
issue_fields_compact_vertical_separator = '-'*125

queue_file_name = 'queue.txt'

request_timeout_seconds = 120

help_text = ''' -- Jira integration CLI --
cue x <command from query definition>
   run query, update content in results, update queue
cue c <issue reference>
   see issue details
cue ls
   see queue
cue q
   step through queue and remove items when done'''
