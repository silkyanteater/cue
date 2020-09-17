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
    step_through_queue,
    print_queue,
    normalise_issue_ref,
    ANSIColors,
    JiraIssues
)

from const import (
    valid_commands,
)


help_text = ''' -- Jira integration CLI --
cue x <command from query definition>
   run query, update content in results, update queue
cue c <issue reference>
   see issue details
cue ls
   see queue
cue q
   step through queue and remove items when done'''


def init():
    init_lib()

def on_command(cli_args):
    command = cli_args[0]
    assert command in valid_commands, f"Command '{command}' not found"
    if command in ('h', '-h', '?', '-?', '-help', '--help'):
        sys.stdout.write(help_text)
    elif command == 'x':
        assert len(cli_args) >= 2, f"Query name expected after 'x'"
        for query_name in cli_args[1:]:
            query_title, jql = get_query(query_name)
            data = search_issues(jql)
            issues = JiraIssues(data['issues'])
            stored_data_set = get_stored_core_data_for_query(query_name)
            updated_issues = get_updated_issues(issues, stored_data_set)
            update_queue(query_title, updated_issues)
            write_issues(query_title, issues)
            sys.stdout.write(issues_details(issues))
    elif command == 'c':
        assert len(cli_args) > 1, f"Issue reference is missing"
        issue = get_jira_issue(normalise_issue_ref(cli_args[1]))
        sys.stdout.write(issue_details(issue))
    elif command == 'ls':
        print_queue()
    elif command == 'q':
        step_through_queue()


class RemsREPL(Cmd):

    def do_help(self, inp):
        sys.stdout.write(help_text)

    def do_EOF(self, inp):
        print(f'^D')
        return True

    def default(self, inp):
        try:
            on_command(shlex.split(inp))
            print()
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
            on_command(sys.argv[1:])
            print()
        except AssertionError as ae:
            print(f'{ae}')
