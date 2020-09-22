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
