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
    params = [arg for arg in cli_args[1:] if not arg.startswith('-')]
    flags = [arg for arg in cli_args[1:] if arg.startswith('-')]
    if command in ('h', '-h', '?', '-?', '-help', '--help'):
        sys.stdout.write(help_text)
    elif command in ('quit', 'exit'):
        raise EOFError()
    elif command == 'x':
        print_short_format = len({'-s', '--short'}.intersection(set(flags))) > 0
        assert len(params) >= 1, f"Query name expected after 'x'"
        for query_name in params:
            query_title, jql = get_query(query_name)
            data = search_issues(jql)
            issues = JiraIssues(data['issues'])
            stored_data_set = get_stored_core_data_for_query(query_name)
            updated_issues = get_updated_issues(issues, stored_data_set)
            update_queue(query_title, updated_issues)
            write_issues(query_title, issues)
            if len(issues) > 0:
                if print_short_format:
                    print(issues)
                else:
                    sys.stdout.write(issues.details())
            else:
                print(f"{query_title}: no issues found")
    elif command == 'c':
        assert len(params) >= 1, f"Issue reference is missing"
        issue = get_jira_issue(normalise_issue_ref(cli_args[1]))
        print(issue.details())
    elif command == 'ls':
        print_queue()
    elif command == 'q':
        step_through_queue()


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
            on_command(shlex.split(inp))
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
            on_command(sys.argv[1:])
        except AssertionError as ae:
            print(f'{ae}')
