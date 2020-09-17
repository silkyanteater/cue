import traceback
import shlex
from cmd import Cmd
import sys

from lib import (
    init_lib,
    get_jira_issue,
    search_issues,
    get_query,
    write_issues,
    issues_details,
    issue_details,
    get_stored_core_data_for_query,
    get_updated_issues,
    update_queue,
    print_queue,
    ANSIColors,
    JiraIssues
)

from const import (
    valid_commands,
)


def init():
    init_lib()

def on_command(cli_args):
    command = cli_args[0]
    assert command in valid_commands, f"Command '{command}' not found"
    if command == 'x':
        assert len(cli_args) >= 2, f"Query name expected after 'x'"
        for query_name in cli_args[1:]:
            query_title, jql = get_query(query_name)
            data = search_issues(jql)
            issues = JiraIssues(data['issues'])
            stored_data_set = get_stored_core_data_for_query(query_name)
            updated_issues = get_updated_issues(issues, stored_data_set)
            update_queue(query_title, updated_issues)
            write_issues(query_title, issues)
            print(issues_details(issues))
    elif command == 'c':
        issue = get_jira_issue(cli_args[1])
        print(issue_details(issue))
    elif command == 'q':
        print_queue()


class RemsREPL(Cmd):

    def do_help(self, inp):
        print('Jira integration CLI')

    def do_EOF(self, inp):
        print(f'^D')
        return True

    def default(self, inp):
        try:
            on_command(shlex.split(inp))
        except AssertionError as ae:
            print(f'{ae}')
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
        remsrepl.prompt = f"{ANSIColors.l_blue}cue·{ANSIColors.reset} "
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
            on_command(sys.argv[1:])
        except AssertionError as ae:
            print(f'{ae}')
