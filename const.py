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

issue_display_keys = (
    ('title', 'Title'),
    ('type', 'Type'),
    ('assignee', 'Assignee'),
    ('status', 'Status'),
    ('resolution', 'Resolution'),
    ('target_version', 'Target version'),
    ('git_branches', 'Git branches'),
    ('created_str', 'Created'),
    ('labels_str', 'Labels'),
)
display_key_len = max(len(item[1]) for item in issue_display_keys)