import traceback
import shlex
from cmd import Cmd
import sys

from lib import (
    init_lib,
    get_jira_issue,
    search_issues,
    get_command,
    write_issues,
    ANSIColors,
    JiraIssues
)


def init():
    init_lib()

def on_command(cli_args):
    command_name, jql = get_command(cli_args[0])
    data = search_issues(jql)
    issues = JiraIssues(data['issues'])
    write_issues(command_name, issues)
    print(issues)


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
