import traceback
import shlex
from cmd import Cmd
import sys

from quickparse import QuickParse

from lib import (
    ANSIColors,
    JiraIssues,
    init_lib,
    get_jira_issues,
    search_issues,
    get_query,
    get_all_query_names,
    write_issues,
    get_stored_core_data_for_query,
    get_updated_issues,
    update_queue,
    step_through_queue,
    print_queue,
    normalise_issue_ref,
    show_help,
    get_format_option,
    sound_alert_if_queue_not_empty,
)

from const import (
    help_text,
)


def init():
    init_lib()

def exit_cue():
    raise EOFError()

def execute_command(quickparse):
    all_query_names = get_all_query_names()
    assert len(quickparse.parameters) >= 1 or '--all' in quickparse.options, f"Query name expected - available: {', '.join(all_query_names)}"
    unknown_query_names = [query_name for query_name in quickparse.parameters if query_name not in all_query_names]
    assert len(unknown_query_names) == 0, f"Unknown query names: {', '.join(unknown_query_names)}"
    query_names = all_query_names if '--all' in quickparse.options else quickparse.parameters
    for query_name in query_names:
        stored_data_set = get_stored_core_data_for_query(query_name)
        if len(stored_data_set) == 0 or '--refresh' in quickparse.options:
            query_title, jql = get_query(query_name)
            data = search_issues(jql)
            issues = JiraIssues(data['issues'])
            updated_issues = get_updated_issues(issues, stored_data_set)
            update_queue(query_title, updated_issues)
            write_issues(query_title, issues)
        else:
            issues = JiraIssues(stored_data_set)
        if len(issues) > 0:
            print(issues.details(format=get_format_option(quickparse)))
        else:
            print(f"{query_title}: no issues found")

def show_issue(quickparse):
    assert len(quickparse.parameters) >= 1, f"Issue reference is missing"
    jira_issue_refs = [normalise_issue_ref(ref) for ref in quickparse.parameters]
    data = get_jira_issues(jira_issue_refs)
    issues = JiraIssues(data['issues'])
    print(issues.details(format=get_format_option(quickparse)))

commands_config = {
    ('h', 'help'): show_help,
    ('quit', 'exit'): exit_cue,
    ('x', 'exec', 'execute'): execute_command,
    ('c', 'see', 'show'): show_issue,
    ('l', 'ls', 'list'): print_queue,
    ('q', 'queue'): step_through_queue,
    ('a', 'alert'): sound_alert_if_queue_not_empty,
}

options_config = (
    ('-s', '--short'),
    ('-l', '--long'),
    ('-r', '--refresh'),
)


class RemsREPL(Cmd):

    def cmdloop(self, intro=None):
        while True:
            try:
                super(RemsREPL, self).cmdloop(intro="")
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
            print()
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
        remsrepl = RemsREPL()
        remsrepl.prompt = f"{ANSIColors.l_blue}cue·{ANSIColors.reset}"
        nothing_worse_than_keyboardinterrupt = True
        while(nothing_worse_than_keyboardinterrupt):
            nothing_worse_than_keyboardinterrupt = False
            try:
                remsrepl.cmdloop()
            except KeyboardInterrupt:
                print(f'^C')
                nothing_worse_than_keyboardinterrupt = True
    else:
        try:
            QuickParse(commands_config, options_config=options_config).execute()
        except AssertionError as ae:
            print(f'{ae}')
