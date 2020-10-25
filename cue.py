import traceback
import shlex
from cmd import Cmd
import os
import sys
import webbrowser

from quickparse import QuickParse

from lib import *


def init():
    init_lib()

def exit_cue():
    raise EOFError()

def handle_no_command(quickparse):
    cli_input = ' '.join(quickparse.args)
    if len(quickparse.args) > 0 and cli_input.startswith('.'):
        if cli_input.startswith('.cd'):
            try:
                os.chdir(cli_input[4:])
            except Exception as e:
                print(e)
        else:
            os.system(cli_input[1:])
    else:
        assert len(quickparse.args) == 0, f"Unknown command: {' '.join(quickparse.args)}"

def execute_command(quickparse):
    incoming_query_names = [str(param) for param in quickparse.parameters]
    all_query_names = get_all_query_names()
    active_query_names = get_active_query_names()
    assert len(quickparse.parameters) >= 1 or '--all' in quickparse.options, f"Query name expected - available: {', '.join(all_query_names)}"
    unknown_query_names = [query_name for query_name in incoming_query_names if query_name not in all_query_names]
    assert len(unknown_query_names) == 0, f"Unknown query names: {', '.join(unknown_query_names)}"
    if '--all' in quickparse.options:
        query_names = set(active_query_names)
        query_names.update(incoming_query_names)
    else:
        query_names = incoming_query_names
    for query_name in query_names:
        stored_issues = get_stored_issues_for_query(query_name)
        if len(stored_issues) == 0 or '--refresh' in quickparse.options:
            query_title, jql = get_query(query_name)
            # TODO: make extra params work with multiple query names
            issues = search_issues(add_extra_params(jql, quickparse))
            update_queue(query_title, get_updated_issues(issues, stored_issues))
            write_issues(query_title, issues)
        else:
            issues = stored_issues
        if len(issues) > 0:
            update_all_issues_cache(issues)
            print(issues.format(variant=get_format_option(quickparse), add_colors=sys.stdout.isatty(), add_separator_to_multiline=sys.stdout.isatty(), expand_links=True, align_field_separator = True))
        else:
            print(f"{query_title}: no issues found")

def execute_query(quickparse):
    assert len(quickparse.parameters) > 0, 'Query expected'
    assert len(quickparse.parameters) == 1, 'Too many parameters'
    issues = search_issues(quickparse.parameters[0])
    update_all_issues_cache(issues)
    print(issues.format(variant=get_format_option(quickparse), add_colors=sys.stdout.isatty(), add_separator_to_multiline=sys.stdout.isatty(), expand_links=True, align_field_separator = True))

def search_issues_by_text(quickparse):
    assert len(quickparse.parameters) > 0, 'Keywords are expected'
    keywords = ' '.join(quickparse.parameters)
    jql = f'text ~ "{keywords}"'
    if '--project' in quickparse.options:
        jql += f" and project={quickparse.options['--project'].upper()}"
    issues = search_issues(jql)
    update_all_issues_cache(issues)
    print(issues.format(variant=get_format_option(quickparse), add_colors=sys.stdout.isatty(), add_separator_to_multiline=sys.stdout.isatty(), expand_links=True, align_field_separator = True))

def show_issue(quickparse):
    assert len(quickparse.parameters) >= 1, f"Issue reference is missing"
    jira_issue_refs = [convert_to_issue_ref(ref) for ref in quickparse.parameters]
    if '--refresh' in quickparse.options:
        issues = get_jira_issues(jira_issue_refs)
    else:
        cache_issues = JiraIssues().update(load_all_issues_cache()).filter(jira_issue_refs)
        new_issue_refs = [issue_ref for issue_ref in jira_issue_refs if issue_ref not in cache_issues]
        new_issues = JiraIssues()
        if len(new_issue_refs) > 0:
            new_issues = get_jira_issues(jira_issue_refs)
        issues = JiraIssues().update(cache_issues).update(new_issues)
    update_all_issues_cache(issues)
    print(issues.format(variant=get_format_option(quickparse), add_colors=sys.stdout.isatty(), add_separator_to_multiline=sys.stdout.isatty(), expand_links=True, align_field_separator = True))

def open_issue_in_browser(quickparse):
    assert len(quickparse.parameters) >= 1, f"Issue reference is missing"
    for ref in (convert_to_issue_ref(ref) for ref in quickparse.parameters):
        webbrowser.open(f"https://jira.pbs.one/browse/{ref}")

# TODO: add a command to list all queries
# TODO: add a command to update all queries that are older than a certain time and not passive
# TODO: truncate output at the end of the line
# TODO: match column widths in output
# TODO: save parametrised queries together with parameters
# TODO: save query results only as keys and put the issues in the registry
# TODO: show the issue count at the end of the query
# TODO: show the time of the request at the end of the query
# TODO: add query for epics that are not in the right state to their child issues
# TODO: find tickets in review with accepted revisions
# TODO: add limit to a query as a parameter in queries.yaml
# TODO: query for checking initials labels on active tickets
# TODO: check if the query names are unique
commands_config = {
    '': handle_no_command,
    ('h', 'help'): show_help,
    ('quit', 'exit'): exit_cue,
    ('x', 'exec', 'execute'): execute_command,
    ('xq', 'exec-query', 'execute-query'): execute_query,
    ('s', 'search'): search_issues_by_text,
    ('c', 'see', 'show'): show_issue,
    ('l', 'ls', 'list'): print_queue,
    ('q', 'queue'): step_through_queue,
    ('a', 'alert'): alert_if_queue_not_empty,
    ('o', 'open'): open_issue_in_browser,
}

options_config = (
    ('-a', '--all'),
    ('-o', '--oneline'),
    ('-c', '--compact'),
    ('-l', '--long'),
    ('-r', '--refresh'),
    ('-p', '--project', str),
    ('-x', '--extra', str),
)


class CueREPL(Cmd):

    def cmdloop(self, intro=None):
        while True:
            try:
                super(CueREPL, self).cmdloop(intro="")
                break
            except KeyboardInterrupt:
                print("^C")

    def do_help(self, inp):
        sys.stdout.write(help_text)

    def do_EOF(self, inp):
        print()
        return True

    def default(self, inp):
        try:
            QuickParse(commands_config, options_config=options_config, cli_args=shlex.split(inp)).execute()
        except AssertionError as ae:
            print(f'{ae}')
        except EOFError as ee:
            sys.stdout.write(f'{ee}')
            return True
        except KeyboardInterrupt:
            print(f'^C')
        except:
            traceback.print_exc()
        return False


if __name__ == '__main__':
    try:
        init()
    except AssertionError as ae:
        print(f'{ae}')
        exit()
    if len(sys.argv) == 1:
        if SCRIPT_PATH is not None:
            os.chdir(SCRIPT_PATH)
        cuerepl = CueREPL()
        cuerepl.prompt = f"{CLR.l_blue}cue·{CLR.reset}"
        nothing_worse_than_keyboardinterrupt = True
        while(nothing_worse_than_keyboardinterrupt):
            nothing_worse_than_keyboardinterrupt = False
            try:
                cuerepl.cmdloop()
            except KeyboardInterrupt:
                print(f'^C')
                nothing_worse_than_keyboardinterrupt = True
    else:
        try:
            QuickParse(commands_config, options_config=options_config).execute()
        except AssertionError as ae:
            print(f'{ae}')
