import os, sys
import subprocess
from types import ModuleType
from typing import List


class ScriptFunc(ModuleType):

    def __init__(self, script_dir_path: str, script_name: str, script_args: List[str]=[]) -> None:
        script_dir_path = os.path.abspath(script_dir_path)
        if not os.path.isdir(script_dir_path):
            raise ValueError(f"'{script_dir_path}' not found")

        if not script_name.endswith(".py"):
            raise ValueError("Only python scripts supported at this time")

        if not isinstance(script_args, list):
            raise TypeError('script_args should be a list')

        self.__file__ = os.path.join(script_dir_path, script_name)

        if not os.path.isfile(self.__file__):
            raise FileNotFoundError(f"'{self.__file__}' not found")

        self.script_dir_path = script_dir_path
        self.script_name = script_name
        self.script_args = list(str(s) for s in script_args)

        self.__module__ = self.script_dir_path
        self.__qualname__ = f'[{self.script_name}]'
        if len(self.script_args) > 0:
            self.__qualname__ += ' ' + ' '.join(self.script_args)

        self.__doc__ = f"Script called '{self.script_name}' defined in '{self.script_dir_path}'"

        self.__wd = os.getcwd() # capture working directory to change back to once script is complete


    def __call__(self):
        os.chdir(self.script_dir_path)
        cmd = [sys.executable, "-u", self.__file__] + self.script_args

        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # Grab stdout line by line as it becomes available.  This will loop until p terminates.
            while p.poll() is None:
                l = p.stdout.readline().decode().strip() # This blocks until it receives a newline.
                print(l)
            # # When the subprocess terminates there might be unconsumed output
            # # that still needs to be processed.
            print(p.stdout.read().decode().strip())
            err = p.stderr.read().decode().strip()
            if p.returncode != 0:
                e = err.split('\n')[-1]
                raise Exception(f"{e}\n\nraised from subprocess:\n{err}")
            else:
                print(err) # not really an error? maybe a warning, or script returns 0 after failure :/
            p.wait()

        finally:
            os.chdir(self.__wd)

